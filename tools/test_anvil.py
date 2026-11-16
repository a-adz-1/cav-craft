#!/usr/bin/env python3
"""Self-check for anvil.py: bit packing, NBT and region round trips."""
import os
import sys
import tempfile

import numpy as np

import anvil

rng = np.random.default_rng(1)
for bits in (4, 5, 6, 7, 9, 12):
    v = rng.integers(0, 1 << bits, 4096)
    assert (anvil.unpack(anvil.pack(v, bits), bits) == v).all(), bits
    assert len(anvil.pack(v, bits)) == -(-4096 // (64 // bits))

pal = [("minecraft:air", None), ("minecraft:stone", None), ("minecraft:water", (("level", "0"),))] + \
      [("minecraft:wool%d" % i, None) for i in range(30)]
blocks = rng.integers(0, len(pal), (40, 16, 16)).astype(np.int32)
blocks[30:] = 0
nbt = anvil.chunk_nbt(3, -2, blocks, pal)
back = anvil.read_nbt(anvil.nbt_bytes(nbt))
assert back["xPos"] == 3 and back["zPos"] == -2 and back["Status"] == "minecraft:full"
for s in back["sections"]:
    i = (s["Y"] * 16 + 64)
    p = s["block_states"]["palette"]
    want = blocks[i:i + 16] if i + 16 <= len(blocks) else np.concatenate([blocks[i:], np.zeros((16 - len(blocks[i:]), 16, 16), int)])
    if len(p) == 1:
        assert (want == [n for n, _ in pal].index(p[0]["Name"])).all()
        continue
    idx = anvil.unpack(s["block_states"]["data"], max(4, (len(p) - 1).bit_length()))
    names = np.array([e["Name"] for e in p])[idx].reshape(16, 16, 16)
    assert (names == np.array([n for n, _ in pal])[want]).all()
    assert all(e.get("Properties", {}) == dict(pal[[n for n, _ in pal].index(e["Name"])][1] or {}) for e in p)

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "r.0.0.mca")
    anvil.write_region(path, {(1, 2): nbt, (31, 31): anvil.chunk_nbt(31, 31, blocks, pal)})
    assert anvil.read_chunk(path, 1, 2)["xPos"] == 3
    assert anvil.read_chunk(path, 31, 31)["zPos"] == 31
    assert anvil.read_chunk(path, 0, 0) is None
    anvil.write_level_dat(os.path.join(d, "level.dat"), "T", (1, 2, 3), (0, 0), 100)
print("anvil ok")
