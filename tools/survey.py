#!/usr/bin/env python3
"""Building-by-building survey of Cavcraft, the way Splitwater surveyed Henley (splitwater docs/HENLEY_SURVEY.md),
but for every building in Caversham.

    .venv/bin/python tools/survey.py catalogue     # docs/buildings.csv: every building, its street, kind, size
    .venv/bin/python tools/survey.py mapillary     # index every Mapillary street photo in the area
    .venv/bin/python tools/survey.py commons       # Wikimedia Commons photos in the area (+ splitwater's)
    .venv/bin/python tools/survey.py sheets        # per street: the photos that look at its houses

Photos are reference only (shapes, materials, colours), kept in .downloads/ref (gitignored), never copied into
the world. The Mapillary token is splitwater's (~/.config/splitwater/mapillary_token; never committed).
"""
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
from pyproj import Transformer

from box import E0, N1

REF = ".downloads/ref"
UA = {"User-Agent": "cavcraft-survey/1.0 (a-adz-1@proton.me)"}
TOKEN = os.path.expanduser("~/.config/splitwater/mapillary_token")
to_ll = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
BOX_LL = (-1.012, 51.458, -0.925, 51.497)   # lon/lat round the world mask


def get(url, headers=None, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            print("  retry", k, str(e)[:80])
            time.sleep(2 ** k)
    return None


def xz(e, n):
    return e - E0, N1 - n


# ---------------------------------------------------------------- catalogue

def catalogue():
    osm = json.load(open("build/osm.json"))
    L = np.load("build/layers.npz")
    mask = L["mask"]
    streets = [l for l in osm["lines"] if l["tags"].get("highway") and l["tags"].get("name")]
    seg = []   # (x0, z0, x1, z1, name) for nearest-street lookup
    for s in streets:
        p = [xz(*q) for q in s["pts"]]
        seg += [(a[0], a[1], b[0], b[1], s["tags"]["name"]) for a, b in zip(p[:-1], p[1:])]
    S = np.array([s[:4] for s in seg])
    names = [s[4] for s in seg]
    seen, rows = set(), []
    for a in osm["areas"] + [{"id": l["id"], "tags": l["tags"], "rings": [l["pts"]]} for l in osm["lines"]
                             if l["tags"].get("building") and l["pts"][0] == l["pts"][-1]]:
        t = a["tags"]
        if not t.get("building") or t["building"] == "no" or a["id"] in seen:
            continue
        ring = np.array([xz(*q) for q in a["rings"][0]])
        cx, cz = ring.mean(axis=0)
        if not (0 <= cz < mask.shape[0] and 0 <= cx < mask.shape[1]) or not mask[int(cz), int(cx)]:
            continue
        seen.add(a["id"])
        area = 0.5 * abs(np.dot(ring[:-1, 0], ring[1:, 1]) - np.dot(ring[1:, 0], ring[:-1, 1]))
        street = t.get("addr:street")
        # nearest named street (distance to segment)
        d = S[:, 2:] - S[:, :2]
        tt = np.clip(((cx - S[:, 0]) * d[:, 0] + (cz - S[:, 1]) * d[:, 1]) / np.maximum((d ** 2).sum(1), 1e-9), 0, 1)
        dist = np.hypot(S[:, 0] + tt * d[:, 0] - cx, S[:, 1] + tt * d[:, 1] - cz)
        i = int(np.argmin(dist))
        lon, lat = to_ll.transform(cx + E0, N1 - cz)
        rows.append({"osm": a["id"], "x": round(cx), "z": round(cz), "lat": round(lat, 6), "lon": round(lon, 6),
                     "street": street or names[i], "street_dist": round(float(dist[i])),
                     "kind": t["building"], "footprint_m2": round(area), "levels": t.get("building:levels", ""),
                     "name": t.get("name", ""), "number": t.get("addr:housenumber", ""),
                     "amenity": t.get("amenity", "") or t.get("shop", "") or t.get("religion", "")})
    os.makedirs("docs", exist_ok=True)
    with open("docs/buildings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(r["street"] for r in rows)
    print(len(rows), "buildings on", len(c), "streets; biggest:", c.most_common(8))


# ---------------------------------------------------------------- Mapillary index

def mapillary():
    tok = open(TOKEN).read().strip()
    out = f"{REF}/mapillary_index.json"
    idx = json.load(open(out)) if os.path.exists(out) else {}
    w, s, e, n = BOX_LL
    step = 0.004
    for lat in np.arange(s, n, step):
        for lon in np.arange(w, e, step):
            key = f"{lon:.4f},{lat:.4f}"
            if key in idx.get("_done", []):
                continue
            url = ("https://graph.mapillary.com/images?fields=id,captured_at,compass_angle,computed_compass_angle,"
                   "geometry,computed_geometry,is_pano,creator&limit=2000&bbox="
                   f"{lon:.5f},{lat:.5f},{lon + step:.5f},{lat + step:.5f}")
            data = get(url, {"Authorization": f"OAuth {tok}"})
            if data is None:
                continue
            for im in json.loads(data).get("data", []):
                g = (im.get("computed_geometry") or im["geometry"])["coordinates"]
                idx[im["id"]] = {"lon": g[0], "lat": g[1], "t": im["captured_at"],
                                 "dir": im.get("computed_compass_angle", im.get("compass_angle")),
                                 "pano": im.get("is_pano", False)}
            idx.setdefault("_done", []).append(key)
        json.dump(idx, open(out, "w"))
        print(f"lat {lat:.3f}: {len(idx) - 1} images")
    print(len(idx) - 1, "Mapillary images indexed")


def mapillary_thumb(image_id, path):
    if os.path.exists(path):
        return True
    tok = open(TOKEN).read().strip()
    data = get(f"https://graph.mapillary.com/{image_id}?fields=thumb_1024_url", {"Authorization": f"OAuth {tok}"})
    if not data:
        return False
    url = json.loads(data).get("thumb_1024_url")
    img = get(url) if url else None
    if img:
        open(path, "wb").write(img)
    return bool(img)


# ---------------------------------------------------------------- Commons

def commons():
    os.makedirs(f"{REF}/commons", exist_ok=True)
    meta_path = f"{REF}/commons/meta.json"
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    w, s, e, n = BOX_LL
    for lat in np.arange(s, n, 0.006):
        for lon in np.arange(w, e, 0.009):
            q = urllib.parse.urlencode({"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}",
                                        "gsradius": 500, "gslimit": 500, "gsnamespace": 6, "format": "json"})
            data = get("https://commons.wikimedia.org/w/api.php?" + q)
            for g in (json.loads(data).get("query", {}).get("geosearch", []) if data else []):
                meta.setdefault(g["title"], {"lat": g["lat"], "lon": g["lon"]})
            time.sleep(0.5)
    titles = [t for t in meta if "file" not in meta[t]]
    for k in range(0, len(titles), 40):
        q = urllib.parse.urlencode({"action": "query", "titles": "|".join(titles[k:k + 40]), "prop": "imageinfo",
                                    "iiprop": "url", "iiurlwidth": 800, "format": "json"})
        data = get("https://commons.wikimedia.org/w/api.php?" + q)
        for p in (json.loads(data).get("query", {}).get("pages", {}).values() if data else []):
            ii = p.get("imageinfo")
            if ii and p["title"] in meta:
                meta[p["title"]]["thumb"] = ii[0].get("thumburl") or ii[0]["url"]
        time.sleep(0.5)
    for i, (title, m) in enumerate(meta.items()):
        if "thumb" not in m or not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        fn = f"{REF}/commons/{abs(hash(title)) % 10**10}.jpg" if "file" not in m else m["file"]
        m["file"] = fn
        if not os.path.exists(fn):
            img = get(m["thumb"])
            if img:
                open(fn, "wb").write(img)
            time.sleep(0.3)
    json.dump(meta, open(meta_path, "w"), indent=1)
    print(len(meta), "Commons photos")


# ---------------------------------------------------------------- per-street contact sheets

def sheets(only=None):
    from PIL import Image, ImageDraw
    rows = list(csv.DictReader(open("docs/buildings.csv")))
    idx = json.load(open(f"{REF}/mapillary_index.json"))
    idx.pop("_done", None)
    ids = list(idx)
    P = np.array([xz(*to_bng.transform(idx[i]["lon"], idx[i]["lat"])) for i in ids])
    D = np.array([idx[i]["dir"] or 0 for i in ids], float)
    T = np.array([idx[i]["t"] for i in ids], float)
    pano = np.array([idx[i]["pano"] for i in ids])
    by_street = {}
    for r in rows:
        if int(r["street_dist"]) <= 60:
            by_street.setdefault(r["street"], []).append(r)
    os.makedirs(f"{REF}/streets", exist_ok=True)
    os.makedirs(f"{REF}/mapillary", exist_ok=True)
    summary = {}
    for street, rs in sorted(by_street.items(), key=lambda kv: -len(kv[1])):
        if only and street not in only:
            continue
        houses = np.array([[float(r["x"]), float(r["z"])] for r in rs])
        # photos within 40 m of a house on this street, looking at it (house within 35 deg of view direction)
        picks = []
        order = np.argsort(-T)   # newest first
        for hi in np.linspace(0, len(rs) - 1, min(len(rs), 12)).astype(int):
            hx, hz = houses[hi]
            d = np.hypot(P[:, 0] - hx, P[:, 1] - hz)
            bearing = (np.degrees(np.arctan2(hx - P[:, 0], -(hz - P[:, 1]))) + 360) % 360   # 0 = north
            off = np.abs((bearing - D + 180) % 360 - 180)
            ok = (d > 6) & (d < 40) & (off < 35) & ~pano
            cand = [i for i in order if ok[i]]
            if cand and cand[0] not in picks:
                picks.append(cand[0])
            if len(picks) >= 6:
                break
        files = []
        for i in picks:
            fn = f"{REF}/mapillary/{ids[i]}.jpg"
            if mapillary_thumb(ids[i], fn):
                files.append(fn)
        summary[street] = {"buildings": len(rs), "photos": files}
        if files:
            W, Hh = 640, 360
            sheet = Image.new("RGB", (W * 3, Hh * ((len(files) + 2) // 3) + 30), "white")
            dr = ImageDraw.Draw(sheet)
            dr.text((8, 8), f"{street}: {len(rs)} buildings", fill="black")
            for k, fn in enumerate(files):
                try:
                    im = Image.open(fn).convert("RGB")
                    im.thumbnail((W, Hh))
                    sheet.paste(im, ((k % 3) * W, 30 + (k // 3) * Hh))
                except Exception:
                    pass
            sheet.save(f"{REF}/streets/{street.replace('/', '-')}.jpg", quality=80)
        print(f"{street}: {len(rs)} buildings, {len(files)} photos")
    json.dump(summary, open(f"{REF}/streets/summary.json", "w"), indent=1)


if __name__ == "__main__":
    {"catalogue": catalogue, "mapillary": mapillary, "commons": commons,
     "sheets": lambda: sheets(sys.argv[2:] or None)}[sys.argv[1]]()
