#!/usr/bin/env python3
"""Turns the street surveys into a style for every street (docs/street_styles.json).

docs/street_survey.csv gives a street a style family (from looking at its photos); docs/heights_survey.json
(Caversham Heights) and .downloads/ref/sv/*/result.json (the rest of town, section by section, with the
screenshots kept) give streets their own measured mix (walls, upper floors, mock-Tudor share, roofs, front
boundary), estimated street by street from Street View. Streets nobody looked at take the style of the nearest
surveyed street (by the middle of their houses), so a close inherits the road it comes off.

    .venv/bin/python tools/styles.py
"""
import csv
import glob
import json
import os
import re

import numpy as np

fam = json.load(open("docs/style_families.json"))
survey = {r["street"]: r["family"] for r in csv.DictReader(open("docs/street_survey.csv"))}
rows = list(csv.DictReader(open("docs/buildings.csv")))
centre = {}
for r in rows:
    centre.setdefault(r["street"], []).append((float(r["x"]), float(r["z"])))
centre = {k: np.mean(v, axis=0) for k, v in centre.items()}

ERA = {"victorian_edwardian": ("victorian_villa", "victorian_terrace"), "interwar_1920s_30s": ("interwar_detached", "interwar_semi"),
       "postwar_1950s": ("postwar_council", "postwar_council"), "estate_1960s_70s": ("estate_6070", "estate_6070"),
       "modern_1980s_on": ("modern", "modern")}
COLOURS = {"black": "black_concrete", "navy": "blue_concrete", "blue": "blue_concrete", "green": "green_concrete",
           "red": "red_concrete", "white": "white_concrete", "grey": "gray_concrete", "gray": "gray_concrete",
           "cream": "smooth_sandstone", "yellow": "yellow_concrete", "purple": "purple_concrete",
           "orange": "orange_concrete", "teal": "cyan_concrete", "burgundy": "red_nether_bricks", "brown": "brown_concrete"}
FRONTS = {"hedge": "hedge", "low_brick_wall": "wall", "fence": "wall", "open": None, "none": None}


def mix(shares, slots=12):
    """{'red_brick': 0.5, 'white_render': 0.5} -> a list of 12 names in those shares (the builder picks one).
    Names the builder knows only: 'red_brick (painted below)' counts as red_brick, anything else is dropped."""
    from houses import ROOFS, WALLS
    known = set(WALLS) | set(ROOFS)
    clean = {}
    for name, v in shares.items():
        name = re.split(r"[^a-z_]", name.strip().lower())[0]
        if name in known and isinstance(v, (int, float)):
            clean[name] = clean.get(name, 0) + v
    shares = clean
    tot = sum(shares.values()) or 1
    out = []
    for name, v in sorted(shares.items(), key=lambda kv: -kv[1]):
        out += [name] * max(1, round(slots * v / tot)) if v / tot >= 0.04 else []
    return out


def measured(street, v):
    """A style from one street's Street View survey."""
    form = v.get("form", {})
    joined = form.get("semi", 0) + form.get("terrace", 0) > form.get("detached", 0)
    if v.get("era") in ERA:
        family = ERA[v["era"]][1 if joined else 0]
        if family == "victorian_terrace" and form.get("terrace", 0) < 0.4:
            family = "victorian_villa"
    else:
        family = survey.get(street, "interwar_detached")
    shares = [int(n) for n in re.findall(r"(\d+)\s*%", v.get("shops", ""))]
    if survey.get(street) == "town" or (shares and max(shares) >= 40):
        family = "town"                         # shopfronts on the main-road ground floors
    st = dict(fam[family], family=family, walls=mix(v["walls"]), roof=mix(v["roof"]), tudor=round(v.get("tudor", 0), 2),
              note=v.get("note", ""), source="street view")
    st.pop("upper", None), st.pop("upper_p", None)
    upper = mix({v["upper"]: 1}) if isinstance(v.get("upper"), str) else []
    if v.get("upper_differs", 0) >= 0.05 and upper:
        st["upper"], st["upper_p"] = upper[:1], round(v["upper_differs"], 2)
    if v.get("front") in FRONTS:
        st["front"] = FRONTS[v["front"]]
    words = re.findall(r"[a-z]+", v.get("shops", "").lower())
    fascias = [COLOURS[w] for w in words if w in COLOURS]
    if len(fascias) >= 2:
        st["fascias"] = fascias
    return st


base = {s: dict(fam[f], family=f) for s, f in survey.items()}
measured_all = {}
for path in ["docs/heights_survey.json"] + sorted(glob.glob(".downloads/ref/sv/*/result.json")):
    if os.path.exists(path):
        measured_all.update(json.load(open(path)))
for s, v in measured_all.items():
    if mix(v.get("walls") or {}) and mix(v.get("roof") or {}) and v.get("confidence") in ("high", "medium", "low"):
        base[s] = measured(s, v)
known = [s for s in base if s in centre]
K = np.array([centre[s] for s in known])
out, inherited = {}, 0
for st, c in centre.items():
    if st in base:
        out[st] = base[st]
    else:
        out[st] = base[known[int(np.argmin(((K - c) ** 2).sum(1)))]]
        inherited += 1
json.dump(out, open("docs/street_styles.json", "w"), indent=1)
print(f"{len(out)} streets: {len(out) - inherited} surveyed ({sum(1 for s in out.values() if s.get('source'))} measured "
      f"on Street View), {inherited} from their nearest surveyed neighbour")
assert mix({"red_brick": 0.5, "slate (old)": 0.5}).count("slate") == 6 and mix({"stucco": 1}) == []
