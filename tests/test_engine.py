import time
import unittest

from glassscroll.config import Config
from glassscroll.gestures import GestureEngine, Mode


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(short_ms=40, long_ms=200)
        self.engine = GestureEngine(self.cfg)
        self.events = []
        self.engine.scrolled.connect(lambda m, n: self.events.append((m, n)))

    def test_quick_tap_is_replayed(self):
        self.engine.on_down()
        self.assertTrue(self.engine.on_up())

    def test_scroll_during_idle_is_ignored_and_not_replayed(self):
        self.engine.on_down()
        self.engine.on_scroll(120)
        self.assertEqual(self.events, [])
        self.assertFalse(self.engine.on_up())

    def test_short_hold_is_volume(self):
        self.engine.on_down()
        time.sleep(0.07)
        self.engine.on_scroll(120)
        self.engine.on_scroll(-240)
        self.assertEqual(self.events, [(Mode.VOLUME, 1), (Mode.VOLUME, -2)])
        self.assertFalse(self.engine.on_up())

    def test_long_hold_is_track(self):
        self.engine.on_down()
        time.sleep(0.25)
        self.engine.on_scroll(120)
        self.assertEqual(self.events, [(Mode.TRACK, 1)])

    def test_invert(self):
        self.cfg.invert_scroll = True
        self.engine.on_down()
        time.sleep(0.07)
        self.engine.on_scroll(120)
        self.assertEqual(self.events, [(Mode.VOLUME, -1)])

    def test_config_clamp(self):
        c = Config(short_ms=500, long_ms=100).clamp()
        self.assertGreaterEqual(c.long_ms, c.short_ms + 150)


if __name__ == "__main__":
    unittest.main()
