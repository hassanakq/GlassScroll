"""Application entry: wires the gesture engine, media control, HUD, window and tray."""
from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QDir, QLockFile, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import APP_NAME
from .config import Config
from .gestures import GestureEngine, Mode
from .icons import app_icon
from .media import MediaController
from .overlay import Overlay
from .ui import MainWindow


class Controller(QObject):
    def __init__(self, app: QApplication, cfg: Config) -> None:
        super().__init__()
        self.app, self.cfg = app, cfg
        self.media = MediaController()
        self.engine = GestureEngine(cfg)
        self.overlay = Overlay(cfg)
        self.window = MainWindow(cfg, self.engine)
        self._last_skip = 0.0
        self._told_about_tray = False

        self._save_timer = QTimer(self, singleShot=True, interval=500)
        self._save_timer.timeout.connect(self.cfg.save)
        self._t_short = QTimer(self, singleShot=True)
        self._t_long = QTimer(self, singleShot=True)
        self._t_short.timeout.connect(self._enter_volume)
        self._t_long.timeout.connect(self._enter_track)

        # tray ----------------------------------------------------------------
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        act_open = QAction("Open GlassScroll", menu)
        self.act_enabled = QAction("Gesture control", menu, checkable=True)
        self.act_enabled.setChecked(cfg.enabled)
        act_quit = QAction("Quit", menu)
        act_open.triggered.connect(self.show_window)
        self.act_enabled.toggled.connect(self.set_enabled)
        act_quit.triggered.connect(self.quit)
        for a in (act_open, self.act_enabled):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # wiring ----------------------------------------------------------------
        self.window.settings_changed.connect(self._save_timer.start)
        self.window.enabled_toggled.connect(self._sync_tray_enabled)
        self.window.hide_requested.connect(self.hide_window)
        self.window.quit_requested.connect(self.quit)
        self.engine.pressed.connect(self._on_pressed)
        self.engine.released.connect(self._on_released)
        self.engine.scrolled.connect(self._on_scrolled)
        self.engine.start()

    # -- window / tray ------------------------------------------------------------
    def show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def hide_window(self) -> None:
        self.window.hide()
        if not self._told_about_tray:
            self._told_about_tray = True
            self.tray.showMessage(APP_NAME, "Still running in the tray. Right-click the icon to quit.",
                                  QSystemTrayIcon.Information, 2500)

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def set_enabled(self, value: bool) -> None:
        self.cfg.enabled = value
        self.window.set_enabled(value)
        self._save_timer.start()

    def _sync_tray_enabled(self, value: bool) -> None:
        self.act_enabled.blockSignals(True)
        self.act_enabled.setChecked(value)
        self.act_enabled.blockSignals(False)

    def quit(self) -> None:
        self.cfg.save()
        self.engine.stop()
        self.tray.hide()
        self.app.quit()

    # -- gesture feedback ---------------------------------------------------------
    def _on_pressed(self) -> None:
        self._t_short.start(self.cfg.short_ms)
        self._t_long.start(self.cfg.long_ms)

    def _on_released(self) -> None:
        self._t_short.stop()
        self._t_long.stop()

    def _enter_volume(self) -> None:
        if not self.engine.down:
            return
        percent = self.media.get_volume()
        if percent is not None:
            self.overlay.show_volume(percent, 0)
        else:
            self.overlay.show_mode("volume")

    def _enter_track(self) -> None:
        if self.engine.down:
            self.overlay.show_mode("track")

    def _on_scrolled(self, mode: int, notches: int) -> None:
        if mode == Mode.VOLUME:
            percent = self.media.change_volume(notches * self.cfg.volume_step)
            self.overlay.show_volume(percent, 1 if notches > 0 else -1)
        elif mode == Mode.TRACK:
            now = time.monotonic()
            if (now - self._last_skip) * 1000 < self.cfg.skip_cooldown_ms:
                return
            self._last_skip = now
            if notches > 0:
                self.media.next_track()
            else:
                self.media.previous_track()
            self.overlay.show_track(notches > 0)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    start_minimized = "--minimized" in argv

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GlassScroll.App")
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI Variable Text", 10))

    lock = QLockFile(os.path.join(QDir.tempPath(), "glassscroll.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "GlassScroll is already running.\nLook for its icon in the system tray.")
        return 0

    controller = Controller(app, Config.load())
    if not start_minimized:
        controller.show_window()
    code = app.exec()
    lock.unlock()
    return code
