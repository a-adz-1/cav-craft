#!/usr/bin/env python3
"""The Cavcraft gift card: credit-card size (85.6 x 54 mm at 300 dpi), a blocky CAV CRAFT logo and a
creeper-green QR code to the GitHub page on the front, an achievement checklist on the back, and an A4
print sheet (10 cards a side, cut marks, back page mirrored for long-edge double-sided printing).

    .venv/bin/python tools/card.py      -> docs/card/front.png, back.png, cavcraft-cards-a4.pdf

Checks itself: the QR code must decode (zbarimg) to the URL, or it stops.
"""
import os
import random
import subprocess

import qrcode
from PIL import Image, ImageDraw, ImageFont

URL = "https://github.com/a-adz-1/cav-craft"
DPI = 300
W, H = round(85.6 / 25.4 * DPI), round(54 / 25.4 * DPI)        # 1011 x 638
OUT = "docs/card"
BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
REG = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
ACHIEVEMENTS = [
    "Have tea on Whittington's Tea Barge",
    "Watch a film at Caversham Court",
    "Skate at Winter Wonderland",
    "Work Caversham Lock",
    "Relax on the sandy beach",
    "Row a boat on the river",
    "Find your house",
    "Find the treasure at your school",
    "Cross the weir footbridge",
    "Spot the swans",
    "See St Peter's glow at night",
]
GREENS = [(46, 125, 50), (56, 142, 60), (27, 94, 32), (67, 160, 71), (30, 110, 40)]
PALE = (232, 245, 233)

# 5 x 7 pixel letters (original, blocky)
FONT = {
    "C": ["01111", "11000", "11000", "11000", "11000", "11000", "01111"],
    "A": ["01110", "11011", "11011", "11111", "11011", "11011", "11011"],
    "V": ["11011", "11011", "11011", "11011", "11011", "01110", "00100"],
    "R": ["11110", "11011", "11011", "11110", "11011", "11011", "11011"],
    "F": ["11111", "11000", "11000", "11110", "11000", "11000", "11000"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}


def block(d, x, y, s, top, side):
    """One little block: a face with a lighter top-left edge and darker bottom-right."""
    d.rectangle([x, y, x + s - 1, y + s - 1], fill=side)
    hi = tuple(min(255, c + 40) for c in side)
    lo = tuple(max(0, c - 50) for c in side)
    e = max(1, s // 7)
    d.rectangle([x, y, x + s - 1, y + e - 1], fill=top if top else hi)
    d.rectangle([x, y, x + e - 1, y + s - 1], fill=hi)
    d.rectangle([x, y + s - e, x + s - 1, y + s - 1], fill=lo)
    d.rectangle([x + s - e, y, x + s - 1, y + s - 1], fill=lo)


def word(d, text, x, y, s, rng):
    """Grass-block letters: the top two rows of each letter are grass, the rest dirt."""
    for ch in text:
        for r, row in enumerate(FONT[ch]):
            for c, on in enumerate(row):
                if on == "1":
                    if r < 2:
                        col = rng.choice(GREENS[:4])
                    else:
                        col = rng.choice([(134, 96, 67), (121, 85, 58), (150, 108, 74)])
                    block(d, x + c * s, y + r * s, s, None, col)
        x += 6 * s
    return x


def creeper_qr(size):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=3, box_size=1)
    q.add_data(URL)
    q.make(fit=True)
    m = q.get_matrix()
    n = len(m)
    px = size // n
    img = Image.new("RGB", (n * px, n * px), PALE)
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    for r in range(n):
        for c in range(n):
            if m[r][c]:
                block(d, c * px, r * px, px, None, rng.choice(GREENS[:3]))
    # a creeper face in the middle (error correction H rebuilds the modules it covers)
    face = ["11111111", "10011001", "10011001", "11100111", "11000011", "11000011", "11011011", "11111111"]
    f0 = (n - 8) // 2
    for r, row in enumerate(face):
        for c, on in enumerate(row):
            col = rng.choice(GREENS) if on == "1" else (20, 20, 20)
            block(d, (f0 + c) * px, (f0 + r) * px, px, None, col)
    return img


def front():
    rng = random.Random(3)
    img = Image.new("RGB", (W, H), (24, 26, 30))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 22):                                  # faint stone texture
        for x in range(0, W, 22):
            g = rng.randint(28, 40)
            d.rectangle([x, y, x + 21, y + 21], fill=(g, g + 2, g + 6))
    qr = creeper_qr(440)
    img.paste(qr, (W - qr.width - 40, (H - qr.height) // 2))
    s = 13
    word(d, "CAV", 48, 70, s, rng)
    word(d, "CRAFT", 48, 70 + 9 * s, s, rng)
    f1 = ImageFont.truetype(BOLD, 34)
    f2 = ImageFont.truetype(REG, 26)
    d.text((50, 330), "Caversham in Minecraft", font=f1, fill=(240, 240, 240))
    d.text((50, 376), "Every street, the river, the lock,", font=f2, fill=(200, 210, 200))
    d.text((50, 408), "Winter Wonderland and more", font=f2, fill=(200, 210, 200))
    d.text((50, 470), "FREE  -  scan me!", font=ImageFont.truetype(BOLD, 40), fill=(126, 211, 33))
    d.text((50, 560), "Minecraft Java Edition", font=ImageFont.truetype(REG, 22), fill=(150, 160, 150))
    return img


def back():
    img = Image.new("RGB", (W, H), (244, 241, 230))
    d = ImageDraw.Draw(img)
    rng = random.Random(5)
    for x in range(0, W, 20):                                  # a strip of grass blocks along the top
        block(d, x, 0, 20, None, rng.choice(GREENS))
        block(d, x, 20, 20, None, rng.choice([(134, 96, 67), (121, 85, 58)]))
    d.text((40, 54), "CAVCRAFT ACHIEVEMENTS", font=ImageFont.truetype(BOLD, 40), fill=(40, 60, 40))
    f = ImageFont.truetype(REG, 23)
    col_x = (40, W // 2 + 10)
    per = (len(ACHIEVEMENTS) + 1) // 2
    for i, a in enumerate(ACHIEVEMENTS):
        x = col_x[i // per]
        y = 130 + (i % per) * 72
        d.rectangle([x, y + 4, x + 26, y + 30], outline=(40, 90, 40), width=3)
        words, lines, cur = a.split(), [], ""
        for w_ in words:                                       # wrap to the column
            if d.textlength((cur + " " + w_).strip(), font=f) > W // 2 - 110:
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        for k, line in enumerate(lines[:2]):
            d.text((x + 38, y + k * 28), line, font=f, fill=(30, 30, 30))
    d.text((40, H - 46), "github.com/a-adz-1/cav-craft   Merry Christmas!", font=ImageFont.truetype(BOLD, 22),
           fill=(60, 90, 60))
    d.text((W - 300, H - 42), "Map: OpenStreetMap, EA LiDAR", font=ImageFont.truetype(REG, 16), fill=(120, 120, 110))
    return img


def sheet(card, mirror):
    """A4 at 300 dpi, 2 x 5 cards with cut marks; the back sheet swaps columns for long-edge duplex."""
    A4 = (2480, 3508)
    page = Image.new("RGB", A4, "white")
    d = ImageDraw.Draw(page)
    gx, gy = (A4[0] - 2 * W) // 2, (A4[1] - 5 * H) // 2
    for r in range(5):
        for c in range(2):
            cc = 1 - c if mirror else c
            page.paste(card, (gx + cc * W, gy + r * H))
    for x in (gx, gx + W, gx + 2 * W):                         # cut marks in the margins
        d.line([x, gy - 60, x, gy - 15], fill="black", width=2)
        d.line([x, gy + 5 * H + 15, x, gy + 5 * H + 60], fill="black", width=2)
    for r in range(6):
        y = gy + r * H
        d.line([gx - 60, y, gx - 15, y], fill="black", width=2)
        d.line([gx + 2 * W + 15, y, gx + 2 * W + 60, y], fill="black", width=2)
    return page


def main():
    os.makedirs(OUT, exist_ok=True)
    f, b = front(), back()
    f.save(f"{OUT}/front.png", dpi=(DPI, DPI))
    b.save(f"{OUT}/back.png", dpi=(DPI, DPI))
    got = subprocess.run(["zbarimg", "-q", "--raw", f"{OUT}/front.png"], capture_output=True, text=True).stdout.strip()
    assert got == URL, f"QR code doesn't scan: {got!r}"
    pages = [sheet(f, False), sheet(b, True)]
    pages[0].save(f"{OUT}/cavcraft-cards-a4.pdf", save_all=True, append_images=pages[1:], resolution=DPI)
    print("QR scans to", got, "->", OUT)


if __name__ == "__main__":
    main()
