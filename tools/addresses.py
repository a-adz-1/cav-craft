#!/usr/bin/env python3
"""Real house numbers and names by postcode, from open data, for the houses OSM has no address for.

HM Land Registry Price Paid Data (every sale since 1995: number or name, street, postcode; Open Government
Licence) and each postcode's centre from postcodes.io (ONS data). A postcode is about 15 neighbouring houses,
usually one side of one stretch of a street, so this says which numbers and names exist where to within a few
doors, though not which exact house is which.

    .venv/bin/python tools/addresses.py  -> build/addresses.json
    {STREET: {postcode: {"e": easting, "n": northing, "nums": [12, 14, ...], "names": ["Rose Cottage", ...]}}}
"""
import csv
import json
import os
import re
import urllib.request

RAW = ".downloads/ppd"
URL = "https://landregistry.data.gov.uk/app/ppd/ppd_data.csv?header=true&limit=all&postcode=%s&min_date=1+January+1995"


def fetch():
    os.makedirs(RAW, exist_ok=True)
    for area in ("RG4", "RG1"):
        path = f"{RAW}/{area.lower()}.csv"
        if not os.path.exists(path):
            urllib.request.urlretrieve(URL % area, path)
        yield from csv.DictReader(open(path, encoding="utf-8", errors="replace"))


def centres(postcodes):
    path = f"{RAW}/centres.json"
    got = json.load(open(path)) if os.path.exists(path) else {}
    todo = sorted(set(postcodes) - set(got))
    for k in range(0, len(todo), 100):
        req = urllib.request.Request("https://api.postcodes.io/postcodes", json.dumps({"postcodes": todo[k:k + 100]}).encode(),
                                     {"Content-Type": "application/json"})
        for r in json.load(urllib.request.urlopen(req, timeout=60))["result"]:
            v = r["result"]
            got[r["query"]] = [v["eastings"], v["northings"]] if v and v.get("eastings") else None
        json.dump(got, open(path, "w"))
    return got


def parse(paon):
    """'12' -> (12, None); '12A' -> (12, None); 'ROSE COTTAGE, 12' -> (12, None); 'ROSE COTTAGE' -> (None, name);
    ranges and flats ('12 - 14', 'FLAT 3') -> the first number or nothing."""
    m = re.search(r"(?:^|, )(\d+)[A-Z]?(?: - \d+[A-Z]?)?$", paon)
    if m:
        return int(m.group(1)), None
    if re.search(r"\d|^(FLAT|UNIT|APARTMENT|LAND|GARAGE|PLOT)\b", paon) or not paon:
        return None, None
    return None, paon.title()


def main():
    out = {}
    for r in fetch():
        if not r["street"] or r["property_type"] == "O":       # "other": shops, garages, land
            continue
        num, name = parse(r["paon"].strip())
        if r["saon"]:
            name = None                                         # a flat in a named block, not a house name
        d = out.setdefault(r["street"], {}).setdefault(r["postcode"], {"nums": set(), "names": set()})
        if num:
            d["nums"].add(num)
        if name:
            d["names"].add(name)
    cen = centres([pc for st in out.values() for pc in st])
    res = {}
    for street, pcs in out.items():
        for pc, d in pcs.items():
            if cen.get(pc) and (d["nums"] or d["names"]):
                res.setdefault(street, {})[pc] = {"e": cen[pc][0], "n": cen[pc][1], "nums": sorted(d["nums"]),
                                                  "names": sorted(d["names"])}
    json.dump(res, open("build/addresses.json", "w"))
    print(len(res), "streets,", sum(len(v) for v in res.values()), "postcodes,",
          sum(len(d["nums"]) for v in res.values() for d in v.values()), "numbers,",
          sum(len(d["names"]) for v in res.values() for d in v.values()), "house names")
    assert parse("ROSE COTTAGE, 12") == (12, None) and parse("12A") == (12, None) and parse("THE FIRS") == (None, "The Firs")
    assert parse("FLAT 3") == (None, None) and parse("12 - 14") == (12, None)


if __name__ == "__main__":
    main()
