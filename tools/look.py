#!/usr/bin/env python3
"""Reference photos of one building: Mapillary shots looking at it and Commons photos taken near it.

    .venv/bin/python tools/look.py <osm id, e.g. w139149858> [radius m] -> build/look_<id>.jpg
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import survey
from survey import REF, to_bng, xz

oid = sys.argv[1]
rad = float(sys.argv[2]) if len(sys.argv) > 2 else 90
row = next(r for r in csv.DictReader(open("docs/buildings.csv")) if r["osm"] == oid)
bx, bz = float(row["x"]), float(row["z"])
files = []
idx = json.load(open(f"{REF}/mapillary_index.json"))
idx.pop("_done", None)
cand = []
for i, v in idx.items():
    x, z = xz(*to_bng.transform(v["lon"], v["lat"]))
    d = math.hypot(x - bx, z - bz)
    if d < rad and not v["pano"]:
        bearing = (math.degrees(math.atan2(bx - x, -(bz - z))) + 360) % 360
        off = abs(((bearing - (v["dir"] or 0)) + 180) % 360 - 180)
        if off < 30:
            cand.append((d + off, v["t"], i))
cand.sort()
for _, _, i in cand[:6]:
    fn = f"{REF}/mapillary/{i}.jpg"
    if survey.mapillary_thumb(i, fn):
        files.append(fn)
metas = [(f"{REF}/commons/meta.json", ""),
         ("/home/adz/Projects/splitwater/.downloads/ref/caversham/survey/commons/meta.json",
          "/home/adz/Projects/splitwater/.downloads/ref/caversham/survey/commons/")]
for path, base in metas:
    if not os.path.exists(path):
        continue
    for title, m in json.load(open(path)).items():
        if "lat" not in m:
            continue
        x, z = xz(*to_bng.transform(m["lon"], m["lat"]))
        fn = m.get("file", "")
        if base:
            fn = base + os.path.basename(fn)
        if math.hypot(x - bx, z - bz) < rad * 0.8 and os.path.exists(fn):
            files.append(fn)
files = files[:12]
W, H = 480, 320
sheet = Image.new("RGB", (W * 4, H * max(1, (len(files) + 3) // 4) + 24), "white")
ImageDraw.Draw(sheet).text((6, 6), f"{oid} {row['name']} ({row['kind']}, {row['street']}) {len(files)} photos", fill="black")
for k, fn in enumerate(files):
    try:
        im = Image.open(fn).convert("RGB")
        im.thumbnail((W, H))
        sheet.paste(im, ((k % 4) * W, 24 + (k // 4) * H))
    except Exception:
        pass
sheet.save(f"build/look_{oid}.jpg", quality=80)
print(len(files), "photos ->", f"build/look_{oid}.jpg")
