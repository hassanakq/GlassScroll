"""Main settings window."""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from . import __version__, startup
from .config import TRIGGERS, Config
from .gestures import GestureEngine, Mode
from .glass import GlassWidget
from .icons import app_pixmap

ICE = QColor(120, 205, 255)
CORAL = QColor(255, 170, 125)

STYLE = """
* { color: rgba(255,255,255,235); font-size: 13px; }
QLabel { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#sub, QLabel#hint { color: rgba(255,255,255,140); font-size: 12px; }
QLabel#section { color: rgba(255,255,255,130); font-size: 12px; font-weight: 600; }
QLabel#value { color: rgb(150,215,255); }
QLabel#error { color: rgb(255,150,140); font-size: 12px; }
QPushButton#winbtn { background: transparent; border: none; border-radius: 8px; font-size: 17px;
    min-width: 34px; max-width: 34px; min-height: 28px; max-height: 28px; color: rgba(255,255,255,200); }
QPushButton#winbtn:hover { background: rgba(255,255,255,32); }
QPushButton#closebtn:hover { background: rgba(232,17,35,210); }
QPushButton#quit { background: rgba(255,255,255,20); border: 1px solid rgba(255,255,255,50);
    border-radius: 8px; padding: 6px 16px; }
QPushButton#quit:hover { background: rgba(255,255,255,42); }
QComboBox { background: rgba(255,255,255,22); border: 1px solid rgba(255,255,255,50);
    border-radius: 8px; padding: 6px 30px 6px 10px; }
QComboBox:hover { background: rgba(255,255,255,34); }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView { background: #1d2230; border: 1px solid rgba(255,255,255,60);
    selection-background-color: rgba(120,205,255,70); outline: 0; padding: 4px; }
QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,42); border-radius: 2px; }
QSlider::sub-page:horizontal { background: rgba(150,215,255,210); border-radius: 2px; }
QSlider::handle:horizontal { background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
"""


class GlassCard(QFrame):
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.fillPath(path, QColor(255, 255, 255, 18))
        p.setPen(QPen(QColor(255, 255, 255, 38), 1))
        p.drawPath(path)


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._knob = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._animate)

    def _get(self) -> float:
        return self._knob

    def _set(self, v: float) -> None:
        self._knob = v
        self.update()

    knob = Property(float, _get, _set)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._knob
        off, on = QColor(255, 255, 255, 50), QColor(110, 190, 255, 235)
        c = QColor(int(off.red() + (on.red() - off.red()) * t),
                   int(off.green() + (on.green() - off.green()) * t),
                   int(off.blue() + (on.blue() - off.blue()) * t),
                   int(off.alpha() + (on.alpha() - off.alpha()) * t))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(c)
        p.drawRoundedRect(QRectF(.5, .5, self.width() - 1, self.height() - 1), 12, 12)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        x = 3 + (self.width() - 24 + 1) * t
        p.drawEllipse(QRectF(x, 3, 18, 18))


class GlassCombo(QComboBox):
    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 190), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx, cy = self.width() - 16, self.height() / 2
        p.drawPolyline(QPolygonF([QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2)]))


class HoldTimeline(QWidget):
    """Shows tap / volume / track zones and a live playhead while the button is held."""

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self._elapsed: float | None = None
        self.setFixedHeight(78)

    def set_elapsed(self, ms: float | None) -> None:
        self._elapsed = ms
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        top, hgt = 8.0, 34.0
        total = self.cfg.long_ms * 1.5
        x1 = w * self.cfg.short_ms / total
        x2 = w * self.cfg.long_ms / total

        active = None
        if self._elapsed is not None:
            e = self._elapsed
            active = 0 if e < self.cfg.short_ms else (1 if e < self.cfg.long_ms else 2)

        zones = [(0.0, x1, QColor(255, 255, 255, 26), "Tap"),
                 (x1, x2, QColor(120, 205, 255, 80), "Volume"),
                 (x2, float(w), QColor(255, 170, 125, 80), "Tracks")]
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, top, w, hgt), 10, 10)
        p.setClipPath(clip)
        for i, (a, b, col, _label) in enumerate(zones):
            p.fillRect(QRectF(a, top, b - a, hgt), col)
            if active == i:
                p.fillRect(QRectF(a, top, b - a, hgt), QColor(255, 255, 255, 46))
        p.setClipping(False)

        font = QFont(self.font())
        font.setPointSize(9)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 230))
        for a, b, _c, label in zones:
            p.drawText(QRectF(a, top, b - a, hgt), Qt.AlignCenter, label)

        font.setWeight(QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 120))
        p.drawText(QRectF(x1 - 40, 48, 80, 18), Qt.AlignCenter, f"{self.cfg.short_ms} ms")
        p.drawText(QRectF(x2 - 40, 48, 80, 18), Qt.AlignCenter, f"{self.cfg.long_ms} ms")

        if self._elapsed is not None:
            x = min(w - 2.0, w * self._elapsed / total)
            p.setPen(QPen(QColor(255, 255, 255, 240), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x, top - 5), QPointF(x, top + hgt + 5))


def _row(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(QLabel(label))
    lay.addStretch(1)
    lay.addWidget(widget)
    return w


class MainWindow(GlassWidget):
    settings_changed = Signal()
    enabled_toggled = Signal(bool)
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(self, cfg: Config, engine: GestureEngine) -> None:
        super().__init__(radius=8, drag_height=64)
        self.cfg = cfg
        self.engine = engine
        self.setWindowTitle("GlassScroll")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 18)
        root.setSpacing(14)

        # header ------------------------------------------------------------
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(app_pixmap(96).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("GlassScroll")
        t.setObjectName("title")
        s = QLabel("Scroll wheel media control")
        s.setObjectName("sub")
        titles.addWidget(t)
        titles.addWidget(s)
        minimize, close = QPushButton("\u2013"), QPushButton("\u00d7")
        for b in (minimize, close):
            b.setObjectName("winbtn")
            b.setCursor(Qt.PointingHandCursor)
        close.setObjectName("winbtn")
        close.setProperty("class", "close")
        close.setStyleSheet("QPushButton:hover { background: rgba(232,17,35,210); }")
        minimize.clicked.connect(self.hide_requested)
        close.clicked.connect(self.hide_requested)
        head.addWidget(icon)
        head.addSpacing(8)
        head.addLayout(titles)
        head.addStretch(1)
        head.addWidget(minimize, 0, Qt.AlignTop)
        head.addWidget(close, 0, Qt.AlignTop)
        root.addLayout(head)

        # status card -------------------------------------------------------
        card = GlassCard()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        self.enable_switch = ToggleSwitch(cfg.enabled)
        self.enable_switch.toggled.connect(self._on_enabled)
        lay.addWidget(_row("Gesture control", self.enable_switch))
        root.addWidget(card)

        # timeline card -----------------------------------------------------
        card = GlassCard()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(6)
        lbl = QLabel("Hold, then scroll")
        lbl.setObjectName("section")
        self.timeline = HoldTimeline(cfg)
        self.status = QLabel("Hold your button to see it live")
        self.status.setObjectName("hint")
        lay.addWidget(lbl)
        lay.addWidget(self.timeline)
        lay.addWidget(self.status)
        root.addWidget(card)

        # settings card -----------------------------------------------------
        card = GlassCard()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        lbl = QLabel("Settings")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        self.combo = GlassCombo()
        for key, text in TRIGGERS.items():
            self.combo.addItem(text, key)
        self.combo.setCurrentIndex(list(TRIGGERS).index(cfg.trigger))
        self.combo.currentIndexChanged.connect(self._on_trigger)
        lay.addWidget(_row("Trigger button", self.combo))

        self.s_short = self._slider(lay, "Short hold \u2192 volume", 80, 600, cfg.short_ms, " ms", "short_ms")
        self.s_long = self._slider(lay, "Long hold \u2192 tracks", 230, 2000, cfg.long_ms, " ms", "long_ms")
        self.s_step = self._slider(lay, "Volume step", 1, 10, cfg.volume_step, " %", "volume_step")
        self.s_cool = self._slider(lay, "Track skip delay", 150, 1500, cfg.skip_cooldown_ms, " ms", "skip_cooldown_ms")

        self.t_invert = ToggleSwitch(cfg.invert_scroll)
        self.t_invert.toggled.connect(lambda v: self._set_bool("invert_scroll", v))
        lay.addWidget(_row("Reverse scroll direction", self.t_invert))
        self.t_overlay = ToggleSwitch(cfg.show_overlay)
        self.t_overlay.toggled.connect(lambda v: self._set_bool("show_overlay", v))
        lay.addWidget(_row("Show on-screen overlay", self.t_overlay))
        self.t_startup = ToggleSwitch(startup.is_enabled() if sys.platform == "win32" else cfg.start_with_windows)
        self.t_startup.toggled.connect(self._on_startup)
        lay.addWidget(_row("Start with Windows", self.t_startup))
        root.addWidget(card)

        # footer ------------------------------------------------------------
        foot = QHBoxLayout()
        ver = QLabel(f"Version {__version__}")
        ver.setObjectName("hint")
        quit_btn = QPushButton("Quit GlassScroll")
        quit_btn.setObjectName("quit")
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.clicked.connect(self.quit_requested)
        self.error = QLabel("")
        self.error.setObjectName("error")
        foot.addWidget(ver)
        foot.addStretch(1)
        foot.addWidget(quit_btn)
        root.addLayout(foot)
        root.addWidget(self.error)
        self.error.hide()

        self.setFixedHeight(root.sizeHint().height())

        # live playhead -----------------------------------------------------
        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._on_tick)
        engine.pressed.connect(self._on_pressed)
        engine.released.connect(self._on_released)
        engine.hook_failed.connect(self.show_error)

    # -- helpers --------------------------------------------------------------
    def _slider(self, lay: QVBoxLayout, label: str, lo: int, hi: int, val: int, unit: str, attr: str) -> QSlider:
        head = QHBoxLayout()
        head.addWidget(QLabel(label))
        head.addStretch(1)
        value = QLabel(f"{val}{unit}")
        value.setObjectName("value")
        head.addWidget(value)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setProperty("unit", unit)
        s._value_label = value
        s.valueChanged.connect(lambda v, a=attr: self._on_slider(a, v))
        box = QVBoxLayout()
        box.setSpacing(6)
        box.addLayout(head)
        box.addWidget(s)
        lay.addLayout(box)
        return s

    def _on_slider(self, attr: str, value: int) -> None:
        setattr(self.cfg, attr, value)
        self.cfg.clamp()
        for s, a in ((self.s_short, "short_ms"), (self.s_long, "long_ms"),
                     (self.s_step, "volume_step"), (self.s_cool, "skip_cooldown_ms")):
            v = getattr(self.cfg, a)
            if s.value() != v:
                s.blockSignals(True)
                s.setValue(v)
                s.blockSignals(False)
            s._value_label.setText(f"{v}{s.property('unit')}")
        self.timeline.update()
        self.settings_changed.emit()

    def _on_trigger(self, _i: int) -> None:
        self.cfg.trigger = self.combo.currentData()
        self.settings_changed.emit()

    def _set_bool(self, attr: str, value: bool) -> None:
        setattr(self.cfg, attr, value)
        self.settings_changed.emit()

    def _on_startup(self, value: bool) -> None:
        self.cfg.start_with_windows = value
        startup.set_enabled(value)
        self.settings_changed.emit()

    def _on_enabled(self, value: bool) -> None:
        self.cfg.enabled = value
        self.enabled_toggled.emit(value)
        self.settings_changed.emit()

    def set_enabled(self, value: bool) -> None:
        self.enable_switch.blockSignals(True)
        self.enable_switch.setChecked(value)
        self.enable_switch._knob = 1.0 if value else 0.0
        self.enable_switch.update()
        self.enable_switch.blockSignals(False)

    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()

    def _on_pressed(self) -> None:
        if self.isVisible():
            self._tick.start()

    def _on_released(self) -> None:
        self._tick.stop()
        self.timeline.set_elapsed(None)
        self.status.setText("Hold your button to see it live")

    def _on_tick(self) -> None:
        ms = self.engine.elapsed_ms()
        self.timeline.set_elapsed(ms)
        mode = self.engine.mode_at(ms)
        self.status.setText({Mode.IDLE: "Release now to click normally",
                             Mode.VOLUME: "Volume mode: scroll up or down",
                             Mode.TRACK: "Track mode: scroll up for next, down for previous"}[mode])
