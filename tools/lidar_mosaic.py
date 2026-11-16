#!/usr/bin/env python3
"""Mosaics the EA 1 m LiDAR tiles over the Cavcraft box.

    .venv/bin/python -I tools/lidar_mosaic.py <ea_dir> build/lidar.npz

<ea_dir>/*dtm*/, *first_return_dsm*/ and *vom*/ hold GeoTIFFs with .tfw world files.
Output arrays (rows = north to south, cols = west to east, 1 m cells, metres AOD; VOM in metres
above ground): dtm, dsm, vom (NaN where there's no data), plus box = [E0, N0, E1, N1].
Contains Environment Agency information © Environment Agency and/or database right, OGL v3.
"""
import glob
import os
import sys

import numpy as np
import tifffile

from box import E0, N0, E1, N1

ea_dir, out = sys.argv[1], sys.argv[2]
W, H = E1 - E0, N1 - N0


def mosaic(pattern):
    grid = np.full((H, W), np.nan, np.float32)
    for tif in sorted(glob.glob(os.path.join(ea_dir, pattern, "*.tif"))):
        if "_HS_" in tif:   # hillshade picture, not heights
            continue
        tfw = [float(v) for v in open(tif[:-4] + ".tfw").read().split()]
        assert tfw[0] == 1.0 and tfw[3] == -1.0, (tif, tfw)
        left, top = round(tfw[4] - 0.5), round(tfw[5] + 0.5)   # tfw gives the centre of the top-left cell
        a = tifffile.imread(tif).astype(np.float32)
        a[(a < -1000) | (a > 10000)] = np.nan
        c0, r0 = left - E0, N1 - top
        rs, cs = max(0, -r0), max(0, -c0)
        re, ce = min(a.shape[0], H - r0), min(a.shape[1], W - c0)
        if rs >= re or cs >= ce:
            continue
        dst = grid[r0 + rs:r0 + re, c0 + cs:c0 + ce]
        src = a[rs:re, cs:ce]
        np.copyto(dst, src, where=~np.isnan(src) & np.isnan(dst))
        print(os.path.basename(tif))
    print(pattern, "missing cells:", int(np.isnan(grid).sum()))
    return grid


np.savez_compressed(out, dtm=mosaic("*_dtm_*"), dsm=mosaic("*first_return_dsm*"), vom=mosaic("*vom*"),
                    box=np.array([E0, N0, E1, N1]))
