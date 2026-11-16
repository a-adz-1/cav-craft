#!/usr/bin/env python3
"""Pulls every OSM feature inside the Cavcraft box out of the Geofabrik extracts.

    PROJ_NETWORK=ON .venv/bin/python -I tools/osm_extract.py .downloads/osm/*.osm.pbf build/osm.json

Output: {"areas": [{"id", "tags", "rings": [[[e, n], ...] outer, then inners...]}],
         "lines": [{"id", "tags", "pts": [[e, n], ...]}], "nodes": [{"id", "tags", "pt": [e, n]}]}
in British National Grid metres. Data © OpenStreetMap contributors, ODbL.
"""
import json
import sys

import osmium
from pyproj import Transformer, network

network.set_network_enabled(True)   # OSTN15 grid: cm-accurate WGS84 -> BNG
to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
W, S, E, N = -1.03, 51.450, -0.92, 51.505   # lon/lat box, a bit bigger than Caversham + lakes

*pbfs, out = sys.argv[1:]
areas, lines, nodes, seen = [], [], [], set()


def pts(locs):
    xs, ys = to_bng.transform([l.lon for l in locs], [l.lat for l in locs])
    return [[round(x, 2), round(y, 2)] for x, y in zip(xs, ys)]


def inside(locs):
    return any(W <= l.lon <= E and S <= l.lat <= N for l in locs)


for pbf in pbfs:
    fp = osmium.FileProcessor(pbf).with_locations().with_areas()
    for o in fp:
        if not o.tags:
            continue
        tags = dict(o.tags)
        try:
            if o.is_area():
                key = ("a", o.orig_id(), o.from_way())
                if key in seen:
                    continue
                for outer in o.outer_rings():
                    locs = [n.location for n in outer]
                    if not inside(locs):
                        continue
                    seen.add(key)
                    rings = [pts(locs)] + [pts([n.location for n in inner]) for inner in o.inner_rings(outer)]
                    areas.append({"id": ("w" if o.from_way() else "r") + str(o.orig_id()), "tags": tags, "rings": rings})
            elif o.is_way():
                key = ("w", o.id)
                locs = [n.location for n in o.nodes]
                if key in seen or not inside(locs):
                    continue
                seen.add(key)
                lines.append({"id": "w" + str(o.id), "tags": tags, "pts": pts(locs)})
            elif o.is_node():
                key = ("n", o.id)
                if key in seen or not inside([o.location]):
                    continue
                seen.add(key)
                nodes.append({"id": "n" + str(o.id), "tags": tags, "pt": pts([o.location])[0]})
        except osmium.InvalidLocationError:
            pass

json.dump({"areas": areas, "lines": lines, "nodes": nodes}, open(out, "w"))
print(len(areas), "areas", len(lines), "lines", len(nodes), "nodes")
