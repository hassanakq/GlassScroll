"""Volume and media-key control.

Volume is set directly through the Windows Core Audio API (via pycaw) so the
exact percentage can be shown. If that is unavailable we fall back to the
standard volume media keys.
"""
from __future__ import annotations

import math
import sys

VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3


def _press(vk: int) -> None:
    if sys.platform != "win32":
        return
    import ctypes
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0x0001, 0)            # key down (extended)
    user32.keybd_event(vk, 0, 0x0001 | 0x0002, 0)   # key up


class MediaController:
    def __init__(self) -> None:
        self._endpoint = None
        self._failed = False

    # -- core audio -------------------------------------------------------
    def _get_endpoint(self):
        if self._failed or sys.platform != "win32":
            return None
        if self._endpoint is not None:
            return self._endpoint
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            speakers = AudioUtilities.GetSpeakers()
            if hasattr(speakers, "EndpointVolume"):          # newer pycaw
                self._endpoint = speakers.EndpointVolume
            else:                                            # older pycaw
                iface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._endpoint = cast(iface, POINTER(IAudioEndpointVolume))
        except Exception:
            self._failed = True
            self._endpoint = None
        return self._endpoint

    def get_volume(self) -> int | None:
        ep = self._get_endpoint()
        if ep is None:
            return None
        try:
            return round(ep.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            self._endpoint = None
            return None

    def change_volume(self, delta_percent: int) -> int | None:
        """Change volume by delta_percent. Returns the new percent, or None."""
        for _ in range(2):
            ep = self._get_endpoint()
            if ep is None:
                break
            try:
                current = ep.GetMasterVolumeLevelScalar()
                new = min(1.0, max(0.0, current + delta_percent / 100.0))
                ep.SetMasterVolumeLevelScalar(new, None)
                if delta_percent > 0 and ep.GetMute():
                    ep.SetMute(0, None)
                return round(new * 100)
            except Exception:
                self._endpoint = None        # device changed - re-acquire once
        # fallback: each key press is a 2 % step
        presses = max(1, math.ceil(abs(delta_percent) / 2))
        for _ in range(presses):
            _press(VK_VOLUME_UP if delta_percent > 0 else VK_VOLUME_DOWN)
        return None

    # -- transport --------------------------------------------------------
    def next_track(self) -> None:
        _press(VK_MEDIA_NEXT_TRACK)

    def previous_track(self) -> None:
        _press(VK_MEDIA_PREV_TRACK)

    def play_pause(self) -> None:
        _press(VK_MEDIA_PLAY_PAUSE)
