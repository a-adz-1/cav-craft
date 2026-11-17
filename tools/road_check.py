#!/usr/bin/env python3
"""Checks every road and pavement in a built world for drops of more than one block between neighbouring
cells, reading the blocks actually written (so it sees bridges, ramps, crossings and anything stamped on top).

    .venv/bin/python tools/road_check.py world/Cavcraft [out.json]

The walking height of a cell is the top of the road-like block at or just below the planned road height (a
slab counts half). Cells with something standing on them (a building, car, lamp, bench, bridge structure) are
not walked on and are skipped; bridge decks are checked by walking each bridge separately. Prints a count by step size and the worst places; exits 1 if any drop is over 1.
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

import anvil

ROADISH = {"gray_concrete", "polished_andesite", "white_concrete", "smooth_stone", "stone", "stone_bricks",
           "dirt_path", "coarse_dirt", "gravel", "yellow_concrete", "polished_deepslate_slab",
           "polished_andesite_slab", "smooth_stone_slab", "blackstone_slab", "red_carpet",
           "spruce_slab", "spruce_planks", "light_gray_concrete", "grass_block"}
PASS = {"air", "cave_air", "light", "short_grass", "tall_grass", "fern", "dandelion", "poppy", "red_carpet",
        "white_carpet", "snow", "spruce_pressure_plate"}
W = None
LIMIT = float(os.environ.get("ROAD_LIMIT", 1))   # report steps bigger than this


def chunk_heights(args):
    world, cx, cz = args
    L = W
    x0, z0 = cx * 16, cz * 16
    road = L["road"][z0:z0 + 16, x0:x0 + 16]
    if road.shape != (16, 16) or not road.any():
        return None
    g = L["ground"][z0:z0 + 16, x0:x0 + 16].astype(int)
    ch = anvil.read_chunk(os.path.join(world, "region", f"r.{cx // 32}.{cz // 32}.mca"), cx % 32, cz % 32)
    if ch is None:
        return None
    blocks = {}
    for s in ch["sections"]:
        p = s["block_states"]["palette"]
        idx = np.zeros(4096, int) if len(p) == 1 else anvil.unpack(s["block_states"]["data"],
                                                                     max(4, (len(p) - 1).bit_length()))
        blocks[s["Y"]] = (np.array([e["Name"][10:] for e in p], object)[idx]).reshape(16, 16, 16)
    out = np.full((16, 16), np.nan)
    bld = L["building"][z0:z0 + 16, x0:x0 + 16]

    def name(y, zz, xx):
        sec = blocks.get(y // 16)
        return "air" if sec is None else sec[y % 16, zz, xx]
    for zz, xx in zip(*np.nonzero(road & (bld == 0))):
        gy = g[zz, xx]
        # something standing on the road (car, wall, lamp, bench, bridge structure): not a walking cell
        above = [name(y, zz, xx) for y in (gy + 1, gy + 2)]
        if any(n not in PASS and not n.endswith("_slab") for n in above):
            continue
        for y in range(gy + 1, gy - 4, -1):
            n = name(y, zz, xx)
            if n in ROADISH or n.endswith("_slab"):
                out[zz, xx] = y + (0.5 if n.endswith("_slab") else 1.0) - (0.9 if n == "red_carpet" else 0)
                break
    return cx, cz, out


def main():
    global W
    world = sys.argv[1]
    L = np.load("build/layers.npz")
    road = np.isin(L["surface"], (3, 4, 5)) & L["mask"] & (L["water"] == -999)
    W = {"road": road, "ground": L["ground"], "building": L["building"]}
    H, Wd = road.shape
    jobs = [(world, cx, cz) for cz in range(-(-H // 16)) for cx in range(-(-Wd // 16))
            if road[cz * 16:cz * 16 + 16, cx * 16:cx * 16 + 16].any()]
    os.nice(10)
    hgt = np.full((H, Wd), np.nan)
    with mp.get_context("fork").Pool(max(1, os.cpu_count() - 4)) as pool:
        for r in pool.imap_unordered(chunk_heights, jobs, chunksize=16):
            if r:
                cx, cz, o = r
                hgt[cz * 16:cz * 16 + 16, cx * 16:cx * 16 + 16] = o[:min(16, H - cz * 16), :min(16, Wd - cx * 16)]
    steps = []
    hist = {}
    for dz, dx in ((0, 1), (1, 0)):
        a, b = hgt[:H - dz, :Wd - dx], hgt[dz:, dx:]
        d = np.abs(a - b)
        ok = ~np.isnan(d)
        for k in np.unique(d[ok]):
            hist[float(k)] = hist.get(float(k), 0) + int((d[ok] == k).sum())
        zz, xx = np.nonzero(ok & (d > LIMIT))
        steps += [(float(d[z, x]), int(x), int(z)) for z, x in zip(zz, xx)]
    steps.sort(reverse=True)
    print("neighbour pairs by step:", {k: v for k, v in sorted(hist.items())})
    print(f"drops over 1 block: {len(steps)}; worst: {steps[:10]}")
    if len(sys.argv) > 2:
        json.dump(steps, open(sys.argv[2], "w"))
    sys.exit(1 if steps else 0)


if __name__ == "__main__":
    main()
