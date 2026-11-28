#!/usr/bin/env python3
"""Real house numbers and names by postcode, from open data, for the houses OSM has no address for.

HM Land Registry Price Paid Data (every sale since 1995: number or name, street, postcode; Open Government
Licence) and each postcode's centre from postcodes.io (ONS data). A postcode is about 15 neighbouring houses,
usually one side of one stretch of a street, so this says which numbers and names exist where to within a few
doors, though not which exact house is which.

    .venv/bin/python tools/addresses.py  -> build/addresses.json
    {STREET: {postcode: {"e": easting, "n": northing, "nums": [12, 14, ...], "names": ["Rose Cottage", ...]}}}

Also which postcode each house is in, exactly: OS Open UPRN (the position of every address in Britain) joined to
the ONS UPRN Directory (each address's postcode), both Open Government Licence, cut to our box.

    .venv/bin/python tools/addresses.py points  -> build/address_points.json  [[easting, northing, postcode], ...]
    (needs .downloads/uprn/osopenuprn.zip from api.os.uk/downloads/v1/products/OpenUPRN and
     .downloads/uprn/onsud.zip, the ONS UPRN Directory, from geoportal.statistics.gov.uk: about 1.8 GB)
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


def points():
    import io
    import zipfile
    from box import E0, E1, N0, N1
    where = {}
    z = zipfile.ZipFile(".downloads/uprn/osopenuprn.zip")
    with z.open(next(n for n in z.namelist() if n.lower().endswith(".csv"))) as f:
        r = csv.reader(io.TextIOWrapper(f, "utf-8-sig"))
        next(r)
        for row in r:                               # UPRN, X_COORDINATE, Y_COORDINATE, ...
            e, n = float(row[1]), float(row[2])
            if E0 <= e <= E1 and N0 <= n <= N1:
                where[row[0]] = (e, n)
    out = []
    z = zipfile.ZipFile(".downloads/uprn/onsud.zip")
    with z.open(next(n for n in z.namelist() if n.endswith("_SE.csv"))) as f:     # the South East file
        r = csv.reader(io.TextIOWrapper(f, "utf-8-sig"))
        h = [c.upper() for c in next(r)]
        iu, ip = h.index("UPRN"), h.index("PCDS")
        for row in r:
            if row[iu] in where:
                out.append([*where[row[iu]], row[ip]])
    json.dump(out, open("build/address_points.json", "w"))
    print(len(out), "address points with a postcode")


if __name__ == "__main__":
    import sys
    points() if sys.argv[1:] == ["points"] else main()
