#!/usr/bin/env python3
"""The built world from straight above, in true block colours (the texture averages eye_view uses), with a
little height shading. For checking layouts against an aerial photo.

    .venv/bin/python tools/top_view.py world/Cavcraft x0 z0 x1 z1 out.png [px per block, default 4]
"""
import sys

import numpy as np
from PIL import Image

import eye_view


def top(world, x0, z0, x1, z1, out, scale=4, tdir=None):
    vol, names = eye_view.load(world, x0, x1, z0, z1, 20, 140)
    solid = np.array([n not in eye_view.PASS for n in names])
    cols = np.array([eye_view.tex_colour(n, tdir or eye_view.TEX) for n in names])
    s = solid[vol]
    y = s.shape[0] - 1 - np.argmax(s[::-1], axis=0)                 # highest block in each column
    img = cols[np.take_along_axis(vol, y[None], 0)[0]]
    shade = 1 + np.clip((y - np.roll(y, 1, 0)) * 0.08, -0.25, 0.25)  # lit from the north
    Image.fromarray((img * shade[..., None]).clip(0, 255).astype(np.uint8)).resize(
        ((x1 - x0) * scale, (z1 - z0) * scale), Image.NEAREST).save(out)


if __name__ == "__main__":
    a = sys.argv
    top(a[1], int(a[2]), int(a[3]), int(a[4]), int(a[5]), a[6], int(a[7]) if len(a) > 7 else 4)
