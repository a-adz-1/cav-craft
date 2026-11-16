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

WALLS_HOUSE = [P("bricks"), P("bricks"), P("bricks"), P("white_terracotta"), P("smooth_quartz"),
               P("granite"), P("light_gray_terracotta")]
ROOFS_HOUSE = [P("deepslate_tiles"), P("deepslate_tiles"), P("terracotta"), P("brown_terracotta"),
               P("polished_blackstone")]
WALLS_BIG = [P("light_gray_concrete"), P("white_concrete"), P("smooth_stone"), P("bricks"), P("cyan_terracotta")]
ROOF_FLAT = P("gray_concrete")
WALL_CHURCH, ROOF_CHURCH = P("stone_bricks"), P("deepslate_tiles")
WALL_SHED, ROOF_SHED = P("spruce_planks"), P("dark_oak_planks")
FLOOR = P("oak_planks")
BIG = {"commercial", "industrial", "retail", "warehouse", "office", "school", "university", "college",
       "hospital", "supermarket", "sports_centre", "civic", "public", "hotel", "apartments", "train_station"}
CHURCH = {"church", "chapel", "cathedral"}
SHED = {"shed", "garage", "garages", "hut", "cabin", "greenhouse", "carport", "boathouse"}

G = {}   # globals shared with forked workers


def prepare(layers, lidar, buildings):
    """Whole-map arrays the chunk builder reads: building base/roof heights and materials."""
    ground = layers["ground"].astype(np.int32)
    bid = layers["building"]
    n = len(buildings)
    inb = bid > 0
    sums = np.bincount(bid[inb], ground[inb], minlength=n)
    counts = np.bincount(bid[inb], minlength=n)
    base_of = np.zeros(n, np.int32)
    base_of[counts > 0] = np.round(sums[counts > 0] / counts[counts > 0])
    base = np.where(inb, base_of[bid], 0)

    dsm = np.nan_to_num(lidar["dsm"], nan=0.0)
    roof = np.where(inb, np.round(dsm).astype(np.int32), 0)
    # tall, thin outliers (trees over a roof) are cut to the building's 90th percentile height
    p90 = np.zeros(n, np.int32)
    order = np.argsort(bid[inb], kind="stable")
    hb = (roof[inb] - base[inb])[order]
    ids = bid[inb][order]
    starts = np.searchsorted(ids, np.arange(n))
    ends = np.searchsorted(ids, np.arange(n), side="right")
    for i in range(1, n):
        if ends[i] > starts[i]:
            p90[i] = int(np.percentile(hb[starts[i]:ends[i]], 90))
    roof = np.where(inb, np.clip(roof, base + 3, base + np.maximum(p90[bid], 3)), 0)

    wall_of = np.zeros(n, np.int32)
    roof_of = np.zeros(n, np.int32)
    flat_of = np.zeros(n, bool)
    for i, b in enumerate(buildings):
        if not b:
            continue
        t = b["tags"].get("building", "yes")
        h = zlib.crc32(b["id"].encode()) & 0xffff
        if t in CHURCH or b["tags"].get("amenity") == "place_of_worship":
            wall_of[i], roof_of[i] = WALL_CHURCH, ROOF_CHURCH
        elif t in SHED:
            wall_of[i], roof_of[i] = WALL_SHED, ROOF_SHED
        elif t in BIG or counts[i] > 600:
            wall_of[i], roof_of[i], flat_of[i] = WALLS_BIG[h % len(WALLS_BIG)], ROOF_FLAT, True
        else:
            wall_of[i], roof_of[i] = WALLS_HOUSE[h % len(WALLS_HOUSE)], ROOFS_HOUSE[(h >> 4) % len(ROOFS_HOUSE)]
    # big flat-roofed buildings: one roof height for the whole thing
    flat = inb & flat_of[bid]
    roof = np.where(flat, base + np.maximum(p90[bid], 3), roof)

    # edge cells (a 4-neighbour is a different building or none) become walls
    edge = np.zeros_like(inb)
    shell = roof.copy()
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        nb = np.roll(bid, sh, ax)
        edge |= inb & (nb != bid)
        shell = np.minimum(shell, np.where(nb == bid, np.roll(roof, sh, ax), shell))
    G.update(b_base=base, b_roof=roof, b_shell=shell, b_edge=edge,
             b_wall=np.where(inb, wall_of[bid], 0), b_rooftop=np.where(inb, roof_of[bid], 0))


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
    b[(Y > g) & (Y <= w)] = WATER
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

    # buildings
    bb = get("b_base")
    inb = get("b_wall") > 0
    if inb.any():
        roof, shell, edge = get("b_roof"), get("b_shell"), get("b_edge", False)
        wall, rooftop = get("b_wall"), get("b_rooftop")
        above = (Y > bb) & inb
        b[above & (Y <= roof)] = AIR                          # clear plants/terrain poking up inside
        b[(Y <= bb) & (Y > g) & inb] = DIRT                   # fill under the floor where ground dips
        b[(Y == bb) & inb] = FLOOR
        walls = edge & inb
        b[:] = np.where(walls & (Y > bb) & (Y < roof), wall[None], b)
        window = walls & ((Y - bb) % 3 == 2) & (((np.arange(16)[None, :] + x0) + (np.arange(16)[:, None] + z0)) % 3 != 0)
        b[window & (Y > bb) & (Y < roof - 1)] = GLASS
        b[:] = np.where(inb & (Y >= np.minimum(shell, roof)) & (Y <= roof) & (Y > bb), rooftop[None], b)

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
                chunks[(lx, lz)] = anvil.chunk_nbt(cx, cz, blk, P.entries, Y_MIN, G.get("block_entities", {}).get((cx, cz), []))
    if chunks:
        anvil.write_region(os.path.join(out, "region", f"r.{rx}.{rz}.mca"), chunks)
    return len(chunks)


def main():
    out = sys.argv[1]
    t0 = time.time()
    layers = dict(np.load("build/layers.npz"))
    lidar = np.load("build/lidar.npz")
    buildings = json.load(open("build/buildings.json"))
    G.update(layers)
    prepare(layers, lidar, buildings)
    import features
    features.setup(G, P, lidar)
    print(f"prepared in {time.time() - t0:.0f}s, palette {len(P.entries)}")

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "region"))
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
