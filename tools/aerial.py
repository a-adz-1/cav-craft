#!/usr/bin/env python3
"""An aerial picture of a box of the world, for checking layouts against the ground truth: Esri World Imagery
tiles (zoom 19) stitched and cropped, north up, 2 px per block.

    .venv/bin/python tools/aerial.py x0 z0 x1 z1 out.jpg [px per block, default 2]
"""
import io
import math
import os
import sys

from PIL import Image

from survey import get, to_ll
from box import E0, N1

Z = 19
CACHE = ".downloads/ref/aerial"


def tile_xy(lat, lon):
    n = 2 ** Z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def aerial(x0, z0, x1, z1, out, scale=2):
    os.makedirs(CACHE, exist_ok=True)
    corners = [tile_xy(*to_ll.transform(E0 + x, N1 - z)[::-1]) for x, z in ((x0, z0), (x1, z1))]
    (ax, ay), (bx, by) = corners
    tx0, ty0, tx1, ty1 = int(ax), int(ay), int(bx), int(by)
    sheet = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            fn = f"{CACHE}/{Z}_{tx}_{ty}.jpg"
            if not os.path.exists(fn):
                data = get(f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{Z}/{ty}/{tx}")
                if not data:
                    continue
                open(fn, "wb").write(data)
            sheet.paste(Image.open(fn), ((tx - tx0) * 256, (ty - ty0) * 256))
    # shortcut: treats the box as north-up web-mercator (grid north is under 1 degree off here), fine for looking
    crop = sheet.crop((int((ax - tx0) * 256), int((ay - ty0) * 256), int((bx - tx0) * 256), int((by - ty0) * 256)))
    crop.resize(((x1 - x0) * scale, (z1 - z0) * scale), Image.LANCZOS).save(out, quality=85)


if __name__ == "__main__":
    a = sys.argv
    aerial(int(a[1]), int(a[2]), int(a[3]), int(a[4]), a[5], int(a[6]) if len(a) > 6 else 2)
