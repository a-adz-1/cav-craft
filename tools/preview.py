#!/usr/bin/env python3
"""Top-down picture of build/layers.npz (or a region of it) for checking by eye.

    .venv/bin/python tools/preview.py build/layers.npz out.png [scale] [row0 row1 col0 col1]
"""
import sys

import numpy as np
from PIL import Image

from layers_colours import COLOURS

L = np.load(sys.argv[1])
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
r0, r1, c0, c1 = map(int, sys.argv[4:8]) if len(sys.argv) > 7 else (0, L["mask"].shape[0], 0, L["mask"].shape[1])
surface = L["surface"][r0:r1, c0:c1]
img = COLOURS[surface]
ground = L["ground"][r0:r1, c0:c1].astype(np.float32)
shade = np.clip(1 + (ground - np.roll(ground, 1, 0)) * 0.08, 0.6, 1.3)   # light from the north
img = np.clip(img * shade[..., None], 0, 255)
b = L["building"][r0:r1, c0:c1] > 0
img[b] = [150, 90, 80]
img[~L["mask"][r0:r1, c0:c1]] = [20, 20, 30]
im = Image.fromarray(img.astype(np.uint8))
im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
im.save(sys.argv[2])
