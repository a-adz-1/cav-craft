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

import landmarks

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
    "sandstone": "smooth_sandstone",
}
FASCIAS = ["black_concrete", "blue_concrete", "green_concrete", "red_concrete", "white_concrete", "cyan_concrete",
           "gray_concrete", "purple_concrete", "orange_concrete"]
DOORS = ["oak_door", "spruce_door", "dark_oak_door", "birch_door", "jungle_door"]

HOUSE_KINDS = {"house", "detached", "semidetached_house", "terrace", "bungalow", "residential", "yes",
               "cottage", "farm"}
DEFAULT_STYLE = {"walls": ["red_brick", "red_brick", "white_render", "pebbledash", "buff_brick"],
                 "roof": ["dark_tile", "slate", "brown_tile"], "tudor": 0.0}


def fit_roof(rel, inside, edge, attached=None, force=None, ridge_pct=95, low=False):
    """rel: DSM - floor (m) over the building's crop; returns (kind, eave, ridge, dist field).
    low: single-storey outbuildings (garages, sheds), which the DSM often confuses with trees over them."""
    vals = rel[inside]
    if vals.size < 6:
        return "flat", 3, 3, np.zeros_like(rel)
    ridge = float(np.percentile(vals, ridge_pct))
    # eaves: a couple of metres in from the walls (the outline's edge cells often catch the ground beside it)
    d_in = ndimage.distance_transform_edt(inside)
    ring = inside & (d_in > 1.5) & (d_in <= 2.5)
    eave = float(np.percentile(rel[ring], 25)) if ring.sum() > 3 else float(np.percentile(vals, 30))
    if low:
        eave, ridge = 2.5, min(ridge, 4.5)
    elif force is None and ridge < 2.5 and vals.size <= 300:
        force, eave, ridge = "gable", 5.6, 8.5   # built after the LiDAR survey: a plain two-storey house
    elif force is None:
        # tree canopy over a roof reads as a tall spike: no house roof rises more than 45 deg from its eaves,
        # and no ordinary house is taller than 13 m
        ridge = min(ridge, 13.0 if vals.size <= 300 else 99.0, max(eave, 5.6) + max(float(d_in.max()) - 0.5, 1.0))
    # a house with a real upstairs has eaves at 4.5 m or more; only low ridges (bungalows) sit lower
    eave = max(5.6 if ridge >= 7 and not low else 2.5, min(eave, ridge))   # two storeys: walls to y+6
    region = inside | (attached if attached is not None else False)
    lab, _ = ndimage.label(region)
    region = lab == np.bincount(lab[inside]).argmax()
    d_hip = ndimage.distance_transform_edt(np.pad(region, 1)) [1:-1, 1:-1]
    zz, xx = np.nonzero(region)
    pts = np.stack([xx, zz], 1).astype(float)
    c = pts.mean(0)
    u, s, vt = np.linalg.svd(pts - c, full_matrices=False)
    minor = vt[1]
    off = (np.stack(np.meshgrid(np.arange(rel.shape[1]), np.arange(rel.shape[0])), -1) - c) @ minor
    half = np.abs(off[region]).max() + 0.5
    d_gab = np.where(region, half - np.abs(off), 0)
    if force in ("hip", "gable"):
        return force, eave, max(ridge, eave + 2.5), d_hip if force == "hip" else d_gab   # landmarks keep a pitch
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


BAY_FAMILIES = {"grey_terrace": 2, "riverside_villa": 2, "victorian_terrace": 2, "victorian_villa": 2, "interwar_semi": 2, "interwar_detached": 2,
                "postwar_council": 0}


def add_bay(P, blocks, inside, bidcrop, dz_, dx_, dx, dz, x0, z0, fl, ey, wall, roof, family, stats):
    """A bay window beside the front door: 3 wide, 1 out from the wall, glazed on its three faces, up one or
    two storeys (Victorian and 1930s houses), with a tiled cap."""
    storeys = BAY_FAMILIES[family]
    if not storeys:
        return
    ax, az = dz, dx            # along the wall
    for sign, k0 in ((1, 1), (-1, 1), (1, 2), (-1, 2), (1, 0), (-1, 0)):
        cells = [(dz_ + az * sign * k, dx_ + ax * sign * k) for k in (k0 + 1, k0 + 2, k0 + 3)]
        ok = all(0 <= a < inside.shape[0] and 0 <= c < inside.shape[1] and inside[a, c] for a, c in cells)
        out = [(a + dz, c + dx) for a, c in cells]
        ok &= all(0 <= a < inside.shape[0] and 0 <= c < inside.shape[1] and bidcrop[a, c] == 0 for a, c in out)
        if not ok:
            continue
        top = min(fl + 3 * storeys, ey - 1)
        pane = P("glass_pane", **{k: "true" if k in (("east", "west") if dx == 0 else ("north", "south")) else "false"
                                  for k in ("north", "south", "east", "west")})
        for i, (a, c) in enumerate(out):
            X, Z = x0 + c, z0 + a
            for y in range(fl + 1, top + 1):
                corner = i != 1
                sill = (y - fl) % 3 == 0 or y == fl + 1
                blocks[(X, y, Z)] = wall if corner or sill else pane
            blocks[(X, fl, Z)] = wall
            blocks[(X, top + 1, Z)] = roof
        stats["bays"] = stats.get("bays", 0) + 1
        return


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
    landmarks.add_pub_points(layers, buildings)
    styles = load_styles()
    streets = street_of_buildings()
    objs = ndimage.find_objects(bid)
    H, W = bid.shape
    roofY = np.zeros((H, W), np.int16)      # top roof block y
    base = np.zeros((H, W), np.int16)
    blocks = {}                              # (x, y, z) -> palette index (sparse extras: doors, chimneys, stairs)
    wallmat = np.zeros((H, W), np.int32)
    upmat = np.zeros((H, W), np.int32)       # upper-storey wall material where it differs (render over brick)
    roofmat = np.zeros((H, W), np.int32)
    edge_all = np.zeros((H, W), bool)
    floors_every = np.zeros((H, W), np.int8)
    winstyle = np.zeros((H, W), np.int8)     # 0 houses (2x2), 1 lancets, 2 tall mullioned
    roadish = np.isin(surface, (3, 4, 5, 6, 9))
    main_road = surface == 3
    stats = {"flat": 0, "hip": 0, "gable": 0}
    # shop names from OSM points (most shops are mapped as a point inside the building, not on the outline)
    shop_names = {}
    for nd in json.load(open("build/osm.json"))["nodes"]:
        tt = nd["tags"]
        if tt.get("name") and (tt.get("shop") or tt.get("amenity") in ("cafe", "restaurant", "fast_food", "pub", "bar",
                                                                    "bank", "pharmacy", "post_office", "dentist")):
            from box import E0 as _E0, N1 as _N1
            xx_, zz_ = int(nd["pt"][0] - _E0), int(_N1 - nd["pt"][1])
            if 0 <= zz_ < H and 0 <= xx_ < W and bid[zz_, xx_]:
                shop_names.setdefault(buildings[bid[zz_, xx_]]["id"], tt["name"])
    for i in range(1, n):
        sl = objs[i - 1] if i - 1 < len(objs) else None
        if sl is None or buildings[i] is None:
            continue
        b = buildings[i]
        t = b["tags"]
        kind = t.get("building", "yes")
        # crop with a 1-cell margin
        z0, z1 = max(0, sl[0].start - 12), min(H, sl[0].stop + 12)
        x0, x1 = max(0, sl[1].start - 12), min(W, sl[1].stop + 12)
        inside = bid[z0:z1, x0:x1] == i
        if inside.sum() < 4 or landmarks.LANDMARKS.get(b["id"], {}).get("skip"):
            continue
        g = ground[z0:z1, x0:x1]
        fl = int(round(g[inside].mean()))
        rel = dsm[z0:z1, x0:x1] - fl
        edge = inside & ~ndimage.binary_erosion(inside)
        # attached neighbours (semis, terraces) count as roof, not as outside: the roof runs over the party wall
        attached = (bid[z0:z1, x0:x1] > 0)
        lm = landmarks.LANDMARKS.get(b["id"])
        if lm and lm["roof"] != "flat":
            # landmarks: gabled; a tower's height mustn't set the nave's ridge
            rkind, eave, ridge, d = fit_roof(rel, inside, edge, attached, force=lm.get("roof_kind", "gable"),
                                             ridge_pct=70 if "tower" in lm else 95)
        else:
            rkind, eave, ridge, d = fit_roof(rel, inside, edge, attached,
                                             low=kind in ("garage", "garages", "shed", "hut", "carport", "service"))
        stats[rkind] += 1
        h = zlib.crc32(b["id"].encode())
        st = styles.get(streets.get(b["id"].lstrip("wr"), ""), None) or styles.get(streets.get(b["id"], ""), None)
        big = kind not in HOUSE_KINDS or inside.sum() > 400
        if st is None:
            st = DEFAULT_STYLE if not big else {"walls": ["concrete", "red_brick", "buff_brick", "white_render"],
                                                  "roof": ["flat"], "tudor": 0}
        if kind in ("school", "kindergarten", "college") or t.get("amenity") in ("school", "kindergarten"):
            st = {"walls": ["red_brick", "buff_brick", "orange_brick", "red_brick"], "roof": ["flat", "dark_tile", "slate"],
                  "tudor": 0, "family": "school"}
        if kind in ("church", "chapel") or t.get("amenity") == "place_of_worship":
            st = {"walls": ["stone", "flint"], "roof": ["slate"], "tudor": 0}
        if kind in ("garage", "garages", "shed", "hut", "carport"):
            st = {"walls": ["red_brick", "concrete", "timber"], "roof": ["felt"], "tudor": 0}
            rkind = "flat" if rkind == "flat" or ridge - eave < 1.5 else rkind
        if lm:
            st = {"walls": [lm["walls"]], "roof": [lm["roof"]], "tudor": 0}
            if lm["roof"] == "flat":
                rkind = "flat"
            elif rkind == "flat":
                rkind = lm.get("roof_kind", "gable")
        wname = st["walls"][h % len(st["walls"])]
        upper = st.get("upper") and ((h >> 13) % 100) < st.get("upper_p", 0.5) * 100
        uname = st["upper"][(h >> 17) % len(st["upper"])] if upper else None
        rname = st["roof"][(h >> 5) % len(st["roof"])]
        if rkind == "flat":
            rname = "flat" if big or lm else "felt"
        elif rname == "flat":
            rname = "slate"
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
        if uname and uname != wname:
            upmat[sub] = np.where(inside, P(WALLS[uname]), upmat[sub])
        # grey-brick terraces: red brick band at every floor and over the windows
        if st.get("family") == "grey_terrace":
            zz, xx = np.nonzero(edge)
            for zl, xl in zip(zz, xx):
                for y in range(fl + 3, int(top[zl, xl]), 3):
                    blocks.setdefault((x0 + xl, y, z0 + zl), P("bricks"))
        # brick quoins on the corners of grey-brick and rendered houses
        if wname in ("grey_brick", "white_render", "cream_render") and st.get("quoins", 0) > ((h >> 21) % 100) / 100:
            corner = edge & (ndimage.convolve(inside.astype(int), np.ones((3, 3), int), mode="constant") <= 4)
            zz, xx = np.nonzero(corner)
            for zl, xl in zip(zz, xx):
                for y in range(fl + 1, int(top[zl, xl])):
                    blocks.setdefault((x0 + xl, y, z0 + zl), P("bricks"))
        roofmat[sub] = np.where(inside, P(full), roofmat[sub])
        # shopfronts: glazed ground floor with a coloured fascia on the road side of shops, pubs, cafés
        shop_colour = (lm or {}).get("shopfront")
        if not shop_colour and (kind in ("retail", "commercial", "supermarket") or t.get("shop") or
                                t.get("amenity") in ("pub", "cafe", "restaurant", "bar", "fast_food", "bank",
                                                     "pharmacy", "post_office")):
            shop_colour = FASCIAS[(h >> 7) % len(FASCIAS)]
        if not shop_colour and st.get("family") == "town" and inside.sum() < 400:
            near_main = ndimage.binary_dilation(main_road[z0:z1, x0:x1], iterations=12)
            if (near_main & inside).any() and (h % 3):
                shop_colour = FASCIAS[(h >> 7) % len(FASCIAS)]
        if shop_colour:
            front = edge & ndimage.binary_dilation(roadish[z0:z1, x0:x1], iterations=4)
            for zl, xl in zip(*np.nonzero(front)):
                X, Z = x0 + xl, z0 + zl
                blocks[(X, fl + 1, Z)] = P("glass_pane") if (X + Z) % 4 else P("dark_oak_planks")
                blocks[(X, fl + 2, Z)] = P("glass_pane") if (X + Z) % 4 else P("dark_oak_planks")
                blocks[(X, fl + 3, Z)] = P(shop_colour)
                if lm and lm.get("canopy"):   # a canopy over the shop windows, one block out
                    for dx_c, dz_c in DIRS.values():
                        a_, c_ = zl + dz_c, xl + dx_c
                        if 0 <= a_ < inside.shape[0] and 0 <= c_ < inside.shape[1] and not inside[a_, c_]:
                            blocks.setdefault((X + dx_c, fl + 3, Z + dz_c), P(lm["canopy"], type="top"))
            if front.any():
                stats.setdefault("shopfronts", 0)
                stats["shopfronts"] += 1
                # the shop's real name on a sign on the fascia, facing the street
                sname = t.get("name") or shop_names.get(b["id"])
                if sname:
                    fz, fx = np.argwhere(front)[len(np.argwhere(front)) // 2]
                    for name_, (dx, dz) in DIRS.items():
                        a_, c_ = fz + dz, fx + dx
                        if 0 <= a_ < inside.shape[0] and 0 <= c_ < inside.shape[1] and not inside[a_, c_]:
                            SX, SZ = int(x0 + c_), int(z0 + a_)
                            blocks[(SX, fl + 3, SZ)] = P("dark_oak_wall_sign", facing=name_)
                            words = sname.split()
                            lines, cur = [], ""
                            for w_ in words:
                                if len(cur) + len(w_) + 1 > 15 and cur:
                                    lines.append(cur)
                                    cur = w_
                                else:
                                    cur = (cur + " " + w_).strip()
                            lines.append(cur)
                            G.setdefault("sign_texts", []).append((SX, int(fl) + 3, SZ, lines[:4]))
                            stats["named"] = stats.get("named", 0) + 1
                            break
        church = kind in ("church", "chapel") or t.get("amenity") == "place_of_worship"
        ws = {"lancet": 1, "tall": 2}.get(lm.get("windows"), 0) if lm else (1 if church else 2 if st.get("family") == "school" else 0)
        if ws:
            winstyle[sub] = np.where(inside, ws, winstyle[sub])
        if lm:
            if lm.get("dress"):
                landmarks.dressings(P, blocks, inside, edge, x0, z0, fl, top, lm)
            if "tower" in lm:
                pk = np.unravel_index(np.argmax(np.where(inside, rel, -99)), rel.shape)
                landmarks.tower(P, blocks, inside, fl, fl + int(round(rel[pk])), (x0 + pk[1], z0 + pk[0]),
                                lm["tower"], P(full), P(stair) if stair else None)
            if lm.get("colonnade"):
                landmarks.colonnade(P, blocks, inside, x0, z0, fl, (ry - 1) if rkind == "flat" else ey, lm["colonnade"])
            if lm.get("terrace"):
                # a paved terrace at floor level along the south front, balustraded, steps down at its middle
                south = np.zeros_like(inside)
                for k in range(1, 7):
                    south[k:] |= inside[:-k]
                south &= ~inside & (bid[z0:z1, x0:x1] == 0)
                rim = south & ~np.roll(south, -1, 0)
                mid = int(np.median(np.nonzero(rim)[1])) if rim.any() else -1
                for zl, xl in zip(*np.nonzero(south)):
                    X, Z = x0 + xl, z0 + zl
                    for y in range(int(G["ground"][Z, X]) + 1, fl + 1):
                        blocks[(X, y, Z)] = P("smooth_stone")
                    if rim[zl, xl] and abs(xl - mid) > 2:
                        blocks[(X, fl + 1, Z)] = P("sandstone_wall", up="true", east="low", west="low",
                                                   north="none", south="none")
                    elif rim[zl, xl]:
                        for k in range(fl - int(G["ground"][Z, X])):
                            blocks[(X, fl - k, Z + k)] = P("sandstone_stairs", facing="north", half="bottom",
                                                         shape="straight")
            if lm.get("parapet"):
                for zl, xl in zip(*np.nonzero(edge)):
                    blocks[(x0 + xl, int(top[zl, xl]) + 1, z0 + zl)] = P(lm["parapet"], up="true")
            if lm.get("yews"):
                # flint wall + a row of clipped yew drums along the nearest road, 2 m inside it
                rd = np.isin(surface[z0:z1, x0:x1], (3, 5))
                dist_r = ndimage.distance_transform_edt(~rd)
                line = (dist_r >= 2) & (dist_r < 3) & ~inside & (bid[z0:z1, x0:x1] == 0)
                for k, (zl, xl) in enumerate(np.argwhere(line)):
                    g0 = int(G["ground"][z0 + zl, x0 + xl])
                    blocks[(x0 + xl, g0 + 1, z0 + zl)] = P("andesite_wall", up="true", north="none", south="none",
                                                             east="none", west="none")
                    if k % 3 == 0:
                        for dy in range(2, 6):
                            blocks[(x0 + xl, g0 + dy, z0 + zl)] = P("spruce_leaves", persistent="true")
            if lm.get("vane"):
                pk = np.argwhere(inside & (top == top[inside].max()))[0]
                blocks[(x0 + pk[1], int(top.max()) + 1, z0 + pk[0])] = P("lightning_rod")
            print(f"landmark: {lm['name']} ({rkind} roof, eave {eave:.1f} m, ridge {ridge:.1f} m)")
        edge_all[sub] |= edge
        floors_every[sub] = np.where(inside, 3, floors_every[sub])
        # stairs on the slopes: each faces up its own slope (the low side's opposite neighbour is higher);
        # ridge and hip-corner cells with no clear uphill keep the full block
        if stair and rkind != "flat":
            zz, xx = np.nonzero(inside)
            for zl, xl in zip(zz, xx):
                y = top[zl, xl]
                if y <= ey - 1:
                    continue

                def nb(dx, dz):
                    a_, c_ = zl + dz, xl + dx
                    if 0 <= a_ < top.shape[0] and 0 <= c_ < top.shape[1] and inside[a_, c_]:
                        return top[a_, c_]
                    return -999
                def straight(dx, dz):   # the roof edge runs on level both sides (not a zigzag on a diagonal wall)
                    return nb(dz, dx) == y and nb(-dz, -dx) == y
                faces = [OPP[name] for name, (dx, dz) in DIRS.items()
                         if nb(dx, dz) < y and nb(-dx, -dz) > y and straight(dx, dz)]
                if len(faces) == 1:
                    blocks[(x0 + xl, int(y), z0 + zl)] = P(stair, facing=faces[0], half="bottom", shape="straight")
                elif not faces:
                    lows = [name for name, (dx, dz) in DIRS.items() if nb(dx, dz) < y and straight(dx, dz)]
                    if len(lows) == 1:   # eaves row: one low side, the rest level
                        blocks[(x0 + xl, int(y), z0 + zl)] = P(stair, facing=OPP[lows[0]], half="bottom",
                                                                shape="straight")
        # inside: a staircase up to the first floor along one wall, and a few furnishings per floor
        if kind in HOUSE_KINDS and not big and not lm and ey - fl >= 5:
            inner = inside & ~edge
            cells = np.argwhere(inner & ndimage.binary_dilation(edge))   # just inside the walls
            run = None
            for zl, xl in cells:
                for name, (dx, dz) in DIRS.items():
                    path = [(zl + dz * k, xl + dx * k) for k in range(3)]
                    if all(0 <= a < inside.shape[0] and 0 <= c < inside.shape[1] and inner[a, c] for a, c in path):
                        run = (path, name)
                        break
                if run:
                    break
            if run:
                path, name = run
                for k, (a, c) in enumerate(path):
                    X, Z = x0 + c, z0 + a
                    blocks[(X, fl + 1 + k, Z)] = P("oak_stairs", facing=name, half="bottom", shape="straight")
                    for y in range(fl + 2 + k, fl + 5):
                        blocks.setdefault((X, y, Z), P("air"))          # stairwell through the first floor
            free = [tuple(v) for v in np.argwhere(inner & ~ndimage.binary_dilation(edge))]
            rng_h = np.random.default_rng(h)
            if len(free) >= 6:
                pick = rng_h.choice(len(free), 4, replace=False)
                (a1, c1), (a2, c2), (a3, c3), (a4, c4) = (free[i] for i in pick)
                blocks.setdefault((x0 + c1, fl + 1, z0 + a1), P("crafting_table"))
                blocks.setdefault((x0 + c2, fl + 1, z0 + a2), P("furnace", facing="north", lit="false"))
                blocks.setdefault((x0 + c3, fl + 4, z0 + a3), P("red_bed", facing="north", part="head", occupied="false"))
                blocks.setdefault((x0 + c4, fl + 4, z0 + a4), P("bookshelf"))
        # flat-roofed blocks: a parapet round the roof edge, a plant room on top of the big ones, and balconies
        # on apartment blocks (a slab ledge + glass rail under every other upper-floor window row)
        if rkind == "flat" and not lm and kind not in ("garage", "garages", "shed", "hut", "carport"):
            cap = P("smooth_stone_slab", type="bottom")
            for zl, xl in zip(*np.nonzero(edge)):
                blocks.setdefault((x0 + xl, int(top[zl, xl]) + 1, z0 + zl), cap)
            if inside.sum() > 300:
                core = np.argwhere(inside & (ndimage.distance_transform_edt(inside) >= 4))
                if len(core):
                    zc, xc = core[len(core) // 2]
                    for dz in range(-2, 3):
                        for dx in range(-2, 3):
                            a_, c_ = zc + dz, xc + dx
                            if 0 <= a_ < inside.shape[0] and 0 <= c_ < inside.shape[1] and inside[a_, c_]:
                                blocks[(x0 + c_, int(top[a_, c_]) + 1, z0 + a_)] = P("light_gray_concrete")
                                blocks[(x0 + c_, int(top[a_, c_]) + 2, z0 + a_)] = P("light_gray_concrete")
            if kind == "apartments" and ry - fl >= 8:
                front = edge & ndimage.binary_dilation(roadish[z0:z1, x0:x1], iterations=15)
                for zl, xl in zip(*np.nonzero(front)):
                    for name, (dx, dz) in DIRS.items():
                        a_, c_ = zl + dz, xl + dx
                        if 0 <= a_ < inside.shape[0] and 0 <= c_ < inside.shape[1] and not inside[a_, c_] and \
                                bid[z0 + a_, x0 + c_] == 0:
                            for y in range(fl + 3, ry - 1, 3):
                                if ((x0 + xl) + (z0 + zl)) % 4 in (1, 2):
                                    blocks.setdefault((x0 + c_, y, z0 + a_), P("smooth_stone_slab", type="top"))
                                    blocks.setdefault((x0 + c_, y + 1, z0 + a_), P(
                                        "glass_pane", north="true", south="true", east="true", west="true"))
                            break
        # Tudor beams on the upper storey for some streets
        if (lm and lm.get("tudor_gable")) or (st.get("tudor", 0) and (h % 100) < st["tudor"] * 100):
            zz, xx = np.nonzero(edge)
            for zl, xl in zip(zz, xx):
                if (x0 + xl + z0 + zl) % 3 == 0:
                    for y in range(fl + 4, min(ey, top[zl, xl])):
                        blocks[(x0 + xl, y, z0 + zl)] = P("dark_oak_log")
        # chimney for houses with pitched roofs: on the ridge near one end
        if rkind != "flat" and not big and not lm and kind not in ("garage", "garages", "shed"):
            ridge = inside & (top >= top[inside].max() - 1)
            # attached houses: the stack sits on the party wall (the ridge cell next to the neighbour)
            party = ridge & ndimage.binary_dilation((bid[z0:z1, x0:x1] > 0) & ~inside)
            ridge_cells = np.argwhere(party) if party.any() else np.argwhere(ridge & (top == top[inside].max()))
            if len(ridge_cells):
                zl, xl = ridge_cells[len(ridge_cells) // 2] if party.any() else (
                    ridge_cells[0] if (h & 1) else ridge_cells[-1])
                for y in range(int(top[zl, xl]) - 1, int(top[zl, xl]) + 2):
                    blocks[(x0 + xl, y, z0 + zl)] = P("bricks")
                blocks[(x0 + xl, int(top[zl, xl]) + 2, z0 + zl)] = P("flower_pot")
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
                        # porch canopy over the door: a slab hood on brackets (Victorian/Edwardian), a tiled
                        # lean-to porch (1930s), a flat timber canopy (1960s)
                        fam = st.get("family")
                        if not lm and not shop_colour:
                            OX, OZ = X + dx, Z + dz
                            if fam in ("victorian_terrace", "victorian_villa", "grey_terrace", "riverside_villa"):
                                blocks[(OX, fl + 3, OZ)] = P("stone_brick_slab", type="top")
                            elif fam in ("interwar_semi", "interwar_detached", "postwar_council"):
                                for k in (-1, 0, 1):
                                    PX, PZ = OX + dz * k, OZ + dx * k
                                    blocks.setdefault((PX, fl + 3, PZ), P(stair, facing=OPP[name], half="bottom",
                                                                          shape="straight") if stair else P(full))
                            elif fam in ("estate_6070", "modern"):
                                for k in (-1, 0, 1):
                                    blocks.setdefault((OX + dz * k, fl + 3, OZ + dx * k), P("spruce_slab", type="bottom"))
                        if st.get("family") in BAY_FAMILIES and not lm and not shop_colour:
                            add_bay(P, blocks, inside, bid[z0:z1, x0:x1], dz_, dx_, dx, dz, x0, z0, fl,
                                    ey, P(WALLS[wname]), P(full), st["family"], stats)
                        break
    print("roofs:", stats)
    G["h_blocks"] = blocks
    front_paths(G, surface, bid)
    front_boundaries(G, P, bid, surface, buildings, styles, streets)
    # lowest roof block per cell: down to one above the lowest neighbour in the same building, so slopes are solid
    lo = roofY.astype(np.int32)
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        same = np.roll(bid, sh, ax) == bid
        lo = np.where(same & (bid > 0), np.minimum(lo, np.roll(roofY, sh, ax).astype(np.int32) + 1), lo)
    lo = np.minimum(lo, roofY)
    G.update(h_win=winstyle, h_up=upmat, h_roof=roofY, h_base=base, h_wall=wallmat, h_rooftop=roofmat, h_edge=edge_all, h_lo=lo.astype(np.int16),
             h_blocks=blocks)


BRICK_WALLS = []


def stamp_factory(G, P):
    BRICK_WALLS[:] = [P(WALLS[k]) for k in ("red_brick", "orange_brick", "buff_brick", "grey_brick")]
    sill_block = P("smooth_stone")
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
            up = G["h_up"][sl]
            b[:] = np.where((walls & (up > 0))[None] & (Y > fl + 3) & (Y < top), up[None], b)
            X = np.arange(16)[None, None, :] + x0
            Z = np.arange(16)[None, :, None] + z0
            ws = G["h_win"][sl][None]
            win = walls[None] & (ws == 0) & ((rel % 3 == 1) | (rel % 3 == 2)) & (((X + Z) % 4 == 1) | ((X + Z) % 4 == 2))
            # churches: tall narrow lancets; civic: tall mullioned pairs
            win |= walls[None] & (ws == 1) & (rel >= 2) & (rel <= 5) & ((X + Z) % 3 == 1)
            win |= walls[None] & (ws == 2) & ((rel % 4 == 1) | (rel % 4 == 2) | (rel % 4 == 3)) & ((X + Z) % 3 != 0)
            placed = win & (Y > fl) & (Y < top) & ((b == wall[None]) | (b == up[None]))
            b[:] = np.where(placed, glass, b)
            # pale sills under and lintels over the windows, on brick walls only
            brickish = np.isin(wall, BRICK_WALLS)[None]
            sill = np.zeros_like(placed)
            sill[1:] |= placed[:-1]          # cell above a window = lintel
            sill[:-1] |= placed[1:]          # cell below = sill
            b[:] = np.where(sill & ~placed & brickish & (b == wall[None]), sill_block, b)
            lo = G["h_lo"][sl].astype(np.int32)
            b[:] = np.where(inb[None] & (Y >= lo) & (Y <= top), rooftop[None], b)
        for x, y, z, blk in by_chunk.get((x0 // 16, z0 // 16), ()):
            if 0 <= y + 64 < b.shape[0]:
                b[y + 64, z - z0, x - x0] = blk
    return stamp


FRONT = {"grey_terrace": "wall", "riverside_villa": "hedge", "victorian_terrace": "wall", "victorian_villa": "wall", "cottage": "hedge", "interwar_semi": "hedge",
         "interwar_detached": "hedge", "postwar_council": "hedge", "estate_6070": None, "modern": "wall",
         "town": None}


def front_paths(G, surface, bid):
    """A paved path from each front door straight to the nearest pavement or road, over the front lawn.
    Front walls and hedges are laid on grass only, so they leave a gap where the path meets them."""
    road = np.isin(surface, (3, 4, 5))
    _, (rz, rx) = ndimage.distance_transform_edt(~road, return_indices=True)
    n = 0
    for x, _, z in G.get("doorsteps", []):
        if not (0 <= z < surface.shape[0] and 0 <= x < surface.shape[1]):
            continue
        tz, tx = rz[z, x], rx[z, x]
        steps = int(max(abs(tz - z), abs(tx - x)))
        if steps > 20:
            continue
        for k in range(steps + 1):
            cz = int(round(z + (tz - z) * k / max(steps, 1)))
            cx = int(round(x + (tx - x) * k / max(steps, 1)))
            if bid[cz, cx] or surface[cz, cx] not in (1, 9):
                break
            surface[cz, cx] = 9   # "paved": a front path, not pavement (front walls follow pavements only)
        n += 1
        # driveway: 3 wide, parallel to the path, 4 m to one side, across the front garden (track = gravel)
        if steps < 3:
            continue
        dz_, dx_ = (tz - z) / steps, (tx - x) / steps
        side = (-dx_, dz_)
        for off in (4, 5, 6):
            for k in range(steps + 1):
                cz = int(round(z + dz_ * k + side[0] * off))
                cx = int(round(x + dx_ * k + side[1] * off))
                if not (0 <= cz < surface.shape[0] and 0 <= cx < surface.shape[1]):
                    break
                if bid[cz, cx] or surface[cz, cx] not in (1, 7):
                    continue
                surface[cz, cx] = 7
        drives = G.setdefault("drives", [])
        drives.append((int(round(z + dz_ * (steps // 2) + side[0] * 5)), int(round(x + dx_ * (steps // 2) + side[1] * 5)),
                       abs(dx_) > abs(dz_)))
    print("front paths:", n)


def front_boundaries(G, P, bid, surface, buildings, styles, streets):
    """Front garden walls and hedges: on grass right beside the pavement or road, in front of houses, by family
    (Victorian brick walls, interwar privet hedges, open-plan 1960s lawns)."""
    road = np.isin(surface, (3, 4, 5))
    grass = surface == 1
    beside = grass & ndimage.binary_dilation(road) & (bid == 0)
    d, (iz, ix) = ndimage.distance_transform_edt(bid == 0, return_indices=True)
    near = beside & (d <= 14)
    zz, xx = np.nonzero(near)
    wall, cap = P("brick_wall"), None
    hedge = P("oak_leaves", persistent="true")
    blocks = G["h_blocks"]
    ground = G["ground"]
    n = 0
    walls_at = {}
    for z, x in zip(zz, xx):
        b = buildings[bid[iz[z, x], ix[z, x]]]
        if not b or b["tags"].get("building") not in HOUSE_KINDS:
            continue
        st = styles.get(streets.get(b["id"], ""), {})
        kind = FRONT.get(st.get("family"), None)
        if not kind or (x * 7 + z * 13) % 11 == 0:   # gaps for gates and drives
            continue
        g = int(ground[z, x])
        if kind == "wall":
            walls_at[(x, g + 1, z)] = True
        else:
            blocks.setdefault((x, g + 1, z), hedge)
            blocks.setdefault((x, g + 2, z), hedge)
        n += 1
    for k, v in connect(walls_at, "brick_wall", P).items():
        blocks.setdefault(k, v)
    print("front garden walls/hedges:", n)
    garden_fences(G, P, bid, surface, buildings, d, iz, ix, road)


def garden_fences(G, P, bid, surface, buildings, d, iz, ix, road):
    """Fences between neighbouring gardens: where the nearest house changes, on grass within 25 m of the
    houses, away from the road (fronts are open, walled or hedged instead)."""
    near = bid[iz, ix]
    house = np.zeros(len(buildings), bool)
    for i, b in enumerate(buildings):
        if b and b["tags"].get("building") in HOUSE_KINDS:
            house[i] = True
    ok = (surface == 1) & (bid == 0) & (d <= 25) & house[near]
    droad = ndimage.distance_transform_edt(~road)
    ok &= droad > droad[iz, ix] + 1          # behind the house (back gardens only; fronts stay open)
    split = np.zeros_like(ok)
    split[:, :-1] |= near[:, :-1] != near[:, 1:]
    split[:-1, :] |= near[:-1, :] != near[1:, :]
    cells = ok & split
    ground = G["ground"]
    blocks = G["h_blocks"]
    fence = {}
    for z, x in zip(*np.nonzero(cells)):
        fence[(int(x), int(ground[z, x]) + 1, int(z))] = True
    for k, v in connect(fence, "spruce_fence", P, wall=False).items():
        blocks.setdefault(k, v)
    print("garden fence blocks:", len(fence))
    garden_life(G, P, bid, surface, buildings, d, iz, ix, road, house, droad)


def garden_life(G, P, bid, surface, buildings, d, iz, ix, road, house, droad):
    """Front gardens: flower beds and shrubs along the house front. Back gardens: a shed near the far end."""
    rng = np.random.default_rng(71)
    ground = G["ground"]
    blocks = G["h_blocks"]
    grass = (surface == 1) & (bid == 0) & house[bid[iz, ix]]
    front = grass & (droad < droad[iz, ix]) & (d <= 2)
    flowers = [P("poppy"), P("dandelion"), P("blue_orchid"), P("allium"), P("oxeye_daisy"), P("cornflower"),
               P("pink_tulip"), P("red_tulip"), P("white_tulip"), P("lilac", half="lower")]
    shrub = P("azalea_leaves", persistent="true")
    nf = 0
    for z, x in zip(*np.nonzero(front)):
        r = rng.random()
        g = int(ground[z, x])
        if r < 0.45:
            f = flowers[rng.integers(len(flowers))]
            blocks.setdefault((int(x), g + 1, int(z)), f)
            if f == flowers[-1]:
                blocks.setdefault((int(x), g + 2, int(z)), P("lilac", half="upper"))
            nf += 1
        elif r < 0.6:
            blocks.setdefault((int(x), g + 1, int(z)), shrub)
    # sheds: for each house, the back-garden cell furthest from the road (within 25 m) gets a 3x2 shed
    back = grass & (droad > droad[iz, ix] + 6) & (d >= 8) & (d <= 25)
    owner = np.where(back, bid[iz, ix], 0)
    from scipy import ndimage
    idx = ndimage.maximum_position(np.where(back, d, 0), owner, index=np.arange(1, len(buildings)))
    wall, roof = P("spruce_planks"), P("dark_oak_slab", type="bottom")
    ns = 0
    for i, pos in enumerate(idx, start=1):
        if not house[i] or (i * 2654435761) % 10 >= 6:
            continue
        z, x = pos
        if not back[z, x]:
            continue
        g = int(ground[z, x])
        cells = [(z + a, x + b) for a in (0, 1) for b in (0, 1, 2)]
        if not all(0 <= a < back.shape[0] and 0 <= b < back.shape[1] and back[a, b] and owner[a, b] == i
                   for a, b in cells):
            continue
        for a, b in cells:
            blocks[(b, g + 1, a)] = wall
            blocks[(b, g + 2, a)] = wall
            blocks[(b, g + 3, a)] = roof
        blocks[(x + 1, g + 1, z)] = P("spruce_door", facing="north", half="lower", hinge="left", open="false")
        blocks[(x + 1, g + 2, z)] = P("spruce_door", facing="north", half="upper", hinge="left", open="false")
        ns += 1
    print(f"front-garden flowers: {nf}, sheds: {ns}")


def connect(cells, name, P, wall=True):
    """Gives walls/fences their side connections (Minecraft draws a lone post otherwise)."""
    out = {}
    for (x, y, z) in cells:
        sides = {}
        for side, (dx, dz) in DIRS.items():
            on = (x + dx, y, z + dz) in cells
            sides[side] = ("low" if on else "none") if wall else ("true" if on else "false")
        if wall:
            straight = (sides["north"] == sides["south"] == "low" and sides["east"] == sides["west"] == "none") or \
                       (sides["east"] == sides["west"] == "low" and sides["north"] == sides["south"] == "none")
            sides["up"] = "false" if straight else "true"
        out[(x, y, z)] = P(name, **sides)
    return out
