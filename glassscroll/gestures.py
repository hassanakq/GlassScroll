"""Global mouse gesture engine.

Hold the trigger button (middle click by default) and scroll:

    tap (< short_ms)            -> normal click is replayed
    short hold (>= short_ms)    -> VOLUME mode  (scroll up/down = volume +/-)
    long hold  (>= long_ms)     -> TRACK mode   (scroll up = next, down = previous)

A WH_MOUSE_LL hook runs on its own thread. It swallows the trigger button and
the wheel while the gesture is active, and talks to the UI via Qt signals.
"""
from __future__ import annotations

import sys
import threading
import time
from enum import IntEnum

from PySide6.QtCore import QObject, Signal


class Mode(IntEnum):
    IDLE = 0
    VOLUME = 1
    TRACK = 2


MAGIC = 0x474C5343  # "GLSC" - marks events we inject ourselves


class GestureEngine(QObject):
    pressed = Signal()
    released = Signal()
    scrolled = Signal(int, int)      # (Mode, signed number of wheel notches)
    hook_failed = Signal(str)

    def __init__(self, cfg) -> None:
        super().__init__()
        self.cfg = cfg
        self.down = False
        self.used = False
        self._t0 = 0.0
        self._hook = None

    # -- state machine (called from the hook thread) ----------------------
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000.0 if self.down else 0.0

    def mode_at(self, elapsed_ms: float) -> Mode:
        if elapsed_ms >= self.cfg.long_ms:
            return Mode.TRACK
        if elapsed_ms >= self.cfg.short_ms:
            return Mode.VOLUME
        return Mode.IDLE

    def on_down(self) -> None:
        self.down = True
        self.used = False
        self._t0 = time.monotonic()
        self.pressed.emit()

    def on_up(self) -> bool:
        """Returns True if the press was a plain tap that should be replayed."""
        elapsed = self.elapsed_ms()
        self.down = False
        replay = (not self.used) and elapsed < self.cfg.short_ms
        self.released.emit()
        return replay

    def on_scroll(self, delta: int) -> None:
        self.used = True
        mode = self.mode_at(self.elapsed_ms())
        if mode is Mode.IDLE:
            return
        notches = max(1, abs(delta) // 120)
        direction = 1 if delta > 0 else -1
        if self.cfg.invert_scroll:
            direction = -direction
        self.scrolled.emit(int(mode), direction * notches)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if sys.platform != "win32":
            self.hook_failed.emit("Mouse hook is only available on Windows.")
            return
        self._hook = _WinMouseHook(self)
        self._hook.start()

    def stop(self) -> None:
        if self._hook is not None:
            self._hook.stop()
            self._hook = None


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    WH_MOUSE_LL = 14
    WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
    WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
    WM_MOUSEWHEEL = 0x020A
    WM_QUIT = 0x0012

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), ctypes.c_void_p, wintypes.UINT, wintypes.UINT]
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p

    class _WinMouseHook(threading.Thread):
        def __init__(self, engine: GestureEngine) -> None:
            super().__init__(daemon=True, name="glassscroll-mouse-hook")
            self.engine = engine
            self._tid = 0
            self._handle = None
            self._proc_ref = HOOKPROC(self._proc)   # keep a reference alive

        # -- hook callback: must stay fast ---------------------------------
        def _proc(self, n_code, w_param, l_param):
            if n_code == 0:
                try:
                    info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    if info.dwExtraInfo != MAGIC and self._handle_event(w_param, info):
                        return 1
                except Exception:
                    pass
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        def _handle_event(self, msg: int, info) -> bool:
            eng, cfg = self.engine, self.engine.cfg
            is_down = None
            if cfg.trigger == "middle" and msg in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                is_down = msg == WM_MBUTTONDOWN
            elif cfg.trigger in ("x1", "x2") and msg in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                which = (info.mouseData >> 16) & 0xFFFF
                if which == (1 if cfg.trigger == "x1" else 2):
                    is_down = msg == WM_XBUTTONDOWN

            if is_down is True:
                if not cfg.enabled:
                    return False
                eng.on_down()
                return True
            if is_down is False:
                if eng.down:
                    if eng.on_up():
                        threading.Thread(target=self._replay_click, daemon=True).start()
                    return True
                return False
            if msg == WM_MOUSEWHEEL and eng.down:
                delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                eng.on_scroll(delta)
                return True
            return False

        def _replay_click(self) -> None:
            time.sleep(0.005)
            trig = self.engine.cfg.trigger
            if trig == "middle":
                user32.mouse_event(0x0020, 0, 0, 0, MAGIC)   # MIDDLEDOWN
                user32.mouse_event(0x0040, 0, 0, 0, MAGIC)   # MIDDLEUP
            else:
                btn = 1 if trig == "x1" else 2
                user32.mouse_event(0x0080, 0, 0, btn, MAGIC)  # XDOWN
                user32.mouse_event(0x0100, 0, 0, btn, MAGIC)  # XUP

        # -- thread --------------------------------------------------------
        def run(self) -> None:
            self._tid = kernel32.GetCurrentThreadId()
            self._handle = user32.SetWindowsHookExW(
                WH_MOUSE_LL, self._proc_ref, kernel32.GetModuleHandleW(None), 0
            )
            if not self._handle:
                self.engine.hook_failed.emit(
                    f"Could not install the mouse hook (error {ctypes.get_last_error()})."
                )
                return
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            user32.UnhookWindowsHookEx(self._handle)
            self._handle = None

        def stop(self) -> None:
            if self._tid:
                user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
