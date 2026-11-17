"""Extra things stamped into the world on top of terrain and buildings: spawn, trees, bridges,
the beach, the lock, swans. build_world calls setup() once, then each stamp per chunk."""
import json

import numpy as np

from box import E0, N1


def xz(e, n):
    return int(round(e - E0)), int(round(N1 - n))


def setup(G, P, lidar):
    G["stamps"] = []
    G["block_entities"] = {}
    import lock
    for x, y, z, lines in G.get("sign_texts", []):   # shop-name signs placed by the house builder
        pad = [""] * ((4 - len(lines)) // 2)
        G["block_entities"].setdefault((x // 16, z // 16), []).append(
            lock.sign_entity(x, y, z, (pad + [l.replace('"', "'") for l in lines])[:4]))
    # spawn on the north bank at Caversham Bridge
    br = [b for b in json.load(open("build/bridges.json")) if "Caversham Bridge" in (b["tags"].get("name"), b["tags"].get("bridge:name"))]
    e, n = np.mean([p for b in br for p in b["pts"]], axis=0)
    # nearest open grass to the bridge's north end, facing the river
    bx, bz = xz(e, n)
    ok = G["mask"] & (G["water"] == -999) & (G["building"] == 0) & (G["surface"] == 1)
    zz, xx = np.nonzero(ok[bz - 120:bz, bx - 60:bx + 60])
    i = np.argmin((zz - 120 + 25) ** 2 + (xx - 60) ** 2)
    x, z = int(xx[i] + bx - 60), int(zz[i] + bz - 120)
    G["spawn"] = (x, int(G["ground"][z, x]) + 1, z)

    bridge_setup(G, lidar)
    # bridge_setup raises some road: grade the roads again so those lifts ease in, before anything stands on them
    from grade import road_grade
    rd = np.isin(G["surface"], (3, 4, 5)) & G["mask"] & (G["water"] == -999)
    G["ground"][:] = np.floor(road_grade(G["ground"].astype(np.float32), rd, 0.5) + 0.5)
    import lock
    lock.setup(G, P, json.load(open("build/levels.json")))
    G["stamps"].append(beach(G, P))
    G["stamps"].append(bridge_stamp(G, P))
    G["stamps"].append(swans(G, P))
    G["stamps"].extend(streets(G, P))
    G["stamps"].append(credits_sign(G, P))
    G["stamps"].append(barriers(G, P))
    G["stamps"].append(structures(G, P, lidar))
    moorings(G, P)
    animals(G, P)
    G["stamps"].append(furniture(G, P))
    G["stamps"].append(cars(G, P))
    G["stamps"].append(christchurch_mast(G, P))
    G["stamps"].append(churchyards(G, P))
    G["stamps"].append(street_signs(G, P))
    G["stamps"].append(weirs(G, P))
    G["stamps"].append(leisure(G, P))
    G["stamps"].append(car_parks(G, P))
    G["stamps"].insert(1, countryside(G, P))
    G["stamps"].append(allotments(G, P))
    G["stamps"].append(crossings(G, P))
    G["stamps"].append(island_paths(G, P))
    G["stamps"].append(winter_wonderland(G, P))
    G["stamps"].append(data_signs(G, P))
    river_boats(G)
    G["stamps"].append(barges(G, P))
    G["stamps"].append(cinema(G, P))
    G["stamps"].append(school_treasure(G, P))
    G["stamps"].append(xmas_centre(G, P))
    marina(G, P)
    G["stamps"].insert(0, waterside(G, P))   # first, so swans, boats-in-lanes and bridges win
    G["trees"] = find_trees(G, lidar["vom"])
    for bx0, bz0, bx1, bz1 in G.get("no_trees", []):           # keep crowns off the cinema screen, treasure trees
        t = G["trees"]
        r = t[:, 4]
        G["trees"] = t[~((t[:, 0] >= bx0 - r) & (t[:, 0] <= bx1 + r) & (t[:, 1] >= bz0 - r) & (t[:, 1] <= bz1 + r))]
    print("trees:", len(G["trees"]))
    G["stamps"].append(tree_stamp(G, P))


# ---- trees from the EA vegetation object model ------------------------------------------------

def find_trees(G, vom):
    """One tree per canopy peak: (x, z, ground y, height, crown radius, kind)."""
    from scipy import ndimage
    v = np.nan_to_num(vom, nan=0.0)
    v = ndimage.gaussian_filter(v, 1.0)
    peak = (v == ndimage.maximum_filter(v, size=7)) & (v >= 3.0)
    peak &= G["mask"] & (G["building"] == 0) & (G["water"] == -999) & (G["surface"] != 10)   # no trees on the beach
    # a street tree's canopy peak can sit over the road: move its trunk to the nearest verge/garden cell
    hard = np.isin(G["surface"], (3, 4, 5, 6, 8, 9, 18))
    zs, xs = np.nonzero(peak)
    hs = v[zs, xs]
    soft = G["mask"] & ~hard & (G["building"] == 0) & (G["water"] == -999)
    _, (sz, sx) = ndimage.distance_transform_edt(~soft, return_indices=True)
    moved = hard[zs, xs]
    zs, xs = np.where(moved, sz[zs, xs], zs), np.where(moved, sx[zs, xs], xs)
    print("street trees moved off the road:", int(moved.sum()))
    # crown radius: how far the canopy stays above half the peak height, sampled on 8 rays
    r = np.full(len(zs), 1.0)
    for dz, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        step = np.hypot(dz, dx)
        reach = np.zeros(len(zs))
        alive = np.ones(len(zs), bool)
        for k in range(1, 9):
            zz = np.clip(zs + dz * k, 0, v.shape[0] - 1)
            xx = np.clip(xs + dx * k, 0, v.shape[1] - 1)
            alive &= v[zz, xx] > hs * 0.5
            reach[alive] = k * step
        r += reach / 8
    r = np.clip(r, 1.5, 7.0)
    rng = np.random.default_rng(7)
    kind = rng.choice(4, len(zs), p=[0.6, 0.2, 0.12, 0.08])   # oak, birch, spruce, dark oak
    g = G["ground"][zs, xs]
    return np.stack([xs, zs, g, np.round(hs), r, kind], axis=1)


def tree_stamp(G, P):
    logs = [P("oak_log"), P("birch_log"), P("spruce_log"), P("dark_oak_log")]
    leaves = [P(n, persistent="true") for n in ("oak_leaves", "birch_leaves", "spruce_leaves", "dark_oak_leaves")]
    buckets = {}
    for t in G["trees"]:
        x, z, r = int(t[0]), int(t[1]), t[4]
        for cz in range((z - int(r) - 1) // 16, (z + int(r) + 1) // 16 + 1):
            for cx in range((x - int(r) - 1) // 16, (x + int(r) + 1) // 16 + 1):
                buckets.setdefault((cx, cz), []).append(t)
    Y_MIN = -64

    def stamp(b, x0, z0, g, w, s, Y):
        X = np.arange(16)[None, None, :] + x0
        Z = np.arange(16)[None, :, None] + z0
        for x, z, gy, h, r, kind in buckets.get((x0 // 16, z0 // 16), ()):
            x, z, gy, h, kind = int(x), int(z), int(gy), int(h), int(kind)
            if kind == 2:   # spruce: a cone
                cy = gy + h * 0.55
                d = np.hypot(X - x, Z - z)
                cone = (Y > gy + h * 0.25) & (Y <= gy + h) & (d <= r * (gy + h - Y) / (h * 0.75) + 0.5)
                leaf = cone
            else:
                ry = max(2.0, min(r * 1.1, h * 0.35))
                cy = gy + h - ry                    # crown top at the measured height, rounded not flat
                q = ((X - x) ** 2 + (Z - z) ** 2) / r ** 2 + (Y - cy) ** 2 / ry ** 2
                # ragged edge: the outer shell is patchy so neighbouring crowns don't merge into one sheet
                noise = ((X * 73 + Y * 37 + Z * 151 + x * 7) % 10) / 10.0
                leaf = (q <= 0.7) | ((q <= 1.0) & (noise < 0.6))
            put = leaf & (b == 0)
            b[put] = leaves[kind]
            if x0 <= x < x0 + 16 and z0 <= z < z0 + 16:
                top = int(min(gy + h - 1, max(cy, gy + 2)))
                lx, lz = x - x0, z - z0
                ys = np.arange(gy + 1, top + 1) - Y_MIN
                ys = ys[(ys >= 0) & (ys < b.shape[0])]
                col = b[ys, lz, lx]
                b[ys, lz, lx] = np.where((col == 0) | np.isin(col, leaves), logs[kind], col)
    return stamp


# ---- bridges: decks at the DSM height along each OSM bridge way ----------------------------

BRIDGE_WIDTH = {"primary": 11, "secondary": 10, "tertiary": 8, "residential": 6, "unclassified": 6,
                "service": 4, "footway": 3, "cycleway": 4, "path": 3, "pedestrian": 4, "steps": 3}


def bridge_setup(G, lidar):
    from scipy import ndimage
    dsm = np.nan_to_num(lidar["dsm"], nan=-999.0)
    Hh, Ww = G["mask"].shape
    deck = np.full((Hh, Ww), -999, np.int32)
    kind = np.zeros((Hh, Ww), np.int8)
    centre = np.zeros((Hh, Ww), bool)
    arch = np.full((Hh, Ww), -999, np.int32)   # underside of the arch (fill from here up to the deck)
    FOOT = ("footway", "cycleway", "path", "pedestrian", "steps")
    # road bridges first: a footbridge mapped alongside a road bridge (its pavement) takes the road's deck
    # rather than sitting beside it at its own height
    for br in sorted(json.load(open("build/bridges.json")), key=lambda b: b["tags"].get("highway") in FOOT):
        t = br["tags"]
        hw = t.get("highway")
        if hw not in BRIDGE_WIDTH:
            continue
        pts = np.array([xz(e, n) for e, n in br["pts"]], float)
        seg = np.diff(pts, axis=0)
        L = np.hypot(seg[:, 0], seg[:, 1])
        samples = np.concatenate([pts[i] + seg[i] * np.linspace(0, 1, max(2, int(L[i] * 2)))[:, None]
                                  for i in range(len(seg))])
        si = np.round(samples).astype(int)
        ok = (si[:, 0] >= 0) & (si[:, 0] < Ww) & (si[:, 1] >= 0) & (si[:, 1] < Hh)
        if not ok.all() or not G["mask"][si[:, 1], si[:, 0]].any():
            continue
        # the deck is the low part of the DSM across the bridge (parapets, lamps and cars stick up)
        w = BRIDGE_WIDTH[hw]
        ys = []
        for x, z in si:
            win = dsm[max(0, z - 2):z + 3, max(0, x - 2):x + 3]
            win = win[win > -999]
            ys.append(np.percentile(win, 30) if win.size else -999)
        ys = ndimage.median_filter(np.array(ys), size=15, mode="nearest")
        # ease the deck down to the road at both ends: no steeper than 1 block per 4 m (samples are 0.5 m)
        gs = np.array([G["ground"][z, x] if 0 <= z < Hh and 0 <= x < Ww else -999 for x, z in si], float)
        dry = np.array([0 <= z < Hh and 0 <= x < Ww and G["water"][z, x] == -999 for x, z in si])

        def street(p, d):
            """Ground of the street just past a bridge end: first dry cell within 12 m out along the road."""
            for r in range(1, 13):
                X, Z = (p + d * r).round().astype(int)
                if 0 <= Z < Hh and 0 <= X < Ww and G["mask"][Z, X] and G["water"][Z, X] == -999:
                    return G["ground"][Z, X]
            return None
        k = np.arange(len(ys))
        u0 = (samples[0] - samples[1]) / max(np.hypot(*(samples[0] - samples[1])), 1e-9)
        u1 = (samples[-1] - samples[-2]) / max(np.hypot(*(samples[-1] - samples[-2])), 1e-9)
        g0, g1 = street(samples[0], u0), street(samples[-1], u1)
        if g0 is not None:                                       # ease down to the street at each end
            ys = np.minimum(ys, g0 + 1 + k / 8)
        if g1 is not None:
            ys = np.minimum(ys, g1 + 1 + (len(ys) - 1 - k) / 8)
        ys = np.where(dry, np.maximum(ys, gs), ys)
        ys = np.round(ys).astype(int)
        r = w / 2
        # arches: over each run of water under the bridge, one arch per ≤45 m, springing from the water at the
        # piers and rising to 2 below the deck at mid-span (road bridges only; footbridges are light girders)
        wet = np.array([G["water"][z, x] > -999 for x, z in si])
        soffit = np.full(len(si), -999)
        if hw not in ("footway", "cycleway", "path", "pedestrian", "steps") and wet.any():
            i = 0
            while i < len(wet):
                if not wet[i]:
                    i += 1
                    continue
                j = i
                while j < len(wet) and wet[j]:
                    j += 1
                n = max(1, int(np.ceil((j - i) / 2 / 45)))           # samples are 0.5 m apart
                bounds = np.linspace(i, j, n + 1)
                for a, b_ in zip(bounds[:-1], bounds[1:]):
                    for k in range(int(a), int(b_)):
                        t = (k - a) / max(b_ - a, 1)
                        wl = G["water"][si[k, 1], si[k, 0]]
                        soffit[k] = int(round(wl + (ys[k] - 2 - wl) * (1 - (2 * t - 1) ** 4)))
                i = j
        for (x, z), y, so in zip(samples, ys, soffit):
            for dz in range(-int(r) - 1, int(r) + 2):
                for dx in range(-int(r) - 1, int(r) + 2):
                    if dx * dx + dz * dz <= r * r:
                        X, Z = int(round(x + dx)), int(round(z + dz))
                        if hw in FOOT and 0 <= X < Ww and 0 <= Z < Hh:
                            near = np.s_[max(0, Z - 3):Z + 4, max(0, X - 3):X + 4]
                            if (kind[near] == 1).any():          # a road's pavement: flush with the road deck
                                rz_, rx_ = np.nonzero(kind[near] == 1)
                                j_ = np.argmin((rz_ + max(0, Z - 3) - Z) ** 2 + (rx_ + max(0, X - 3) - X) ** 2)
                                rd_ = deck[near][rz_[j_], rx_[j_]]       # the nearest road cell's deck
                                if kind[Z, X] != 1:
                                    deck[Z, X], arch[Z, X], kind[Z, X] = rd_, so, 2
                                continue
                        if 0 <= X < Ww and 0 <= Z < Hh and y > deck[Z, X]:
                            deck[Z, X] = y
                            arch[Z, X] = so
                            kind[Z, X] = 2 if hw in ("footway", "cycleway", "path", "pedestrian", "steps") else 1
            centre[int(round(z)), int(round(x))] = True
    # where the deck is just one above the road, raise the road instead (its ramps then come from the road
    # slab rule); only where it is clear of the ground does the deck need building
    lift = (deck == G["ground"] + 1) & G["mask"] & (G["water"] == -999) & (kind == 1)
    G["ground"][lift] += 1
    G["surface"][lift] = 3
    deck[(deck <= G["ground"] + 1) | ~G["mask"]] = -999
    inb = deck > -999
    edge = inb & ~ndimage.binary_erosion(inb)
    # no parapet where the street carries on off the deck, or it walls the road off like a fort
    street = np.isin(G["surface"], (3, 4, 5)) & G["mask"] & (G["water"] == -999) & ~inb
    edge &= ~ndimage.binary_dilation(street)
    G.update(br_deck=deck, br_kind=kind, br_edge=edge, br_arch=arch)
    print("bridge cells:", int(inb.sum()))


def bridge_stamp(G, P):
    road, foot, under = P("gray_concrete"), P("smooth_stone"), P("stone_bricks")
    wall, rail = P("stone_brick_wall"), P("iron_bars")
    concrete = P("light_gray_concrete")
    Y_MIN = -64

    slab = P("polished_deepslate_slab", type="bottom")
    Hh, Ww = G["mask"].shape

    def stamp(b, x0, z0, g, w, s, Y):
        d = G["br_deck"][z0:z0 + 16, x0:x0 + 16]
        if d.shape != (16, 16) or not (G["br_deck"][max(0, z0 - 1):z0 + 17, max(0, x0 - 1):x0 + 17] > -999).any():
            return                                               # (a chunk touching a deck still gets its ramps)
        k = G["br_kind"][z0:z0 + 16, x0:x0 + 16]
        e = G["br_edge"][z0:z0 + 16, x0:x0 + 16]
        on = d > -999
        top = np.where(k == 2, foot, road)
        b[:] = np.where(on & (Y > d) & (Y <= d + 4), 0, b)     # headroom: no leaves on the road
        b[:] = np.where(on & (Y == d), top[None], b)
        b[:] = np.where(on & (Y >= d - 1) & (Y < d), under, b)
        a = G["br_arch"][z0:z0 + 16, x0:x0 + 16]
        b[:] = np.where(on & (a > -999) & (Y >= a) & (Y < d - 1), concrete, b)
        b[:] = np.where(on & e & (Y == d + 1), np.where(k == 2, rail, wall)[None], b)
        # last, or the headroom clearing wipes them: a half slab on the lower side of each one-block step makes a ramp
        za, xa = max(0, z0 - 1), max(0, x0 - 1)
        D = G["br_deck"][za:z0 + 17, xa:x0 + 17]
        Gd = G["ground"][za:z0 + 17, xa:x0 + 17].astype(int)
        R = np.isin(G["surface"][za:z0 + 17, xa:x0 + 17], (3, 4))
        Hs = np.where(D > -999, D, np.where(R, Gd, -999))       # walking height: deck, or road
        oz, ox = z0 - za, x0 - xa
        for zz in range(16):
            for xx in range(16):
                h = Hs[zz + oz, xx + ox]
                if h == -999:
                    continue
                nb = [Hs[zz + oz + dz_, xx + ox + dx_] for dz_, dx_ in ((1, 0), (-1, 0), (0, 1), (0, -1))
                      if 0 <= zz + oz + dz_ < Hs.shape[0] and 0 <= xx + ox + dx_ < Hs.shape[1]]
                ondeck = D[zz + oz, xx + ox] > -999
                if ondeck and e[zz, xx]:
                    continue                                     # the parapet stands there
                if h + 1 in nb:
                    yy = h + 1 + 64
                    if 0 <= yy < b.shape[0] and b[yy, zz, xx] == 0:   # only into open air
                        b[yy, zz, xx] = slab
    return stamp


# ---- swans on the Thames (block-built: no swan mob without mods) ---------------------------

def swans(G, P, n=14):
    from scipy import ndimage
    water = G["water"] > -999
    thames = water & (G["water"] >= 35) & (G["water"] <= 36)
    dist = ndimage.distance_transform_edt(thames)
    clear = (dist >= 8) & (G["br_deck"] == -999)
    clear &= ndimage.binary_erosion(G["br_deck"] == -999, iterations=20)
    zs, xs = np.nonzero(clear)
    rng = np.random.default_rng(11)
    picks = []
    for i in rng.permutation(len(zs)):
        x, z = xs[i], zs[i]
        if all(abs(x - a) + abs(z - c) > 120 for a, c in picks):
            picks.append((x, z))
        if len(picks) >= n:
            break
    wool, beak, eye = P("white_wool"), P("orange_concrete"), P("black_concrete")
    blocks = {}
    for x, z in picks:
        lvl = int(G["water"][z, x])
        d = 1 if rng.random() < 0.5 else -1          # facing east or west
        for k in range(3):
            blocks[(x - d * k, lvl, z)] = wool       # body sits in the water
        blocks[(x - d * 2, lvl + 1, z)] = wool       # tail
        blocks[(x, lvl + 1, z)] = wool               # neck
        blocks[(x, lvl + 2, z)] = wool               # head
        blocks[(x + d, lvl + 2, z)] = beak
        # a cygnet or two following some of them
        if rng.random() < 0.5:
            blocks[(x - d * 5, lvl, z)] = P("light_gray_wool")
    print("swans:", len(picks))
    return block_stamp(blocks)


def block_stamp(blocks):
    by_chunk = {}
    for (x, y, z), blk in blocks.items():
        by_chunk.setdefault((x // 16, z // 16), []).append((x, y, z, blk))

    def stamp(b, x0, z0, g, w, s, Y):
        for x, y, z, blk in by_chunk.get((x0 // 16, z0 // 16), ()):
            b[y + 64, z - z0, x - x0] = blk
    return stamp


# ---- Caversham Lakes beach (as in docs/caversham-lakes-beach.webp) ----------------------

BEACH_AT = (474040, 174700)   # NW shore of the island lake between the rowing lake and the Thames (BNG);
BEACH_LAKE = (474095, 174635)  # a point in that lake. The user: the beach is on the river side of the lakes


def beach(G, P):
    from scipy import ndimage
    px, pz = xz(*BEACH_AT)
    water = G["water"] > -999
    win = np.s_[pz - 250:pz + 250, px - 250:px + 250]
    wz, wx = np.nonzero(water[win])
    wz += pz - 250
    wx += px - 250
    # the shore point nearest the venue, on a lake (not the Thames)
    lab, _ = ndimage.label(water)
    lake = lab == lab[xz(*BEACH_LAKE)[::-1]]
    land = G["mask"] & ~water
    shore = lake & ndimage.binary_dilation(land)
    sz, sx = np.nonzero(shore[win])
    sz += pz - 250
    sx += px - 250
    i = np.argmin((sx - px) ** 2 + (sz - pz) ** 2)
    cx, cz = int(sx[i]), int(sz[i])
    lvl = int(G["water"][cz, cx])
    Z, X = np.ogrid[:G["mask"].shape[0], :G["mask"].shape[1]]
    near = (X - cx) ** 2 + (Z - cz) ** 2
    sand = land & (near <= 35 ** 2)
    shallow = lake & (near <= 35 ** 2) & (G["water"] == lvl)
    d_land = ndimage.distance_transform_edt(~land)
    d_water = ndimage.distance_transform_edt(~shallow)
    # sand slopes gently down to the water and on out under it: 1 block per 6 m
    G["ground"][sand] = np.minimum(G["ground"][sand], lvl + 1 + (d_water[sand] // 8).astype(np.int16))
    G["surface"][sand] = 10   # sand
    G["building"][sand] = 0
    G["h_wall"][sand] = 0
    G["ground"][shallow] = np.maximum(G["ground"][shallow], lvl - 1 - (d_land[shallow] // 6).astype(np.int16))
    G["ground"][shallow] = np.minimum(G["ground"][shallow], lvl - 1)
    G["sandy_bed"] = shallow
    # props: loungers and parasols on the sand, huts at the back, a buoy rope round the swim area
    rng = np.random.default_rng(5)
    blocks = {}
    lounger = P("smooth_quartz_slab")
    pole = P("oak_fence")
    canopies = [P("red_wool"), P("blue_wool"), P("yellow_wool"), P("white_wool"), P("lime_wool")]
    zs, xs = np.nonzero(sand & (d_water <= 12) & (d_water >= 3))
    placed = []
    for k in rng.permutation(len(zs))[:400]:
        x, z = int(xs[k]), int(zs[k])
        if any(abs(x - a) < 5 and abs(z - c) < 5 for a, c in placed):
            continue
        placed.append((x, z))
        y = int(G["ground"][z, x]) + 1
        if len(placed) % 3:
            blocks[(x, y, z)] = lounger
            blocks[(x + 1, y, z)] = lounger
        else:
            blocks[(x, y, z)] = pole
            blocks[(x, y + 1, z)] = pole
            c = canopies[len(placed) % len(canopies)]
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    blocks[(x + dx, y + 2, z + dz)] = c
        if len(placed) >= 18:
            break
    zs, xs = np.nonzero(sand & (d_water >= 18) & (d_water <= 22))
    huts = []
    walls_c = [P("spruce_planks"), P("birch_planks"), P("cyan_terracotta"), P("orange_terracotta")]
    for k in rng.permutation(len(zs)):
        x, z = int(xs[k]), int(zs[k])
        if any(abs(x - a) < 6 and abs(z - c) < 6 for a, c in huts):
            continue
        huts.append((x, z))
        y = int(G["ground"][z, x])
        wc = walls_c[len(huts) % len(walls_c)]
        for dx in range(3):
            for dz in range(3):
                G["ground"][z + dz, x + dx] = y
                for dy in range(1, 4):
                    edge = dx in (0, 2) or dz in (0, 2)
                    blocks[(x + dx, y + dy, z + dz)] = wc if edge and not (dx == 1 and dz == 0 and dy < 3) else 0
                blocks[(x + dx, y + 4, z + dz)] = P("dark_oak_slab")
        if len(huts) >= 4:
            break
    ring = shallow & (d_land >= 14) & (d_land < 15)
    zs, xs = np.nonzero(ring)
    buoys = [P("red_wool"), P("white_wool")]
    for k, (x, z) in enumerate(zip(xs, zs)):
        if k % 3 == 0:
            blocks[(int(x), lvl, int(z))] = buoys[(k // 3) % 2]
    print(f"beach at x {cx} z {cz} (level {lvl}): {int(sand.sum())} m² sand, {len(placed)} props, {len(huts)} huts")
    G["beach_spot"] = (cx, lvl + 2, cz)
    return block_stamp(blocks)


# ---- street detail: centre lines on main roads, lamp posts, credits sign at spawn ---------------

MARKED = {"primary", "secondary", "tertiary"}
LIT = {"primary": 9, "secondary": 8, "tertiary": 7, "residential": 6, "unclassified": 6}


def streets(G, P):
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    line_cells = np.zeros((Hh, Ww), bool)
    blocks = {}
    post, lamp = P("dark_oak_fence"), P("lantern")
    road_cls = (3, 4)   # surfaces: road, minor_road
    lamps = 0
    for ln in osm["lines"]:
        t = ln["tags"]
        hw = t.get("highway")
        if hw not in LIT or (t.get("bridge") not in (None, "no")) or t.get("tunnel") not in (None, "no"):
            continue
        pts = np.array([xz(e, n) for e, n in ln["pts"]], float)
        walked = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            seg = b - a
            L = float(np.hypot(*seg))
            if L == 0:
                continue
            d = seg / L
            normal = np.array([-d[1], d[0]])
            for k in np.arange(0, L, 1.0):
                p = a + d * k
                x, z = int(round(p[0])), int(round(p[1]))
                s = walked + k
                if 0 <= x < Ww and 0 <= z < Hh and G["mask"][z, x]:
                    if hw in MARKED and (s % 6) < 3 and G["surface"][z, x] in road_cls:
                        line_cells[z, x] = True
                    if s % 25 < 1:
                        side = 1 if int(s // 25) % 2 else -1          # alternate sides, like real streets
                        q = p + normal * side * (LIT[hw] / 2 + 1)
                        lx, lz = int(round(q[0])), int(round(q[1]))
                        if (0 <= lx < Ww and 0 <= lz < Hh and G["mask"][lz, lx] and G["water"][lz, lx] == -999
                                and G["building"][lz, lx] == 0 and G["surface"][lz, lx] not in road_cls):
                            g = int(G["ground"][lz, lx])
                            for dy in (1, 2, 3):
                                blocks[(lx, g + dy, lz)] = post
                            blocks[(lx, g + 4, lz)] = lamp
                            lamps += 1
            walked += L
    G["road_line"] = line_cells
    white = P("white_concrete")

    def stamp(b, x0, z0, g, w, s, Y):
        m = G["road_line"][z0:z0 + 16, x0:x0 + 16]
        if m.shape == (16, 16) and m.any():
            b[:] = np.where(m[None] & (Y == g), white, b)
    print("street lamps:", lamps, "centre-line cells:", int(line_cells.sum()))
    return [stamp, block_stamp(blocks)]


def credits_sign(G, P):
    x, y, z = G["spawn"]
    sx, sz = x + 2, z
    import lock
    G["block_entities"].setdefault((sx // 16, sz // 16), []).append(
        lock.sign_entity(sx, y, sz, ["Cavcraft", "© OpenStreetMap", "© Environment", "Agency, OGL v3"]))
    return block_stamp({(sx, y, sz): P("oak_sign", rotation=8)})


# ---- hedges, walls and fences from OSM barrier lines -----------------------------------------

def barriers(G, P):
    osm = json.load(open("build/osm.json"))
    kinds = {"hedge": (P("oak_leaves", persistent="true"), 2), "wall": (P("cobblestone_wall"), 2),
             "fence": (P("oak_fence"), 1), "retaining_wall": (P("cobblestone_wall"), 1)}
    Hh, Ww = G["mask"].shape
    blocks = {}
    conn = {kinds["wall"][0]: {}, kinds["fence"][0]: {}}
    for ln in osm["lines"]:
        k = kinds.get(ln["tags"].get("barrier"))
        if not k:
            continue
        blk, height = k
        pts = np.array([xz(e, n) for e, n in ln["pts"]], float)
        for a, b in zip(pts[:-1], pts[1:]):
            L = max(1, int(np.hypot(*(b - a)) * 2))
            for t in np.linspace(0, 1, L + 1):
                x, z = (int(round(v)) for v in a + (b - a) * t)
                if not (0 <= x < Ww and 0 <= z < Hh) or not G["mask"][z, x]:
                    continue
                if G["water"][z, x] != -999 or G["building"][z, x] or G["surface"][z, x] in (3, 4, 9):
                    continue    # never across water, houses or roads (gaps where OSM crosses them)
                g = int(G["ground"][z, x])
                for dy in range(1, height + 1):
                    if blk in conn:
                        conn[blk][(x, g + dy, z)] = True
                    else:
                        blocks[(x, g + dy, z)] = blk
    import houses
    blocks.update(houses.connect(conn[kinds["wall"][0]], "cobblestone_wall", P))
    blocks.update(houses.connect(conn[kinds["fence"][0]], "oak_fence", P, wall=False))
    print("barrier blocks:", len(blocks))
    return block_stamp(blocks)


# ---- structures that aren't houses: the Emmer Green water tower, war memorial ---------------

def structures(G, P, lidar):
    dsm = np.nan_to_num(lidar["dsm"], nan=0.0)
    blocks = {}
    # water tower (Phillimore Road photos): a pale concrete drum on a narrow shaft
    wt = json.load(open("build/buildings.json"))
    idx = next(i for i, b in enumerate(wt) if b and b["id"] == "w171331924")
    zz, xx = np.nonzero(G["building"] == idx)
    cx, cz = int(round(xx.mean())), int(round(zz.mean()))
    g = int(G["ground"][cz, cx])
    top = int(round(np.percentile(dsm[zz, xx], 90)))
    top = max(top, g + 18)
    for y in range(g + 1, top + 1):
        tank = y > top - 7
        r = 5.5 if tank else 2.5
        for dz in range(-6, 7):
            for dx in range(-6, 7):
                d = (dx * dx + dz * dz) ** 0.5
                if d <= r:
                    shell = d > r - 1.2 or y in (top, top - 7)
                    blocks[(cx + dx, y, cz + dz)] = P("white_concrete" if tank else "light_gray_concrete") if shell \
                        else P("air")
    for dx, dz in ((0, 3), (0, -3), (3, 0), (-3, 0)):
        blocks[(cx + dx, top - 3, cz + dz)] = P("white_concrete")
    blocks[(cx, top + 1, cz)] = P("lightning_rod")
    G["building"][cz - 7:cz + 8, cx - 7:cx + 8] = 0
    G["h_wall"][cz - 7:cz + 8, cx - 7:cx + 8] = 0
    # Caversham war memorial, Christchurch Meadows (Commons photos): a tall pale-stone column with a cross carved
    # near the top, on a two-step plinth on an octagonal paved base, poppy wreaths at its foot
    mx, mz = 3269, 3660
    gm = int(G["ground"][mz, mx])
    for dx in range(-4, 6):
        for dz in range(-4, 6):
            if abs(dx - 0.5) + abs(dz - 0.5) <= 6.5:                 # octagonal flagstones
                blocks[(mx + dx, gm, mz + dz)] = P("smooth_stone")
    for dx in range(-2, 4):                                       # lower step
        for dz in range(-2, 4):
            blocks[(mx + dx, gm + 1, mz + dz)] = P("smooth_sandstone_slab", type="bottom")
    for dx in range(-1, 3):                                       # upper step / plinth
        for dz in range(-1, 3):
            blocks[(mx + dx, gm + 1, mz + dz)] = P("smooth_sandstone")
            blocks[(mx + dx, gm + 2, mz + dz)] = P("cut_sandstone")
    for y in range(gm + 3, gm + 12):                              # the 2 x 2 column
        for dx in (0, 1):
            for dz in (0, 1):
                blocks[(mx + dx, y, mz + dz)] = P("smooth_sandstone")
    for dx in (0, 1):                                             # carved cross near the top, on every face
        for dz in (0, 1):
            blocks[(mx + dx, gm + 10, mz + dz)] = P("chiseled_sandstone")
    for dx in (0, 1):
        for dz in (0, 1):
            blocks[(mx + dx, gm + 12, mz + dz)] = P("smooth_sandstone_slab", type="bottom")
    for (dx, dz) in ((-1, 0), (-1, 1), (2, 0), (2, 1), (0, -1), (1, -1), (0, 2), (1, 2)):
        blocks[(mx + dx, gm + 3, mz + dz)] = P("red_carpet")         # wreaths on the plinth (poppies need soil)
    for dx, dz in ((-2, 0), (-2, 1), (3, 1), (0, 3)):
        blocks[(mx + dx, gm + 2, mz + dz)] = P("red_carpet")
    print(f"water tower at {cx},{cz} top y {top}; war memorial at {mx},{mz}")
    return block_stamp(blocks)


# ---- moored boats along the Thames banks (vanilla boats; Fry's Island and the town reach are full of them) ----

def moorings(G, P, n=70):
    from scipy import ndimage
    import lock
    w = G["water"]
    thames = (w == 35) | (w == 36)
    land = G["mask"] & (w == -999)
    bank = thames & ndimage.binary_dilation(land) & ~ndimage.binary_dilation(G["br_deck"] > -999, iterations=10)
    lockzone = np.zeros_like(bank)
    lockzone[4140:4200, 4010:4110] = True
    bank &= ~lockzone
    zs, xs = np.nonzero(bank)
    rng = np.random.default_rng(3)
    picks = []
    for i in rng.permutation(len(zs)):
        x, z = xs[i], zs[i]
        if all(abs(x - a) + abs(z - c) > 18 for a, c in picks):
            picks.append((x, z))
        if len(picks) >= n:
            break
    kinds = ["oak", "spruce", "birch", "dark_oak", "mangrove", "cherry"]
    for k, (x, z) in enumerate(picks):
        # parallel to the bank: face along the shore
        gz, gx = np.gradient(land[z - 2:z + 3, x - 2:x + 3].astype(float))
        rot = float(np.degrees(np.arctan2(gz[2, 2], gx[2, 2])))
        b = lock.boat(x + 0.5, w[z, x] + 0.9, z + 0.5, rot)
        b["Type"] = kinds[k % len(kinds)]
        lock.add_entity(G, b)
    print("moored boats:", len(picks))


# ---- street furniture from OSM points ----------------------------------------------------------

def furniture(G, P):
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    blocks = {}
    n = {}
    red = P("red_concrete")
    for nd in osm["nodes"]:
        t = nd["tags"]
        x, z = xz(*nd["pt"])
        if not (0 <= z < Hh and 0 <= x < Ww) or not G["mask"][z, x] or G["water"][z, x] != -999:
            continue
        g = int(G["ground"][z, x])
        a, hw, bar = t.get("amenity"), t.get("highway"), t.get("barrier")
        kind = None
        if a == "post_box":
            blocks[(x, g + 1, z)] = red
            blocks[(x, g + 2, z)] = P("red_concrete")
            blocks[(x, g + 3, z)] = P("red_terracotta")          # Royal Mail pillar box with a darker cap
            kind = "post box"
        elif a == "bench":
            blocks[(x, g + 1, z)] = P("dark_oak_stairs", facing="north", half="bottom", shape="straight")
            kind = "bench"
        elif a == "waste_basket":
            blocks[(x, g + 1, z)] = P("composter", level=0)
            kind = "bin"
        elif hw == "bus_stop":
            for dy in (1, 2, 3):
                blocks[(x, g + dy, z)] = P("iron_bars", north="false", south="false", east="false", west="false")
            blocks[(x, g + 4, z)] = P("red_concrete")
            if t.get("shelter") == "yes":
                for dx in (-1, 0, 1):
                    for dy in (1, 2):
                        blocks[(x + dx, g + dy, z + 1)] = P("glass_pane", east="true", west="true", north="false",
                                                            south="false")
                    blocks[(x + dx, g + 3, z + 1)] = P("smooth_stone_slab", type="bottom")
                    blocks[(x + dx, g + 3, z)] = P("smooth_stone_slab", type="bottom")
            kind = "bus stop"
        elif t.get("man_made") == "telephone_box" or a == "telephone":
            for dy in (1, 2):
                for dx, dz in ((0, 0),):
                    blocks[(x, g + dy, z)] = P("red_stained_glass")
            blocks[(x, g + 3, z)] = red
            kind = "phone box"
        elif bar == "bollard":
            blocks[(x, g + 1, z)] = P("polished_blackstone_wall", up="true", north="none", south="none",
                                      east="none", west="none")
            kind = "bollard"
        elif bar in ("gate", "swing_gate"):
            blocks[(x, g + 1, z)] = P("oak_fence_gate", facing="north", open="false", in_wall="false",
                                      powered="false")
            kind = "gate"
        elif a in ("bicycle_parking",):
            blocks[(x, g + 1, z)] = P("iron_bars", north="false", south="false", east="true", west="true")
            kind = "cycle rack"
        elif t.get("tourism") == "information" and t.get("information") in ("board", "map"):
            blocks[(x, g + 1, z)] = P("dark_oak_fence", north="false", south="false", east="false", west="false",
                                      waterlogged="false")
            blocks[(x, g + 2, z)] = P("dark_oak_wall_sign", facing="south")
            kind = "info board"
        elif a == "recycling":
            blocks[(x, g + 1, z)] = P("green_shulker_box", facing="up")
            kind = "recycling"
        if kind:
            n[kind] = n.get(kind, 0) + 1
    print("street furniture:", n)
    return block_stamp(blocks)


# ---- waterside life, the rowing lake's race lanes, pitch markings ----------------------------------

def waterside(G, P):
    from scipy import ndimage
    rng = np.random.default_rng(21)
    w, g = G["water"], G["ground"]
    water = w > -999
    land = G["mask"] & ~water
    shore = water & ndimage.binary_dilation(land)
    blocks = {}
    # reeds and grass along the edge, lily pads on still water (lakes and ponds, not the Thames)
    river = (w == 35) | (w == 36)
    zs, xs = np.nonzero(shore)
    for z, x in zip(zs, xs):
        r = rng.random()
        depth = w[z, x] - g[z, x]
        if r < 0.25 and depth <= 2:
            blocks[(x, int(g[z, x]) + 1, z)] = P("seagrass")
        elif r < 0.30 and not river[z, x]:
            blocks[(x, int(w[z, x]) + 1, z)] = P("lily_pad")
    edge = land & ndimage.binary_dilation(water)
    zs, xs = np.nonzero(edge & (G["surface"] == 1))
    for z, x in zip(zs, xs):
        if rng.random() < 0.35:
            y = int(g[z, x]) + 1
            blocks[(x, y, z)] = P("tall_grass", half="lower")
            blocks[(x, y + 1, z)] = P("tall_grass", half="upper")
    # Redgrave Pinsent Rowing Lake: 6 buoyed lanes 13.5 m apart down the long axis, white buoys every 10 m
    osm = json.load(open("build/osm.json"))
    lake = next(a for a in osm["areas"] if a["tags"].get("name") == "Redgrave Pinsent Rowing Lake")
    pts = np.array([xz(*p) for p in lake["rings"][0]], float)
    c = pts.mean(0)
    u, s_, vt = np.linalg.svd(pts - c, full_matrices=False)
    major, minor = vt[0], vt[1]
    along = (pts - c) @ major
    lvl = None
    n = 0
    for lane in range(7):
        off = (lane - 3) * 13.5
        for t in np.arange(along.min() + 60, along.max() - 60, 10):
            x, z = (int(round(v)) for v in c + major * t + minor * off)
            if 0 <= z < w.shape[0] and 0 <= x < w.shape[1] and w[z, x] > -999:
                blocks[(x, int(w[z, x]), z)] = P("white_wool") if lane % 6 else P("orange_wool")
                n += 1
    # pitch markings: a white line round each football/rugby pitch and across the middle
    lines = 0
    for a in osm["areas"]:
        t = a["tags"]
        if t.get("leisure") != "pitch" or t.get("sport") not in ("soccer", "football", "rugby_union", "rugby"):
            continue
        pts = np.array([xz(*p) for p in a["rings"][0]], float)
        seg = list(zip(pts[:-1], pts[1:]))
        c2 = pts.mean(0)
        u2, s2, vt2 = np.linalg.svd(pts - c2, full_matrices=False)
        half = np.abs((pts - c2) @ vt2[1]).max()
        seg.append((c2 - vt2[1] * half, c2 + vt2[1] * half))
        for p0, p1 in seg:
            for k in np.linspace(0, 1, int(np.hypot(*(p1 - p0))) + 1):
                x, z = (int(round(v)) for v in p0 + (p1 - p0) * k)
                if 0 <= z < w.shape[0] and 0 <= x < w.shape[1] and G["mask"][z, x] and G["surface"][z, x] in (1, 13):
                    blocks[(x, int(g[z, x]), z)] = P("white_concrete")
                    lines += 1
    print(f"waterside plants + lanes: {len(blocks)} blocks, {n} lane buoys, {lines} pitch-line blocks")
    return block_stamp(blocks)


# ---- grazing animals in meadows (vanilla mobs as saved entities; spawning is off so these are all there are) ----

def animals(G, P, per_ha=1.5, cap=6):
    from PIL import Image, ImageDraw
    import lock
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    rng = np.random.default_rng(31)
    total = {}
    for a in osm["areas"]:
        t = a["tags"]
        if t.get("landuse") == "meadow":
            kinds = ["cow", "cow", "sheep"]
        elif t.get("leisure") == "horse_riding" or t.get("landuse") == "paddock":
            kinds = ["horse"]
        else:
            continue
        img = Image.new("L", (Ww, Hh), 0)
        ImageDraw.Draw(img).polygon([xz(*p) for p in a["rings"][0]], fill=1)
        inside = np.asarray(img).astype(bool) & G["mask"] & (G["water"] == -999) & (G["building"] == 0)
        zs, xs = np.nonzero(inside)
        if len(zs) < 400:
            continue
        n = min(cap, int(len(zs) / 10000 * per_ha) + 1)
        kind = kinds[rng.integers(len(kinds))]
        for i in rng.choice(len(zs), n, replace=False):
            x, z = xs[i], zs[i]
            e = {"id": "minecraft:" + kind, "Pos": [x + 0.5, float(G["ground"][z, x] + 1), z + 0.5],
                 "Motion": [0.0, 0.0, 0.0], "Rotation": [anvil_float(rng.uniform(0, 360)), anvil_float(0)],
                 "UUID": lock.uuid_ints(), "OnGround": lock.anvil.Byte(1), "Air": lock.anvil.Short(300),
                 "FallDistance": anvil_float(0), "Fire": lock.anvil.Short(-1), "Health": anvil_float(10),
                 "PersistenceRequired": lock.anvil.Byte(1), "Invulnerable": lock.anvil.Byte(0), "PortalCooldown": 0}
            if kind == "sheep":
                e["Color"] = lock.anvil.Byte(0)
            if kind == "horse":
                e["Variant"] = int(rng.integers(0, 7))
                e["Tame"] = lock.anvil.Byte(0)
            lock.add_entity(G, e)
            total[kind] = total.get(kind, 0) + 1
    print("animals:", total)


def anvil_float(v):
    import anvil
    return anvil.Float(v)


# ---- parked cars on driveways (block-built: a body, glass cabin, black wheels) ------------------------

CAR_COLOURS = ["white_concrete", "black_concrete", "gray_concrete", "light_gray_concrete", "blue_concrete",
               "red_concrete", "light_blue_concrete", "white_concrete", "gray_concrete", "black_concrete"]


def cars(G, P):
    rng = np.random.default_rng(41)
    blocks = {}
    n = 0
    for z, x, along_x in G.get("drives", []):
        if rng.random() > 0.55 or not (0 <= z < G["mask"].shape[0] and 0 <= x < G["mask"].shape[1]):
            continue
        if G["surface"][z, x] != 7:
            continue
        g = int(G["ground"][z, x])
        body = P(CAR_COLOURS[rng.integers(len(CAR_COLOURS))])
        # 4 long x 2 wide; along the drive direction
        cells = [(z + (0 if along_x else k), x + (k if along_x else 0)) for k in (-2, -1, 0, 1)]
        ok = all(0 <= a < G["mask"].shape[0] and 0 <= b < G["mask"].shape[1] and G["building"][a, b] == 0
                 for a, b in cells)
        if not ok:
            continue
        for k, (a, b) in enumerate(cells):
            for w in (0, 1):
                A, B = (a + w, b) if along_x else (a, b + w)
                end = k in (0, 3)
                blocks[(B, g + 1, A)] = P("black_concrete") if end and w == 0 and False else body
                if not end:
                    blocks[(B, g + 2, A)] = P("light_gray_stained_glass")
        n += 1
    print("parked cars:", n)
    return block_stamp(blocks)


# ---- Christchurch Bridge: the 39 m white mast and its fan of stay cables (from Commons photos) ----------

def christchurch_mast(G, P):
    br = [b for b in json.load(open("build/bridges.json")) if b["tags"].get("name") == "Christchurch Bridge"
          and b["tags"].get("highway") == "cycleway"]
    pts = np.array([xz(*p) for b in br for p in b["pts"]], float)
    if not len(pts):
        return block_stamp({})
    w = G["water"]
    # the mast stands at the south (Reading) end of the river span; cables fan to the deck across the water
    over = [p for p in pts if w[int(p[1]), int(p[0])] > -999]
    span = np.array(over if over else pts)
    # the river crossing: the two over-water deck points furthest apart (the ramp along the bank is shorter)
    d = ((span[:, None, :] - span[None, :, :]) ** 2).sum(-1)
    i, j = np.unravel_index(np.argmax(d), d.shape)
    south, north = (span[i], span[j]) if span[i][1] > span[j][1] else (span[j], span[i])
    mx, mz = int(round(south[0])), int(round(south[1])) + 3
    g = int(G["ground"][mz, mx])
    top = g + 39
    blocks = {}
    for y in range(g + 1, top + 1):
        blocks[(mx, y, mz)] = P("white_concrete")
    blocks[(mx, top + 1, mz)] = P("end_rod", facing="up")
    deck = G["br_deck"]
    chain = P("chain", axis="y")
    # anchor points: along the deck itself (it bends mid-river), walking out from the mast end
    ways = {b["id"]: [xz(*p) for p in b["pts"]] for b in br}
    path = []
    for wid in ("w373229922", "w373230004"):
        path += ways.get(wid, [])
    if not path:
        path = [tuple(south), tuple(north)]
    path = np.array(path, float)
    if np.hypot(*(path[0] - south)) > np.hypot(*(path[-1] - south)):
        path = path[::-1]
    seg = np.hypot(*np.diff(path, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    for k in range(1, 9):
        s_ = cum[-1] * k / 9
        tx = np.interp(s_, cum, path[:, 0])
        tz = np.interp(s_, cum, path[:, 1])
        tx, tz = int(round(tx)), int(round(tz))
        dy = deck[tz, tx] if deck[tz, tx] > -999 else g + 6
        ay = top - k * 2
        n = max(abs(tx - mx), abs(tz - mz), abs(ay - dy))
        for i in range(n + 1):
            f = i / n
            x = int(round(mx + (tx - mx) * f))
            z = int(round(mz + (tz - mz) * f))
            y = int(round(ay + (dy + 1 - ay) * f))
            blocks.setdefault((x, y, z), chain)
    print(f"Christchurch Bridge mast at {mx},{mz}, top y {top}")
    return block_stamp(blocks)


# ---- churchyard gravestones, marina boats -----------------------------------------------------------

def churchyards(G, P):
    rng = np.random.default_rng(51)
    cem = (G["surface"] == 17) & G["mask"] & (G["building"] == 0)
    zs, xs = np.nonzero(cem)
    blocks = {}
    stones = [P("stone_brick_wall", up="true", north="none", south="none", east="none", west="none"),
              P("cobblestone_wall", up="true", north="none", south="none", east="none", west="none"),
              P("andesite_wall", up="true", north="none", south="none", east="none", west="none"),
              P("stone_brick_slab", type="bottom")]
    n = 0
    for z, x in zip(zs, xs):
        if x % 3 == 0 and z % 4 == 0 and rng.random() < 0.6:     # rows, like a real churchyard
            blocks[(int(x), int(G["ground"][z, x]) + 1, int(z))] = stones[rng.integers(len(stones))]
            n += 1
    print("gravestones:", n)
    return block_stamp(blocks)


def marina(G, P):
    import lock
    from PIL import Image, ImageDraw
    osm = json.load(open("build/osm.json"))
    m = next((a for a in osm["areas"] if a["tags"].get("leisure") == "marina"), None)
    if not m:
        return
    Hh, Ww = G["mask"].shape
    img = Image.new("L", (Ww, Hh), 0)
    ImageDraw.Draw(img).polygon([xz(*p) for p in m["rings"][0]], fill=1)
    area = np.asarray(img).astype(bool) & (G["water"] > -999)
    from scipy import ndimage
    edge = area & ndimage.binary_dilation(~area)
    zs, xs = np.nonzero(edge)
    rng = np.random.default_rng(61)
    picks = []
    for i in rng.permutation(len(zs)):
        if all(abs(xs[i] - a) + abs(zs[i] - c) > 7 for a, c in picks):
            picks.append((xs[i], zs[i]))
        if len(picks) >= 40:
            break
    for k, (x, z) in enumerate(picks):
        b = lock.boat(x + 0.5, G["water"][z, x] + 0.9, z + 0.5, float(rng.uniform(0, 360)))
        b["Type"] = ["oak", "birch", "spruce", "cherry"][k % 4]
        lock.add_entity(G, b)
    print("marina boats:", len(picks))


# ---- street name signs at each end of every named road ---------------------------------------------

def street_signs(G, P):
    import lock
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    from scipy import ndimage
    soft = G["mask"] & ~np.isin(G["surface"], (3, 4, 6, 18)) & (G["building"] == 0) & (G["water"] == -999)
    _, (sz, sx) = ndimage.distance_transform_edt(~soft, return_indices=True)
    ends = {}
    for ln in osm["lines"]:
        t = ln["tags"]
        if t.get("highway") not in ("primary", "secondary", "tertiary", "residential", "unclassified",
                                    "living_street") or not t.get("name"):
            continue
        for p in (ln["pts"][0], ln["pts"][-1]):
            ends.setdefault(t["name"], []).append(xz(*p))
    blocks = {}
    n = 0
    for name, pts in ends.items():
        placed = []
        for x, z in pts:
            if not (0 <= z < Hh and 0 <= x < Ww) or not G["mask"][z, x]:
                continue
            if any(abs(x - a) + abs(z - c) < 60 for a, c in placed):
                continue
            px, pz = int(sx[z, x]), int(sz[z, x])
            if abs(px - x) + abs(pz - z) > 12 or (px, pz) in [(k[0], k[2]) for k in blocks]:
                continue
            placed.append((x, z))
            g = int(G["ground"][pz, px])
            # face the road: rotation 0 = sign text faces south; pick from direction to the road point
            ang = (np.degrees(np.arctan2(x - px, -(z - pz)))) % 360   # 0 = north
            rot = int(round(((ang + 180) % 360) / 22.5)) % 16
            blocks[(px, g + 1, pz)] = P("dark_oak_fence")
            blocks[(px, g + 2, pz)] = P("oak_sign", rotation=rot)
            words = name.split(" ")
            lines = [name] if len(name) <= 15 else [" ".join(words[:len(words) // 2]), " ".join(words[len(words) // 2:])]
            G["block_entities"].setdefault((px // 16, pz // 16), []).append(
                lock.sign_entity(px, g + 2, pz, [""] + lines + ([""] if len(lines) == 1 else [])))
            n += 1
    print("street name signs:", n)
    return block_stamp(blocks)


# ---- Caversham Weir: concrete sill, sluice frames and a railed walkway along the OSM weir lines ---------

def weirs(G, P):
    """Caversham Weir as in the Commons photos: a row of sluice bays between concrete piers, a raised metal
    footbridge along the top with railings both sides, tall white gate frames on the upstream side, the white
    control hut over the middle, and white water (bubble columns over soul sand) churning below it."""
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    lv = json.load(open("build/levels.json"))
    up, down = lv["up"], lv["down"]
    water = G["water"]
    blocks = {}
    n = 0
    for ln in osm["lines"]:
        if ln["tags"].get("waterway") != "weir" or "Caversham" not in ln["tags"].get("name", "Caversham Weir"):
            continue
        pts = np.array([xz(*p) for p in ln["pts"]], float)
        if not all(0 <= z < Hh and 0 <= x < Ww and G["mask"][int(z), int(x)] for x, z in pts):
            continue
        cells = []
        for a, b in zip(pts[:-1], pts[1:]):
            L = int(np.hypot(*(b - a))) + 1
            for t in np.linspace(0, 1, L + 1):
                c = tuple(int(round(v)) for v in a + (b - a) * t)
                if not cells or c != cells[-1]:
                    cells.append(c)
        d = pts[-1] - pts[0]
        nx, nz = (-1, 0) if abs(d[1]) > abs(d[0]) else (0, -1)      # across the weir, on the grid
        mid = np.array(cells[len(cells) // 2])

        def lvl(k):
            x, z = (mid + [nx * k, nz * k]).astype(int)
            return water[z, x] if 0 <= z < Hh and 0 <= x < Ww else -999
        if lvl(4) < lvl(-4):                                        # make (nx, nz) point upstream
            nx, nz = -nx, -nz
        for k, (x, z) in enumerate(cells):
            def at(o):
                return x + nx * o, z + nz * o
            bed = int(G["ground"][z, x])
            pier = k % 5 == 0
            for o in (0, 1):                                        # the weir body; piers are stone
                X, Z = at(o)
                for y in range(bed + 1, up + (2 if pier else 1)):
                    blocks[(X, y, Z)] = P("stone_bricks" if pier else ("gray_concrete" if y >= up - 1 else
                                                                       "light_gray_concrete"))
            for o in (-1, 0, 1, 2):                                 # deck: top slabs, walking level up+2
                X, Z = at(o)
                blocks[(X, up + 1, Z)] = P("smooth_stone_slab", type="top")
            for o in (-1, 2):                                       # railings
                X, Z = at(o)
                blocks[(X, up + 2, Z)] = P("iron_bars", north="true", south="true", east="true", west="true")
            if pier:                                                # gate frame over the upstream side
                X, Z = at(2)
                for y in range(up + 2, up + 7):
                    blocks[(X, y, Z)] = P("white_concrete")
                blocks[(X, up + 7, Z)] = P("smooth_quartz_slab", type="bottom")
            X, Z = at(2)
            blocks[(X, up + 6, Z)] = P("white_concrete")             # the frames' top beam
            for o in range(3, 8):                                   # white water below
                X, Z = at(-o)
                if not (0 <= Z < Hh and 0 <= X < Ww) or water[Z, X] == -999:
                    continue
                g = int(G["ground"][Z, X])
                blocks[(X, g, Z)] = P("soul_sand")
                for y in range(g + 1, int(water[Z, X]) + 1):
                    blocks[(X, y, Z)] = P("bubble_column", drag="false")
        # control hut over the middle of the weir, on the gate frames
        k0 = len(cells) // 2
        for k in range(k0 - 2, k0 + 3):
            x, z = cells[k]
            for o in (0, 1, 2):
                X, Z = x + nx * o, z + nz * o
                for y in range(up + 7, up + 10):
                    edge = k in (k0 - 2, k0 + 2) or o in (0, 2)
                    blocks[(X, y, Z)] = (P("white_concrete") if not edge or y != up + 8 or k == k0 else
                                         P("glass_pane", north="true", south="true", east="true", west="true"))
                blocks[(X, up + 10, Z)] = P("light_gray_concrete")
        n += 1
    print("weirs built:", n)
    return block_stamp(blocks)


# ---- playgrounds, tennis nets, swimming pools ---------------------------------------------------------

def leisure(G, P):
    from PIL import Image, ImageDraw
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    rng = np.random.default_rng(81)
    blocks = {}
    stats = {}

    def poly(a):
        img = Image.new("L", (Ww, Hh), 0)
        ImageDraw.Draw(img).polygon([xz(*p) for p in a["rings"][0]], fill=1)
        return np.asarray(img).astype(bool) & G["mask"] & (G["building"] == 0)

    for a in osm["areas"]:
        t = a["tags"]
        kind = t.get("leisure")
        if kind not in ("playground", "pitch", "swimming_pool"):
            continue
        pts = np.array([xz(*p) for p in a["rings"][0]], float)
        cx, cz = pts.mean(0).astype(int)
        if not (0 <= cz < Hh and 0 <= cx < Ww) or not G["mask"][cz, cx]:
            continue
        inside = poly(a)
        if inside.sum() < 6:
            continue
        zs, xs = np.nonzero(inside)
        if kind == "playground":
            # bark surface, a swing frame, a slide, a climbing frame
            for z, x in zip(zs, xs):
                blocks[(int(x), int(G["ground"][z, x]), int(z))] = P("coarse_dirt")
            g = int(G["ground"][cz, cx])
            for dx in (-2, 2):
                for y in range(g + 1, g + 5):
                    blocks[(cx + dx, y, cz)] = P("red_concrete")
            for dx in range(-2, 3):
                blocks[(cx + dx, g + 5, cz)] = P("red_concrete")
            for dx in (-1, 1):
                for y in (g + 3, g + 4):
                    blocks[(cx + dx, y, cz)] = P("chain", axis="y")
                blocks[(cx + dx, g + 2, cz)] = P("oak_slab", type="top")
            sx, sz = cx + 5, cz
            for k in range(4):
                blocks[(sx + k, g + 4 - k, sz)] = P("yellow_concrete") if k == 0 else P(
                    "smooth_quartz_stairs", facing="west", half="bottom", shape="straight")
            for y in range(g + 1, g + 4):
                blocks[(sx - 1, y, sz)] = P("ladder", facing="west")
            blocks[(sx, g + 1, sz)] = P("blue_concrete")
            blocks[(sx, g + 2, sz)] = P("blue_concrete")
            blocks[(sx, g + 3, sz)] = P("blue_concrete")
            stats["playgrounds"] = stats.get("playgrounds", 0) + 1
        elif kind == "pitch" and t.get("sport") == "tennis":
            # net across the middle of the court's short axis
            c = pts.mean(0)
            u, s_, vt = np.linalg.svd(pts - c, full_matrices=False)
            half = np.abs((pts - c) @ vt[1]).max()
            for k in np.linspace(-half, half, int(2 * half) + 1):
                x, z = (int(round(v)) for v in c + vt[1] * k)
                if 0 <= z < Hh and 0 <= x < Ww and inside[z, x]:
                    blocks[(x, int(G["ground"][z, x]) + 1, z)] = P("white_stained_glass_pane", north="true",
                                                                   south="true", east="true", west="true")
            stats["tennis nets"] = stats.get("tennis nets", 0) + 1
        elif kind == "swimming_pool":
            g = int(np.median(G["ground"][zs, xs]))
            edge = inside & ~__import__("scipy.ndimage", fromlist=["x"]).binary_erosion(inside)
            for z, x in zip(zs, xs):
                if edge[z, x]:
                    blocks[(int(x), g, int(z))] = P("smooth_quartz")
                else:
                    blocks[(int(x), g - 2, int(z))] = P("light_blue_concrete")
                    blocks[(int(x), g - 1, int(z))] = P("water", level=0)
                    blocks[(int(x), g, int(z))] = P("water", level=0)
            stats["pools"] = stats.get("pools", 0) + 1
    print("leisure:", stats)
    return block_stamp(blocks)


# ---- car parks: white bay lines, a few parked cars ---------------------------------------------------

def car_parks(G, P):
    from PIL import Image, ImageDraw
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    rng = np.random.default_rng(91)
    blocks = {}
    n = 0
    for a in osm["areas"]:
        if a["tags"].get("amenity") != "parking" or a["tags"].get("parking") in ("underground", "multi-storey"):
            continue
        pts = np.array([xz(*p) for p in a["rings"][0]], float)
        img = Image.new("L", (Ww, Hh), 0)
        ImageDraw.Draw(img).polygon([tuple(p) for p in pts], fill=1)
        inside = np.asarray(img).astype(bool) & G["mask"] & (G["building"] == 0) & (G["surface"] == 8)
        if inside.sum() < 40:
            continue

        def paint(X, Z, blk):
            if 0 <= Z < Hh and 0 <= X < Ww and inside[Z, X]:
                blocks[(X, int(G["ground"][Z, X]) + (0 if blk == line_blk else 1), Z)] = blk
                return True
            return False

        def car(cx, cz, u, nv):
            """A car 2 wide (along u) x 3 long (along nv), nose into the bay."""
            g = int(G["ground"][int(round(cz)), int(round(cx))])
            col = P(CAR_COLOURS[rng.integers(len(CAR_COLOURS))])
            cells = [(int(round(cx + u[0] * a_ + nv[0] * b_)), int(round(cz + u[1] * a_ + nv[1] * b_)), b_)
                     for a_ in (-0.5, 0.5) for b_ in (-1, 0, 1)]
            if all(0 <= Z < Hh and 0 <= X < Ww and inside[Z, X] for X, Z, _ in cells):
                for X, Z, b_ in cells:
                    blocks[(X, g + 1, Z)] = col
                    if b_ <= 0:
                        blocks[(X, g + 2, Z)] = P("light_gray_stained_glass")

        line_blk = P("white_concrete")
        # bays come off the car park's mapped aisles: a 5 m line every 3 m either side, cars nose-in between
        aisles = []
        for l in osm["lines"]:
            if l["tags"].get("service") == "parking_aisle" or l["tags"].get("highway") == "service":
                q = np.array([xz(*p) for p in l["pts"]], float)
                inn = [(0 <= int(z) < Hh and 0 <= int(x) < Ww and inside[int(z), int(x)]) for x, z in q]
                if sum(inn) >= 1 and len(q) >= 2:
                    aisles += [(q[k], q[k + 1]) for k in range(len(q) - 1)]
        if aisles:
            for a0, a1 in aisles:
                L = np.hypot(*(a1 - a0))
                if L < 4:
                    continue
                ang = np.arctan2(*(a1 - a0)[::-1])
                snap = np.round(ang / (np.pi / 2)) * (np.pi / 2)
                if abs(ang - snap) < np.radians(20):              # nearly square to the grid: square it up
                    ang = snap
                u = np.array([np.cos(ang), np.sin(ang)])
                nv = np.array([-u[1], u[0]])
                for side in (1, -1):
                    nn = nv * side
                    for t in np.arange(1.5, L - 1, 3.0):
                        base = a0 + u * t
                        for r in np.arange(3.5, 8.5, 0.5):        # separator line (aisle is ~6 m wide)
                            X, Z = (int(round(v)) for v in base + nn * r)
                            paint(X, Z, line_blk)
                        if rng.random() < 0.35 and t + 1.5 < L - 1:
                            cxz = base + u * 1.5 + nn * 6
                            car(cxz[0], cxz[1], u, nn)
            n += 1
            continue
        # no aisles mapped: rows on the car park's long axis, snapped square to the grid when nearly square
        c = pts.mean(0)
        u_, s_, vt = np.linalg.svd(pts - c, full_matrices=False)
        ang = np.arctan2(vt[0][1], vt[0][0])
        snap = np.round(ang / (np.pi / 2)) * (np.pi / 2)
        if abs(ang - snap) < np.radians(20):
            ang = snap
        major = np.array([np.cos(ang), np.sin(ang)])
        minor = np.array([-major[1], major[0]])
        zs, xs = np.nonzero(inside)
        rel = np.stack([xs, zs], 1) - c
        along, across = rel @ major, rel @ minor
        row = np.mod(across, 16)
        bays = (row < 5) | (row >= 11)
        for (x, z), l in zip(zip(xs, zs), bays & (np.mod(along, 3) < 1)):
            if l:
                paint(int(x), int(z), line_blk)
        for f in np.arange(np.floor(along.min() / 3) * 3 + 1.5, along.max(), 3):
            for rc in (2.5, 13.5):
                for k in np.arange(np.floor(across.min() / 16) * 16, across.max(), 16):
                    if rng.random() < 0.35:
                        cxz = c + major * f + minor * (k + rc)
                        car(cxz[0], cxz[1], major, minor)
        n += 1
    print("car parks marked:", n)
    return block_stamp(blocks)


# ---- countryside: hedgerows round fields, undergrowth in woods -----------------------------------------

def countryside(G, P):
    from scipy import ndimage
    rng = np.random.default_rng(101)
    s = G["surface"]
    field = np.isin(s, (11,)) | ((s == 1) & (G["building"] == 0))
    farm = np.isin(s, (11,))
    # hedgerow on the boundary of farmland where it meets anything else (not water or roads)
    boundary = farm & ndimage.binary_dilation(~farm & ~np.isin(s, (2, 3, 4, 5)) & G["mask"])
    blocks = {}
    hedge = P("oak_leaves", persistent="true")
    for z, x in zip(*np.nonzero(boundary)):
        g = int(G["ground"][z, x])
        blocks[(int(x), g + 1, int(z))] = hedge
        blocks[(int(x), g + 2, int(z))] = hedge
    # woodland floor: ferns, bushes, fallen logs, bluebells-ish
    wood = (s == 15) & (G["building"] == 0)
    zs, xs = np.nonzero(wood)
    picks = rng.random(len(zs))
    for z, x, r in zip(zs, xs, picks):
        g = int(G["ground"][z, x])
        if r < 0.04:
            blocks.setdefault((int(x), g + 1, int(z)), P("oak_leaves", persistent="true"))
        elif r < 0.08:
            blocks.setdefault((int(x), g + 1, int(z)), P("large_fern", half="lower"))
            blocks.setdefault((int(x), g + 2, int(z)), P("large_fern", half="upper"))
        elif r < 0.09:
            blocks.setdefault((int(x), g + 1, int(z)), P("blue_orchid"))
        elif r < 0.0915:
            for k in range(3):
                blocks.setdefault((int(x) + k, g + 1, int(z)), P("oak_log", axis="x"))
    print(f"hedgerows: {int(boundary.sum())} m, woodland floor blocks: {len(blocks) - 2 * int(boundary.sum())}")
    return block_stamp(blocks)


def allotments(G, P):
    """Allotments as they look: 5 m plots split by grass paths, a shed with a felt roof on about one plot in
    four, compost bins, water butts and runner-bean canes."""
    rng = np.random.default_rng(202)
    s, ground = G["surface"], G["ground"]
    allot = (s == 12) & (G["building"] == 0)   # surfaces.SURFACE "allotment"
    blocks = {}
    shed = P("spruce_planks")
    roof = P("spruce_slab", type="bottom")
    zs, xs = np.nonzero(allot)
    sheds = 0
    for z, x in zip(zs, xs):
        z, x = int(z), int(x)
        g = int(ground[z, x])
        if x % 6 == 0 or z % 12 == 0:            # grass paths between plots
            blocks[(x, g, z)] = P("grass_block")
            blocks[(x, g + 1, z)] = P("short_grass") if rng.random() < 0.3 else P("air")
            continue
        r = rng.random()
        if x % 6 == 1 and z % 12 == 1 and r < 0.25 and allot[z:z + 3, x:x + 3].all():
            for dx in range(2):                     # 2 x 2 shed, door onto the path
                for dz in range(2):
                    gg = int(ground[z + dz, x + dx])
                    blocks[(x + dx, gg + 1, z + dz)] = shed
                    blocks[(x + dx, gg + 2, z + dz)] = shed
                    blocks[(x + dx, gg + 3, z + dz)] = roof
            blocks[(x, g + 1, z + 1)] = P("spruce_door", facing="west", half="lower", hinge="left", open="false")
            blocks[(x, g + 2, z + 1)] = P("spruce_door", facing="west", half="upper", hinge="left", open="false")
            sheds += 1
        elif r < 0.01:
            blocks.setdefault((x, g + 1, z), P("composter", level=5))
        elif r < 0.015:
            blocks.setdefault((x, g + 1, z), P("barrel", facing="up", open="false"))   # water butt
        elif r < 0.03 and z % 12 == 6:
            blocks[(x, g, z)] = P("coarse_dirt")    # bamboo won't stand on farmland
            for dy in (1, 2):                       # bean canes
                blocks[(x, g + dy, z)] = P("bamboo", age=0, leaves="small", stage=0)
    print(f"allotments: {int(allot.sum())} m2, {sheds} sheds")
    return block_stamp(blocks)


def crossings(G, P):
    """Road crossings from OSM nodes. Zebras: white stripes running with the traffic across the road, and a
    Belisha beacon (black-and-white pole, orange globe) on each kerb. Signal crossings and junction signals:
    a black traffic-light pole on each kerb."""
    osm = json.load(open("build/osm.json"))
    s, ground, mask = G["surface"], G["ground"], G["mask"]
    Hh, Ww = mask.shape
    road = np.isin(s, (3, 4))   # surfaces.SURFACE road, minor_road
    segs = []
    for l in osm["lines"]:
        if l["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
                                        "residential", "service", "living_street"):
            p = [xz(*q) for q in l["pts"]]
            segs += [(a[0], a[1], b[0], b[1]) for a, b in zip(p[:-1], p[1:])]
    S = np.array(segs, float)
    d = S[:, 2:] - S[:, :2]
    blocks = {}
    zebras = signals = 0
    for nd in osm["nodes"]:
        t = nd["tags"]
        hw = t.get("highway")
        zebra = hw == "crossing" and (t.get("crossing_ref") in ("zebra", "parallel") or t.get("crossing") in ("zebra", "marked", "uncontrolled"))
        signal = hw == "traffic_signals" or (hw == "crossing" and t.get("crossing") == "traffic_signals")
        if not (zebra or signal):
            continue
        x, z = xz(*nd["pt"])
        if not (0 <= z < Hh and 0 <= x < Ww) or not mask[z, x]:
            continue
        if not road[z, x]:                                   # mapped on the pavement edge: snap onto the road
            near = np.argwhere(road[max(0, z - 3):z + 4, max(0, x - 3):x + 4])
            if not len(near):
                continue
            j = int(np.argmin(((near - [min(z, 3), min(x, 3)]) ** 2).sum(1)))
            z, x = int(near[j][0] + max(0, z - 3)), int(near[j][1] + max(0, x - 3))
        tt = np.clip(((x - S[:, 0]) * d[:, 0] + (z - S[:, 1]) * d[:, 1]) / np.maximum((d ** 2).sum(1), 1e-9), 0, 1)
        k = int(np.argmin(np.hypot(S[:, 0] + tt * d[:, 0] - x, S[:, 1] + tt * d[:, 1] - z)))
        ux, uz = d[k] / max(np.hypot(*d[k]), 1e-9)          # along the road
        vx, vz = -uz, ux                                     # across it
        kerbs = []
        for sgn in (1, -1):                                  # walk out to each kerb
            for r in range(1, 14):
                cx, cz = int(round(x + vx * r * sgn)), int(round(z + vz * r * sgn))
                if not (0 <= cz < Hh and 0 <= cx < Ww) or not road[cz, cx]:
                    kerbs.append((cx, cz, r))
                    break
        if len(kerbs) < 2:
            continue
        if zebra:
            for cz in range(max(0, z - 14), min(Hh, z + 15)):    # each road block: along/across the crossing
                for cx in range(max(0, x - 14), min(Ww, x + 15)):
                    a, c = (cx - x) * ux + (cz - z) * uz, (cx - x) * vx + (cz - z) * vz
                    if road[cz, cx] and abs(a) <= 1.5 and -kerbs[1][2] < c < kerbs[0][2] and round(c) % 2 == 0:
                        blocks[(cx, int(ground[cz, cx]), cz)] = P("white_concrete")
            zebras += 1
        else:
            signals += 1
        for cx, cz, _ in kerbs:
            if not (0 <= cz < Hh and 0 <= cx < Ww) or G["building"][cz, cx] or G["water"][cz, cx] != -999:
                continue
            g = int(ground[cz, cx])
            if zebra:
                for dy in (1, 2, 3):
                    blocks[(cx, g + dy, cz)] = P("polished_blackstone_wall" if dy % 2 else "diorite_wall", up="true",
                                                 north="none", south="none", east="none", west="none")
                blocks[(cx, g + 4, cz)] = P("shroomlight")
            else:
                for dy in (1, 2):
                    blocks[(cx, g + dy, cz)] = P("polished_blackstone_wall", up="true", north="none", south="none",
                                                 east="none", west="none")
                blocks[(cx, g + 3, cz)] = P("black_concrete")
                blocks[(cx, g + 4, cz)] = P("black_concrete")
    print(f"crossings: {zebras} zebras, {signals} signal poles pairs")
    return block_stamp(blocks)


# ---- Caversham Lock island and View Island: lamps, benches, railings, a carved head ------------------------

LOCK_PATHS = (3880, 4180, 3940, 4200)   # x0, x1, z0, z1 round the lock, the weir and View Island


def island_paths(G, P):
    """The paths round the lock island, over the weir and through View Island, from the Commons photos: black
    Victorian lamp posts, blue benches facing the water, black railings where the path meets the water, and
    one of View Island's chainsaw-carved wooden heads in the trees."""
    osm = json.load(open("build/osm.json"))
    x0, x1, z0, z1 = LOCK_PATHS
    Hh, Ww = G["mask"].shape
    s, ground, water = G["surface"], G["ground"], G["water"]
    rng = np.random.default_rng(55)
    blocks = {}
    lamps = benches = rails = 0
    post = P("polished_blackstone_wall", up="true", north="none", south="none", east="none", west="none")
    for l in osm["lines"]:
        if l["tags"].get("highway") not in ("footway", "cycleway", "path") or l["tags"].get("bridge"):
            continue
        pts = np.array([xz(*q) for q in l["pts"]], float)
        if not ((pts[:, 0] > x0) & (pts[:, 0] < x1) & (pts[:, 1] > z0) & (pts[:, 1] < z1)).any():
            continue
        walked = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            seg = np.hypot(*(b - a))
            if seg < 0.5:
                continue
            u = (b - a) / seg
            nrm = np.array([-u[1], u[0]])
            for t in np.arange(0, seg, 1.0):
                c = a + u * t
                walked += 1
                if not (x0 < c[0] < x1 and z0 < c[1] < z1):
                    continue
                X, Z = int(round(c[0])), int(round(c[1]))
                if not (0 <= Z < Hh and 0 <= X < Ww) or not G["mask"][Z, X] or water[Z, X] != -999:
                    continue
                # which side is the water? (look 6 m either way)
                wet = []
                for sg in (1, -1):
                    q = (c + nrm * sg * np.arange(2, 7)[:, None]).round().astype(int)
                    ok = (q[:, 1] >= 0) & (q[:, 1] < Hh) & (q[:, 0] >= 0) & (q[:, 0] < Ww)
                    wet.append(ok.all() and (water[q[:, 1], q[:, 0]] != -999).any())
                side = 1 if wet[0] else (-1 if wet[1] else 0)
                if int(walked) % 18 == 0:                       # lamp post on the landward side
                    lx, lz = (c - nrm * (side or 1) * 2).round().astype(int)
                    if 0 <= lz < Hh and 0 <= lx < Ww and water[lz, lx] == -999 and not G["building"][lz, lx]:
                        g = int(ground[lz, lx])
                        for dy in (1, 2, 3):
                            blocks[(int(lx), g + dy, int(lz))] = post
                        blocks[(int(lx), g + 4, int(lz))] = P("lantern", hanging="false")
                        lamps += 1
                if side and int(walked) % 40 == 9:              # bench facing the water
                    bx, bz = (c + nrm * side * 2).round().astype(int)
                    if 0 <= bz < Hh and 0 <= bx < Ww and water[bz, bx] == -999 and not G["building"][bz, bx]:
                        facing = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[
                            tuple(int(v) for v in np.sign(np.round(nrm * side)))] if abs(nrm[0]) < 0.3 or abs(nrm[1]) < 0.3 else None
                        if facing:
                            g = int(ground[bz, bx])
                            # stairs face away from where you sit: a seat facing the water has its back landward
                            back = {"west": "east", "east": "west", "north": "south", "south": "north"}[facing]
                            ax_ = (0, 1) if facing in ("east", "west") else (1, 0)
                            for k in (0, 1):
                                blocks[(int(bx) + ax_[0] * k, g + 1, int(bz) + ax_[1] * k)] = P(
                                    "warped_stairs", facing=back, half="bottom", shape="straight")
                            benches += 1
                if side:                                        # railing on the bank edge, past the verge
                    for r in range(2, 6):
                        q = (c + nrm * side * r).round().astype(int)
                        if not (0 <= q[1] < Hh and 0 <= q[0] < Ww):
                            break
                        if water[q[1], q[0]] != -999:
                            e = (c + nrm * side * (r - 1)).round().astype(int)
                            if water[e[1], e[0]] == -999 and not G["building"][e[1], e[0]] and s[e[1], e[0]] not in (3, 4, 5, 6, 9):
                                blocks.setdefault((int(e[0]), int(ground[e[1], e[0]]) + 1, int(e[1])), P(
                                    "iron_bars", north="true", south="true", east="true", west="true"))
                                rails += 1
                            break
    # a carved head in View Island's trees (as in the photos): weathered wood, eyes and a big nose
    vz = np.argwhere((s[3960:4100, 4000:4200] == 15) & (water[3960:4100, 4000:4200] == -999))
    if len(vz):
        hz, hx = vz[len(vz) // 2] + [3960, 4000]
        g = int(ground[hz, hx])
        for dx in (0, 1):
            for dz in (0, 1):
                for dy in (1, 2, 3):
                    blocks[(int(hx) + dx, g + dy, int(hz) + dz)] = P("stripped_spruce_wood", axis="y")
        blocks[(int(hx), g + 3, int(hz) - 1)] = P("spruce_button", face="wall", facing="north", powered="false")
        blocks[(int(hx) + 1, g + 3, int(hz) - 1)] = P("spruce_button", face="wall", facing="north", powered="false")
        blocks[(int(hx), g + 2, int(hz) - 1)] = P("stripped_spruce_log", axis="z")   # the nose
    print(f"lock island paths: {lamps} lamps, {benches} benches, {rails} railing blocks")
    return block_stamp(blocks)


# ---- Reading Winter Wonderland on Hills Meadow car park (7 Nov 2026 - 3 Jan 2027) -----------------------

WONDERLAND = "w28963401"   # Hills Meadow car park


def winter_wonderland(G, P):
    """Reading's Winter Wonderland on Hills Meadow car park, from the user's photos: the white observation wheel
    (white gondolas, red-and-white legs, a ring of coloured lights), an ice rink under an open-sided white tent,
    wooden chalets with lit eaves, a harlequin helter-skelter, the yellow Coaster, the jungle funhouse with its
    blue spiral slide, striped prize stalls, a Catch-a-Fish stall, the Apres Bar deck, candy canes, lit trees,
    red carpet down the avenue and the red oval entrance arch with nutcrackers. Snow underfoot, for magic."""
    from PIL import Image, ImageDraw
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    area = next(a for a in osm["areas"] if a["id"] == WONDERLAND)
    img = Image.new("L", (Ww, Hh), 0)
    ImageDraw.Draw(img).polygon([xz(*p) for p in area["rings"][0]], fill=1)
    site = np.asarray(img).astype(bool) & G["mask"] & (G["building"] == 0)
    used = np.zeros_like(site)
    ground = G["ground"]
    rng = np.random.default_rng(1225)
    blocks = {}
    ents = []

    def put(x, y, z, name, **kw):
        blocks[(int(x), int(y), int(z))] = P(name, **kw)

    zs, xs = np.nonzero(site)
    mid = np.array([xs.mean(), zs.mean()])
    _, _, vt = np.linalg.svd(np.stack([xs, zs], 1) - mid, full_matrices=False)
    major, minor = vt[0], vt[1]
    span = np.ptp(np.stack([xs, zs], 1) @ major)

    def at(f, off=0.0):
        """A point f of the way along the site's long axis (-0.5 .. 0.5), off metres across it."""
        return mid + major * f * span + minor * off

    def place(w, d, pad=2, target=None):
        """The free spot nearest target (default the middle) that fits a w x d footprint (+ pad all round)."""
        cx, cz = target if target is not None else mid
        best = None
        for z in range(zs.min(), zs.max() - d + 1, 2):
            for x in range(xs.min(), xs.max() - w + 1, 2):
                box = np.s_[z - pad:z + d + pad, x - pad:x + w + pad]
                if site[box].all() and not used[box].any():
                    dist = (z + d / 2 - cz) ** 2 + (x + w / 2 - cx) ** 2
                    if best is None or dist < best[0]:
                        best = (dist, x, z)
        if best is None:
            return None
        _, x, z = best
        used[z - pad:z + d + pad, x - pad:x + w + pad] = True
        return x, z

    g0 = int(np.median(ground[site]))
    zs, xs = np.nonzero(site)
    # the giant wheel: 32 m across, in an x-y plane, A-frame legs, coloured gondolas, lights on the rim
    wx, wz = place(36, 10, 3, at(0.32))
    hx, hz, hy, R = wx + 18, wz + 5, g0 + 22, 16
    for t in np.linspace(0, 2 * np.pi, 400, endpoint=False):
        put(round(hx + R * np.cos(t)), round(hy + R * np.sin(t)), hz, "white_concrete")
    for k in range(16):                                           # spokes
        t = 2 * np.pi * k / 16
        for r in np.arange(1, R, 0.5):
            put(round(hx + r * np.cos(t)), round(hy + r * np.sin(t)), hz, "iron_bars", north="true", south="true",
                east="false", west="false")
    colours = ["red", "blue", "yellow", "lime", "orange", "magenta", "light_blue", "white"]
    for t in np.linspace(0, 2 * np.pi, 400, endpoint=False):    # coloured light ring just inside the rim
        put(round(hx + (R - 1) * np.cos(t)), round(hy + (R - 1) * np.sin(t)), hz,
            ["lime", "light_blue", "cyan", "light_blue"][int(t * 4) % 4] + "_stained_glass")
    for k in range(32):                                           # lamps round the rim
        t = 2 * np.pi * k / 32 + 0.05
        put(round(hx + R * np.cos(t)), round(hy + R * np.sin(t)), hz, "sea_lantern")
    for k in range(20):                                           # white gondolas hang just below the rim
        t = 2 * np.pi * k / 20
        gx, gy = round(hx + (R + 1) * np.cos(t)), round(hy + (R + 1) * np.sin(t)) - 2
        for dz in (-1, 0, 1):
            put(gx, gy, hz + dz, "white_concrete")
            put(gx, gy + 1, hz + dz, "glass_pane", north="false", south="false", east="true", west="true")
            put(gx, gy + 2, hz + dz, "smooth_quartz_slab", type="bottom")
    for dz in (-4, 4):                                            # A-frame legs to the hub, red and white
        for side in (-1, 1):
            for r in np.arange(0, 1, 0.02):
                y = round(g0 + 1 + (hy - g0 - 1) * r)
                put(round(hx + side * 9 * (1 - r)), y, hz + round(dz * (1 - r)),
                    "red_concrete" if (y // 3) % 2 else "white_concrete")
    put(hx, hy, hz, "sea_lantern")
    for dz in (-1, 1):
        put(hx, hy, hz + dz, "light_blue_concrete")
    # the ice rink: a white marquee 30 x 20 with a real ice floor, rink boards, glazed sides
    rx, rz = place(30, 20, 3, at(0.0))
    for z in range(rz, rz + 20):
        for x in range(rx, rx + 30):
            for y in range(g0 + 1, int(ground[z, x]) + 1):       # level the floor where the car park rises
                put(x, y, z, "air")
            edge = x in (rx, rx + 29) or z in (rz, rz + 19)
            put(x, g0, z, "packed_ice" if not edge else "smooth_stone")
            if x in (rx + 1, rx + 28) or z in (rz + 1, rz + 18):
                if not edge:
                    put(x, g0, z, "blue_ice")                     # the rink's edge ice
            ridge = min(z - rz, rz + 19 - z)                      # pitched roof rising to the middle
            if edge and (x - rx) % 6 == 0 and (z - rz) % 19 == 0 or edge and x in (rx, rx + 29) and (z - rz) % 6 == 0:
                for y in range(g0 + 1, g0 + 6):                   # tent poles; the sides stay open
                    put(x, y, z, "white_concrete")
            put(x, g0 + 6 + min(ridge, 8) // 2, z, "white_wool")
            if edge:
                put(x, g0 + 5, z, "white_wool")                   # the valance round the eaves
        for x in (rx + 2, rx + 27):                               # rink boards
            put(x, g0 + 1, z, "spruce_fence")
    for x in range(rx + 2, rx + 28):
        for z in (rz + 2, rz + 17):
            put(x, g0 + 1, z, "spruce_fence")
    for x in range(rx + 3, rx + 27, 4):                           # lights under the roof
        put(x, g0 + 8, rz + 10, "sea_lantern")
    sign_at = (rx + 15, g0 + 4, rz + 20)
    put(rx + 15, g0 + 4, rz + 19, "white_concrete")
    put(*sign_at, "spruce_wall_sign", facing="south")
    ents.append(sign_at + (["ICE RINK", "", "skate on real", "ice"],))
    # a carousel: round platform, striped canopy
    cx_, cz_ = place(11, 11, 2, at(-0.3))
    ccx, ccz = cx_ + 5, cz_ + 5
    for dz in range(-5, 6):
        for dx in range(-5, 6):
            r = np.hypot(dx, dz)
            if r <= 5.4:
                put(ccx + dx, g0 + 1, ccz + dz, "smooth_quartz_slab", type="bottom")
                put(ccx + dx, g0 + 6 + (r < 3.5) + (r < 1.5), ccz + dz,
                    "red_wool" if (int(np.degrees(np.arctan2(dz, dx)) // 30)) % 2 else "white_wool")
                if 3.5 < r <= 4.5 and (dx + dz) % 3 == 0:
                    for y in range(g0 + 2, g0 + 6):
                        put(ccx + dx, y, ccz + dz, "end_rod", facing="up")      # brass poles
                    put(ccx + dx, g0 + 3, ccz + dz, colours[(dx * 3 + dz) % len(colours)] + "_concrete")
    for y in range(g0 + 2, g0 + 9):
        put(ccx, y, ccz, "gold_block")
    # market chalets: spruce huts with a serving hatch, snow on the roof, a lantern
    # a helter-skelter: a striped tower with a slide spiralling down it
    hsx, hsz = place(7, 7, 2, at(-0.15, 18))
    tx, tz = hsx + 3, hsz + 3
    tg = int(ground[tz, tx])
    for y in range(tg + 1, tg + 15):
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                put(tx + dx, y, tz + dz, "red_concrete" if (y // 2 + dx + dz) % 2 else "yellow_concrete")
    for k in range(56):                                           # the slide: slabs round the tower, 1 down per 4
        t = k * np.pi / 8
        put(round(tx + 2.4 * np.cos(t)), tg + 14 - k // 4, round(tz + 2.4 * np.sin(t)), "yellow_terracotta")
    for dz in range(-2, 3):
        for dx in range(-2, 3):
            put(tx + dx, tg + 15 + (abs(dx) < 2 and abs(dz) < 2), tz + dz, "gold_block" if abs(dx) == 2 or abs(dz) == 2 else "red_wool")
    put(tx, tg + 17, tz, "red_wool")
    put(tx, tg + 18, tz, "white_banner", rotation=0)
    chalets = 0
    lane = [(f, side * 9) for f in np.linspace(-0.42, 0.42, 16) for side in (-1, 1)]   # an avenue of chalets
    for k in range(32):
        spot = place(4, 3, 1, at(*lane[k]))
        if spot is None:
            break
        x, z = spot
        g0 = int(ground[z:z + 3, x:x + 4].max())                 # each chalet on its own patch of ground
        for dz in range(3):
            for dx in range(4):
                edge = dx in (0, 3) or dz in (0, 2)
                for y in (g0 + 1, g0 + 2):
                    if edge:
                        hatch = dz == 2 and dx in (1, 2) and y == g0 + 2
                        put(x + dx, y, z + dz, "air" if hatch else "spruce_planks")
                put(x + dx, g0 + 3, z + dz, "spruce_slab", type="bottom")
                put(x + dx, g0 + 4, z + dz, "snow", layers=2)
        put(x + 1, g0 + 1, z + 2, "spruce_slab", type="top")     # counter
        put(x + 2, g0 + 1, z + 2, "spruce_slab", type="top")
        for dx in range(4):                                       # fairy lights along the front eave
            put(x + dx, g0 + 2, z + 3, "end_rod", facing="south") if dx in (0, 3) else None
        put(x + 1, g0 + 3, z + 3, "lantern", hanging="false")
        chalets += 1
    # the Coaster: a yellow track on posts in an oval with a dip, little cars on it
    spot = place(26, 12, 2, at(0.2, -20))
    if spot:
        x0_, z0_ = spot
        cxo, czo = x0_ + 13, z0_ + 6
        for k in range(160):
            t = 2 * np.pi * k / 160
            X, Z = round(cxo + 12 * np.cos(t)), round(czo + 5 * np.sin(t))
            h = int(ground[Z, X]) + 3 + round(1.5 * np.sin(2 * t))
            put(X, h, Z, "yellow_concrete")
            if k % 8 == 0:
                for y in range(int(ground[Z, X]) + 1, h):
                    put(X, y, Z, "yellow_terracotta" if y % 2 else "white_concrete")
        for k in (0, 1, 2):
            t = 2 * np.pi * (k + 40) / 160
            X, Z = round(cxo + 12 * np.cos(t)), round(czo + 5 * np.sin(t))
            put(X, int(ground[Z, X]) + 4 + round(1.5 * np.sin(2 * t)), Z, "red_concrete")
        put(x0_, int(ground[z0_, x0_]) + 5, z0_ - 1, "yellow_wall_banner", facing="north")
    # the jungle funhouse: three storeys of balconies, lit arches, a blue slide spiralling down the side
    spot = place(12, 7, 2, at(-0.05, 22))
    if spot:
        x0_, z0_ = spot
        fg = int(ground[z0_:z0_ + 7, x0_:x0_ + 12].max())
        for dz in range(7):
            for dx in range(9):
                for y in range(fg + 1, fg + 12):
                    front = dz == 6
                    if dx in (0, 8) or dz in (0, 6) or (y - fg) % 4 == 0:
                        blk = "lime_terracotta" if not front else (
                            "yellow_concrete" if (y - fg) % 4 == 0 else "glowstone" if dx % 2 else "green_concrete")
                        put(x0_ + dx, y, z0_ + dz, blk)
                put(x0_ + dx, fg + 12, z0_ + dz, "orange_terracotta")
            for dx in range(9):
                for k in (1, 2, 3):                               # yellow balcony rails
                    put(x0_ + dx, fg + 4 * k - 3 + 1, z0_ + 7, "yellow_stained_glass_pane") if k > 1 else None
        for k in range(36):                                       # blue spiral slide down the east side
            t = k * np.pi / 6
            put(round(x0_ + 10 + 1.6 * np.cos(t)), fg + 11 - k * 10 // 36, round(z0_ + 3 + 1.6 * np.sin(t)),
                "light_blue_concrete")
        put(x0_ + 4, fg + 13, z0_ + 6, "lime_concrete")
        put(x0_ + 4, fg + 13, z0_ + 7, "spruce_wall_sign", facing="south")
        ents.append((x0_ + 4, fg + 13, z0_ + 7, ["", "JUNGLE", "WORLD", ""]))
    # prize stalls under red-and-yellow striped tents, and the round Catch-a-Fish stall
    for k in range(4):
        spot = place(5, 5, 1, at(-0.25 + 0.18 * k, -16 if k % 2 else 16))
        if spot is None:
            break
        x0_, z0_ = spot
        sg = int(ground[z0_ + 2, x0_ + 2])
        for dz in range(5):
            for dx in range(5):
                if dx in (0, 4) and dz in (0, 4):
                    for y in range(sg + 1, sg + 4):
                        put(x0_ + dx, y, z0_ + dz, "white_concrete")
                put(x0_ + dx, sg + 4 + (0 < dx < 4 and 0 < dz < 4) + (dx == 2 and dz == 2), z0_ + dz,
                    "red_wool" if dx % 2 else "yellow_wool")
                if dz in (1, 3) and 0 < dx < 4:
                    put(x0_ + dx, sg + 1, z0_ + dz, "spruce_slab", type="top")    # counters
                if dz == 2 and 0 < dx < 4:
                    put(x0_ + dx, sg + 1, z0_ + dz, colours[(dx + k) % len(colours)] + "_wool")   # prizes
    spot = place(7, 7, 1, at(-0.38, 10))
    if spot:
        cfx, cfz = spot[0] + 3, spot[1] + 3
        fg = int(ground[cfz, cfx])
        for dz in range(-3, 4):
            for dx in range(-3, 4):
                r = np.hypot(dx, dz)
                if r <= 3.4:
                    put(cfx + dx, fg + 1, cfz + dz, "light_blue_concrete" if r > 2.4 else "water", **({} if r > 2.4 else {"level": 0}))
                    put(cfx + dx, fg + 5 + (r < 2), cfz + dz, "yellow_wool" if (dx + dz) % 2 else "white_wool")
                    if 2.4 < r <= 3.4 and (dx * dz) % 3 == 0 and abs(dx) + abs(dz) > 2:
                        for y in range(fg + 2, fg + 5):
                            put(cfx + dx, y, cfz + dz, "end_rod", facing="up")
        put(cfx, fg + 2, cfz, "yellow_concrete")                 # a duck
        put(cfx + 1, fg + 2, cfz, "lily_pad")
    # the Apres Bar: a raised wooden deck behind a picket fence, with a lit roof and tables
    spot = place(9, 7, 1, at(0.42, 0))
    if spot:
        x0_, z0_ = spot
        bg = int(ground[z0_:z0_ + 7, x0_:x0_ + 9].max())
        for dz in range(7):
            for dx in range(9):
                put(x0_ + dx, bg + 1, z0_ + dz, "spruce_slab", type="bottom")
                edge = dx in (0, 8) or dz in (0, 6)
                if edge and not (dz == 6 and dx in (4,)):
                    put(x0_ + dx, bg + 2, z0_ + dz, "spruce_fence")
                if 1 < dx < 7 and 1 < dz < 5:
                    put(x0_ + dx, bg + 6, z0_ + dz, "spruce_planks")
                if dx in (2, 6) and dz in (2, 4):
                    for y in range(bg + 2, bg + 6):
                        put(x0_ + dx, y, z0_ + dz, "spruce_log", axis="y")
        for dx in range(2, 7):
            put(x0_ + dx, bg + 5, z0_ + 5, "end_rod", facing="south")
        for tx_ in (3, 5):
            put(x0_ + tx_, bg + 2, z0_ + 3, "spruce_fence")
            put(x0_ + tx_, bg + 3, z0_ + 3, "spruce_pressure_plate")
        put(x0_ + 4, bg + 6, z0_ + 6, "orange_concrete")
        put(x0_ + 4, bg + 6, z0_ + 7, "spruce_wall_sign", facing="south")
        ents.append((x0_ + 4, bg + 6, z0_ + 7, ["", "Apres Bar", "", ""]))
    # Christmas trees with lights and a star
    trees = 0
    for k in range(10):
        spot = place(5, 5, 1, at(rng.uniform(-0.45, 0.45), rng.uniform(-20, 20)))
        if spot is None:
            break
        x, z = spot[0] + 2, spot[1] + 2
        g0 = int(ground[z, x])
        for y in range(g0 + 1, g0 + 11):
            put(x, y, z, "spruce_log", axis="y")
        for y in range(g0 + 3, g0 + 11):
            r = (g0 + 11 - y) / 3.5
            for dz in range(-2, 3):
                for dx in range(-2, 3):
                    if (dx or dz) and np.hypot(dx, dz) <= r + 0.3:
                        lit = rng.random() < 0.15
                        put(x + dx, y, z + dz, ("glowstone" if rng.random() < 0.5 else "sea_lantern") if lit else
                            "spruce_leaves", **({} if lit else {"persistent": "true"}))
        put(x, g0 + 11, z, "spruce_leaves", persistent="true")
        put(x, g0 + 12, z, "gold_block")
        trees += 1
    # the fair fills only part of the car park (the rest stays parking): a fenced zone round the attractions,
    # cleared of parked cars, snow underfoot, and festoon lights on posts round its edge
    from scipy import ndimage
    zone = ndimage.binary_dilation(used, iterations=5) & site
    zone = ndimage.binary_fill_holes(ndimage.binary_closing(zone, iterations=6)) & site
    zs, xs = np.nonzero(zone)
    rel_ = np.stack([xs, zs], 1) - mid
    avenue = np.abs(rel_ @ minor) < 2.5                           # red carpet down the middle of the fair
    road_s = np.isin(G["surface"], (3, 4, 5))
    for z, x, av in zip(zs, xs, avenue):
        g = int(ground[z, x])
        if (int(x), g + 1, int(z)) in blocks:                    # an attraction stands here
            continue
        if road_s[z, x] and any(road_s[z + dz, x + dx] and ground[z + dz, x + dx] == g + 1
                                for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            continue                                              # a road ramp slab stays (snow can't sit on it)
        put(x, g + 1, z, "red_carpet" if av else "snow", **({} if av else {"layers": 1}))
        blocks.setdefault((int(x), g + 2, int(z)), P("air"))     # car roofs from the car-park stamp
    for f in np.linspace(-0.4, 0.4, 9):                           # candy canes along the avenue
        for side in (-3.5, 3.5):
            X, Z = (int(round(v)) for v in at(f, side))
            if 0 <= Z < Hh and 0 <= X < Ww and zone[Z, X] and not used[Z, X]:
                g = int(ground[Z, X])
                for y in range(g + 1, g + 5):
                    put(X, y, Z, "red_concrete" if y % 2 else "white_concrete")
                hx_, hz_ = (int(round(v)) for v in at(f, side) + minor * np.sign(side))
                put(hx_, g + 5, hz_, "red_concrete")
                put(X, g + 5, Z, "white_concrete")
    for z, x in zip(*np.nonzero(zone)):                           # hidden lights so the fair glows at night
        if x % 6 == 0 and z % 6 == 0:
            blocks.setdefault((int(x), int(ground[z, x]) + 3, int(z)), P("light", level=14))
    rim = zone & ~ndimage.binary_erosion(zone)
    for i, (z, x) in enumerate(np.argwhere(rim)):
        if i % 6 == 0:
            g = int(ground[z, x])
            for y in (g + 1, g + 2, g + 3):
                put(x, y, z, "spruce_fence")
            put(x, g + 4, z, "lantern", hanging="false")
    # entrance arch on the side nearest Caversham Bridge road (the site's west corner)
    zs, xs = np.nonzero(zone)
    ez, ex = zs[np.argmin(xs)], xs.min() + 1
    g = int(ground[ez, ex])
    for dz in (-4, 4):                                            # posts: grey panels with a nutcracker on each
        for y in range(g + 1, g + 7):
            put(ex, y, ez + dz, "light_gray_concrete")
        put(ex - 1, g + 1, ez + dz, "white_concrete")             # nutcracker: white boots,
        put(ex - 1, g + 2, ez + dz, "blue_concrete")              # blue trousers,
        put(ex - 1, g + 3, ez + dz, "red_concrete")               # red tunic,
        put(ex - 1, g + 4, ez + dz, "white_terracotta")           # face,
        put(ex - 1, g + 5, ez + dz, "black_concrete")             # tall black hat
    for dz in range(-4, 5):                                       # the top beam, gold-edged
        put(ex, g + 7, ez + dz, "light_gray_concrete")
        put(ex, g + 8, ez + dz, "gold_block" if abs(dz) == 4 else "light_gray_concrete")
    for dz in range(-2, 3):                                       # the red oval sign over the middle
        for y in range(g + 7, g + 10 + (abs(dz) < 2)):
            put(ex - 1, y, ez + dz, "red_concrete")
    put(ex - 1, g + 11, ez, "sea_lantern")                        # the floodlight on top
    put(ex - 2, g + 8, ez, "spruce_wall_sign", facing="west")
    ents.append((ex - 2, g + 8, ez, ["WINTER", "WONDERLAND", "Reading", "7 Nov - 3 Jan"]))
    import lock
    for x, y, z, lines in ents:
        x, y, z = int(x), int(y), int(z)
        G["block_entities"].setdefault((x // 16, z // 16), []).append(lock.sign_entity(x, y, z, lines))
    print(f"winter wonderland: wheel at {hx},{hz}, rink at {rx},{rz}, entrance at {ex},{g},{ez}, {chalets} chalets, {trees} trees")
    return block_stamp(blocks)


# ---- thank-you signs at the two organisations whose data built the world -----------------------------------

DATA_SIGNS = {"w136162171": ["Environment Agency", "Kings Meadow House", "thanks for the", "LiDAR!"],
              "w77508260": ["Thames Water", "Clearwater Court", "thanks for", "the river!"]}


def data_signs(G, P):
    """A signpost outside each building, on the open ground nearest its road."""
    import lock
    from scipy import ndimage
    B = json.load(open("build/buildings.json"))
    idx = {b["id"]: i for i, b in enumerate(B) if b}
    blocks = {}
    for oid, lines in DATA_SIGNS.items():
        if oid not in idx:
            continue
        inside = G["building"] == idx[oid]
        zz, xx = np.nonzero(inside)
        z0, z1, x0, x1 = zz.min() - 25, zz.max() + 25, xx.min() - 25, xx.max() + 25
        sub = np.s_[z0:z1, x0:x1]
        road = np.isin(G["surface"][sub], (3, 4))
        d_b = ndimage.distance_transform_edt(~inside[sub])
        d_r = ndimage.distance_transform_edt(~road)
        ok = (d_b > 2) & (d_b < 4) & (G["building"][sub] == 0) & (G["water"][sub] == -999) & ~road
        if not ok.any():
            continue
        z, x = np.unravel_index(np.argmin(np.where(ok, d_r, 1e9)), d_r.shape)
        X, Z = int(x + x0), int(z + z0)
        # face the sign toward the road: the direction of the nearest road cell, as a 16-step rotation
        rz, rx = np.unravel_index(np.argmin(np.where(road, np.hypot(np.arange(road.shape[0])[:, None] - z,
                                                                       np.arange(road.shape[1])[None] - x), 1e9)),
                                  road.shape)
        rot = int(round(np.degrees(np.arctan2(-(rx - x), rz - z)) / 22.5)) % 16   # 0 = facing south (+z)
        g = int(G["ground"][Z, X])
        blocks[(X, g + 1, Z)] = P("oak_sign", rotation=rot)
        G["block_entities"].setdefault((X // 16, Z // 16), []).append(lock.sign_entity(X, g + 1, Z, lines))
        print(f"data sign: {lines[0]} at {X},{g + 1},{Z}")
    return block_stamp(blocks)


# ---- rowing boats out on the open water, ready to ride --------------------------------------------------

def river_boats(G, n=40):
    """Free-floating boats (ordinary Minecraft boats, so they work in Java and Bedrock) dotted along the Thames
    and on the lakes, away from the banks and at least 40 m apart."""
    import lock
    from scipy import ndimage
    w = G["water"]
    open_water = (w > -999) & G["mask"] & (ndimage.distance_transform_edt(w > -999) >= 6)
    open_water &= ~ndimage.binary_dilation(G["br_deck"] > -999, iterations=8)   # not under bridges
    zs, xs = np.nonzero(open_water)
    rng = np.random.default_rng(77)
    placed = []
    for i in rng.permutation(len(zs)):
        x, z = int(xs[i]), int(zs[i])
        if any((x - a) ** 2 + (z - b) ** 2 < 40 ** 2 for a, b in placed):
            continue
        b = lock.boat(x + 0.5, int(w[z, x]) + 0.9, z + 0.5, rot=float(rng.uniform(0, 360)))
        b["Type"] = ["oak", "spruce", "birch", "dark_oak", "mangrove"][len(placed) % 5]
        lock.add_entity(G, b)
        placed.append((x, z))
        if len(placed) >= n:
            break
    print(f"river boats: {len(placed)} free-floating")


# ---- moored narrowboats and Whittington's Tea Barge, block-built so you can walk aboard ------------------

NARROWBOAT_COLOURS = [("green_concrete", "red_concrete"), ("red_terracotta", "yellow_terracotta"),
                      ("blue_terracotta", "white_concrete"), ("cyan_terracotta", "black_concrete"),
                      ("red_concrete", "green_concrete"), ("light_blue_terracotta", "white_concrete")]
TEA_BARGE_X = (3880, 3940)   # Hills Meadow's bank (north bank, upstream of the weir), where Whittington's moors


def find_moorings(G, L, Wd, n, x_range=None, spacing=35, rng=None, bank_side=None, z_range=None):
    """Straight stretches of Thames bank a boat L long x Wd wide fits against, squared to the grid:
    [(x, z, ux, uz, vx, vz)], origin at the stern on the bank side, u along the boat, v away from the bank."""
    w = G["water"]
    river = (w == 35) | (w == 36)
    land = G["mask"] & (w == -999)
    clear = ~np.zeros_like(river)
    if "br_deck" in G:
        from scipy import ndimage
        clear = ~ndimage.binary_dilation(G["br_deck"] > -999, iterations=10)
    import lock
    lx0, lx1, lz0, lz1 = lock.SITE
    Hh, Ww = river.shape
    zs, xs = np.nonzero(river & np.roll(land, 1, 0) | river & np.roll(land, -1, 0) | river & np.roll(land, 1, 1) |
                        river & np.roll(land, -1, 1))
    order = (rng or np.random.default_rng(5)).permutation(len(zs))
    out = []
    for i in order:
        x, z = int(xs[i]), int(zs[i])
        if x_range and not (x_range[0] <= x <= x_range[1]):
            continue
        if z_range and not (z_range[0] <= z <= z_range[1]):
            continue
        if lx0 - 30 <= x <= lx1 + 30 and lz0 - 30 <= z <= lz1 + 30:
            continue
        if any((x - a) ** 2 + (z - b) ** 2 < spacing ** 2 for a, b, *_ in out):
            continue
        for (ux, uz) in ((1, 0), (0, 1)):
            for side in (1, -1):
                vx, vz = uz * side, ux * side                    # away from the bank
                if bank_side and (vx, vz) != bank_side:
                    continue
                cells = [(x + ux * a + vx * b, z + uz * a + vz * b) for a in range(L) for b in range(Wd)]
                bank = [(x + ux * a - vx, z + uz * a - vz) for a in range(L)]
                if not all(0 <= cz < Hh and 0 <= cx < Ww and river[cz, cx] and clear[cz, cx] for cx, cz in cells):
                    continue
                if sum(0 <= cz < Hh and 0 <= cx < Ww and land[cz, cx] for cx, cz in bank) < 0.7 * L:
                    continue
                if len({int(w[cz, cx]) for cx, cz in cells}) != 1:
                    continue
                out.append((x, z, ux, uz, vx, vz))
                break
            else:
                continue
            break
        if len(out) >= n:
            break
    return out


def hull(P, blocks, G, site, L, Wd, hull_c, cabin_c, trim_c, cabin=(3, 3), side_door=None):
    """A barge at its mooring: hull floor at the water line, gunwales, a cabin with windows and a stern door,
    a pointed bow, a tiller on the stern deck. Returns (wl, cell(i, j) -> (x, z))."""
    x, z, ux, uz, vx, vz = site
    wl = int(G["water"][z, x])

    def cell(i, j):
        return x + ux * i + vx * j, z + uz * i + vz * j
    c0, c1 = cabin[0], L - cabin[1]
    for i in range(L):
        for j in range(Wd):
            X, Z = cell(i, j)
            if i == L - 1 and j in (0, Wd - 1):
                continue                                          # pointed bow
            edge = j in (0, Wd - 1) or i in (0, L - 1) or (i == L - 2 and j in (1, Wd - 2) and Wd > 3)
            blocks[(X, wl, Z)] = P(hull_c) if edge else P("spruce_planks")   # floorboards inside
            blocks[(X, wl - 1, Z)] = P("black_concrete")          # below the water line
            in_cabin = c0 <= i < c1
            if in_cabin:
                wall = edge or i in (c0, c1 - 1)
                for y in (wl + 1, wl + 2):
                    if wall:
                        door = (i == c0 and j == Wd // 2) or (side_door is not None and j == 0 and
                                                              i in (side_door, side_door + 1))
                        win = y == wl + 2 and (i - c0) % 3 == 1
                        blocks[(X, y, Z)] = P("air") if door else (
                            P("glass_pane", north="true", south="true", east="true", west="true") if win else P(cabin_c))
                    else:
                        blocks[(X, y, Z)] = P("air")
                blocks[(X, wl + 3, Z)] = P(trim_c) if edge else P("smooth_stone_slab", type="bottom")
            else:
                for y in (wl + 1, wl + 2):
                    blocks[(X, y, Z)] = P("air")
                if edge:
                    blocks[(X, wl + 1, Z)] = P(hull_c + "") if hull_c.endswith("concrete") else P(hull_c)
    sx, sz = cell(0, Wd // 2)
    blocks[(sx, wl + 1, sz)] = P("spruce_fence")                  # the tiller
    blocks[(sx, wl + 2, sz)] = P("spruce_fence")
    return wl, cell


def barges(G, P):
    rng = np.random.default_rng(31)
    blocks = {}
    # Whittington's Tea Barge (Hills Meadow): a 20 x 5 wide-beam, dark green hull, cream cabin, tables inside
    # Whittington's lies alongside Hills Meadow's bank (which runs on a slant there): moored at the straightest
    # 20 m of it, with a wooden pontoon deck over the water left between the barge and the bank
    L_tea = 20
    xa, xb = TEA_BARGE_X
    w = G["water"]

    def bank_z(X):
        Z = 4140
        while Z > 4100 and w[Z, X] > -999:
            Z -= 1
        return Z                                                  # last land row

    best = None
    for xs_ in range(xa, xb - L_tea):
        zb = [bank_z(X) for X in range(xs_, xs_ + L_tea)]
        z0 = max(zb) + 1
        gap = sum(z0 - 1 - b_ for b_ in zb)
        if best is None or gap < best[0]:
            best = (gap, xs_, z0, zb)
    _, x0_, z0_, zb = best
    tea = (x0_, z0_, 1, 0, 0, 1)                                  # stern at (x, z), along +x, away from the bank +z
    wl_ = int(w[z0_ + 2, x0_ + 5])
    for i, b_ in enumerate(zb):
        for Z in range(b_ + 1, z0_):
            blocks[(x0_ + i, wl_, Z)] = P("spruce_planks")       # the pontoon
            if Z == b_ + 1 and i % 4 == 0:
                blocks[(x0_ + i, wl_ - 1, Z)] = P("spruce_log", axis="y")
    if True:
        wl, cell = hull(P, blocks, G, tea, L_tea, 5, "dark_prismarine", "birch_planks", "dark_prismarine",
                        cabin=(3, 2), side_door=8)
        for i in range(3, L_tea - 2):                             # dark green roof, blue curtains by the windows
            for j in range(5):
                X, Z = cell(i, j)
                blocks[(X, wl + 3, Z)] = P("dark_prismarine")    # bottle green, as in the photos
            if (i - 3) % 3 == 1:
                for j in (1, 3):
                    X, Z = cell(i + 1, j)
                    blocks.setdefault((X, wl + 2, Z), P("blue_wool"))
        # white plastic tables and chairs on the bank, and the A-board
        for k, i in enumerate((2, 13, 17)):                       # on the pontoon or the bank beside the barge
            tX, tZ = cell(i, -2)
            if 0 <= tZ < G["mask"].shape[0]:
                g = wl if G["water"][tZ, tX] > -999 else int(G["ground"][tZ, tX])
                blocks[(tX, g + 1, tZ)] = P("birch_fence")
                blocks[(tX, g + 2, tZ)] = P("white_carpet")
                for d in (-1, 1):
                    cX, cZ = cell(i + d, -3)
                    cg = wl if G["water"][cZ, cX] > -999 else int(G["ground"][cZ, cX])
                    blocks[(cX, cg + 1, cZ)] = P(
                        "quartz_stairs", facing={(1, 0): "east", (-1, 0): "west", (0, 1): "south",
                                                 (0, -1): "north"}[(tea[2] * d, tea[3] * d)], half="bottom",
                        shape="straight")
        for i in range(5, 15, 3):                                 # tea tables with a chair either end
            X, Z = cell(i, 2)
            blocks[(X, wl + 1, Z)] = P("spruce_fence")
            blocks[(X, wl + 2, Z)] = P("white_carpet")
            for di, face in ((-1, None), (1, None)):
                cX, cZ = cell(i + di, 2)
                blocks[(cX, wl + 1, cZ)] = P("oak_stairs", facing={(1, 0): "east", (-1, 0): "west", (0, 1): "south",
                                                                     (0, -1): "north"}[(tea[2] * di, tea[3] * di)],
                                             half="bottom", shape="straight")
        for j in (1, 2, 3):                                       # the counter with cakes, at the bow end
            X, Z = cell(16, j)
            blocks[(X, wl + 1, Z)] = P("spruce_planks")
            blocks[(X, wl + 2, Z)] = P("cake", bites=0)
        for i in (6, 12):
            X, Z = cell(i, 2)
            blocks[(X, wl + 2, Z)] = blocks.get((X, wl + 2, Z), P("white_carpet"))
            lX, lZ = cell(i + 1, 1)
            blocks[(lX, wl + 2, lZ)] = P("lantern", hanging="true") if False else P("light", level=13)
        # a black rubbing strake round the hull at the water line, and dark window frames (spruce trapdoor shutters)
        for i in range(L_tea - 1):
            for j in (-1, 5):
                X, Z = cell(i, j)
                if G["water"][Z, X] > -999 and (X, wl, Z) not in blocks:
                    blocks[(X, wl, Z)] = P("dark_oak_slab", type="bottom")
        # gangplank from the bank to the side door
        for k in (1, 2):
            gX, gZ = cell(8, -k)
            gX2, gZ2 = cell(9, -k)
            for (a_, b_) in ((gX, gZ), (gX2, gZ2)):
                blocks[(a_, max(wl, int(G["ground"][b_, a_])) , b_)] = P("spruce_slab", type="top")
        sX, sZ = cell(12, -1)
        g = int(G["ground"][sZ, sX])
        blocks[(sX, max(g, wl) + 1, sZ)] = P("oak_sign", rotation={(0, 1): 0, (0, -1): 8, (1, 0): 12, (-1, 0): 4}[(-tea[4], -tea[5])])
        import lock
        G["block_entities"].setdefault((sX // 16, sZ // 16), []).append(
            lock.sign_entity(int(sX), int(max(g, wl) + 1), int(sZ), ["Whittington's", "Tea Barge", "afternoon tea", "come aboard"]))
        print(f"tea barge at {tea[0]},{tea[1]}")
    # narrowboats moored along the Thames
    boats = find_moorings(G, 17, 3, 25, rng=rng, spacing=45)
    boats = [b for b in boats if not tea or (b[0] - tea[0]) ** 2 + (b[1] - tea[1]) ** 2 > 40 ** 2]
    for k, site in enumerate(boats):
        cab, trim = NARROWBOAT_COLOURS[k % len(NARROWBOAT_COLOURS)]
        wl, cell = hull(P, blocks, G, site, 17, 3, "black_concrete", cab, trim, cabin=(3, 3))
        for i in (5, 9, 12):                                      # clutter on the roof: pots, a bike, logs
            X, Z = cell(i, 1)
            blocks[(X, wl + 4, Z)] = P(["flower_pot", "potted_red_tulip", "oak_log"][(i + k) % 3],
                                       **({"axis": "x"} if (i + k) % 3 == 2 else {}))
        X, Z = cell(7, 1)
        blocks[(X, wl + 1, Z)] = P("red_bed", facing="north", part="foot", occupied="false") if False else P("barrel", facing="up", open="false")
    print(f"barges: {len(boats)} narrowboats, tea barge {'yes' if tea else 'no'}")
    return block_stamp(blocks)


# ---- small helpers shared by the Christmas extras ----------------------------------------------------------

def area_mask(G, osm_id):
    from PIL import Image, ImageDraw
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    a = next(a for a in osm["areas"] if a["id"] == osm_id)
    img = Image.new("L", (Ww, Hh), 0)
    ImageDraw.Draw(img).polygon([xz(*p) for p in a["rings"][0]], fill=1)
    return np.asarray(img).astype(bool) & G["mask"]


def open_spot(G, inside, w, d, target=None):
    """The w x d box of open ground (grass or paving, no building or water) inside `inside` nearest target."""
    ok = inside & (G["building"] == 0) & (G["water"] == -999) & np.isin(G["surface"], (1, 9, 13, 15))
    zs, xs = np.nonzero(inside)
    tx, tz = target if target is not None else (xs.mean(), zs.mean())
    best = None
    for z in range(zs.min(), zs.max() - d + 1):
        for x in range(xs.min(), xs.max() - w + 1):
            if ok[z:z + d, x:x + w].all():
                dist = (x + w / 2 - tx) ** 2 + (z + d / 2 - tz) ** 2
                if best is None or dist < best[0]:
                    best = (dist, x, z)
    return best[1:] if best else None


def sign_post(G, P, blocks, x, y, z, rot, lines):
    import lock
    blocks[(int(x), int(y), int(z))] = P("oak_sign", rotation=rot)
    G["block_entities"].setdefault((int(x) // 16, int(z) // 16), []).append(lock.sign_entity(int(x), int(y), int(z), lines))


def xmas_tree(P, blocks, x, g, z, h=6, rng=None):
    rng = rng or np.random.default_rng(1)
    for y in range(g + 1, g + h):
        blocks[(x, y, z)] = P("spruce_log", axis="y")
    for y in range(g + 2, g + h):
        r = (g + h - y) / 2.5
        for dz in range(-2, 3):
            for dx in range(-2, 3):
                if (dx or dz) and np.hypot(dx, dz) <= r + 0.3:
                    lit = rng.random() < 0.18
                    blocks[(x + dx, y, z + dz)] = (P(["glowstone", "sea_lantern", "redstone_block"][rng.integers(2)]) if lit
                                                   else P("spruce_leaves", persistent="true"))
    blocks[(x, g + h, z)] = P("spruce_leaves", persistent="true")
    blocks[(x, g + h + 1, z)] = P("gold_block")


# ---- the pop-up cinema at Caversham Court Gardens, lit at night -----------------------------------------

def cinema(G, P):
    """An outdoor cinema on the lawn (from the user's photo): a big black inflatable screen whose face glows
    (sea lanterns) so it's lit at night, black speaker stacks either side, rows of red-and-white deckchairs,
    red and blue beanbags at the front, festoon lights round the edge and a sign."""
    inside = area_mask(G, "w183189177")                           # Caversham Court Gardens
    spot = open_spot(G, inside, 22, 26)
    if spot is None:
        print("cinema: no room")
        return block_stamp({})
    x0, z0 = spot
    blocks = {}
    g = int(np.median(G["ground"][z0:z0 + 26, x0:x0 + 22]))
    # the screen across the south end, facing north (the audience looks south, towards the river)
    sz = z0 + 24
    for x in range(x0 + 2, x0 + 20):
        for y in range(g + 1, g + 12):
            face = x0 + 3 <= x <= x0 + 18 and g + 3 <= y <= g + 10
            blocks[(x, y, sz)] = P("sea_lantern") if face else P("black_concrete")
            blocks[(x, y, sz + 1)] = P("black_concrete")
    for x in range(x0 + 4, x0 + 18, 3):                           # hidden lights so the lawn glows in front
        blocks[(x, g + 2, sz - 3)] = P("light", level=12)
    for sx in (x0, x0 + 20):                                       # speaker stacks
        for y in range(g + 1, g + 5):
            for dx in (0, 1):
                blocks[(sx + dx, y, sz - 1)] = P("black_concrete") if y != g + 3 else P("gray_concrete")
    # beanbags at the front, then deckchairs, facing the screen (a stair's back is its "facing" side: north)
    for x in range(x0 + 3, x0 + 19):
        if x % 2:
            blocks[(x, g + 1, sz - 6)] = P("red_wool" if (x // 2) % 2 else "blue_wool")
            blocks[(x, g + 1, sz - 8)] = P("blue_wool" if (x // 2) % 2 else "red_wool")
    for r, z in enumerate(range(sz - 11, z0 + 1, -3)):
        for x in range(x0 + 3, x0 + 19):
            if (x - x0) % 8 == 6:                                  # aisles
                continue
            blocks[(x, g + 1, z)] = P("quartz_stairs" if (x + r) % 2 else "red_nether_brick_stairs",
                                      facing="north", half="bottom", shape="straight")
    # festoon lights on posts round the seating
    for k, (x, z) in enumerate([(x0, z) for z in range(z0, sz, 5)] + [(x0 + 21, z) for z in range(z0, sz, 5)]):
        gg = int(G["ground"][z, x])
        for y in (gg + 1, gg + 2, gg + 3):
            blocks[(x, y, z)] = P("spruce_fence")
        blocks[(x, gg + 4, z)] = P("lantern", hanging="false")
    sign_post(G, P, blocks, x0 + 11, int(G["ground"][z0, x0 + 11]) + 1, z0 - 1, 8,
              ["Caversham Court", "POP-UP CINEMA", "tonight: the", "Christmas film"])
    G.setdefault("no_trees", []).append((x0 - 2, z0 - 2, x0 + 24, sz + 3))
    print(f"cinema at {x0},{z0} (screen z {sz})")
    return block_stamp(blocks)


# ---- treasure at every school: a lit tree with a chest of presents under it -----------------------------

SCHOOLS = ["w54890383", "w54896165", "w77517876", "w137356791", "w144371895", "w153747650", "w182216368",
           "w388293024", "w390632900", "w391622941", "w392621052", "w703348397", "w1314689827"]


def school_treasure(G, P):
    import anvil
    blocks = {}
    rng = np.random.default_rng(12)
    n = 0
    for sid in SCHOOLS:
        try:
            inside = area_mask(G, sid)
        except StopIteration:
            continue
        spot = open_spot(G, inside, 7, 7)
        if spot is None:
            continue
        x, z = spot[0] + 3, spot[1] + 3
        g = int(G["ground"][z, x])
        xmas_tree(P, blocks, x, g, z, 6, rng)
        G.setdefault("no_trees", []).append((x - 4, z - 4, x + 4, z + 5))
        cx, cz = x, z + 3                                          # the chest, in front of the tree
        blocks[(cx, g + 1, cz)] = P("chest", facing="south", type="single", waterlogged="false")
        items = [("diamond", 1), ("cake", 1), ("cookie", 16), ("firework_rocket", 8), ("gold_ingot", 3),
                 ("glow_berries", 8)]
        G["block_entities"].setdefault((cx // 16, cz // 16), []).append(
            {"id": "minecraft:chest", "x": cx, "y": g + 1, "z": cz,
             "Items": [{"Slot": anvil.Byte(k * 2), "id": "minecraft:" + it, "count": c} for k, (it, c) in enumerate(items)]})
        sign_post(G, P, blocks, cx + 1, g + 1, cz, 0, ["You found the", "CAVCRAFT", "TREASURE!", "Merry Christmas"])
        n += 1
    print(f"school treasure: {n} schools")
    return block_stamp(blocks)


# ---- Christmas in Caversham centre: lights across the shopping streets, a town tree ----------------------

XMAS_STREETS = ("Church Street", "Prospect Street", "Bridge Street")


def xmas_centre(G, P):
    """Strings of coloured lights hung across the centre's streets every 12 m, from the building on one side to
    the building on the other at first-floor height, and a big lit tree with a star at the junction."""
    osm = json.load(open("build/osm.json"))
    Hh, Ww = G["mask"].shape
    bid, ground = G["building"], G["ground"]
    rng = np.random.default_rng(24)
    blocks = {}
    strings = 0
    ends = {}
    for l in osm["lines"]:
        name = l["tags"].get("name")
        if name not in XMAS_STREETS or not l["tags"].get("highway"):
            continue
        pts = np.array([xz(*q) for q in l["pts"]], float)
        ends.setdefault(name, []).append(pts)
        walked = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            L = np.hypot(*(b - a))
            if L < 1:
                continue
            u = (b - a) / L
            nv = np.array([-u[1], u[0]])
            for t in np.arange(0, L, 1.0):
                walked += 1
                if int(walked) % 12:
                    continue
                c = a + u * t
                X, Z = int(round(c[0])), int(round(c[1]))
                if not (0 <= Z < Hh and 0 <= X < Ww) or not G["mask"][Z, X]:
                    continue
                hit = []
                for sg in (1, -1):                                 # the building face each side
                    for r in range(2, 16):
                        q = (c + nv * sg * r).round().astype(int)
                        if not (0 <= q[1] < Hh and 0 <= q[0] < Ww):
                            break
                        if bid[q[1], q[0]]:
                            hit.append(c + nv * sg * (r - 1))
                            break
                if len(hit) < 2:
                    continue
                y = int(ground[Z, X]) + 6
                p0, p1 = hit
                n = int(np.hypot(*(p1 - p0))) + 1
                axis = "x" if abs(nv[0]) >= abs(nv[1]) else "z"
                colours = ["ochre_froglight", "verdant_froglight", "pearlescent_froglight", "shroomlight", "sea_lantern"]
                for k in range(n + 1):
                    q = (p0 + (p1 - p0) * k / n).round().astype(int)
                    sag = int(round(1.2 * np.sin(np.pi * k / n)))  # the string droops in the middle
                    if k % 2:
                        blocks[(int(q[0]), y - sag, int(q[1]))] = P("chain", axis=axis)
                    else:
                        c_ = colours[(k // 2) % len(colours)]
                        blocks[(int(q[0]), y - sag, int(q[1]))] = P(c_, axis="y") if "froglight" in c_ else P(c_)
                strings += 1
    # the town tree: open ground nearest where the streets meet
    tree = None
    if len(ends) >= 2:
        allp = [p for v in ends.values() for arr in v for p in arr]
        names = list(ends)
        best = None
        for pa in [p for arr in ends[names[0]] for p in arr]:
            for nb in names[1:]:
                for pb in [p for arr in ends[nb] for p in arr]:
                    d = np.hypot(*(pa - pb))
                    if best is None or d < best[0]:
                        best = (d, pa)
        jx, jz = best[1]
        ok = (bid == 0) & (G["water"] == -999) & np.isin(G["surface"], (1, 5, 9))
        zs, xs = np.nonzero(ok[int(jz) - 25:int(jz) + 25, int(jx) - 25:int(jx) + 25])
        good = [(x, z) for x, z in zip(xs, zs) if ok[int(jz) - 25 + z - 2:int(jz) - 25 + z + 3,
                                                      int(jx) - 25 + x - 2:int(jx) - 25 + x + 3].all()]
        if good:
            x, z = min(good, key=lambda v: (v[0] - 25) ** 2 + (v[1] - 25) ** 2)
            tree = (int(jx) - 25 + x, int(jz) - 25 + z)
            g = int(ground[tree[1], tree[0]])
            for y in range(g + 1, g + 11):
                blocks[(tree[0], y, tree[1])] = P("spruce_log", axis="y")
            for y in range(g + 3, g + 11):
                r = (g + 11 - y) / 3.2
                for dz in range(-3, 4):
                    for dx in range(-3, 4):
                        if (dx or dz) and np.hypot(dx, dz) <= r + 0.3:
                            lit = rng.random() < 0.2
                            blocks[(tree[0] + dx, y, tree[1] + dz)] = (
                                P(["glowstone", "sea_lantern", "redstone_block", "gold_block"][rng.integers(4)]) if lit
                                else P("spruce_leaves", persistent="true"))
            blocks[(tree[0], g + 11, tree[1])] = P("spruce_leaves", persistent="true")
            blocks[(tree[0], g + 12, tree[1])] = P("glowstone")       # the star
            blocks[(tree[0], g + 13, tree[1])] = P("end_rod", facing="up")
    print(f"christmas centre: {strings} strings of lights, town tree at {tree}")
    return block_stamp(blocks)
