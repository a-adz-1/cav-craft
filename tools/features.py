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
    x, z = xz(e, n)
    z -= 40
    G["spawn"] = (x, int(G["ground"][z, x]) + 1, z)

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
    peak &= G["mask"] & (G["building"] == 0) & (G["water"] == -999)
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
                cy = gy + h - r * 0.9
                ry = max(r * 0.8, (h - 2) / 2) if h > 2 * r else r * 0.8
                leaf = ((X - x) ** 2 + (Z - z) ** 2) / r ** 2 + (Y - cy) ** 2 / ry ** 2 <= 1.0
                leaf &= Y <= gy + h
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
