#!/usr/bin/env python3
"""Contact sheet of Commons photos whose title contains a phrase.
    .venv/bin/python tools/look_title.py "St Barnabas" -> build/title_<phrase>.jpg"""
import json
import os
import sys

from PIL import Image, ImageDraw

q = sys.argv[1].lower()
files = []
for path, base in ((".downloads/ref/commons/meta.json", ""),
                   ("/home/adz/Projects/splitwater/.downloads/ref/caversham/survey/commons/meta.json",
                    "/home/adz/Projects/splitwater/.downloads/ref/caversham/survey/commons/")):
    for t, m in json.load(open(path)).items():
        fn = m.get("file", "")
        fn = base + os.path.basename(fn) if base else fn
        if q in t.lower() and os.path.exists(fn) and fn not in files:
            files.append(fn)
files = files[:12]
W, H = 480, 360
sheet = Image.new("RGB", (W * 4, H * max(1, (len(files) + 3) // 4)), "white")
for k, fn in enumerate(files):
    im = Image.open(fn).convert("RGB")
    im.thumbnail((W, H))
    sheet.paste(im, ((k % 4) * W, (k // 4) * H))
out = "build/title_" + q.replace(" ", "_") + ".jpg"
sheet.save(out, quality=80)
print(len(files), "->", out)
