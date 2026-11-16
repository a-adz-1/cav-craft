"""Buildings as close to the real thing as blocks allow.

For every building: its OSM outline, its floor at the mean ground under it, and a roof fitted to the EA
LiDAR surface model: flat, hipped (rises from every wall) or gabled (rises from the two long walls, with
gable-end walls up to the ridge), whichever matches the measured roof best, with the measured eave and ridge
heights. Roof slopes are stairs blocks. Walls get rows of windows per storey, floors inside, a front door
on the side nearest the street, and houses get a chimney. Materials come from the street's style (from the
photo survey: docs/street_styles.json), falling back to the building's kind.
"""
import json
import math
import os
import zlib

import numpy as np
from scipy import ndimage

DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}   # (dx, dz)
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}

# roof materials: (full block, stairs, slab)
ROOFS = {
    "slate": ("deepslate_tiles", "deepslate_tile_stairs", "deepslate_tile_slab"),
    "red_tile": ("bricks", "brick_stairs", "brick_slab"),
    "dark_tile": ("red_nether_bricks", "red_nether_brick_stairs", "red_nether_brick_slab"),
    "brown_tile": ("mud_bricks", "mud_brick_stairs", "mud_brick_slab"),
    "grey_tile": ("cobbled_deepslate", "cobbled_deepslate_stairs", "cobbled_deepslate_slab"),
    "flat": ("gray_concrete", None, None),
    "felt": ("blackstone", "blackstone_stairs", "blackstone_slab"),
}
WALLS = {
    "red_brick": "bricks", "orange_brick": "granite", "buff_brick": "mud_bricks", "grey_brick": "tuff_bricks",
    "white_render": "white_concrete", "cream_render": "smooth_sandstone", "pebbledash": "diorite",
    "stone": "stone_bricks", "concrete": "light_gray_concrete", "timber": "spruce_planks",
    "tile_hung": "red_terracotta", "glass": "light_blue_stained_glass", "flint": "andesite",
}
DOORS = ["oak_door", "spruce_door", "dark_oak_door", "birch_door", "jungle_door"]

HOUSE_KINDS = {"house", "detached", "semidetached_house", "terrace", "bungalow", "residential", "yes",
               "cottage", "farm"}
DEFAULT_STYLE = {"walls": ["red_brick", "red_brick", "white_render", "pebbledash", "buff_brick"],
                 "roof": ["dark_tile", "slate", "brown_tile"], "tudor": 0.0}


def fit_roof(rel, inside, edge):
    """rel: DSM - floor (m) over the building's crop; returns (kind, eave, ridge, dist field)."""
    vals = rel[inside]
    if vals.size < 6:
        return "flat", 3, 3, np.zeros_like(rel)
    eave = float(np.percentile(rel[edge], 15)) if edge.any() else float(np.percentile(vals, 10))
    ridge = float(np.percentile(vals, 95))
    eave = max(2.5, min(eave, ridge))
    d_hip = ndimage.distance_transform_edt(inside)
    zz, xx = np.nonzero(inside)
    pts = np.stack([xx, zz], 1).astype(float)
    c = pts.mean(0)
    u, s, vt = np.linalg.svd(pts - c, full_matrices=False)
    minor = vt[1]
    off = (np.stack(np.meshgrid(np.arange(rel.shape[1]), np.arange(rel.shape[0])), -1) - c) @ minor
    half = np.abs(off[inside]).max() + 0.5
    d_gab = np.where(inside, half - np.abs(off), 0)
    if ridge - eave < 1.2 or vals.size > 900:
        return "flat", eave, ridge, d_hip
    best = None
    for kind, d in (("hip", d_hip), ("gable", d_gab)):
        dm = d[inside].max()
        k = (ridge - eave) / max(dm - 0.5, 0.5)
        model = np.clip(eave + k * (d - 0.5), eave, ridge)
        err = np.median(np.abs(model[inside] - vals))
        if best is None or err < best[0]:
            best = (err, kind, d)
    flat_err = np.median(np.abs(ridge - vals))
    if flat_err < best[0] * 0.8:
        return "flat", eave, ridge, d_hip
    return best[1], eave, ridge, best[2]


def load_styles():
    path = "docs/street_styles.json"
    return json.load(open(path)) if os.path.exists(path) else {}


def street_of_buildings():
    import csv
    path = "docs/buildings.csv"
    if not os.path.exists(path):
        return {}
    return {r["osm"]: r["street"] for r in csv.DictReader(open(path))}


def prepare(G, P, layers, lidar, buildings):
    ground = layers["ground"].astype(np.int32)
    bid = layers["building"]
    dsm = np.nan_to_num(lidar["dsm"], nan=0.0)
    surface = layers["surface"]
    n = len(buildings)
    styles = load_styles()
    streets = street_of_buildings()
    objs = ndimage.find_objects(bid)
    H, W = bid.shape
    roofY = np.zeros((H, W), np.int16)      # top roof block y
    base = np.zeros((H, W), np.int16)
    blocks = {}                              # (x, y, z) -> palette index (sparse extras: doors, chimneys, stairs)
    wallmat = np.zeros((H, W), np.int32)
    roofmat = np.zeros((H, W), np.int32)
    edge_all = np.zeros((H, W), bool)
    floors_every = np.zeros((H, W), np.int8)
    roadish = np.isin(surface, (3, 4, 5, 6, 9))
    stats = {"flat": 0, "hip": 0, "gable": 0}
    for i in range(1, n):
        sl = objs[i - 1] if i - 1 < len(objs) else None
        if sl is None or buildings[i] is None:
            continue
        b = buildings[i]
        t = b["tags"]
        kind = t.get("building", "yes")
        # crop with a 1-cell margin
        z0, z1 = max(0, sl[0].start - 1), min(H, sl[0].stop + 1)
        x0, x1 = max(0, sl[1].start - 1), min(W, sl[1].stop + 1)
        inside = bid[z0:z1, x0:x1] == i
        if inside.sum() < 4:
            continue
        g = ground[z0:z1, x0:x1]
        fl = int(round(g[inside].mean()))
        rel = dsm[z0:z1, x0:x1] - fl
        edge = inside & ~ndimage.binary_erosion(inside)
        rkind, eave, ridge, d = fit_roof(rel, inside, edge)
        stats[rkind] += 1
        h = zlib.crc32(b["id"].encode())
        st = styles.get(streets.get(b["id"].lstrip("wr"), ""), None) or styles.get(streets.get(b["id"], ""), None)
        big = kind not in HOUSE_KINDS or inside.sum() > 400
        if st is None:
            st = DEFAULT_STYLE if not big else {"walls": ["concrete", "red_brick", "buff_brick", "white_render"],
                                                  "roof": ["flat"], "tudor": 0}
        if kind in ("church", "chapel") or t.get("amenity") == "place_of_worship":
            st = {"walls": ["stone", "flint"], "roof": ["slate"], "tudor": 0}
        if kind in ("garage", "garages", "shed", "hut", "carport"):
            st = {"walls": ["red_brick", "concrete", "timber"], "roof": ["felt"], "tudor": 0}
            rkind = "flat" if rkind == "flat" or ridge - eave < 1.5 else rkind
        wname = st["walls"][h % len(st["walls"])]
        rname = st["roof"][(h >> 5) % len(st["roof"])]
        if rkind == "flat":
            rname = "flat" if big else "felt"
        full, stair, slab = ROOFS[rname]
        ey = fl + max(3, int(round(eave)))
        ry = fl + max(3, int(round(ridge)))
        if rkind == "flat":
            top = np.full(inside.shape, ry, np.int32)
        else:
            k = (ridge - eave) / max(d[inside].max() - 0.5, 0.5)
            top = np.clip(np.round(fl + eave + k * (d - 0.5)), ey, ry).astype(np.int32)
        sub = np.s_[z0:z1, x0:x1]
        roofY[sub] = np.where(inside, top, roofY[sub])
        base[sub] = np.where(inside, fl, base[sub])
        wallmat[sub] = np.where(inside, P(WALLS[wname]), wallmat[sub])
        roofmat[sub] = np.where(inside, P(full), roofmat[sub])
        edge_all[sub] |= edge
        floors_every[sub] = np.where(inside, 3, floors_every[sub])
        # stairs on the slopes: facing the uphill side
        if stair and rkind != "flat":
            zz, xx = np.nonzero(inside)
            for zl, xl in zip(zz, xx):
                y = top[zl, xl]
                lows = []
                for name, (dx, dz) in DIRS.items():
                    a, c = zl + dz, xl + dx
                    if not (0 <= a < top.shape[0] and 0 <= c < top.shape[1]) or not inside[a, c] or top[a, c] < y:
                        lows.append(name)
                if lows and len(lows) < 4 and y > ey - 1 + (0 if rkind == "hip" else 0):
                    if len(lows) == 1:
                        face = OPP[lows[0]]
                    else:
                        # corner of a hip: face away from the first low side
                        face = OPP[lows[0]]
                    blocks[(x0 + xl, int(y), z0 + zl)] = P(stair, facing=face, half="bottom", shape="straight")
                elif lows and y == ey and rkind == "gable" and edge[zl, xl] and len(lows) < 4:
                    pass
        # Tudor beams on the upper storey for some streets
        if st.get("tudor", 0) and (h % 100) < st["tudor"] * 100:
            zz, xx = np.nonzero(edge)
            for zl, xl in zip(zz, xx):
                if (x0 + xl + z0 + zl) % 3 == 0:
                    for y in range(fl + 4, min(ey, top[zl, xl])):
                        blocks[(x0 + xl, y, z0 + zl)] = P("dark_oak_log")
        # chimney for houses with pitched roofs: on the ridge near one end
        if rkind != "flat" and not big and kind not in ("garage", "garages", "shed"):
            ridge_cells = np.argwhere(inside & (top == top[inside].max()))
            if len(ridge_cells):
                zl, xl = ridge_cells[0] if (h & 1) else ridge_cells[-1]
                for y in range(int(top[zl, xl]) - 1, int(top[zl, xl]) + 3):
                    blocks[(x0 + xl, y, z0 + zl)] = P("bricks")
                blocks[(x0 + xl, int(top[zl, xl]) + 3, z0 + zl)] = P("flower_pot")
        # front door: the wall cell nearest a road/path, on the outside face
        if kind not in ("garage", "garages", "shed", "hut") and inside.sum() >= 12:
            rz, rx = np.nonzero(roadish[z0 - 15 if z0 >= 15 else 0:z1 + 15, x0 - 15 if x0 >= 15 else 0:x1 + 15])
            oz, ox = (z0 - 15 if z0 >= 15 else 0), (x0 - 15 if x0 >= 15 else 0)
            ez, ex = np.nonzero(edge)
            if len(rz) and len(ez):
                dd = (ez[:, None] + z0 - (rz[None] + oz)) ** 2 + (ex[:, None] + x0 - (rx[None] + ox)) ** 2
                j = int(np.argmin(dd.min(1)))
                dz_, dx_ = ez[j], ex[j]
                # which side is outside
                for name, (dx, dz) in DIRS.items():
                    a, c = dz_ + dz, dx_ + dx
                    if 0 <= a < inside.shape[0] and 0 <= c < inside.shape[1] and not inside[a, c]:
                        door = DOORS[(h >> 9) % len(DOORS)]
                        X, Z = x0 + dx_, z0 + dz_
                        blocks[(X, fl + 1, Z)] = P(door, facing=name, half="lower", hinge="left", open="false")
                        blocks[(X, fl + 2, Z)] = P(door, facing=name, half="upper", hinge="left", open="false")
                        G.setdefault("doorsteps", []).append((X + dx, fl, Z + dz))
                        break
    print("roofs:", stats)
    # lowest roof block per cell: down to one above the lowest neighbour in the same building, so slopes are solid
    lo = roofY.astype(np.int32)
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        same = np.roll(bid, sh, ax) == bid
        lo = np.where(same & (bid > 0), np.minimum(lo, np.roll(roofY, sh, ax).astype(np.int32) + 1), lo)
    lo = np.minimum(lo, roofY)
    G.update(h_roof=roofY, h_base=base, h_wall=wallmat, h_rooftop=roofmat, h_edge=edge_all, h_lo=lo.astype(np.int16),
             h_blocks=blocks)


def stamp_factory(G, P):
    glass, floor = P("tinted_glass"), P("oak_planks")   # tinted: windows read dark from outside, like real ones
    by_chunk = {}
    for (x, y, z), blk in G["h_blocks"].items():
        by_chunk.setdefault((x // 16, z // 16), []).append((x, y, z, blk))
    dirt = P("dirt")

    def stamp(b, x0, z0, g, w, s, Y):
        sl = np.s_[z0:z0 + 16, x0:x0 + 16]
        wall = G["h_wall"][sl]
        if wall.shape != (16, 16) or not wall.any():
            extra = by_chunk.get((x0 // 16, z0 // 16))
            if not extra:
                return
        inb = wall > 0
        fl = G["h_base"][sl].astype(np.int32)
        top = G["h_roof"][sl].astype(np.int32)
        edge = G["h_edge"][sl]
        rooftop = G["h_rooftop"][sl]
        if inb.any():
            b[:] = np.where(inb[None] & (Y > fl) & (Y <= top + 6), 0, b)            # clear the volume
            b[:] = np.where(inb[None] & (Y <= fl) & (Y > g), dirt, b)              # fill under the floor
            b[:] = np.where(inb[None] & (Y == fl), floor, b)
            rel = Y - fl
            storey_floor = inb & ~edge
            b[:] = np.where(storey_floor[None] & (rel > 0) & (rel % 3 == 0) & (Y < top - 1), floor, b)
            walls = edge & inb
            b[:] = np.where(walls[None] & (Y > fl) & (Y < top), wall[None], b)
            X = np.arange(16)[None, None, :] + x0
            Z = np.arange(16)[None, :, None] + z0
            win = walls[None] & ((rel % 3 == 1) | (rel % 3 == 2)) & (((X + Z) % 4 == 1) | ((X + Z) % 4 == 2))
            b[:] = np.where(win & (Y > fl) & (Y < top - 1) & (b == wall[None]), glass, b)
            lo = G["h_lo"][sl].astype(np.int32)
            b[:] = np.where(inb[None] & (Y >= lo) & (Y <= top), rooftop[None], b)
        for x, y, z, blk in by_chunk.get((x0 // 16, z0 // 16), ()):
            if 0 <= y + 64 < b.shape[0]:
                b[y + 64, z - z0, x - x0] = blk
    return stamp
