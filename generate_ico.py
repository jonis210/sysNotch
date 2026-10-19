import sys
import math
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPolygonF,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
)
from PIL import Image

_ROBOT_CYAN = QColor("#00F5FF")
_ROBOT_LIGHT_CYAN = QColor("#38BDF8")
_ROBOT_MAGENTA = QColor("#FF007F")
_ROBOT_LIGHT_MAGENTA = QColor("#E879F9")
_ROBOT_DARK_BG = QColor("#060A12")
_ROBOT_SLATE = QColor("#334155")

def draw_robot_mascot(painter: QPainter, center: QPointF, t: float = 0.0, scale: float = 1.0):
    bob_y = 0.0
    cx = center.x()
    cy = center.y()
    gaze_x = 0.0
    eye_open = 1.0
    energy_pulse = 1.0
    parallax_x = 0.0

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    if scale != 1.0:
        painter.translate(center.x(), center.y())
        painter.scale(scale, scale)
        cx = 0.0
        cy = 0.0

    # Back Neon Cyber-Shield Aura (Cyan Left, Magenta Right)
    shield_l = QPainterPath()
    shield_l.moveTo(cx, cy - 9.4)
    shield_l.lineTo(cx - 7.2, cy - 7.2)
    shield_l.lineTo(cx - 8.5, cy + 0.2)
    shield_l.lineTo(cx - 5.5, cy + 6.8)
    shield_l.lineTo(cx, cy + 9.6)

    shield_r = QPainterPath()
    shield_r.moveTo(cx, cy - 9.4)
    shield_r.lineTo(cx + 7.2, cy - 7.2)
    shield_r.lineTo(cx + 8.5, cy + 0.2)
    shield_r.lineTo(cx + 5.5, cy + 6.8)
    shield_r.lineTo(cx, cy + 9.6)

    # Ambient Outer Glow
    glow_alpha = 75
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 245, 255, glow_alpha), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawPath(shield_l)
    painter.setPen(QPen(QColor(255, 0, 127, glow_alpha), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawPath(shield_r)

    # Sharp Neon Outline
    painter.setPen(QPen(QColor(0, 245, 255, 220), 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawPath(shield_l)
    painter.setPen(QPen(QColor(255, 0, 127, 220), 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawPath(shield_r)

    # Outer Power Cables Looping Around Cheeks & Jaw
    cables_left = [
        (QPointF(cx - 2.2, cy + 6.6), QPointF(cx - 6.8, cy + 7.0), QPointF(cx - 7.6, cy + 2.8), QPointF(cx - 6.0, cy + 1.2), _ROBOT_CYAN, 1.2),
        (QPointF(cx - 1.5, cy + 7.2), QPointF(cx - 8.2, cy + 8.0), QPointF(cx - 9.0, cy + 2.0), QPointF(cx - 6.4, cy - 0.4), _ROBOT_LIGHT_CYAN, 0.9),
    ]
    cables_right = [
        (QPointF(cx + 2.2, cy + 6.6), QPointF(cx + 6.8, cy + 7.0), QPointF(cx + 7.6, cy + 2.8), QPointF(cx + 6.0, cy + 1.2), _ROBOT_MAGENTA, 1.2),
        (QPointF(cx + 1.5, cy + 7.2), QPointF(cx + 8.2, cy + 8.0), QPointF(cx + 9.0, cy + 2.0), QPointF(cx + 6.4, cy - 0.4), _ROBOT_LIGHT_MAGENTA, 0.9),
    ]

    for start_pt, c1, c2, end_pt, col, w in cables_left + cables_right:
        p = QPainterPath()
        p.moveTo(start_pt)
        p.cubicTo(c1, c2, end_pt)
        painter.setPen(QPen(_ROBOT_DARK_BG, w + 0.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)
        painter.setPen(QPen(_ROBOT_SLATE, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)
        # Glowing fiber line
        c_glow = QColor(col.red(), col.green(), col.blue(), 230)
        painter.setPen(QPen(c_glow, 0.6, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)

    # Cranial Power Conduit Dreadlocks (Overhead Mohawk Crest)
    crest_cables = [
        (QPointF(cx - 0.7, cy - 4.8), QPointF(cx - 1.0, cy - 8.6), QPointF(cx - 1.3, cy - 9.6), QPointF(cx - 1.5, cy - 10.0), _ROBOT_CYAN),
        (QPointF(cx + 0.7, cy - 4.8), QPointF(cx + 1.0, cy - 8.6), QPointF(cx + 1.3, cy - 9.6), QPointF(cx + 1.5, cy - 10.0), _ROBOT_MAGENTA),
        (QPointF(cx - 1.8, cy - 4.4), QPointF(cx - 2.8, cy - 7.8), QPointF(cx - 3.4, cy - 9.0), QPointF(cx - 3.8, cy - 9.4), _ROBOT_LIGHT_CYAN),
        (QPointF(cx + 1.8, cy - 4.4), QPointF(cx + 2.8, cy - 7.8), QPointF(cx + 3.4, cy - 9.0), QPointF(cx + 3.8, cy - 9.4), _ROBOT_LIGHT_MAGENTA),
        (QPointF(cx - 3.0, cy - 3.6), QPointF(cx - 4.6, cy - 6.6), QPointF(cx - 5.6, cy - 7.4), QPointF(cx - 6.2, cy - 7.6), _ROBOT_CYAN),
        (QPointF(cx + 3.0, cy - 3.6), QPointF(cx + 4.6, cy - 6.6), QPointF(cx + 5.6, cy - 7.4), QPointF(cx + 6.2, cy - 7.6), _ROBOT_MAGENTA),
    ]

    for start_pt, c1, c2, end_pt, glow_col in crest_cables:
        p = QPainterPath()
        p.moveTo(start_pt)
        p.cubicTo(c1, c2, end_pt)
        painter.setPen(QPen(_ROBOT_DARK_BG, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)
        painter.setPen(QPen(_ROBOT_SLATE, 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)
        # Conduit rib pulse
        painter.setPen(QPen(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), 230), 0.6, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(p)
        # Fiber node tip
        painter.setBrush(QBrush(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), 255)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(end_pt, 0.45, 0.45)

    # Titanium Skull Main Chassis
    skull_poly = QPolygonF([
        QPointF(cx - 3.6, cy - 4.5),
        QPointF(cx + 3.6, cy - 4.5),
        QPointF(cx + 5.4, cy - 2.8),
        QPointF(cx + 5.8, cy + 0.4),
        QPointF(cx + 4.8, cy + 3.6),
        QPointF(cx + 3.2, cy + 6.0),
        QPointF(cx + 1.6, cy + 7.6),
        QPointF(cx - 1.6, cy + 7.6),
        QPointF(cx - 3.2, cy + 6.0),
        QPointF(cx - 4.8, cy + 3.6),
        QPointF(cx - 5.8, cy + 0.4),
        QPointF(cx - 5.4, cy - 2.8),
    ])

    skull_path = QPainterPath()
    skull_path.addPolygon(skull_poly)
    skull_path.closeSubpath()

    skull_grad = QLinearGradient(cx, cy - 5.0, cx, cy + 8.0)
    skull_grad.setColorAt(0.0, QColor("#334155"))
    skull_grad.setColorAt(0.35, QColor("#1E293B"))
    skull_grad.setColorAt(0.75, QColor("#0F172A"))
    skull_grad.setColorAt(1.0, QColor("#020617"))

    pen_skull = QPen(QColor(255, 255, 255, 70), 0.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
    painter.setBrush(QBrush(skull_grad))
    painter.setPen(pen_skull)
    painter.drawPath(skull_path)

    # Symmetrical Ear Modules
    for side in (-1, 1):
        ear_x = cx + side * 6.3
        ear_y = cy - 0.2

        ear_rect = QRectF(ear_x - 1.0, ear_y - 2.2, 2.0, 4.4)
        painter.setBrush(QBrush(QColor("#0F172A")))
        painter.setPen(QPen(QColor(255, 255, 255, 55), 0.5))
        painter.drawRoundedRect(ear_rect, 0.6, 0.6)

        h_rect = QRectF(ear_x - 0.8, ear_y + 0.4, 1.6, 1.5)
        painter.setBrush(QBrush(QColor("#0B0F19")))
        painter.setPen(QPen(QColor("#EAB308"), 0.4))
        painter.drawRect(h_rect)
        painter.setPen(QPen(QColor("#FACC15"), 0.55))
        painter.drawLine(QPointF(ear_x - 0.6, ear_y + 0.6), QPointF(ear_x + 0.2, ear_y + 1.6))

        pin_start_x = ear_x + (side * 1.0)
        pin_end_x = ear_x + (side * 2.8)
        painter.setPen(QPen(QColor("#060A12"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(pin_start_x, ear_y), QPointF(pin_end_x, ear_y))
        painter.setPen(QPen(QColor("#64748B"), 0.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(pin_start_x, ear_y), QPointF(pin_end_x, ear_y))

        tip_c = QColor("#00F5FF") if side == -1 else QColor("#FF007F")
        painter.setBrush(QBrush(QColor(tip_c.red(), tip_c.green(), tip_c.blue(), 255)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(pin_end_x, ear_y), 0.5, 0.5)

    # Forehead Shield Crest
    crest_poly = QPolygonF([
        QPointF(cx - 2.5, cy - 4.6),
        QPointF(cx + 2.5, cy - 4.6),
        QPointF(cx + 1.8, cy - 2.4),
        QPointF(cx, cy - 1.8),
        QPointF(cx - 1.8, cy - 2.4),
    ])
    painter.setBrush(QBrush(QColor("#0B0F19")))
    painter.setPen(QPen(QColor(56, 189, 248, 160), 0.5))
    painter.drawPolygon(crest_poly)

    tri_outer = QPolygonF([
        QPointF(cx - 1.4, cy - 4.0),
        QPointF(cx + 1.4, cy - 4.0),
        QPointF(cx, cy - 2.3),
    ])
    painter.setBrush(QBrush(QColor("#0B0F19")))
    painter.setPen(QPen(QColor("#FF007F"), 0.5))
    painter.drawPolygon(tri_outer)

    tri_core = QPolygonF([
        QPointF(cx - 0.9, cy - 3.8),
        QPointF(cx + 0.9, cy - 3.8),
        QPointF(cx, cy - 2.6),
    ])
    painter.setBrush(QBrush(QColor("#00F5FF")))
    painter.setPen(QPen(QColor("#FFFFFF"), 0.35))
    painter.drawPolygon(tri_core)

    # Brow Armor Plates
    brow_l = QPolygonF([
        QPointF(cx - 5.2, cy - 2.2),
        QPointF(cx - 1.0, cy - 1.5),
        QPointF(cx - 0.8, cy - 0.9),
        QPointF(cx - 4.6, cy - 1.2),
    ])
    brow_r = QPolygonF([
        QPointF(cx + 5.2, cy - 2.2),
        QPointF(cx + 1.0, cy - 1.5),
        QPointF(cx + 0.8, cy - 0.9),
        QPointF(cx + 4.6, cy - 1.2),
    ])
    painter.setBrush(QBrush(QColor("#1E293B")))
    painter.setPen(QPen(QColor(255, 255, 255, 75), 0.45))
    painter.drawPolygon(brow_l)
    painter.drawPolygon(brow_r)

    # Eyes
    shutter_h = 1.25
    shutter_glow_h = 2.2

    # Left Eye: Cyan
    left_sock_x = cx - 2.8
    left_sock_y = cy - 0.3
    left_eye_center = QPointF(left_sock_x, left_sock_y)

    sock_l = QPolygonF([
        QPointF(left_sock_x - 1.9, left_sock_y - 0.9),
        QPointF(left_sock_x + 1.7, left_sock_y - 0.7),
        QPointF(left_sock_x + 1.5, left_sock_y + 0.9),
        QPointF(left_sock_x - 1.7, left_sock_y + 0.8),
    ])
    painter.setBrush(QBrush(QColor("#02050E")))
    painter.setPen(QPen(QColor(0, 245, 255, 70), 0.35))
    painter.drawPolygon(sock_l)

    flare_l_len = 4.2
    flare_l_alpha = 240
    grad_l = QLinearGradient(
        left_eye_center.x() + 0.8, left_eye_center.y(),
        left_eye_center.x() - flare_l_len, left_eye_center.y()
    )
    grad_l.setColorAt(0.0, QColor(255, 255, 255, flare_l_alpha))
    grad_l.setColorAt(0.25, QColor(0, 245, 255, int(flare_l_alpha * 0.9)))
    grad_l.setColorAt(1.0, QColor(0, 245, 255, 0))
    painter.setPen(QPen(QBrush(grad_l), max(0.35, shutter_h * 0.85), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(left_eye_center, QPointF(left_eye_center.x() - flare_l_len, left_eye_center.y()))

    bloom_l = QColor(0, 245, 255, 140)
    painter.setBrush(QBrush(bloom_l))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(left_eye_center, 1.8, shutter_glow_h)

    slit_l = QPolygonF([
        QPointF(left_eye_center.x() - 1.1, left_eye_center.y() - shutter_h * 0.5),
        QPointF(left_eye_center.x() + 1.0, left_eye_center.y() - shutter_h * 0.4),
        QPointF(left_eye_center.x() + 1.0, left_eye_center.y() + shutter_h * 0.4),
        QPointF(left_eye_center.x() - 1.1, left_eye_center.y() + shutter_h * 0.5),
    ])
    painter.setBrush(QBrush(QColor("#00F5FF")))
    painter.setPen(QPen(QColor("#A5F3FC"), 0.3))
    painter.drawPolygon(slit_l)

    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(left_eye_center, 0.55, 0.35)

    # Right Eye: Magenta
    right_sock_x = cx + 2.8
    right_sock_y = cy - 0.3
    right_eye_center = QPointF(right_sock_x, right_sock_y)

    sock_r = QPolygonF([
        QPointF(right_sock_x - 1.7, right_sock_y - 0.7),
        QPointF(right_sock_x + 1.9, right_sock_y - 0.9),
        QPointF(right_sock_x + 1.7, right_sock_y + 0.8),
        QPointF(right_sock_x - 1.5, right_sock_y + 0.9),
    ])
    painter.setBrush(QBrush(QColor("#02050E")))
    painter.setPen(QPen(QColor(255, 0, 127, 70), 0.35))
    painter.drawPolygon(sock_r)

    flare_r_len = 4.2
    flare_r_alpha = 240
    grad_r = QLinearGradient(
        right_eye_center.x() - 0.8, right_eye_center.y(),
        right_eye_center.x() + flare_r_len, right_eye_center.y()
    )
    grad_r.setColorAt(0.0, QColor(255, 255, 255, flare_r_alpha))
    grad_r.setColorAt(0.25, QColor(255, 0, 127, int(flare_r_alpha * 0.9)))
    grad_r.setColorAt(1.0, QColor(255, 0, 127, 0))
    painter.setPen(QPen(QBrush(grad_r), max(0.35, shutter_h * 0.85), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(right_eye_center, QPointF(right_eye_center.x() + flare_r_len, right_eye_center.y()))

    bloom_r = QColor(255, 0, 127, 140)
    painter.setBrush(QBrush(bloom_r))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(right_eye_center, 1.8, shutter_glow_h)

    slit_r = QPolygonF([
        QPointF(right_eye_center.x() - 1.0, right_eye_center.y() - shutter_h * 0.4),
        QPointF(right_eye_center.x() + 1.1, right_eye_center.y() - shutter_h * 0.5),
        QPointF(right_eye_center.x() + 1.1, right_eye_center.y() + shutter_h * 0.5),
        QPointF(right_eye_center.x() - 1.0, right_eye_center.y() + shutter_h * 0.4),
    ])
    painter.setBrush(QBrush(QColor("#FF007F")))
    painter.setPen(QPen(QColor("#FBCFE8"), 0.3))
    painter.drawPolygon(slit_r)

    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(right_eye_center, 0.55, 0.35)

    # Nasal Cavity
    nose_poly = QPolygonF([
        QPointF(cx - 0.7, cy + 1.2),
        QPointF(cx + 0.7, cy + 1.2),
        QPointF(cx + 1.1, cy + 3.0),
        QPointF(cx, cy + 3.4),
        QPointF(cx - 1.1, cy + 3.0),
    ])
    painter.setBrush(QBrush(QColor("#02050E")))
    painter.setPen(QPen(QColor(255, 255, 255, 40), 0.35))
    painter.drawPolygon(nose_poly)

    painter.setPen(QPen(QColor("#475569"), 0.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(cx, cy + 1.5), QPointF(cx, cy + 3.1))

    # Rebreather Jaw / Chin
    painter.setPen(QPen(QColor(255, 255, 255, 50), 0.45))
    painter.drawLine(QPointF(cx - 4.4, cy + 1.8), QPointF(cx - 2.3, cy + 3.4))
    painter.drawLine(QPointF(cx + 4.4, cy + 1.8), QPointF(cx + 2.3, cy + 3.4))

    chin_poly = QPolygonF([
        QPointF(cx - 2.4, cy + 4.8),
        QPointF(cx + 2.4, cy + 4.8),
        QPointF(cx + 1.7, cy + 7.4),
        QPointF(cx - 1.7, cy + 7.4),
    ])
    painter.setBrush(QBrush(QColor("#080D16")))
    painter.setPen(QPen(QColor(56, 189, 248, 130), 0.5))
    painter.drawPolygon(chin_poly)

    painter.setPen(QPen(QColor("#64748B"), 0.5))
    painter.drawLine(QPointF(cx - 1.0, cy + 5.4), QPointF(cx - 1.0, cy + 6.8))
    painter.drawLine(QPointF(cx, cy + 5.2), QPointF(cx, cy + 7.0))
    painter.drawLine(QPointF(cx + 1.0, cy + 5.4), QPointF(cx + 1.0, cy + 6.8))

    painter.setBrush(QBrush(QColor(0, 245, 255, 240)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(cx - 0.7, cy + 4.2, 1.4, 0.6), 0.2, 0.2)

    painter.restore()

def main():
    app = QGuiApplication(sys.argv)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pil_images = []

    for s in sizes:
        img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        center = QPointF(s / 2.0, s / 2.0)
        scale = (s * 0.90) / 20.0
        draw_robot_mascot(p, center, 0.0, scale=scale)
        p.end()

        # Convert to PIL Image
        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        pil_img = Image.frombuffer("RGBA", (s, s), bytes(ptr), "raw", "BGRA", 0, 1)
        pil_images.append(pil_img)

    # Save multi-resolution Windows ICO
    pil_images[-1].save(
        "SysNotch.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=pil_images[:-1]
    )
    print("SUCCESS: SysNotch.ico generated with sizes:", sizes)

if __name__ == "__main__":
    main()
