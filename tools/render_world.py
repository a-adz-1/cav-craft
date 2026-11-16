#!/usr/bin/env python3
"""Draws a world's region files from above (top non-air block per column), read back from the
.mca files, so it checks what was actually written.

    .venv/bin/python tools/render_world.py world/Cavcraft out.png [scale] [x0 z0 x1 z1]
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

import anvil

COL = {"grass_block": (110, 160, 70), "water": (60, 90, 200), "gray_concrete": (80, 80, 85),
       "polished_andesite": (160, 160, 160), "dirt_path": (150, 120, 80), "coarse_dirt": (120, 95, 60),
       "stone": (130, 130, 130), "smooth_stone": (170, 170, 165), "sand": (220, 205, 150),
       "wheat": (200, 180, 80), "carrots": (90, 150, 60), "potatoes": (90, 150, 60), "green_terracotta": (80, 130, 90),
       "gravel": (140, 130, 125), "mud": (70, 60, 55), "short_grass": (100, 150, 60), "fern": (70, 120, 50),
       "glass": (200, 230, 240), "deepslate_tiles": (55, 55, 60), "terracotta": (150, 85, 60),
       "brown_terracotta": (80, 55, 40), "polished_blackstone": (45, 40, 45), "bricks": (150, 85, 70),
       "white_terracotta": (210, 180, 160), "smooth_quartz": (235, 230, 225), "gray_concrete_x": 0,
       "light_gray_concrete": (125, 125, 115), "white_concrete": (210, 215, 215), "cyan_terracotta": (85, 90, 90),
       "stone_bricks": (120, 120, 120), "spruce_planks": (110, 80, 50), "dark_oak_planks": (65, 45, 25),
       "oak_leaves": (60, 120, 40), "birch_leaves": (90, 130, 60), "spruce_leaves": (40, 80, 50),
       "oak_log": (100, 80, 50), "bedrock": (20, 20, 20), "birch_log": (200, 200, 190),
       "dark_oak_leaves": (40, 90, 30), "dark_oak_log": (60, 45, 30), "dandelion": (230, 210, 40), "poppy": (200, 40, 30)}


def main():
    world, out = sys.argv[1], sys.argv[2]
    scale = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    win = list(map(int, sys.argv[4:8])) if len(sys.argv) > 7 else None
    regs = glob.glob(os.path.join(world, "region", "r.*.mca"))
    rxz = [tuple(map(int, re.findall(r"r\.(-?\d+)\.(-?\d+)\.mca", r)[0])) for r in regs]
    maxx = (max(r[0] for r in rxz) + 1) * 512
    maxz = (max(r[1] for r in rxz) + 1) * 512
    x0, z0, x1, z1 = win or (0, 0, maxx, maxz)
    img = np.full((z1 - z0, x1 - x0, 3), 20, np.uint8)
    hgt = np.zeros((z1 - z0, x1 - x0), np.int32)
    unknown = set()
    for path, (rx, rz) in zip(regs, rxz):
        if rx * 512 >= x1 or (rx + 1) * 512 <= x0 or rz * 512 >= z1 or (rz + 1) * 512 <= z0:
            continue
        for lz in range(32):
            for lx in range(32):
                cx, cz = rx * 32 + lx, rz * 32 + lz
                if cx * 16 >= x1 or cx * 16 + 16 <= x0 or cz * 16 >= z1 or cz * 16 + 16 <= z0:
                    continue
                ch = anvil.read_chunk(path, lx, lz)
                if ch is None:
                    continue
                top = np.full((16, 16), -1, np.int32)
                name = np.full((16, 16), "", object)
                for s in sorted(ch["sections"], key=lambda s: -s["Y"]):
                    p = s["block_states"]["palette"]
                    names = np.array([e["Name"][10:] for e in p], object)
                    if len(p) == 1:
                        idx = np.zeros(4096, int)
                    else:
                        idx = anvil.unpack(s["block_states"]["data"], max(4, (len(p) - 1).bit_length()))
                    blk = names[idx].reshape(16, 16, 16)
                    for y in range(15, -1, -1):
                        layer = blk[y]
                        new = (top < 0) & (layer != "air")
                        top[new] = s["Y"] * 16 + y
                        name[new] = layer[new]
                    if (top >= 0).all():
                        break
                X, Z = cx * 16 - x0, cz * 16 - z0
                for zz in range(16):
                    for xx in range(16):
                        if 0 <= Z + zz < img.shape[0] and 0 <= X + xx < img.shape[1] and top[zz, xx] >= 0:
                            c = COL.get(name[zz, xx])
                            if c is None:
                                unknown.add(name[zz, xx])
                                c = (255, 0, 255)
                            img[Z + zz, X + xx] = c
                            hgt[Z + zz, X + xx] = top[zz, xx]
    shade = np.clip(1 + (hgt - np.roll(hgt, 1, 0)) * 0.06, 0.6, 1.3)
    img = np.clip(img * shade[..., None], 0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS).save(out)
    if unknown:
        print("no colour for:", sorted(unknown))


main()
