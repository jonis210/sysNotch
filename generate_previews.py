import sys
import os
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QFont
from PIL import Image

sys.path.insert(0, os.path.abspath("."))
import dynamic

def crop_transparent(image_path: str, padding: int = 12):
    """Crop image to non-transparent bounding box with gentle padding."""
    im = Image.open(image_path)
    bbox = im.getbbox()
    if bbox:
        w, h = im.size
        left = max(0, bbox[0] - padding)
        top = max(0, bbox[1] - padding)
        right = min(w, bbox[2] + padding)
        bottom = min(h, bbox[3] + padding)
        cropped = im.crop((left, top, right, bottom))
        cropped.save(image_path)
        print(f"Cropped {image_path} to {cropped.size}")

def render_previews():
    app = QApplication(sys.argv)
    island = dynamic.DesktopDynamicIsland()

    # Common media mock
    island.has_media = True
    island.media_state = "media"
    island.media_source_app = "Spotify.exe"
    island.track_title = "Surat Cinta Untuk Starla"
    island.track_artist = "Virgoun"
    island.track_album = "Surat Cinta Untuk Starla"
    island.position_seconds = 74.0
    island.duration_seconds = 272.0
    island.can_play_pause = True
    island.can_previous = True
    island.can_next = True
    island.is_playing = True

    cues = [
        (10.0, "Teruntuk kamu, hidup dan matiku"),
        (14.0, "Aku tak tahu lagi harus dengan kata apa aku menuliskannya"),
        (18.0, "Atau dengan kalimat apa aku mengungkapkannya"),
        (22.0, "Karena untuk keberkian kalinya"),
    ]
    island.lyrics_cues = cues
    island.lyrics_timestamps = [c[0] for c in cues]
    island.lyrics_smooth_index = 1.0

    # -------------------------------------------------------------
    # 1. PREVIEW: EXPANDED WITH LYRICS DRAWER (HERO SHOWCASE)
    # -------------------------------------------------------------
    island.lyrics_open = True
    island.is_hovered = True
    island.expand_progress = 1.0
    now = time.monotonic()
    target_w = island._calculate_dynamic_lyrics_width(now)
    island.cur_w = target_w
    island.cur_h = island.media_expanded_h

    img_hero = QImage(island.canvas_w, int(island.canvas_h), QImage.Format.Format_ARGB32_Premultiplied)
    img_hero.fill(Qt.GlobalColor.transparent)
    island.render(img_hero)
    path_hero = os.path.abspath("assets/preview_lyrics.png")
    img_hero.save(path_hero)
    crop_transparent(path_hero, padding=16)

    # -------------------------------------------------------------
    # 2. PREVIEW: MEDIA HUB EXPANDED (WITHOUT LYRICS)
    # -------------------------------------------------------------
    island.lyrics_open = False
    island.is_hovered = True
    island.expand_progress = 1.0
    island.cur_w = island.expanded_w
    island.cur_h = island.media_expanded_h

    img_media = QImage(island.canvas_w, int(island.canvas_h), QImage.Format.Format_ARGB32_Premultiplied)
    img_media.fill(Qt.GlobalColor.transparent)
    island.render(img_media)
    path_media = os.path.abspath("assets/preview_media.png")
    img_media.save(path_media)
    crop_transparent(path_media, padding=16)

    # -------------------------------------------------------------
    # 3. PREVIEW: SLEEK COMPACT NOTCH (COLLAPSED CAMERA PILL)
    # -------------------------------------------------------------
    island.lyrics_open = False
    island.is_hovered = False
    island.expand_progress = 0.0
    island.cur_w = island.collapsed_w
    island.cur_h = island.collapsed_h

    img_compact = QImage(island.canvas_w, int(island.canvas_h), QImage.Format.Format_ARGB32_Premultiplied)
    img_compact.fill(Qt.GlobalColor.transparent)
    island.render(img_compact)
    path_compact = os.path.abspath("assets/preview_compact.png")
    img_compact.save(path_compact)
    crop_transparent(path_compact, padding=16)

    # -------------------------------------------------------------
    # 4. PREVIEW: CYBERPUNK MECHA MASCOT HEAD
    # -------------------------------------------------------------
    s = 200
    img_mascot = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
    img_mascot.fill(Qt.GlobalColor.transparent)
    p = QPainter(img_mascot)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    center = QPointF(s / 2.0, s / 2.0)
    scale = (s * 0.88) / 20.0
    island._draw_robot_mascot(p, center, 0.0, scale=scale)
    p.end()
    path_mascot = os.path.abspath("assets/mascot_robot.png")
    img_mascot.save(path_mascot)
    crop_transparent(path_mascot, padding=8)

    print("All previews rendered successfully in assets/")

if __name__ == "__main__":
    render_previews()
