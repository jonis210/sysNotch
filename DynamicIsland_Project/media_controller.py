"""Bridge between the island UI and Windows' active media session."""

from __future__ import annotations

import queue
import sys
import threading
import time
import ctypes
from datetime import datetime, timezone
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

ARTWORK_RETRY_INTERVAL = 0.75
ARTWORK_REFRESH_WINDOW = 2.0


def _seconds(value: Any) -> float:
    """Convert a WinRT TimeSpan (projected as timedelta) to seconds."""
    if value is None:
        return 0.0
    if hasattr(value, "total_seconds"):
        return max(0.0, float(value.total_seconds()))
    # WinRT TimeSpan values are expressed in 100-nanosecond ticks.
    return max(0.0, float(value) / 10_000_000)


def _age_seconds(value: Any) -> float:
    """Return how old a WinRT UTC DateTime sample is, if available."""
    if not isinstance(value, datetime):
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - value).total_seconds())


def _get_result(operation: Any, timeout: float = 1.5) -> Any:
    """Wait for a PyWinRT operation without allowing a permanent worker hang."""
    status = operation.wait(timeout)
    if int(status) == 0:  # AsyncStatus.STARTED
        operation.cancel()
        raise TimeoutError("Windows media API did not respond in time")
    return operation.get()


def _read_thumbnail(thumbnail: Any, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    """Read a WinRT media thumbnail into bounded image bytes."""
    if thumbnail is None:
        return b""

    stream = reader = None
    try:
        from winrt.windows.storage.streams import DataReader

        stream = _get_result(thumbnail.open_read_async())
        size = int(stream.size)
        if size <= 0 or size > max_bytes:
            return b""

        reader = DataReader(stream.get_input_stream_at(0))
        loaded = int(_get_result(reader.load_async(size)))
        if loaded <= 0:
            return b""
        image_bytes = bytearray(loaded)
        reader.read_bytes(image_bytes)
        return bytes(image_bytes)
    except Exception:
        # Some players expose media properties before their thumbnail stream is
        # ready, or do not provide an image at all. Keep media controls usable.
        return b""
    finally:
        for resource in (reader, stream):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass


class WindowsMediaController(QThread):
    """Poll system media state off the UI thread and send transport commands."""

    media_updated = pyqtSignal(dict)
    command_result = pyqtSignal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = threading.Event()
        self._wake_requested = threading.Event()
        self._commands: queue.Queue[str] = queue.Queue()

    def stop(self) -> None:
        self._stop_requested.set()
        self._wake_requested.set()

    def command(self, name: str) -> None:
        if name in {
            "play_pause",
            "previous",
            "next",
            "volume_down",
            "volume_up",
        }:
            self._commands.put(name)
            self._wake_requested.set()

    def run(self) -> None:
        if sys.platform != "win32":
            self.media_updated.emit({"state": "unsupported"})
            return

        try:
            self._poll_media()
        except PermissionError:
            self.media_updated.emit({"state": "access_denied"})
        except ModuleNotFoundError:
            self.media_updated.emit({"state": "dependency_missing"})
        except Exception as error:
            self.media_updated.emit({"state": "error", "message": str(error)})

    def _poll_media(self) -> None:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )

        # Keep all blocking WinRT calls on this worker and bound their wait time.
        manager = _get_result(SessionManager.request_async())
        last_sent = None
        last_artwork_key = None
        cached_artwork = b""
        last_artwork_attempt = 0.0
        artwork_refresh_until = 0.0

        while not self._stop_requested.is_set():
            self._wake_requested.clear()
            try:
                session = manager.get_current_session()
                sessions = list(manager.get_sessions())

                if session is None and sessions:
                    session = next(
                        (
                            candidate
                            for candidate in sessions
                            if candidate.get_playback_info().playback_status
                            == PlaybackStatus.PLAYING
                        ),
                        sessions[0],
                    )

                self._run_pending_commands(manager, session)
                session = manager.get_current_session() or session

                if session is None:
                    snapshot = {"state": "no_media", "source_app": ""}
                    last_artwork_key = None
                    cached_artwork = b""
                    last_artwork_attempt = 0.0
                    artwork_refresh_until = 0.0
                else:
                    # The active app can change between polls; follow the system's
                    # current session instead of retaining a stale player object.
                    session = manager.get_current_session() or session
                    properties = _get_result(session.try_get_media_properties_async())
                    timeline = session.get_timeline_properties()
                    playback = session.get_playback_info()
                    controls = playback.controls
                    source_app = str(getattr(session, "source_app_user_model_id", "") or "")

                    start = _seconds(timeline.start_time)
                    end = _seconds(timeline.end_time)
                    position = max(0.0, _seconds(timeline.position) - start)
                    duration = max(0.0, end - start)
                    status = playback.playback_status
                    is_playing = status == PlaybackStatus.PLAYING
                    playback_rate = getattr(playback, "playback_rate", None)
                    playback_rate = (
                        max(0.0, float(playback_rate))
                        if playback_rate is not None
                        else (1.0 if is_playing else 0.0)
                    )
                    snapshot = {
                        "state": "media",
                        "source_app": source_app,
                        "title": (properties.title or "").strip() or "Media tanpa judul",
                        "artist": (
                            properties.artist or properties.album_artist or ""
                        ).strip(),
                        "album": (properties.album_title or "").strip(),
                        "position": position,
                        # Position is valid as of LastUpdatedTime. Carry the sample
                        # age so the UI can catch up before interpolating locally.
                        "position_age": _age_seconds(
                            getattr(timeline, "last_updated_time", None)
                        ) if is_playing else 0.0,
                        "playback_rate": playback_rate,
                        "duration": duration,
                        "is_playing": is_playing,
                        "can_play_pause": bool(
                            getattr(controls, "is_play_pause_toggle_enabled", False)
                        ),
                        "can_previous": bool(
                            getattr(controls, "is_previous_enabled", False)
                        ),
                        "can_next": bool(getattr(controls, "is_next_enabled", False)),
                    }

                    artwork_key = (
                        getattr(session, "source_app_user_model_id", ""),
                        snapshot["title"],
                        snapshot["artist"],
                        (getattr(properties, "album_title", None) or "").strip(),
                        (getattr(properties, "album_artist", None) or "").strip(),
                        getattr(properties, "track_number", None),
                    )
                    now = time.monotonic()
                    artwork_key_changed = artwork_key != last_artwork_key
                    if artwork_key_changed:
                        last_artwork_key = artwork_key
                        cached_artwork = b""
                        last_artwork_attempt = 0.0
                        artwork_refresh_until = now + ARTWORK_REFRESH_WINDOW
                        # Clear the previous track's cover immediately. The
                        # thumbnail stream may lag behind the new media title.
                        snapshot["artwork"] = b""

                    should_refresh = now < artwork_refresh_until
                    should_retry_missing = not cached_artwork
                    if (
                        (should_refresh or should_retry_missing)
                        and now - last_artwork_attempt >= ARTWORK_RETRY_INTERVAL
                    ):
                        new_artwork = _read_thumbnail(
                            getattr(properties, "thumbnail", None)
                        )
                        last_artwork_attempt = now
                        if new_artwork and new_artwork != cached_artwork:
                            cached_artwork = new_artwork
                            snapshot["artwork"] = cached_artwork

                if snapshot != last_sent:
                    self.media_updated.emit(snapshot)
                    last_sent = snapshot
            except PermissionError:
                raise
            except ModuleNotFoundError as error:
                snapshot = {
                    "state": "dependency_missing",
                    "message": str(error),
                }
                if snapshot != last_sent:
                    self.media_updated.emit(snapshot)
                return
            except Exception as error:
                snapshot = {"state": "error", "message": str(error)}
                if snapshot != last_sent:
                    self.media_updated.emit(snapshot)
                    last_sent = snapshot

            self._wake_requested.wait(0.5)

    def _run_pending_commands(self, manager, fallback_session) -> None:
        methods = {
            "play_pause": "try_toggle_play_pause_async",
            "previous": "try_skip_previous_async",
            "next": "try_skip_next_async",
        }
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return

            if command in {"volume_down", "volume_up"}:
                try:
                    virtual_key = 0xAE if command == "volume_down" else 0xAF
                    user32 = ctypes.windll.user32
                    user32.keybd_event(virtual_key, 0, 0, 0)
                    user32.keybd_event(virtual_key, 0, 0x0002, 0)
                    self.command_result.emit(command, True, "")
                except Exception as error:
                    self.command_result.emit(command, False, str(error))
                continue

            session = manager.get_current_session() or fallback_session
            try:
                succeeded = bool(_get_result(getattr(session, methods[command])()))
                self.command_result.emit(
                    command,
                    succeeded,
                    "" if succeeded else "Pemutar media menolak perintah ini.",
                )
            except PermissionError:
                raise
            except Exception as error:
                # A media app may close its session between polling and a click.
                # The next poll will update the island to the new system state.
                self.command_result.emit(command, False, str(error))
                continue
