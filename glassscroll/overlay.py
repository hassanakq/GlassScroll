"""Small click-through glass HUD shown while gesturing."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .glass import paint_glass
from .icons import draw_next, draw_prev, draw_speaker

ICE = QColor(120, 205, 255)
CORAL = QColor(255, 170, 125)


class Overlay(QWidget):
    W, H = 320, 84

    def __init__(self, cfg) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.cfg = cfg
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.resize(self.W, self.H)

        self.kind = "mode_volume"
        self.title = ""
        self.sub = ""
        self.value: int | None = None
        self._dir = 0

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(1100)
        self._hide_timer.timeout.connect(self._fade_out)

        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)

    # -- public API ----------------------------------------------------------
    def show_mode(self, mode: str) -> None:
        if mode == "volume":
            self._set("mode_volume", "Volume mode", "Scroll up or down to adjust", None)
        else:
            self._set("mode_track", "Track mode", "Scroll up for next, down for previous", None)

    def show_volume(self, percent: int | None, direction: int) -> None:
        self._set("volume", "Volume", "", percent, direction)

    def show_track(self, is_next: bool) -> None:
        if is_next:
            self._set("next", "Next track", "Keep scrolling to skip more", None)
        else:
            self._set("prev", "Previous track", "Keep scrolling to go back", None)

    # -- internals -----------------------------------------------------------
    def _set(self, kind, title, sub, value, direction: int = 0) -> None:
        if not self.cfg.show_overlay:
            return
        self.kind, self.title, self.sub, self.value, self._dir = kind, title, sub, value, direction
        self._anim.stop()
        self.setWindowOpacity(1.0)
        if not self.isVisible():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            g = screen.availableGeometry()
            self.move(g.center().x() - self.W // 2, g.bottom() - self.H - 72)
            self.show()
        self.update()
        self._hide_timer.start()

    def _fade_out(self) -> None:
        self._anim.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        paint_glass(p, QRectF(self.rect()), 22, blurred=False, strong=True)
        p.setRenderHint(QPainter.Antialiasing)
        white = QColor(255, 255, 255, 240)
        icon_rect = QRectF(22, 20, 44, 44)
        accent = CORAL if self.kind in ("next", "prev", "mode_track") else ICE

        if self.kind in ("volume", "mode_volume"):
            level = 0 if self.value == 0 else (1 if (self.value or 50) < 50 else 2)
            draw_speaker(p, icon_rect, accent, level)
        elif self.kind in ("next", "mode_track"):
            draw_next(p, icon_rect, accent)
        else:
            draw_prev(p, icon_rect, accent)

        title_font = QFont(self.font())
        title_font.setPointSize(12)
        title_font.setWeight(QFont.DemiBold)
        sub_font = QFont(self.font())
        sub_font.setPointSize(9)

        if self.kind == "volume":
            p.setFont(title_font)
            p.setPen(white)
            p.drawText(QRectF(84, 14, 140, 28), Qt.AlignLeft | Qt.AlignVCenter, self.title)
            label = f"{self.value}%" if self.value is not None else ("Up" if self._dir > 0 else "Down")
            p.drawText(QRectF(self.W - 100, 14, 76, 28), Qt.AlignRight | Qt.AlignVCenter, label)
            track = QRectF(84, 52, self.W - 84 - 26, 7)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 45))
            p.drawRoundedRect(track, 3.5, 3.5)
            frac = (self.value if self.value is not None else 50) / 100.0
            if frac > 0:
                fill = QRectF(track.x(), track.y(), max(7.0, track.width() * frac), track.height())
                g = QLinearGradient(fill.topLeft(), fill.topRight())
                g.setColorAt(0, QColor(150, 220, 255))
                g.setColorAt(1, QColor(90, 170, 255))
                p.setBrush(g)
                p.drawRoundedRect(fill, 3.5, 3.5)
        else:
            p.setFont(title_font)
            p.setPen(white)
            p.drawText(QRectF(84, 16, self.W - 100, 28), Qt.AlignLeft | Qt.AlignVCenter, self.title)
            p.setFont(sub_font)
            p.setPen(QColor(255, 255, 255, 150))
            p.drawText(QRectF(84, 44, self.W - 100, 22), Qt.AlignLeft | Qt.AlignVCenter, self.sub)
