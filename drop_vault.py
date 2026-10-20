import os
import sys
import time
import socket
import threading
import tempfile
import zipfile
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, List

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QPainterPath, QPen, QBrush
from PyQt6.QtWidgets import QApplication

try:
    import qrcode
    from PIL import Image
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


def get_local_ip() -> str:
    """Detect the machine's local LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def format_size(bytes_val: int) -> str:
    """Convert bytes into clean human-readable size."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def get_file_category(ext: str) -> str:
    ext = ext.lower()
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'):
        return "image"
    if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.wmv'):
        return "video"
    if ext in ('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'):
        return "audio"
    if ext in ('.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.xlsx', '.csv', '.pptx'):
        return "doc"
    if ext in ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'):
        return "archive"
    if ext in ('.py', '.js', '.ts', '.html', '.css', '.json', '.cpp', '.c', '.cs', '.rs', '.go', '.sql'):
        return "code"
    return "other"


class TeleportServer:
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.file_name = os.path.basename(file_path)
        self.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        self.port = 0
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self) -> str:
        ip = get_local_ip()
        file_path = self.file_path
        file_name = self.file_name
        file_size = self.file_size

        class SingleFileHandler(SimpleHTTPRequestHandler):
            def do_GET(self):
                try:
                    self.send_response(200)
                    mime = "application/octet-stream"
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                        mime = f"image/{ext.replace('.', '')}"
                    elif ext == '.pdf':
                        mime = "application/pdf"
                    elif ext in ('.mp4', '.mkv', '.webm'):
                        mime = "video/mp4"
                    elif ext in ('.mp3', '.wav', '.flac', '.m4a'):
                        mime = "audio/mpeg"
                    elif ext == '.zip':
                        mime = "application/zip"

                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                except Exception:
                    pass

            def log_message(self, format, *args):
                pass

        self.server = HTTPServer((ip, 0), SingleFileHandler)
        self.port = self.server.server_port
        self.is_running = True

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        encoded_name = urllib.parse.quote(file_name)
        return f"http://{ip}:{self.port}/{encoded_name}"

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
            self.is_running = False


class VaultItem:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.name = os.path.basename(path)
        self.ext = os.path.splitext(self.name)[1].lower()
        self.size_bytes = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        self.size_str = format_size(self.size_bytes)
        self.category = get_file_category(self.ext)
        self.created_at = time.time()
        self.id = f"{abs(hash(self.path))}_{int(self.created_at)}"
        
        self.thumbnail: Optional[QPixmap] = None
        self._load_thumbnail()

        # Teleport QR state
        self.teleport_server: Optional[TeleportServer] = None
        self.teleport_url: str = ""
        self.teleport_qr: Optional[QPixmap] = None
        self.feedback_copied_until: float = 0.0

    def _load_thumbnail(self):
        if self.category == "image" and os.path.exists(self.path):
            try:
                pm = QPixmap(self.path)
                if not pm.isNull():
                    self.thumbnail = pm.scaled(
                        36, 36,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
            except Exception:
                self.thumbnail = None

    def start_teleport(self) -> str:
        if not self.teleport_server or not self.teleport_server.is_running:
            self.teleport_server = TeleportServer(self.path)
            self.teleport_url = self.teleport_server.start()
            if HAS_QRCODE:
                self.teleport_qr = generate_qr_pixmap(self.teleport_url)
        return self.teleport_url

    def stop_teleport(self):
        if self.teleport_server:
            self.teleport_server.stop()
            self.teleport_server = None
            self.teleport_url = ""
            self.teleport_qr = None


def generate_qr_pixmap(url: str, size: int = 100) -> Optional[QPixmap]:
    if not HAS_QRCODE:
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        pil_img = pil_img.resize((size, size), Image.Resampling.NEAREST)

        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


class DropVaultManager:
    def __init__(self):
        self.items: List[VaultItem] = []
        self.active_qr_item_id: Optional[str] = None
        self.bundle_server: Optional[TeleportServer] = None
        self.bundle_url: str = ""
        self.bundle_qr: Optional[QPixmap] = None
        self.bundle_path: Optional[str] = None
        self.is_bundle_qr_active: bool = False

    def add_path(self, path: str) -> Optional[VaultItem]:
        if not os.path.exists(path):
            return None
        norm_path = os.path.abspath(path)
        self.items = [item for item in self.items if item.path != norm_path]

        item = VaultItem(norm_path)
        self.items.insert(0, item)
        if len(self.items) > 20:
            old = self.items.pop()
            old.stop_teleport()

        return item

    def remove_item(self, item_id: str):
        target = self.get_item_by_id(item_id)
        if target:
            target.stop_teleport()
            self.items.remove(target)
            if self.active_qr_item_id == item_id:
                self.active_qr_item_id = None

    def clear_all(self):
        for item in self.items:
            item.stop_teleport()
        self.items.clear()
        self.active_qr_item_id = None
        self.stop_bundle_teleport()

    def get_item_by_id(self, item_id: str) -> Optional[VaultItem]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def copy_path(self, item_id: str) -> bool:
        item = self.get_item_by_id(item_id)
        if item and os.path.exists(item.path):
            clip = QApplication.clipboard()
            if clip:
                clip.setText(item.path)
                item.feedback_copied_until = time.monotonic() + 2.0
                return True
        return False

    def toggle_teleport(self, item_id: str):
        self.stop_bundle_teleport()
        if self.active_qr_item_id == item_id:
            item = self.get_item_by_id(item_id)
            if item:
                item.stop_teleport()
            self.active_qr_item_id = None
        else:
            if self.active_qr_item_id:
                prev = self.get_item_by_id(self.active_qr_item_id)
                if prev:
                    prev.stop_teleport()
            item = self.get_item_by_id(item_id)
            if item:
                item.start_teleport()
                self.active_qr_item_id = item_id

    def toggle_bundle_teleport(self):
        if self.is_bundle_qr_active:
            self.stop_bundle_teleport()
            return

        if not self.items:
            return

        # If only 1 item, share that 1 item directly
        if len(self.items) == 1:
            self.toggle_teleport(self.items[0].id)
            return

        # Multiple items: create a zip bundle
        self.stop_all_teleports()
        temp_dir = tempfile.gettempdir()
        bundle_file = os.path.join(temp_dir, f"SysNotch_Bundle_{int(time.time())}.zip")
        try:
            with zipfile.ZipFile(bundle_file, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for item in self.items:
                    if os.path.exists(item.path):
                        z.write(item.path, arcname=item.name)
            self.bundle_path = bundle_file
            self.bundle_server = TeleportServer(bundle_file)
            self.bundle_url = self.bundle_server.start()
            self.bundle_qr = generate_qr_pixmap(self.bundle_url)
            self.is_bundle_qr_active = True
        except Exception:
            pass

    def stop_bundle_teleport(self):
        if self.bundle_server:
            self.bundle_server.stop()
            self.bundle_server = None
        self.bundle_url = ""
        self.bundle_qr = None
        self.is_bundle_qr_active = False
        if self.bundle_path and os.path.exists(self.bundle_path):
            try:
                os.remove(self.bundle_path)
            except Exception:
                pass
            self.bundle_path = None

    def stop_all_teleports(self):
        if self.active_qr_item_id:
            item = self.get_item_by_id(self.active_qr_item_id)
            if item:
                item.stop_teleport()
            self.active_qr_item_id = None
        self.stop_bundle_teleport()

    def cleanup(self):
        self.clear_all()
