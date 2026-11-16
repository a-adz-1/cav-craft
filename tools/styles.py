#!/usr/bin/env python3
"""Turns the street survey (docs/street_survey.csv: street -> style family, from looking at its photos) into a
style for every street (docs/street_styles.json). Streets nobody photographed take the family of the nearest
surveyed street (by the middle of their houses), so a close inherits the estate it sits in.

    .venv/bin/python tools/styles.py
"""
import csv
import json

import numpy as np

fam = json.load(open("docs/style_families.json"))
survey = {r["street"]: r["family"] for r in csv.DictReader(open("docs/street_survey.csv"))}
rows = list(csv.DictReader(open("docs/buildings.csv")))
centre = {}
for r in rows:
    centre.setdefault(r["street"], []).append((float(r["x"]), float(r["z"])))
centre = {k: np.mean(v, axis=0) for k, v in centre.items()}
known = [s for s in survey if s in centre]
K = np.array([centre[s] for s in known])
out, inherited = {}, 0
for st, c in centre.items():
    if st in survey:
        f = survey[st]
    else:
        f = survey[known[int(np.argmin(((K - c) ** 2).sum(1)))]]
        inherited += 1
    out[st] = dict(fam[f], family=f)
json.dump(out, open("docs/street_styles.json", "w"), indent=1)
print(f"{len(out)} streets: {len(out) - inherited} surveyed, {inherited} from their nearest surveyed neighbour")
