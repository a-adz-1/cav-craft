#!/usr/bin/env python3
"""Turns the street surveys into a style for every street (docs/street_styles.json).

docs/street_survey.csv gives a street a style family (from looking at its photos); docs/heights_survey.json
gives Caversham Heights streets their own measured mix (walls, upper floors, mock-Tudor share, roofs, front
boundary), estimated street by street from Street View. Streets nobody looked at take the style of the nearest
surveyed street (by the middle of their houses), so a close inherits the road it comes off.

    .venv/bin/python tools/styles.py
"""
import csv
import json
import os

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
FRONTS = {"hedge": "hedge", "low_brick_wall": "wall", "fence": "wall", "open": None}


def mix(shares, slots=12):
    """{'red_brick': 0.5, 'white_render': 0.5} -> a list of 12 names in those shares (the builder picks one)."""
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
    st = dict(fam[family], family=family, walls=mix(v["walls"]), roof=mix(v["roof"]), tudor=round(v.get("tudor", 0), 2),
              note=v.get("note", ""), source="street view")
    st.pop("upper", None), st.pop("upper_p", None)
    if v.get("upper_differs", 0) >= 0.05 and v.get("upper"):
        st["upper"], st["upper_p"] = [v["upper"]], round(v["upper_differs"], 2)
    if v.get("front") in FRONTS:
        st["front"] = FRONTS[v["front"]]
    return st


base = {s: dict(fam[f], family=f) for s, f in survey.items()}
path = "docs/heights_survey.json"
heights = json.load(open(path)) if os.path.exists(path) else {}
for s, v in heights.items():
    if v.get("walls") and v.get("roof") and v.get("confidence") in ("high", "medium", "low"):
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
assert mix({"a": 0.5, "b": 0.5}).count("a") == 6
