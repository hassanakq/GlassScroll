"""Glass window base: frameless, translucent, with Windows 11 acrylic blur."""
from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


def _build() -> int:
    try:
        return sys.getwindowsversion().build
    except Exception:
        return 0


def _accent_blur(hwnd: int) -> bool:
    """Windows 10 fallback: acrylic via SetWindowCompositionAttribute."""
    import ctypes

    class ACCENT_POLICY(ctypes.Structure):
        _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

    class WCAD(ctypes.Structure):
        _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                    ("SizeOfData", ctypes.c_size_t)]

    accent = ACCENT_POLICY(4 if _build() >= 17134 else 3, 0, 0x66181820, 0)   # AABBGGRR
    data = WCAD(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
    return bool(ctypes.windll.user32.SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data)))


def apply_native_glass(widget: QWidget) -> bool:
    """Enable the OS blur-behind. Returns True when a blur is active."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi

        def set_attr(attr: int, value: int) -> int:
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), ctypes.sizeof(v))

        set_attr(20, 1)     # immersive dark mode
        set_attr(33, 2)     # rounded corners
        if _build() >= 22621:
            class MARGINS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int),
                            ("t", ctypes.c_int), ("b", ctypes.c_int)]
            dwm.DwmExtendFrameIntoClientArea(ctypes.c_void_p(hwnd), ctypes.byref(MARGINS(-1, -1, -1, -1)))
            if set_attr(38, 3) == 0:        # DWMWA_SYSTEMBACKDROP_TYPE = acrylic
                return True
        return _accent_blur(hwnd)
    except Exception:
        return False


def paint_glass(p: QPainter, rect: QRectF, radius: float, blurred: bool, strong: bool = False) -> None:
    """Paint the glass surface: tint, light gradient, hairline border."""
    p.setRenderHint(QPainter.Antialiasing)
    r = rect.adjusted(.5, .5, -.5, -.5)
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)

    alpha = 150 if strong else (72 if blurred else 178)
    p.fillPath(path, QColor(14, 18, 30, alpha))

    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0.0, QColor(255, 255, 255, 48))
    g.setColorAt(0.45, QColor(255, 255, 255, 10))
    g.setColorAt(1.0, QColor(255, 255, 255, 22))
    p.fillPath(path, g)

    b = QLinearGradient(r.topLeft(), r.bottomRight())
    b.setColorAt(0.0, QColor(255, 255, 255, 120))
    b.setColorAt(0.5, QColor(255, 255, 255, 36))
    b.setColorAt(1.0, QColor(255, 255, 255, 70))
    p.setPen(QPen(QBrush(b), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


class GlassWidget(QWidget):
    def __init__(self, radius: float = 8, drag_height: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.radius = radius
        self.drag_height = drag_height
        self._blurred = False
        self._native_applied = False
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._native_applied:
            self._native_applied = True
            self._blurred = apply_native_glass(self)
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        paint_glass(p, QRectF(self.rect()), self.radius, self._blurred)

    def mousePressEvent(self, event) -> None:
        if (event.button() == Qt.LeftButton and event.position().y() <= self.drag_height
                and self.windowHandle() is not None):
            self.windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)
