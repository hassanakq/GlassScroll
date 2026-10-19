"""Vector icons drawn with QPainter (no image assets needed at runtime)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF)


def draw_speaker(p: QPainter, r: QRectF, color: QColor, waves: int = 2) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([
        QPointF(x + w * .08, y + h * .38), QPointF(x + w * .28, y + h * .38),
        QPointF(x + w * .50, y + h * .18), QPointF(x + w * .50, y + h * .82),
        QPointF(x + w * .28, y + h * .62), QPointF(x + w * .08, y + h * .62),
    ]))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(color, max(1.5, w * .075), Qt.SolidLine, Qt.RoundCap))
    cx, cy = x + w * .46, y + h * .5
    for i in range(waves):
        rad = w * (.20 + .17 * i)
        p.drawArc(QRectF(cx - rad, cy - rad, rad * 2, rad * 2), -42 * 16, 84 * 16)
    p.restore()


def draw_next(p: QPainter, r: QRectF, color: QColor) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([
        QPointF(x + w * .18, y + h * .20), QPointF(x + w * .18, y + h * .80),
        QPointF(x + w * .66, y + h * .50),
    ]))
    p.drawRoundedRect(QRectF(x + w * .72, y + h * .20, w * .11, h * .60), w * .04, w * .04)
    p.restore()


def draw_prev(p: QPainter, r: QRectF, color: QColor) -> None:
    p.save()
    p.translate(r.x() + r.width(), r.y())
    p.scale(-1, 1)
    draw_next(p, QRectF(0, 0, r.width(), r.height()), color)
    p.restore()


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    m = size * .06
    body = QRectF(m, m, size - 2 * m, size - 2 * m)
    path = QPainterPath()
    path.addRoundedRect(body, size * .24, size * .24)

    g = QLinearGradient(body.topLeft(), body.bottomRight())
    g.setColorAt(0, QColor(54, 104, 168))
    g.setColorAt(1, QColor(18, 28, 56))
    p.fillPath(path, g)

    sheen = QLinearGradient(body.topLeft(), QPointF(body.left(), body.center().y()))
    sheen.setColorAt(0, QColor(255, 255, 255, 95))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setClipPath(path)
    p.fillRect(QRectF(body.left(), body.top(), body.width(), body.height() * .5), sheen)
    p.setClipping(False)

    p.setPen(QPen(QColor(255, 255, 255, 120), max(1.0, size * .012)))
    p.drawPath(path)

    draw_speaker(p, QRectF(size * .22, size * .22, size * .56, size * .56), QColor(255, 255, 255, 240), 2)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(s))
    return icon
