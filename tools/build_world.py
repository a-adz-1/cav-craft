#!/usr/bin/env python3
"""Builds the Cavcraft Java world from build/layers.npz (+ lidar, buildings, features).

    .venv/bin/python tools/build_world.py world/Cavcraft

Minecraft x = easting - E0, z = N1 - northing, y = metres above Ordnance Datum.
"""
import json
import multiprocessing as mp
import os
import shutil
import sys
import time
import zlib

import numpy as np

import anvil
from box import E0, N1
from surfaces import SURFACE

Y_MIN, Y_MAX = -64, 256
H = Y_MAX - Y_MIN


class Palette:
    def __init__(self):
        self.entries, self.index = [], {}
        self("air")

    def __call__(self, name, **props):
        key = ("minecraft:" + name, tuple(sorted((k, str(v).lower()) for k, v in props.items())) or None)
        if key not in self.index:
            self.index[key] = len(self.entries)
            self.entries.append(key)
        return self.index[key]


P = Palette()
AIR, BEDROCK, STONE, DIRT, GRASS = P("air"), P("bedrock"), P("stone"), P("dirt"), P("grass_block")
WATER, GRAVEL, SAND, GLASS = P("water", level=0), P("gravel"), P("sand"), P("glass")

TOP = {  # surface class -> top block
    "void": AIR, "grass": GRASS, "water": GRAVEL, "road": P("gray_concrete"), "minor_road": P("gray_concrete"),
    "footway": P("polished_andesite"), "path": P("dirt_path"), "track": P("coarse_dirt"), "parking": P("stone"),
    "paved": P("smooth_stone"), "sand": SAND, "farmland": P("farmland", moisture=7),
    "allotment": P("farmland", moisture=7), "sports": GRASS, "tennis": P("green_terracotta"), "woodland": GRASS,
    "scrub": GRASS, "cemetery": GRASS, "railway": GRAVEL, "rock": STONE, "wetland": P("mud"), "bridge": STONE,
}
ROAD_IDX = [SURFACE.index(n) for n in ("road", "minor_road", "footway")]
ROAD_SLAB = P("blackstone_slab", type="bottom")   # no concrete slab exists; dark like the tarmac
FOOT_SLAB = P("polished_andesite_slab", type="bottom")
SUB = {"sand": SAND, "water": DIRT, "railway": GRAVEL, "rock": STONE}
TOP_LUT = np.array([TOP[n] for n in SURFACE], np.int32)
SUB_LUT = np.array([SUB.get(n, DIRT) for n in SURFACE], np.int32)

PLANTS = {
    "grass": [(0.08, P("short_grass")), (0.004, P("dandelion")), (0.004, P("poppy"))],
    "woodland": [(0.15, P("fern")), (0.05, P("short_grass"))],
    "scrub": [(0.25, P("sweet_berry_bush", age=3)), (0.1, P("short_grass"))],
    "cemetery": [(0.02, P("cobblestone_wall"))],
    "farmland": [(1.0, P("wheat", age=7))],
    "allotment": [(0.5, P("carrots", age=7)), (0.5, P("potatoes", age=7))],
    "wetland": [(0.3, P("short_grass"))],
}

G = {}   # globals shared with forked workers


def make_chunk(cx, cz):
    x0, z0 = cx * 16, cz * 16
    sl = np.s_[z0:z0 + 16, x0:x0 + 16]
    mask = G["mask"][sl]
    if mask.shape != (16, 16) or not mask.any():
        if mask.size == 0 or not mask.any():
            return None
        pad = ((0, 16 - mask.shape[0]), (0, 16 - mask.shape[1]))
    else:
        pad = None

    def get(name, fill=0):
        a = G[name][sl]
        return np.pad(a, pad, constant_values=fill) if pad else a

    mask = get("mask", False)
    g = get("ground").astype(np.int32)
    w = get("water", -999).astype(np.int32)
    s = get("surface").astype(np.int32)
    Y = np.arange(Y_MIN, Y_MAX, dtype=np.int32)[:, None, None]

    b = np.zeros((H, 16, 16), np.int32)
    b[(Y < g - 3)] = STONE
    sub = (Y >= g - 3) & (Y < g)
    b[:] = np.where(sub, SUB_LUT[s][None], b)
    b[:] = np.where(Y == g, TOP_LUT[s][None], b)
    # road steps: where a road cell sits a block below a road neighbour, a half slab on it makes a ramp
    rd = np.isin(s, ROAD_IDX)
    up = np.zeros((16, 16), bool)
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        nb_g = np.roll(g, sh, ax)
        nb_r = np.roll(rd, sh, ax)
        up |= rd & nb_r & (nb_g == g + 1)
    zz, xx = np.nonzero(up)
    yy = g[zz, xx] + 1 - Y_MIN
    ok = (yy >= 0) & (yy < H)
    slab = np.where(s[zz, xx] == SURFACE.index("footway"), FOOT_SLAB, ROAD_SLAB)
    b[yy[ok], zz[ok], xx[ok]] = slab[ok]
    b[(Y > g) & (Y <= w)] = WATER
    if "sandy_bed" in G:
        b[:] = np.where(get("sandy_bed", False)[None] & (Y == g), SAND, b)
    b[0] = BEDROCK

    # plants on top of open ground
    rng = np.random.default_rng((cx * 73856093) ^ (cz * 19349663) & 0xffffffff)
    r = rng.random((16, 16))
    top = np.zeros((16, 16), np.int32)
    for cls, plants in PLANTS.items():
        acc = 0.0
        here = s == SURFACE.index(cls)
        for p, block in plants:
            top[here & (r >= acc) & (r < acc + p)] = block
            acc += p
    top[w > -999] = 0
    zz, xx = np.nonzero(top)
    yy = g[zz, xx] + 1 - Y_MIN
    ok = (yy >= 0) & (yy < H)
    b[yy[ok], zz[ok], xx[ok]] = top[zz[ok], xx[ok]]

    for stamp in G.get("stamps", []):
        stamp(b, x0, z0, g, w, s, Y)

    # where the world is cut off, water stops at glass so it can't pour out
    m = mask
    edge_cells = np.zeros_like(m)
    full = G["mask"]
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        zi = np.clip(np.arange(z0, z0 + 16) + dz, 0, full.shape[0] - 1)
        xi = np.clip(np.arange(x0, x0 + 16) + dx, 0, full.shape[1] - 1)
        nb = full[zi][:, xi]
        if pad:
            nb = np.pad(nb[:16 - pad[0][1], :16 - pad[1][1]], pad, constant_values=False)
        edge_cells |= m & ~nb
    b[:] = np.where(edge_cells[None] & (b == WATER), GLASS, b)
    b[:, ~m] = AIR
    return b


def build_region(args):
    rx, rz, out = args
    chunks = {}
    for lz in range(32):
        for lx in range(32):
            cx, cz = rx * 32 + lx, rz * 32 + lz
            if cx < 0 or cz < 0:
                continue
            blk = make_chunk(cx, cz)
            if blk is not None:
                chunks[(lx, lz)] = anvil.chunk_nbt(cx, cz, blk, P.entries, Y_MIN, G.get("block_entities", {}).get((cx, cz), []),
                                                 G.get("block_ticks", {}).get((cx, cz), []))
    if chunks:
        anvil.write_region(os.path.join(out, "region", f"r.{rx}.{rz}.mca"), chunks)
    ents = {(cx - rx * 32, cz - rz * 32): {"DataVersion": anvil.DATA_VERSION, "Position": anvil.int_array([cx, cz]),
                                           "Entities": e}
            for (cx, cz), e in G.get("entities", {}).items() if cx // 32 == rx and cz // 32 == rz}
    if ents:
        anvil.write_region(os.path.join(out, "entities", f"r.{rx}.{rz}.mca"), ents)
    return len(chunks)


def main():
    out = sys.argv[1]
    t0 = time.time()
    layers = dict(np.load("build/layers.npz"))
    lidar = np.load("build/lidar.npz")
    buildings = json.load(open("build/buildings.json"))
    G.update(layers)
    import houses
    houses.prepare(G, P, layers, lidar, buildings)
    import features
    features.setup(G, P, lidar)
    G["stamps"].insert(0, houses.stamp_factory(G, P))
    print(f"prepared in {time.time() - t0:.0f}s, palette {len(P.entries)}")

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "region"))
    os.makedirs(os.path.join(out, "entities"))
    hgt, wid = layers["mask"].shape
    jobs = [(rx, rz, out) for rz in range(-(-hgt // 512)) for rx in range(-(-wid // 512))]
    with mp.get_context("fork").Pool(min(len(jobs), os.cpu_count())) as pool:
        n = sum(pool.map(build_region, jobs))
    sx, sy, sz = G["spawn"]
    anvil.write_level_dat(os.path.join(out, "level.dat"), "Cavcraft", (sx, sy, sz), (wid / 2, hgt / 2), max(wid, hgt) + 64)
    with open(os.path.join(out, "CREDITS.txt"), "w") as f:
        f.write(open("CREDITS.md").read())
    print(f"{n} chunks in {time.time() - t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
