#!/usr/bin/env python3
"""
Render the FolioPress icon set from the SVG marks in branding/.

    python packaging/make_icons.py

Writes branding/foliopress.ico (Windows), branding/foliopress.icns (macOS),
branding/icons/<size>.png (Linux hicolor) and the README support badge.
Needs PyQt5 and Pillow.
"""

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QImage, QPainter, QColor
from PyQt5.QtCore import Qt
from PIL import Image

BRANDING = Path(__file__).resolve().parent.parent / "branding"
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]
SMALL = 32                          # at or below this, use the simplified mark


def render(svg, out, w, h, bg=None):
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(bg) if bg else Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    QSvgRenderer(str(svg)).render(p)
    p.end()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(out)):
        sys.exit(f"could not write {out}")
    return out


def main():
    app = QApplication(sys.argv)
    big, small = BRANDING / "foliopress-mark.svg", BRANDING / "foliopress-mark-small.svg"

    pngs = {s: render(small if s <= SMALL else big, BRANDING / "icons" / f"{s}.png", s, s)
            for s in ICON_SIZES}

    # .ico — every size as its own frame, so Windows never scales the big mark down to 16 px
    frames = [Image.open(pngs[s]).convert("RGBA") for s in ICON_SIZES if s <= 256]
    frames[-1].save(BRANDING / "foliopress.ico", format="ICO",
                    sizes=[f.size for f in frames], append_images=frames[:-1])
    big1024 = render(big, BRANDING / "icons" / "1024.png", 1024, 1024)
    Image.open(big1024).convert("RGBA").save(BRANDING / "foliopress.icns", format="ICNS")

    render(big, BRANDING / "foliopress-mark-512.png", 512, 512)
    render(BRANDING / "support-badge.svg", BRANDING / "support-badge.png", 480, 96)
    print("icons written to", BRANDING)


if __name__ == "__main__":
    main()
