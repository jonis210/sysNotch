"""Loopback bridge between the YouTube extension and the island UI."""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 47863
MAX_REQUEST_BYTES = 4096
EXTENSION_ORIGIN_PREFIXES = ("chrome-extension://", "extension://")
EXTENSION_CLIENT_HEADER = "X-Dynamic-Island-Client"
EXTENSION_CLIENT_VALUE = "youtube-extension"
_DIAGNOSTIC_SOURCES = {"service_worker", "content_script"}
_DIAGNOSTIC_EVENTS = {
    "skip_dispatch_to_tab",
    "skip_tab_message_failed",
    "skip_click_result",
    "skip_ack_sent",
    "skip_ack_failed",
    "skip_effect_check",
    "skip_cdp_click_dispatched",
    "skip_cdp_click_result",
    "skip_cdp_click_failed",
    "bridge_tick_http_error",
    "bridge_tick_fetch_failed",
    "content_script_reinjected",
    "content_script_reinject_failed",
}
_DIAGNOSTIC_FIELDS = {
    "tabId": int,
    "commandId": int,
    "clientBuild": str,
    "active": bool,
    "visible": bool,
    "isAd": bool,
    "clicked": bool,
    "duplicate": bool,
    "adStillShowing": bool,
    "canSkip": bool,
    "status": int,
    "reason": str,
    "buttonSelector": str,
    "errorType": str,
}


def _write_log(source: str, event: str, **details) -> None:
    """Keep optional diagnostics in memory only; never create a log file."""
    return None


def _log_extension_diagnostic(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"accepted": False}
    source = payload.get("source")
    event = payload.get("event")
    if source not in _DIAGNOSTIC_SOURCES or event not in _DIAGNOSTIC_EVENTS:
        _write_log("bridge", "extension_log_rejected", reason="invalid_source_or_event")
        return {"accepted": False}

    details = {}
    for key, expected_type in _DIAGNOSTIC_FIELDS.items():
        value = payload.get(key)
        if type(value) is expected_type:
            details[key] = value
    _write_log(source, event, **details)
    return {"accepted": True}


def _is_extension_origin(origin: str) -> bool:
    return origin.startswith(EXTENSION_ORIGIN_PREFIXES)


def _origin_scheme(origin: str) -> str:
    if not origin:
        return "missing"
    if ":" not in origin:
        return "unknown"
    return origin.split(":", 1)[0].lower()


class YouTubeBridge(QObject):
    """Receive ad state and send one-shot skip requests over localhost."""

    ad_state_changed = pyqtSignal(bool, bool)
    ad_state_stale_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._ad_detected = False
        self._can_skip = False
        self._state_stale = False
        self._last_update = 0.0
        self._active_tab_id: int | None = None
        self._skip_pending = False
        self._skip_target_tab: int | None = None
        self._skip_command_id = 0
        self._next_skip_command_id = 0
        self._skip_requested_at = 0.0
        self._last_logged_dispatch_id = 0
        self._last_client_build: str | None = None
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None

        self._expiry_timer = QTimer(self)
        self._expiry_timer.setInterval(500)
        self._expiry_timer.timeout.connect(self._expire_stale_state)

    def start(self) -> bool:
        if self._server is not None:
            return True

        bridge = self

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/health":
                    self._respond(404, {"error": "not_found"})
                    return

                origin = self.headers.get("Origin", "")
                # The popup's read-only health check may omit Origin in Chrome.
                # Keep this endpoint non-sensitive and don't make connection
                # status depend on a header the browser does not guarantee.
                self._respond(
                    200,
                    {"ready": True},
                    cors_origin=origin if _is_extension_origin(origin) else None,
                )

            def do_OPTIONS(self):
                if self.path not in ("/tick", "/log"):
                    self._respond(404, {"error": "not_found"})
                    return

                origin = self.headers.get("Origin", "")
                method = self.headers.get("Access-Control-Request-Method", "")
                requested_headers = {
                    item.strip().lower()
                    for item in self.headers.get("Access-Control-Request-Headers", "").split(",")
                    if item.strip()
                }
                allowed_headers = {"content-type", EXTENSION_CLIENT_HEADER.lower()}
                if (
                    not _is_extension_origin(origin)
                    or method != "POST"
                    or not requested_headers.issubset(allowed_headers)
                ):
                    self._respond(403, {"error": "extension_origin_required"})
                    return

                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    f"Content-Type, {EXTENSION_CLIENT_HEADER}",
                )
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                if self.path not in ("/tick", "/log"):
                    self._respond(404, {"error": "not_found"})
                    return

                origin = self.headers.get("Origin", "")
                client_marker = self.headers.get(EXTENSION_CLIENT_HEADER, "")
                origin_is_extension = _is_extension_origin(origin)
                marker_allows_originless_request = (
                    not origin and client_marker == EXTENSION_CLIENT_VALUE
                )
                if not origin_is_extension and not marker_allows_originless_request:
                    _write_log("bridge", "request_rejected", reason="extension_origin_required")
                    self._respond(
                        403,
                        {
                            "error": "extension_origin_or_marker_required",
                            "origin_scheme": _origin_scheme(origin),
                        },
                    )
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_REQUEST_BYTES:
                        self._respond(
                            413,
                            {"error": "invalid_body_size"},
                            cors_origin=origin if origin_is_extension else None,
                        )
                        return
                    payload = json.loads(self.rfile.read(length))
                    if self.path == "/log":
                        result = _log_extension_diagnostic(payload)
                    else:
                        result = bridge._handle_tick(payload)
                except (ValueError, TypeError, json.JSONDecodeError):
                    _write_log("bridge", "request_rejected", reason="invalid_json")
                    self._respond(
                        400,
                        {"error": "invalid_json"},
                        cors_origin=origin if origin_is_extension else None,
                    )
                    return

                self._respond(
                    200,
                    result,
                    cors_origin=origin if origin_is_extension else None,
                )

            def _respond(self, status: int, value: dict, cors_origin: str | None = None):
                body = json.dumps(value, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                if cors_origin:
                    self.send_header("Access-Control-Allow-Origin", cors_origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        try:
            server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), RequestHandler)
            server.daemon_threads = True
        except OSError:
            _write_log("bridge", "bridge_bind_failed", reason="port_in_use_or_unavailable")
            return False

        self._server = server
        self._server_thread = threading.Thread(
            target=server.serve_forever,
            name="YouTube bridge",
            daemon=True,
        )
        self._server_thread.start()
        self._expiry_timer.start()
        _write_log("bridge", "bridge_started", status=BRIDGE_PORT)
        return True

    def stop(self) -> None:
        self._expiry_timer.stop()
        server, self._server = self._server, None
        thread, self._server_thread = self._server_thread, None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=1.0)
        _write_log("bridge", "bridge_stopped")

    def request_skip(self) -> bool:
        with self._lock:
            if not self._ad_detected or not self._can_skip or self._active_tab_id is None:
                if not self._ad_detected:
                    reason = "ad_not_detected"
                elif not self._can_skip:
                    reason = "skip_button_not_detected"
                else:
                    reason = "active_youtube_tab_unknown"
                _write_log(
                    "bridge",
                    "skip_request_rejected",
                    reason=reason,
                    tabId=self._active_tab_id if self._active_tab_id is not None else -1,
                )
                return False
            if self._skip_pending:
                _write_log(
                    "bridge",
                    "skip_request_coalesced",
                    commandId=self._skip_command_id,
                    tabId=self._skip_target_tab if self._skip_target_tab is not None else -1,
                )
                return True
            self._next_skip_command_id += 1
            self._skip_command_id = self._next_skip_command_id
            self._skip_target_tab = self._active_tab_id
            self._skip_pending = True
            self._skip_requested_at = time.monotonic()
            _write_log(
                "bridge",
                "skip_request_accepted",
                commandId=self._skip_command_id,
                tabId=self._skip_target_tab,
            )
            return True

    def _handle_tick(self, payload: object) -> dict:
        if not isinstance(payload, dict):
            _write_log("bridge", "tick_rejected", reason="payload_not_object")
            return {"skip": False}

        tab_id = payload.get("tabId")
        active = payload.get("active")
        visible = payload.get("visible")
        is_ad = payload.get("isAd")
        can_skip = payload.get("canSkip")
        ack_command_id = payload.get("skipAckCommandId")
        if (
            not isinstance(tab_id, int)
            or isinstance(tab_id, bool)
            or tab_id < 0
            or not all(type(value) is bool for value in (active, visible, is_ad, can_skip))
            or (
                ack_command_id is not None
                and (
                    not isinstance(ack_command_id, int)
                    or isinstance(ack_command_id, bool)
                    or ack_command_id < 1
                )
            )
        ):
            _write_log("bridge", "tick_rejected", reason="invalid_tick_fields")
            return {"skip": False}

        client_build = payload.get("clientBuild")
        if (
            isinstance(client_build, str)
            and re.fullmatch(r"[A-Za-z0-9._-]{1,32}", client_build)
        ):
            with self._lock:
                if client_build != self._last_client_build:
                    self._last_client_build = client_build
                    _write_log(
                        "bridge",
                        "extension_build_reported",
                        clientBuild=client_build,
                        tabId=tab_id,
                    )

        acknowledged = False
        if ack_command_id is not None:
            with self._lock:
                if (
                    self._skip_pending
                    and self._skip_target_tab == tab_id
                    and self._skip_command_id == ack_command_id
                ):
                    self._skip_pending = False
                    self._skip_target_tab = None
                    self._skip_requested_at = 0.0
                    acknowledged = True
            if acknowledged:
                _write_log(
                    "bridge",
                    "skip_acknowledged",
                    commandId=ack_command_id,
                    tabId=tab_id,
                )
            else:
                _write_log(
                    "bridge",
                    "skip_ack_unmatched",
                    commandId=ack_command_id,
                    tabId=tab_id,
                )

        if not active:
            # Keep the last usable Skip state visible, but mark it stale and
            # remove its command target when this is no longer the selected
            # YouTube tab. A minimized window still has an active selected tab.
            with self._lock:
                if self._active_tab_id != tab_id:
                    return {"skip": False}
                old_state = (self._ad_detected, self._can_skip)
                old_stale = self._state_stale
                keep_skip_visible = self._ad_detected and self._can_skip
                if not keep_skip_visible:
                    self._ad_detected = False
                    self._can_skip = False
                self._state_stale = keep_skip_visible
                self._active_tab_id = None
                self._last_update = 0.0
                # Clicking the Island can briefly change page visibility.
                # Keep the command for this tab so its next visible tick can
                # deliver it; _expire_stale_state gives it a short deadline.
                if (
                    self._skip_pending
                    and (
                        self._skip_target_tab != tab_id
                        or time.monotonic() - self._skip_requested_at >= 5.0
                    )
                ):
                    self._skip_pending = False
                    self._skip_target_tab = None
                    self._skip_requested_at = 0.0
                new_state = (self._ad_detected, self._can_skip)
                new_stale = self._state_stale

            if new_state != old_state:
                _write_log(
                    "bridge",
                    "ad_state_changed",
                    tabId=tab_id,
                    active=False,
                    visible=False,
                    isAd=new_state[0],
                    canSkip=new_state[1],
                )
                self.ad_state_changed.emit(*new_state)
            if new_stale != old_stale:
                self.ad_state_stale_changed.emit(new_stale)
            return {"skip": False}

        can_skip = is_ad and can_skip
        with self._lock:
            now = time.monotonic()
            if self._skip_pending and now - self._skip_requested_at >= 5.0:
                _write_log(
                    "bridge",
                    "skip_command_expired",
                    commandId=self._skip_command_id,
                    tabId=self._skip_target_tab if self._skip_target_tab is not None else -1,
                    reason="ack_timeout",
                )
                self._skip_pending = False
                self._skip_target_tab = None
                self._skip_requested_at = 0.0

            old_state = (self._ad_detected, self._can_skip)
            old_stale = self._state_stale
            self._ad_detected = is_ad
            self._can_skip = can_skip
            self._state_stale = False
            self._last_update = now
            self._active_tab_id = tab_id

            send_skip = (
                self._skip_pending
                and self._skip_target_tab == tab_id
                and self._ad_detected
                and self._can_skip
            )
            if send_skip and self._last_logged_dispatch_id != self._skip_command_id:
                self._last_logged_dispatch_id = self._skip_command_id
                _write_log(
                    "bridge",
                    "skip_command_dispatched_to_extension",
                    commandId=self._skip_command_id,
                    tabId=tab_id,
                )
            if self._skip_pending and not self._ad_detected:
                _write_log(
                    "bridge",
                    "skip_command_cancelled",
                    commandId=self._skip_command_id,
                    tabId=tab_id,
                    reason="ad_no_longer_reported",
                )
                self._skip_pending = False
                self._skip_target_tab = None
                self._skip_requested_at = 0.0

            new_state = (self._ad_detected, self._can_skip)

        if new_state != old_state:
            _write_log(
                "bridge",
                "ad_state_changed",
                tabId=tab_id,
                active=True,
                visible=True,
                isAd=new_state[0],
                canSkip=new_state[1],
            )
            self.ad_state_changed.emit(*new_state)
        if old_stale:
            self.ad_state_stale_changed.emit(False)
        return {
            "skip": send_skip,
            "commandId": self._skip_command_id if send_skip else None,
        }

    def _expire_stale_state(self) -> None:
        now = time.monotonic()
        with self._lock:
            command_expired = (
                self._skip_pending
                and now - self._skip_requested_at >= 5.0
            )
            state_expired = bool(self._last_update and now - self._last_update >= 2.0)
            if not command_expired and not state_expired:
                return

            if command_expired:
                _write_log(
                    "bridge",
                    "skip_command_expired",
                    commandId=self._skip_command_id,
                    tabId=self._skip_target_tab if self._skip_target_tab is not None else -1,
                    reason="ack_timeout",
                )
                self._skip_pending = False
                self._skip_target_tab = None
                self._skip_requested_at = 0.0

            if not state_expired:
                return

            old_state = (self._ad_detected, self._can_skip)
            old_stale = self._state_stale
            keep_skip_visible = self._ad_detected and self._can_skip
            if not keep_skip_visible:
                self._ad_detected = False
                self._can_skip = False
            self._state_stale = keep_skip_visible
            self._active_tab_id = None
            self._skip_pending = False
            self._skip_target_tab = None
            self._skip_requested_at = 0.0
            self._last_update = 0.0
            new_state = (self._ad_detected, self._can_skip)
            new_stale = self._state_stale

        if new_state != old_state:
            _write_log("bridge", "ad_state_expired", isAd=new_state[0], canSkip=new_state[1])
            self.ad_state_changed.emit(*new_state)
        if new_stale != old_stale:
            self.ad_state_stale_changed.emit(new_stale)
