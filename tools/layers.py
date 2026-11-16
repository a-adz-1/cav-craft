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
PATH_WIDTH = {"footway": 2, "cycleway": 2, "path": 2, "bridleway": 2, "steps": 2, "track": 3, "pedestrian": 4}
bridges = []
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
                hw == "footway" and t.get("surface") is None and t.get("footway") in ("sidewalk", "crossing")):
            cls = "footway"
        else:
            cls = "path"
    elif t.get("railway") in ("rail", "light_rail"):
        cls, w = "railway", 4
    else:
        continue
    pts = px(ln["pts"])
    d.line(pts, fill=S[cls], width=w)
    for x, y in pts:
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=S[cls])
surface = np.asarray(surf).copy()

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

ground = np.where(np.isfinite(dtm), np.round(dtm), 0).astype(np.int16)
dist = ndimage.distance_transform_edt(water)
bed_depth = np.minimum(np.where(thames, 4, 6), 1 + dist / 3).astype(np.int16)
ground = np.where(water, np.minimum(ground, level - bed_depth), ground)
level[~water] = -999
surface[~mask] = S["void"]

# ---- buildings --------------------------------------------------------------------------
bimg = Image.new("I", (W, H), 0)
bd = ImageDraw.Draw(bimg)
buildings = [None]
for a in areas + [{"id": ln["id"], "tags": ln["tags"], "rings": [ln["pts"]]} for ln in osm["lines"]
                   if ln["tags"].get("building") and ln["pts"][0] == ln["pts"][-1]]:
    t = a["tags"]
    if not t.get("building") or t.get("building") in ("no", "roof") or t.get("location") == "underground":
        continue
    ring = a["rings"][0]
    cr, cc_ = rc(ring[0])
    if not (0 <= cr < H and 0 <= cc_ < W) or not mask[cr, cc_]:
        continue
    if any(b and b["id"] == a["id"] for b in buildings[-3:]):
        continue
    buildings.append({"id": a["id"], "tags": {k: v for k, v in t.items() if not k.startswith(("name:", "ref:", "addr:"))}})
    bd.polygon(px(ring), fill=len(buildings) - 1)
    for inner in a["rings"][1:]:
        bd.polygon(px(inner), fill=0)
building = np.asarray(bimg).astype(np.int32) * mask

json.dump(buildings, open("build/buildings.json", "w"))
json.dump([{"id": b["id"], "tags": b["tags"], "pts": b["pts"]} for b in bridges], open("build/bridges.json", "w"))
json.dump(G_LEVELS, open("build/levels.json", "w"))
np.savez_compressed(out, mask=mask, surface=surface, ground=ground, water=level, building=building,
                    box=np.array([E0, N0, E1, N1]))
print("buildings:", len(buildings) - 1, "bridges:", len(bridges),
      "water levels:", sorted(set(np.unique(level[level > -999]).tolist())))
