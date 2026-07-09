"""Generate resources/crier.ico (+ .png) - a speech bubble with a 'C'.

Run once (or whenever you want to tweak the look):
    pip install pillow
    python build/make_icon.py
"""

import os

from PIL import Image, ImageDraw

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "crier", "resources")
BG = (18, 20, 28, 0)
BUBBLE = (110, 168, 254, 255)
GLYPH = (18, 20, 28, 255)


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    s = size
    # rounded speech bubble
    d.rounded_rectangle([s * 0.10, s * 0.13, s * 0.90, s * 0.72],
                        radius=int(s * 0.18), fill=BUBBLE)
    # tail
    d.polygon([(s * 0.30, s * 0.68), (s * 0.30, s * 0.90), (s * 0.52, s * 0.68)], fill=BUBBLE)
    # 'C' drawn as a thick arc so it's font-independent and crisp at any size
    cx0, cy0, cx1, cy1 = s * 0.30, s * 0.20, s * 0.66, s * 0.56
    width = max(2, int(s * 0.09))
    d.arc([cx0, cy0, cx1, cy1], start=55, end=305, fill=GLYPH, width=width)
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    base = draw(256)
    base.save(os.path.join(OUT_DIR, "crier.png"))
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(os.path.join(OUT_DIR, "crier.ico"), sizes=sizes)
    print("Wrote", os.path.join(OUT_DIR, "crier.ico"))


if __name__ == "__main__":
    main()
