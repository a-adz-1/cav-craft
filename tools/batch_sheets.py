#!/usr/bin/env python3
"""Packs the per-street photos 6 streets to an image (3 photos each, small) for quick classification.
    .venv/bin/python tools/batch_sheets.py  -> .downloads/ref/batches/NNN.jpg + index.json"""
import json
import os

from PIL import Image, ImageDraw

S = json.load(open(".downloads/ref/streets/summary.json"))
streets = [k for k, v in sorted(S.items(), key=lambda kv: -kv[1]["buildings"]) if v["photos"]]
os.makedirs(".downloads/ref/batches", exist_ok=True)
index = {}
W, H = 400, 225
for b in range(0, len(streets), 6):
    group = streets[b:b + 6]
    sheet = Image.new("RGB", (W * 3, (H + 18) * len(group)), "white")
    d = ImageDraw.Draw(sheet)
    for r, st in enumerate(group):
        d.text((4, r * (H + 18) + 3), f"{r + 1}. {st} ({S[st]['buildings']})", fill="black")
        for c, fn in enumerate(S[st]["photos"][:3]):
            try:
                im = Image.open(fn).convert("RGB")
                im.thumbnail((W, H))
                sheet.paste(im, (c * W, r * (H + 18) + 18))
            except Exception:
                pass
    name = f"{b // 6:03d}.jpg"
    sheet.save(f".downloads/ref/batches/{name}", quality=78)
    index[name] = group
json.dump(index, open(".downloads/ref/batches/index.json", "w"), indent=1)
print(len(streets), "streets with photos in", len(index), "batches")
