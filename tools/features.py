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
    G["stamps"].append(furniture(G, P))
    G["trees"] = find_trees(G, lidar["vom"])
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
    zs, xs = np.nonzero(peak)
    hs = v[zs, xs]
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
    for br in json.load(open("build/bridges.json")):
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
        ys = np.round(ys).astype(int)
        r = w / 2
        for (x, z), y in zip(samples, ys):
            for dz in range(-int(r) - 1, int(r) + 2):
                for dx in range(-int(r) - 1, int(r) + 2):
                    if dx * dx + dz * dz <= r * r:
                        X, Z = int(round(x + dx)), int(round(z + dz))
                        if 0 <= X < Ww and 0 <= Z < Hh and y > deck[Z, X]:
                            deck[Z, X] = y
                            kind[Z, X] = 2 if hw in ("footway", "cycleway", "path", "pedestrian", "steps") else 1
            centre[int(round(z)), int(round(x))] = True
    # only where the deck is clear of the ground does it need building
    deck[(deck <= G["ground"] + 1) | ~G["mask"]] = -999
    inb = deck > -999
    edge = inb & ~ndimage.binary_erosion(inb)
    G.update(br_deck=deck, br_kind=kind, br_edge=edge)
    print("bridge cells:", int(inb.sum()))


def bridge_stamp(G, P):
    road, foot, under = P("gray_concrete"), P("smooth_stone"), P("stone_bricks")
    wall, rail = P("stone_brick_wall"), P("iron_bars")
    Y_MIN = -64

    def stamp(b, x0, z0, g, w, s, Y):
        d = G["br_deck"][z0:z0 + 16, x0:x0 + 16]
        if d.shape != (16, 16) or not (d > -999).any():
            return
        k = G["br_kind"][z0:z0 + 16, x0:x0 + 16]
        e = G["br_edge"][z0:z0 + 16, x0:x0 + 16]
        on = d > -999
        top = np.where(k == 2, foot, road)
        b[:] = np.where(on & (Y > d) & (Y <= d + 4), 0, b)     # headroom: no leaves on the road
        b[:] = np.where(on & (Y == d), top[None], b)
        b[:] = np.where(on & (Y >= d - 1) & (Y < d), under, b)
        b[:] = np.where(on & e & (Y == d + 1), np.where(k == 2, rail, wall)[None], b)
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
    kinds = {"hedge": (P("oak_leaves", persistent="true"), 2), "wall": (P("cobblestone_wall"), 1),
             "fence": (P("oak_fence"), 1)}
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
    # Caversham war memorial: Portland stone cross on a stepped base
    mx, mz = 3269, 3660
    gm = int(G["ground"][mz, mx])
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            blocks[(mx + dx, gm + 1, mz + dz)] = P("smooth_stone_slab", type="double")
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            blocks[(mx + dx, gm + 2, mz + dz)] = P("polished_diorite")
    for y in range(gm + 3, gm + 8):
        blocks[(mx, y, mz)] = P("quartz_pillar", axis="y")
    for dx in (-1, 1):
        blocks[(mx + dx, gm + 6, mz)] = P("quartz_block")
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
