#!/usr/bin/env python3
"""Turns OSM + LiDAR into per-metre layers for the world builder.

    .venv/bin/python tools/layers.py build/osm.json build/lidar.npz build/layers.npz

Layers (rows north to south, cols west to east, same grid as lidar.npz):
  mask     1 inside Cavcraft (Caversham + the Thames along it + a strip of the south bank
           + Caversham Lakes), 0 outside
  surface  block class per column, see SURFACE below
  ground   ground height, whole metres AOD (top solid block's y)
  water    water surface y where there is water (top water block), else -999
  building building index into build/buildings.json, 0 = none
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from box import E0, N0, E1, N1
from grade import road_grade
import roads

from surfaces import SURFACE
S = {n: i for i, n in enumerate(SURFACE)}
W, H = E1 - E0, N1 - N0
CAVERSHAM_NODE = "n718511450"
THAMES_AREA = "r106675"

osm = json.load(open(sys.argv[1]))
lidar = np.load(sys.argv[2])
out = sys.argv[3]
dtm = lidar["dtm"]


def px(ring):
    return [(e - E0, N1 - n) for e, n in ring]


def raster(areas, value=1, img=None, mode="L"):
    img = img or Image.new(mode, (W, H), 0)
    d = ImageDraw.Draw(img)
    for a in areas:
        d.polygon(px(a["rings"][0]), fill=value)
        for inner in a["rings"][1:]:
            d.polygon(px(inner), fill=0)
    return img


def arr(img):
    return np.asarray(img).astype(bool)


def rc(pt):
    return int(N1 - pt[1]), int(pt[0] - E0)


areas = osm["areas"]
by_id = {a["id"]: a for a in areas}
nodes = {n["id"]: n for n in osm["nodes"]}

# ---- world mask -------------------------------------------------------------------------
reading = arr(raster([a for a in areas if a["tags"].get("admin_level") == "6" and a["tags"].get("name") == "Reading"]))
water_areas = [a for a in areas if a["tags"].get("natural") == "water" or a["tags"].get("waterway") == "riverbank"]
water_all = arr(raster(water_areas))
lock = by_id["w369412651"]
thames = arr(raster([by_id[THAMES_AREA], lock]))   # the Thames itself, not the Kennet or lakes it touches

# a barrier of the Thames (every channel, drawn fat so the weir and lock can't leak) and Henley Road
bar = Image.new("L", (W, H), 0)
bd = ImageDraw.Draw(bar)
for ln in osm["lines"]:
    t = ln["tags"]
    if (t.get("name") == "River Thames" and t.get("waterway") == "river") or (
            t.get("name") == "Henley Road" and t.get("highway") == "primary"):
        bd.line(px(ln["pts"]), fill=1, width=5)
barrier = arr(bar) | thames
lab, _ = ndimage.label(~barrier)

land = reading & ~barrier
llab, _ = ndimage.label(land)
cav = llab == llab[rc(nodes[CAVERSHAM_NODE]["pt"])]
cav = ndimage.binary_opening(cav, iterations=15)          # drop the borough's thin strip along the river west
llab, _ = ndimage.label(cav)
cav = llab == np.bincount(llab.ravel()[llab.ravel() > 0]).argmax()
cav[:, :np.argmax(cav.sum(axis=0) > 300)] = False             # the red line's west end, at Mapledurham Playing Fields

# Caversham Lakes: east of the borough, south of Henley Road, north of the Thames, near a lake
lakes_side = lab == lab[rc((473205, 174879))]
lakes = water_all & lakes_side & ~reading
lakes[:, :472700 - E0] = False                           # only the lakes east of Caversham
lake_zone = lakes_side & ~reading & ndimage.binary_dilation(lakes, iterations=60)
lake_zone = ndimage.binary_closing(lake_zone, iterations=20) & lakes_side
lake_zone[:N1 - 175400] = False                           # stop short of the lakes further up the river

north = cav | lake_zone
cols = np.nonzero(north.any(axis=0))[0]
river = thames.copy()
river[:, :cols.min()] = False
river[:, cols.max() + 1:] = False
mask = north | river | (barrier & ~thames & ndimage.binary_dilation(north, iterations=6))
mask = ndimage.binary_fill_holes(mask)                       # islands in the river
mask |= ndimage.binary_dilation(river, iterations=30) & ~north  # south bank strip so bridges land
# the people whose data built this world: Thames Water's Clearwater Court and the Environment Agency's Kings
# Meadow House, with King's Meadow Road from the lock to both (Minecraft x 3690-3945, z 4150-4312)
mask[4150:4313, 3690:3946] = True
mask &= np.isfinite(dtm)
lab, n = ndimage.label(mask)
mask = lab == np.bincount(lab.ravel()[lab.ravel() > 0]).argmax()
print("mask cells:", int(mask.sum()), "bbox rows", np.nonzero(mask.any(1))[0][[0, -1]], "cols", cols[[0, -1]])

# ---- surface ----------------------------------------------------------------------------
surf = Image.new("L", (W, H), S["grass"])
d = ImageDraw.Draw(surf)
LANDUSE = {
    ("landuse", "farmland"): "farmland", ("landuse", "allotments"): "allotment",
    ("landuse", "forest"): "woodland", ("natural", "wood"): "woodland", ("natural", "scrub"): "scrub",
    ("natural", "heath"): "scrub", ("landuse", "cemetery"): "cemetery", ("amenity", "grave_yard"): "cemetery",
    ("landuse", "railway"): "railway", ("natural", "bare_rock"): "rock", ("natural", "wetland"): "wetland",
    ("landuse", "commercial"): "paved", ("landuse", "retail"): "paved", ("landuse", "industrial"): "paved",
    ("leisure", "pitch"): "sports", ("leisure", "track"): "sports",
    ("natural", "sand"): "sand", ("natural", "beach"): "sand", ("leisure", "beach_resort"): "sand",
    ("amenity", "parking"): "parking", ("area:highway", None): "paved", ("highway", "pedestrian"): "paved",
    ("place", "square"): "paved",
}
order = ["woodland", "scrub", "wetland", "farmland", "allotment", "cemetery", "railway", "rock", "paved",
         "sports", "sand", "parking"]
groups = {k: [] for k in order}
for a in areas:
    t = a["tags"]
    if t.get("building") or t.get("boundary"):
        continue
    for (k, v), cls in LANDUSE.items():
        if k in t and (v is None or t[k] == v):
            if cls == "sports" and t.get("sport") == "tennis":
                cls = "sports"
            groups[cls].append(a)
            break
for cls in order:
    raster(groups[cls], S[cls], surf)
for a in groups["sports"]:
    if a["tags"].get("sport") == "tennis" or a["tags"].get("surface") in ("asphalt", "tartan", "acrylic"):
        raster([a], S["tennis"], surf)

ROAD_WIDTH = {"motorway": 12, "trunk": 10, "primary": 9, "secondary": 8, "tertiary": 7,
              "unclassified": 6, "residential": 6, "living_street": 5, "service": 4,
              "motorway_link": 6, "trunk_link": 6, "primary_link": 6, "secondary_link": 6, "tertiary_link": 6}
SCHOOL_ROADS = roads.SCHOOL_ROADS
PATH_WIDTH = {"footway": 2, "cycleway": 2, "path": 2, "bridleway": 2, "steps": 2, "track": 3, "pedestrian": 4}


def has_sidewalk(t, side):
    """Whether OSM gives this side of the road a pavement of its own (unknown: yes)."""
    v = t.get("sidewalk:" + side) or t.get("sidewalk:both")
    if v is None:
        v = {"both": "yes", "left": "yes" if side == "left" else "no",
             "right": "yes" if side == "right" else "no"}.get(t.get("sidewalk"), t.get("sidewalk", "yes"))
    return v == "yes"


nopave = Image.new("L", (W, H), 0)
nd_ = ImageDraw.Draw(nopave)
bridges = []
strokes = []                                      # (rank, points in cells, width, class): painted low rank first
RANK = {"path": 0, "track": 0, "footway": 1, "railway": 2, "minor_road": 3, "road": 4}
for ln in osm["lines"]:
    t = ln["tags"]
    hw = t.get("highway")
    if t.get("bridge") and t.get("bridge") != "no" and (hw or t.get("railway")):
        bridges.append(ln)
        continue
    if t.get("tunnel") in ("yes", "culvert") or t.get("layer", "0").startswith("-"):
        continue
    if hw in ROAD_WIDTH:
        cls, w = ("road" if hw not in ("service", "living_street") else "minor_road"), ROAD_WIDTH[hw]
    elif hw in PATH_WIDTH:
        w = PATH_WIDTH[hw]
        if hw == "track":
            cls = "track"
        elif t.get("surface") in ("asphalt", "paved", "paving_stones", "concrete", "sett") or (
                hw in ("footway", "pedestrian", "cycleway") and t.get("surface") is None):
            cls = "footway"   # town footways are paved unless OSM says otherwise; untagged paths stay earth
        else:
            cls = "path"
    elif t.get("railway") in ("rail", "light_rail"):
        cls, w = "railway", 4
    else:
        continue
    if ln["id"] in SCHOOL_ROADS:
        cls, w = "road", SCHOOL_ROADS[ln["id"]]
    if ln["id"] in roads.HEIGHTS_SKIP:
        continue
    q = np.array(ln["pts"], float) if t.get("service") == "parking_aisle" else roads.smooth(ln["pts"])   # bends rounded
    strokes.append((RANK[cls], np.array(px(q)), w, cls))
    if cls == "road":
        for side, sgn in (("left", 1), ("right", -1)):
            if not has_sidewalk(t, side):
                for a, b in zip(q[:-1], q[1:]):
                    tv = (b - a) / max(np.hypot(*(b - a)), 1e-6)
                    off = np.array([-tv[1], tv[0]]) * sgn * (w / 2 + 1.5)
                    nd_.line(px([a + off, b + off]), fill=1, width=3)
surface = np.asarray(surf).copy()
for _, q, w, cls in sorted(strokes, key=lambda v: v[0]):     # a footpath never paints across a road
    roads.paint(surface, q, w, S[cls])
# turning circles at the ends of closes (a round head 15 across; a loop has a grass island in the middle)
for nd in osm["nodes"]:
    kind = nd["tags"].get("highway")
    if kind in ("turning_circle", "turning_loop"):
        c = np.array(px([nd["pt"]])[0])
        r_, c_ = rc(nd["pt"])
        if not (0 <= r_ < H and 0 <= c_ < W) or surface[r_, c_] not in (S["road"], S["minor_road"]):
            continue                                # (only where the road itself was drawn: not on a bridge)
        cls = surface[r_, c_]
        roads.paint(surface, [c, c + (0.01, 0)], 15 if kind == "turning_circle" else 20, cls)
        if kind == "turning_loop":
            roads.paint(surface, [c, c + (0.01, 0)], 6, S["grass"])
# The Heights Primary School forecourt (roads.HEIGHTS_SITE)
for bx0, bx1, bz0, bz1 in roads.HEIGHTS_CLEAR:
    box_ = surface[bz0:bz1 + 1, bx0:bx1 + 1]
    box_[np.isin(box_, (S["parking"], S["minor_road"], S["footway"], S["path"], S["tennis"], S["sports"]))] = S["grass"]
site = np.zeros((H, W), bool)
for cls, sx0, sx1, sz0, sz1 in roads.HEIGHTS_SITE:
    surface[sz0:sz1 + 1, sx0:sx1 + 1] = S[cls]
    site[sz0:sz1 + 1, sx0:sx1 + 1] = True
# pavements: 2 m either side of streets, over grass/verge only (OSM rarely maps them as separate ways), except
# where OSM says that side has none or has its own mapped footway
pave = ndimage.binary_dilation(surface == S["road"], iterations=2) & (surface == S["grass"]) & \
    ~np.asarray(nopave).astype(bool)
surface[pave] = S["footway"]

# ---- water levels -----------------------------------------------------------------------
water = water_all & mask
level = np.full((H, W), -999, np.int16)
lab, n = ndimage.label(water)
lock_poly = arr(raster([lock]))
# cut the water at the weirs and lock gates; the Thames piece holding the west end is the upper reach
cut = Image.new("L", (W, H), 0)
cd = ImageDraw.Draw(cut)
for ln in osm["lines"]:
    if ln["tags"].get("waterway") in ("weir", "lock_gate", "dam"):
        cd.line(px(ln["pts"]), fill=1, width=3)
for nd in osm["nodes"]:
    if nd["tags"].get("waterway") == "lock_gate":
        x, y = px([nd["pt"]])[0]
        cd.ellipse([x - 5, y - 5, x + 5, y + 5], fill=1)
cuts = arr(cut)
# OSM's Caversham Weir stops at an island; carry it straight on to the north bank so the side channel
# past the islands is cut too (otherwise the upper reach leaks round it)
weir = next(l for l in osm["lines"] if l["tags"].get("name") == "Caversham Weir")
(wr, wc) = min((rc(p) for p in weir["pts"]), key=lambda t: t[0])
r = wr - 1
while r > 0 and not water[r, wc]:
    r -= 1
while r > 0 and water[r, wc]:
    cuts[r, wc - 1:wc + 2] = True
    r -= 1
lab, n = ndimage.label(water & ~cuts & ~lock_poly)
west = np.nonzero((lab > 0) & thames)
up_label = lab[west[0][np.argmin(west[1])], west[1].min()]
reach = {}
for i in range(1, n + 1):
    body = lab == i
    if body.sum() < 4:
        continue
    reach[i] = float(np.nanmedian(dtm[body]))
up_level = reach[up_label]
down_labels = [i for i in reach if i != up_label and (lab == i)[thames].any()]
down_level = float(np.median([reach[i] for i in down_labels]))
print(f"Thames above Caversham weir {up_level:.2f} m, below {down_level:.2f} m")
UP = int(np.floor(up_level))
DOWN = UP - max(1, int(round(up_level - down_level)))
for i in reach:
    if i == up_label:
        level[lab == i] = UP
    elif i in down_labels:
        level[lab == i] = DOWN
    else:
        level[lab == i] = int(np.floor(np.nanpercentile(dtm[lab == i], 20)))
# the cut lines themselves: take the higher neighbouring level (weir crest / gate), lock chamber starts full
gap = water & (level == -999)
level[gap & lock_poly] = UP
grown = ndimage.grey_dilation(level, size=5)
level[gap & ~lock_poly] = grown[gap & ~lock_poly]
G_LEVELS = {"up": UP, "down": DOWN}
surface[water] = S["water"]

ground_f = np.where(np.isfinite(dtm), dtm, 0).astype(np.float32)
# roads: level across their width (each cell takes the mean height of the road within 4 m), so a road on a
# hillside steps up along its length only, not side to side
road_cells = np.isin(surface, (S["road"], S["minor_road"], S["footway"])) | site
rw = road_cells.astype(np.float32)
num = ndimage.gaussian_filter(ground_f * rw, 4)    # (and smooth along it: each one-block step is one clean line
den = ndimage.gaussian_filter(rw, 4)               # across the road, with no dips and bumps from LiDAR noise)
ground_f = np.where(road_cells & (den > 1e-3), num / np.maximum(den, 1e-6), ground_f)
# no road steeper than half a block per metre (real roads are far gentler; LiDAR noise and embankment edges
# aren't): the midpoint of the highest and lowest surfaces that meet that limit everywhere along the roads,
# so every climb comes out as slab, block, slab, block and never two full steps in a row
ground_f = road_grade(ground_f, road_cells, 0.5)
ground = np.floor(ground_f + 0.5).astype(np.int16)
dist = ndimage.distance_transform_edt(water)
bed_depth = np.minimum(np.where(thames, 4, 6), 1 + dist / 3).astype(np.int16)
ground = np.where(water, np.minimum(ground, level - bed_depth), ground)
level[~water] = -999
surface[~mask] = S["void"]

HOUSEY = {"house", "semidetached_house", "detached", "terrace", "bungalow", "residential", "garage", "garages",
          "shed", "yes", "cottage", "hut", "school", "kindergarten", "retail", "commercial", "church", "pavilion"}


TURN = {}     # id -> [angle, centre x, centre z] each squared building was turned by (to read LiDAR under it)


def square_houses(ball):
    """Houses square to the block grid: each attached group (a terrace, a pair of semis, a house and its
    garage: outlines that share corners) turns about its own centre to the nearest right angle, so walls are
    flat instead of stair-stepped. Groups over 1500 m2 (flats, schools, shop blocks) turn only when their walls
    all agree on one angle (not a terrace round a bend); non-house buildings keep their angle. Returns
    {id: turned outer ring}."""
    cand = list({a["id"]: a for a in ball[::-1]
                 if a["tags"].get("building") in HOUSEY and len(a["rings"]) == 1}.values())   # each id once
    parent = {a["id"]: a["id"] for a in cand}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for a in cand:
        for p in a["rings"][0]:
            k = (round(p[0], 1), round(p[1], 1))
            if k in owner:
                parent[find(a["id"])] = find(owner[k])
            else:
                owner[k] = a["id"]
    groups = {}
    for a in cand:
        groups.setdefault(find(a["id"]), []).append(a)
    out = {}
    for g in groups.values():
        rings = [np.array(a["rings"][0], float) for a in g]
        area = sum(0.5 * abs(np.dot(r[:-1, 0], r[1:, 1]) - np.dot(r[1:, 0], r[:-1, 1])) for r in rings)
        # the group's angle: length-weighted mean of its edge directions, folded to a quarter turn
        seg = np.concatenate([np.diff(r, axis=0) for r in rings])
        L = np.hypot(seg[:, 0], seg[:, 1])
        ang = np.arctan2(seg[:, 1], seg[:, 0]) * 4
        S, C = (L * np.sin(ang)).sum(), (L * np.cos(ang)).sum()
        th = np.arctan2(S, C) / 4
        agree = np.hypot(S, C) / L.sum()          # 1 = every wall on one grid, low = round a bend
        if area > 20000 or (area > 1500 and agree < 0.9):
            continue
        if abs(np.degrees(th)) < 3:
            continue
        c = np.concatenate(rings).mean(0)
        R = np.array([[np.cos(-th), -np.sin(-th)], [np.sin(-th), np.cos(-th)]])
        for a, r in zip(g, rings):
            out[a["id"]] = ((r - c) @ R.T + c).tolist()
            TURN[a["id"]] = [float(th), float(c[0] - E0), float(N1 - c[1])]
    print("houses squared to the grid:", len(out), "in", sum(1 for g in groups.values()
                                                                 if g[0]["id"] in out), "groups")
    return out


# ---- buildings --------------------------------------------------------------------------
bimg = Image.new("I", (W, H), 0)
bd = ImageDraw.Draw(bimg)
buildings = [None]
seen_b = set()
ball = areas + [{"id": ln["id"], "tags": ln["tags"], "rings": [ln["pts"]]} for ln in osm["lines"]
                if ln["tags"].get("building") and ln["pts"][0] == ln["pts"][-1]]
SQUARED = square_houses(ball)
for a in ball:
    t = a["tags"]
    if not t.get("building") or t.get("building") in ("no", "roof") or t.get("location") == "underground":
        continue
    ring = a["rings"][0]
    cr, cc_ = rc(np.mean(ring, axis=0))           # centre, not the first corner (that can sit on the river edge)
    if not (0 <= cr < H and 0 <= cc_ < W) or not mask[cr, cc_]:
        continue
    if a["id"] in seen_b:
        continue
    seen_b.add(a["id"])
    buildings.append({"id": a["id"], "tags": {k: v for k, v in t.items() if not k.startswith(("name:", "ref:"))}})
    if a["id"] in TURN:
        buildings[-1]["turn"] = TURN[a["id"]]
    if a["id"] in SQUARED:
        continue                                  # drawn below, after the rest, into the cells still free
    bd.polygon(px(ring), fill=len(buildings) - 1)
    for inner in a["rings"][1:]:
        bd.polygon(px(inner), fill=0)
building = np.asarray(bimg).astype(np.int32)
for i, b in enumerate(buildings[1:], start=1):
    ring = SQUARED.get(b["id"])
    if ring is None:
        continue
    P_ = np.array(px(ring))
    lo = np.floor(P_.min(0)).astype(int) - 1
    hi = np.ceil(P_.max(0)).astype(int) + 2
    im = Image.new("L", tuple(hi - lo), 0)
    ImageDraw.Draw(im).polygon([tuple(p - lo) for p in P_], fill=1)
    m = np.asarray(im).astype(bool)
    z0, x0 = lo[1], lo[0]
    sz, sx = slice(max(z0, 0), min(z0 + m.shape[0], H)), slice(max(x0, 0), min(x0 + m.shape[1], W))
    m = m[sz.start - z0:sz.stop - z0, sx.start - x0:sx.stop - x0]
    free = (building[sz, sx] == 0) & ~np.isin(surface[sz, sx], (S["road"], S["minor_road"], S["footway"]))
    building[sz, sx][m & free] = i                # (never turned out into a road or pavement)
building *= mask
# address points (OSM often has the number on a node inside the house): give the number to that building
for nd in osm["nodes"]:
    num = nd["tags"].get("addr:housenumber")
    r_, c_ = rc(nd["pt"])
    if num and 0 <= r_ < H and 0 <= c_ < W and building[r_, c_]:
        buildings[building[r_, c_]]["tags"].setdefault("addr:housenumber", num)
print("buildings with a house number:", sum(1 for b in buildings[1:] if b["tags"].get("addr:housenumber")))


def fill_numbers():
    """Unnumbered houses on the same side of the same street as numbered ones carry the numbering on: the
    numbers in between (12, ?, ?, 18), and past either end of the run in the same step (odds/evens by 2, or
    1-by-1 streets). Rows with no numbers at all stay blank."""
    from scipy.spatial import cKDTree
    pts, way, s_, tan = [], [], [], []
    for wi, ln in enumerate(osm["lines"]):
        if not (ln["tags"].get("highway") and ln["tags"].get("name")):
            continue
        p = np.array(ln["pts"], float)
        acc = 0.0
        for a, b in zip(p[:-1], p[1:]):
            L = np.hypot(*(b - a))
            for f in np.arange(0, L, 2.0):
                pts.append(a + (b - a) * f / L); way.append(wi); s_.append(acc + f); tan.append((b - a) / L)
            acc += L
    tree = cKDTree(np.array(pts))
    way, s_, tan, pts = np.array(way), np.array(s_), np.array(tan), np.array(pts)
    n = len(buildings)
    cnt = np.bincount(building.ravel(), minlength=n)
    rr, cc = np.indices(building.shape)
    cz = np.bincount(building.ravel(), rr.ravel(), n) / np.maximum(cnt, 1)
    cx = np.bincount(building.ravel(), cc.ravel(), n) / np.maximum(cnt, 1)
    homes = {"house", "semidetached_house", "detached", "terrace", "bungalow", "residential", "yes", "cottage"}
    rows = {}
    for i in range(1, n):
        t = buildings[i]["tags"]
        if cnt[i] < 25 or t.get("building") not in homes or t.get("name") or t.get("amenity") or t.get("shop"):
            continue
        e, nn = E0 + cx[i] + 0.5, N1 - cz[i] - 0.5
        d, k = tree.query((e, nn))
        if d > 40:
            continue
        name = osm["lines"][way[k]]["tags"]["name"]
        if t.get("addr:street") and t["addr:street"] != name:
            continue
        side = np.sign(tan[k][0] * (nn - pts[k][1]) - tan[k][1] * (e - pts[k][0]))
        rows.setdefault((way[k], side), []).append((s_[k], i))
    filled = 0
    for row in rows.values():
        row.sort()
        num = [buildings[i]["tags"].get("addr:housenumber") for _, i in row]
        known = [j for j, v in enumerate(num) if v and v.isdigit()]
        if len(known) < 2:
            continue

        def put(j, v):
            nonlocal filled
            if v >= 1:
                buildings[row[j][1]]["tags"]["addr:housenumber"] = str(v)
                filled += 1
        for a, b in zip(known[:-1], known[1:]):
            na, nb = int(num[a]), int(num[b])
            step = (2 if (nb - na) % 2 == 0 else 1) * (1 if nb > na else -1)
            if b - a > 1 and not any(num[a + 1:b]) and abs(nb - na) >= abs(step) * (b - a):
                for j in range(a + 1, b):
                    put(j, na + step * (j - a))
        for end, nxt, rng in ((known[0], known[1], range(known[0] - 1, -1, -1)),
                              (known[-1], known[-2], range(known[-1] + 1, len(row)))):
            step = int(num[end]) - int(num[nxt])
            step = step // abs(step) * (2 if step % 2 == 0 else 1) if step else 0
            for k, j in enumerate(rng, start=1):
                if num[j] or not step:
                    break
                put(j, int(num[end]) + step * k)
    # every house gets a number: rows with one known number count on by 2 from it; rows with none number up the
    # street from 1 (odds) or 2 (evens), the opposite parity to the other side where that side is known;
    # anything still blank takes the house before it plus the row's step
    # shortcut: a street split into several OSM ways restarts its count on each way, fix by chaining ways by name
    guessed = lettered = 0
    for (wi, side), row in rows.items():
        suffix = "a"
        num = [buildings[i]["tags"].get("addr:housenumber") for _, i in row]
        known = [j for j, v in enumerate(num) if v and v.isdigit()]
        if not known:
            other = [buildings[i]["tags"].get("addr:housenumber") for _, i in rows.get((wi, -side), [])]
            other = [int(v) for v in other if v and v.isdigit()]
            first = (2 if other[0] % 2 else 1) if other else (1 if side > 0 else 2)
            vals = {j: first + 2 * j for j in range(len(row))}
        else:
            k0 = known[0]
            vals = {j: int(num[k0]) + 2 * (j - k0) for j in range(len(row))}
            last, step = None, 2
            for j in range(len(row)):           # carry on from the nearest number before, where there is one
                if num[j] and num[j].isdigit():
                    last = (j, int(num[j]))
                elif last:
                    vals[j] = last[1] + step * (j - last[0])
        taken = {int(v) for v in num if v and v.isdigit()}
        prev = None
        for j, (_, i) in enumerate(row):
            have = buildings[i]["tags"].get("addr:housenumber")
            if have:
                prev, suffix = have, "a"
                continue
            if vals[j] >= 1 and vals[j] not in taken:
                buildings[i]["tags"]["addr:housenumber"] = prev = str(vals[j])
                taken.add(vals[j])
            elif prev:                      # the count would repeat a real number: 12a, 12b after the 12
                base = prev.rstrip("abcdefgh")
                buildings[i]["tags"]["addr:housenumber"] = prev = base + suffix
                suffix = chr(ord(suffix) + 1)
                lettered += 1
            else:
                continue
            guessed += 1
    print("house numbers carried on from neighbours:", filled, "guessed along the street:", guessed, "(lettered to avoid a repeat:", lettered, ")")


fill_numbers()

json.dump(buildings, open("build/buildings.json", "w"))
json.dump([{"id": b["id"], "tags": b["tags"], "pts": b["pts"]} for b in bridges], open("build/bridges.json", "w"))
json.dump(G_LEVELS, open("build/levels.json", "w"))
np.savez_compressed(out, mask=mask, surface=surface, ground=ground, water=level, building=building,
                    box=np.array([E0, N0, E1, N1]))
print("buildings:", len(buildings) - 1, "bridges:", len(bridges),
      "water levels:", sorted(set(np.unique(level[level > -999]).tolist())))
