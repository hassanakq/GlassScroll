"""Regenerates assets/icon.* and the preview screenshots (dev tool).

Run from the project root:  python scripts/make_assets.py
The screenshots are composites over a sample wallpaper with a simulated blur.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import (QApplication, QGraphicsBlurEffect, QGraphicsPixmapItem,
                               QGraphicsScene)

from glassscroll.config import Config
from glassscroll.gestures import GestureEngine
from glassscroll.icons import app_pixmap
from glassscroll.overlay import Overlay
from glassscroll.ui import MainWindow

app = QApplication(sys.argv)
app.setStyle("Fusion")
cfg = Config()


def wallpaper(w, h):
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(20, 40, 90)); g.setColorAt(.5, QColor(70, 40, 110)); g.setColorAt(1, QColor(200, 110, 90))
    p.fillRect(0, 0, w, h, g)
    for cx, cy, r, c in [(.2, .25, .45, QColor(80, 200, 255, 150)), (.85, .7, .5, QColor(255, 150, 100, 140)),
                         (.5, .95, .4, QColor(160, 90, 255, 120))]:
        rg = QRadialGradient(w * cx, h * cy, w * r); rg.setColorAt(0, c); rg.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, rg)
    p.end()
    return img


def blurred(img, radius=28):
    sc = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(img))
    fx = QGraphicsBlurEffect(); fx.setBlurRadius(radius)
    item.setGraphicsEffect(fx); sc.addItem(item)
    out = QImage(img.size(), QImage.Format_ARGB32); out.fill(0)
    p = QPainter(out); sc.render(p); p.end()
    return out


os.makedirs("assets", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)
app_pixmap(256).save("assets/icon.png")
Image.open("assets/icon.png").save("assets/icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

win = MainWindow(cfg, GestureEngine(cfg))
win.show(); app.processEvents()
shot = win.grab()
bg = wallpaper(shot.width() + 160, shot.height() + 160)
soft = blurred(bg)
p = QPainter(bg)
path = QPainterPath(); path.addRoundedRect(QRectF(80, 80, shot.width(), shot.height()), 8, 8)
p.setClipPath(path); p.drawImage(0, 0, soft); p.setClipping(False)
p.drawPixmap(80, 80, shot); p.end()
bg.save("screenshots/interface.png")

ov = Overlay(cfg)
shots = []
for fn in (lambda: ov.show_volume(64, 1), lambda: ov.show_mode("track"), lambda: ov.show_track(True)):
    fn(); app.processEvents(); shots.append(ov.grab())
W = sum(s.width() for s in shots) + 60 * (len(shots) + 1); H = shots[0].height() + 120
img = wallpaper(W, H); p = QPainter(img); x = 60
for s in shots:
    p.drawPixmap(x, 60, s); x += s.width() + 60
p.end(); img.save("screenshots/overlay.png")
print("assets generated")
