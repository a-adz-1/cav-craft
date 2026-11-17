#!/usr/bin/env python3
"""A player's-eye picture of the built world without running Minecraft: rays marched through the blocks read
back from the region files, each block coloured by its texture's average colour, faces shaded by direction,
distance haze and sky. For checking streets while the game itself is busy.

    .venv/bin/python tools/eye_view.py world/Cavcraft x y z yaw pitch out.png [textures dir]

yaw/pitch as in Minecraft (yaw 0 = south, 90 = west, 180 = north, -90 = east). Textures are the block PNGs
unzipped from the client jar (assets/minecraft/textures/block).
"""
import os
import sys

import numpy as np
from PIL import Image

import anvil

W, H, FOV, RANGE = 480, 270, 75, 90
SKY = np.array([150, 190, 240], float)
PASS = {"air", "cave_air", "light", "void_air", "barrier", "structure_void"}
THIN = {"short_grass", "tall_grass", "fern", "large_fern", "poppy", "dandelion", "blue_orchid", "allium",
        "oxeye_daisy", "cornflower", "pink_tulip", "red_tulip", "white_tulip", "orange_tulip", "lilac", "rose_bush",
        "peony", "sunflower", "azure_bluet", "lily_of_the_valley", "seagrass", "tall_seagrass", "torch",
        "wall_torch", "redstone_wire", "rail", "lever", "tripwire", "sugar_cane", "vine", "kelp", "kelp_plant",
        "sweet_berry_bush", "wheat", "carrots", "potatoes", "beetroots"}   # small plants: left out
POSTS = ("_fence", "_wall", "iron_bars", "_pane", "iron_chain", "lightning_rod", "lantern", "_sign")


def tex_colour(name, tdir, cache={}):
    if name in cache:
        return cache[name]
    base = name
    for suf in ("_slab", "_stairs", "_wall", "_fence_gate", "_fence", "_pressure_plate", "_trapdoor", "_door",
                "_wall_sign", "_sign", "_carpet", "_pane", "_button"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    alias = {"bricks": "bricks", "oak": "oak_planks", "spruce": "spruce_planks", "dark_oak": "dark_oak_planks",
             "birch": "birch_planks", "jungle": "jungle_planks", "polished_blackstone": "polished_blackstone",
             "smooth_stone": "smooth_stone", "smooth_quartz": "quartz_block_top", "quartz": "quartz_block_side",
             "stone_brick": "stone_bricks", "mud_brick": "mud_bricks", "iron": "iron_bars", "water": "water_still",
             "grass_block": "grass_block_top", "red_carpet": "red_wool", "white_carpet": "white_wool",
             "polished_deepslate": "polished_deepslate", "smooth_sandstone": "sandstone_top",
             "cut_red_sandstone": "cut_red_sandstone", "glass": "glass", "iron_chain": "iron_chain"}
    cands = [alias.get(base, base), base, base + "_top", base + "_side", base + "_planks", base + "_block",
             base.replace("_log", "_log_top"), base + "_0", name]
    col = None
    for c in cands:
        p = os.path.join(tdir, c + ".png")
        if os.path.exists(p):
            a = np.asarray(Image.open(p).convert("RGBA"), float)[:16, :16].reshape(-1, 4)
            a = a[a[:, 3] > 0]
            if len(a):
                col = a[:, :3].mean(0)
                break
    if col is None:
        col = np.array([200, 0, 200], float)
    if name in ("grass_block", "short_grass", "tall_grass", "fern") or "leaves" in name:
        col = col * np.array([0.55, 0.85, 0.45]) if name != "grass_block" else np.array([105, 150, 70], float)
    if name == "water":
        col = np.array([60, 90, 200], float)
    cache[name] = col
    return col


def load(world, x0, x1, z0, z1, y0, y1):
    """Block names in [y, z, x] for the box, as palette indices plus the name list."""
    names = ["air"]
    nid = {"air": 0}
    vol = np.zeros((y1 - y0, z1 - z0, x1 - x0), np.int32)
    for cz in range(z0 // 16, (z1 - 1) // 16 + 1):
        for cx in range(x0 // 16, (x1 - 1) // 16 + 1):
            f = os.path.join(world, "region", f"r.{cx // 32}.{cz // 32}.mca")
            ch = anvil.read_chunk(f, cx % 32, cz % 32) if os.path.exists(f) else None
            if not ch:
                continue
            for s in ch["sections"]:
                Y = s["Y"] * 16
                if Y + 16 <= y0 or Y >= y1:
                    continue
                p = s["block_states"]["palette"]
                ids = np.array([nid.setdefault(e["Name"][10:], len(nid)) for e in p])
                for e in p:
                    if e["Name"][10:] not in names:
                        names.append(e["Name"][10:])
                idx = np.zeros(4096, int) if len(p) == 1 else anvil.unpack(s["block_states"]["data"],
                                                                             max(4, (len(p) - 1).bit_length()))
                blk = ids[idx].reshape(16, 16, 16)
                ya, yb = max(Y, y0), min(Y + 16, y1)
                za, zb = max(cz * 16, z0), min(cz * 16 + 16, z1)
                xa, xb = max(cx * 16, x0), min(cx * 16 + 16, x1)
                vol[ya - y0:yb - y0, za - z0:zb - z0, xa - x0:xb - x0] = \
                    blk[ya - Y:yb - Y, za - cz * 16:zb - cz * 16, xa - cx * 16:xb - cx * 16]
    inv = [None] * len(nid)
    for k, v in nid.items():
        inv[v] = k
    return vol, inv


def render(world, x, y, z, yaw, pitch, out, tdir):
    x0, x1, z0, z1 = int(x - RANGE), int(x + RANGE), int(z - RANGE), int(z + RANGE)
    y0, y1 = int(y - 30), int(y + 40)
    vol, names = load(world, x0, x1, z0, z1, y0, y1)
    solid = np.array([n not in PASS and n not in THIN for n in names])
    cols = np.array([tex_colour(n, tdir) for n in names])
    slab_ = np.array([n.endswith(("_slab", "_carpet")) for n in names])
    post_ = np.array([n.endswith(POSTS) or any(k in n for k in POSTS) for n in names])
    bars_ = np.array([n in ("iron_bars",) or n.endswith("_pane") for n in names])
    yr, pr = np.radians(yaw), np.radians(pitch)
    fwd = np.array([-np.sin(yr) * np.cos(pr), -np.sin(pr), np.cos(yr) * np.cos(pr)])
    right = np.array([-np.cos(yr), 0, -np.sin(yr)])
    up = np.cross(right, fwd)
    f = np.tan(np.radians(FOV) / 2)
    u = (np.arange(W) - W / 2 + 0.5) / (W / 2) * f
    v = (H / 2 - np.arange(H) - 0.5) / (W / 2) * f
    U, V = np.meshgrid(u, v)
    d = fwd[None, None] + U[..., None] * right[None, None] + V[..., None] * up[None, None]
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    d = d.reshape(-1, 3)
    n = len(d)
    img = np.tile(SKY, (n, 1))
    hit = np.zeros(n, bool)
    o = np.array([x, y, z], float)
    prev = np.floor(o).astype(int)
    step = 0.05
    for k in range(1, int(RANGE / step)):
        t = k * step
        p = o + d * t
        b = np.floor(p).astype(int)
        ix, iy, iz = b[:, 0] - x0, b[:, 1] - y0, b[:, 2] - z0
        ok = ~hit & (ix >= 0) & (ix < vol.shape[2]) & (iy >= 0) & (iy < vol.shape[0]) & (iz >= 0) & (iz < vol.shape[1])
        if not ok.any():
            if hit.all() or (~hit & ((ix < 0) | (ix >= vol.shape[2]) | (iz < 0) | (iz >= vol.shape[1]))).all():
                break
            continue
        sel = np.nonzero(ok)[0]
        bid = vol[iy[sel], iz[sel], ix[sel]]
        s_ = solid[bid]
        # half slabs: a bottom slab only fills the lower half
        nm = sel[s_]
        if not len(nm):
            continue
        bid = bid[s_]
        frac = p[nm, 1] - np.floor(p[nm, 1])
        slabish = slab_[bid]
        keep = ~slabish | (frac < 0.5)
        fx, fz = p[nm, 0] - np.floor(p[nm, 0]), p[nm, 2] - np.floor(p[nm, 2])
        keep &= ~post_[bid] | ((np.abs(fx - 0.5) < 0.15) & (np.abs(fz - 0.5) < 0.15))   # fences, bars: just posts
        nm, bid = nm[keep], bid[keep]
        if not len(nm):
            continue
        # face: which coordinate changed last step
        q = np.floor(o + d[nm] * (t - step)).astype(int)
        face = np.argmax(np.abs(np.floor(o + d[nm] * t).astype(int) - q), axis=1)
        shade = np.where(face == 1, 1.0, np.where(face == 0, 0.8, 0.65))
        c = cols[bid] * shade[:, None]
        fog = np.clip(t / RANGE, 0, 1)[None].T ** 1.5
        img[nm] = c * (1 - fog) + SKY * fog
        hit[nm] = True
        if hit.all():
            break
    Image.fromarray(img.reshape(H, W, 3).clip(0, 255).astype(np.uint8)).resize((W * 2, H * 2), Image.NEAREST).save(out)


if __name__ == "__main__":
    a = sys.argv
    render(a[1], float(a[2]), float(a[3]), float(a[4]), float(a[5]), float(a[6]), a[7],
           a[8] if len(a) > 8 else "/tmp/claude-1000/-home-adz-Projects-cavcraft/af00789e-03fb-4c93-9d9d-8ce788c60b72/scratchpad/tex/assets/minecraft/textures/block")
