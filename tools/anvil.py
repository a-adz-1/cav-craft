"""Just enough of Minecraft Java's save format to write a world: NBT, chunk sections, region files.

Written from the format as documented on the Minecraft Wiki (Chunk format, Region file format, NBT format).
Chunks are 1.18+ layout (sections from y -64), tagged with DATA_VERSION; newer Minecraft upgrades on load.
"""
import gzip
import io
import struct
import zlib

import numpy as np

DATA_VERSION = 3955   # 1.21.1

# ---- NBT ---------------------------------------------------------------------------------
# Python values map to tags by type; wrap ints that need a specific width in these.


class Byte(int): pass
class Short(int): pass
class Long(int): pass
class Float(float): pass
class LongArray(np.ndarray): pass
class IntArray(np.ndarray): pass


def long_array(a):
    return np.asarray(a, dtype=">i8").view(LongArray)


def int_array(a):
    return np.asarray(a, dtype=">i4").view(IntArray)


def _name(out, s):
    b = s.encode("utf-8")
    out.write(struct.pack(">H", len(b)))
    out.write(b)


def _tag_id(v):
    if isinstance(v, Byte) or isinstance(v, bool): return 1
    if isinstance(v, Short): return 2
    if isinstance(v, Long): return 4
    if isinstance(v, int): return 3
    if isinstance(v, Float): return 5
    if isinstance(v, float): return 6
    if isinstance(v, str): return 8
    if isinstance(v, list): return 9
    if isinstance(v, dict): return 10
    if isinstance(v, IntArray): return 11
    if isinstance(v, LongArray): return 12
    raise TypeError(type(v))


def _payload(out, v, tid):
    if tid == 1: out.write(struct.pack(">b", int(v)))
    elif tid == 2: out.write(struct.pack(">h", v))
    elif tid == 3: out.write(struct.pack(">i", v))
    elif tid == 4: out.write(struct.pack(">q", v))
    elif tid == 5: out.write(struct.pack(">f", v))
    elif tid == 6: out.write(struct.pack(">d", v))
    elif tid == 8: _name(out, v)
    elif tid == 9:
        et = _tag_id(v[0]) if v else 0
        out.write(struct.pack(">bi", et, len(v)))
        for x in v:
            _payload(out, x, et)
    elif tid == 10:
        for k, x in v.items():
            t = _tag_id(x)
            out.write(struct.pack(">b", t))
            _name(out, k)
            _payload(out, x, t)
        out.write(b"\x00")
    elif tid in (11, 12):
        out.write(struct.pack(">i", len(v)))
        out.write(np.ascontiguousarray(v).tobytes())


def nbt_bytes(root, name=""):
    out = io.BytesIO()
    out.write(b"\x0a")
    _name(out, name)
    _payload(out, root, 10)
    return out.getvalue()


def read_nbt(data):
    """Parses NBT back into plain Python (for tests and checks)."""
    pos = 0

    def take(n):
        nonlocal pos
        pos += n
        return data[pos - n:pos]

    def s():
        n, = struct.unpack(">H", take(2))
        return take(n).decode("utf-8")

    def pl(t):
        if t == 1: return struct.unpack(">b", take(1))[0]
        if t == 2: return struct.unpack(">h", take(2))[0]
        if t == 3: return struct.unpack(">i", take(4))[0]
        if t == 4: return struct.unpack(">q", take(8))[0]
        if t == 5: return struct.unpack(">f", take(4))[0]
        if t == 6: return struct.unpack(">d", take(8))[0]
        if t == 7: n, = struct.unpack(">i", take(4)); return take(n)
        if t == 8: return s()
        if t == 9:
            et, n = struct.unpack(">bi", take(5))
            return [pl(et) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                tt = take(1)[0]
                if tt == 0:
                    return d
                k = s()
                d[k] = pl(tt)
        if t == 11: n, = struct.unpack(">i", take(4)); return np.frombuffer(take(4 * n), ">i4")
        if t == 12: n, = struct.unpack(">i", take(4)); return np.frombuffer(take(8 * n), ">i8")
        raise ValueError(t)

    assert take(1) == b"\x0a"
    s()
    return pl(10)


# ---- block states ---------------------------------------------------------------------------

def pack(indices, bits):
    """Packs 4096 palette indices, (64 // bits) per long, none spanning two longs (1.16+ layout)."""
    per = 64 // bits
    n = -(-len(indices) // per)
    a = np.zeros(n * per, np.uint64)
    a[:len(indices)] = indices
    a = a.reshape(n, per) << (np.arange(per, dtype=np.uint64) * np.uint64(bits))
    return long_array(np.bitwise_or.reduce(a, axis=1).view(np.int64))


def unpack(longs, bits, count=4096):
    per = 64 // bits
    a = np.asarray(longs).astype(np.int64).view(np.uint64)[:, None] >> (np.arange(per, dtype=np.uint64) * np.uint64(bits))
    return (a & np.uint64((1 << bits) - 1)).ravel()[:count].astype(np.int64)


def section(y, ids, palette):
    """ids: (16, 16, 16) [y, z, x] indices into the global `palette` list of (name, props)."""
    used, local = np.unique(ids.ravel(), return_inverse=True)
    pal = []
    for u in used:
        name, props = palette[u]
        e = {"Name": name}
        if props:
            e["Properties"] = dict(props)
        pal.append(e)
    bs = {"palette": pal}
    if len(pal) > 1:
        bs["data"] = pack(local, max(4, int(len(pal) - 1).bit_length()))
    return {"Y": Byte(y), "block_states": bs, "biomes": {"palette": ["minecraft:plains"]}}


def chunk_nbt(cx, cz, blocks, palette, y_min=-64, block_entities=(), block_ticks=()):
    """blocks: (H, 16, 16) [y, z, x] palette indices from y_min upward; index 0 must be air."""
    sections = []
    for i in range(0, blocks.shape[0], 16):
        part = blocks[i:i + 16]
        if part.shape[0] < 16:
            part = np.concatenate([part, np.zeros((16 - part.shape[0], 16, 16), part.dtype)])
        if not part.any() and i > 0:
            continue
        sections.append(section((y_min + i) // 16, part, palette))
    return {
        "DataVersion": DATA_VERSION, "xPos": cx, "zPos": cz, "yPos": y_min // 16,
        "Status": "minecraft:full", "LastUpdate": Long(0), "InhabitedTime": Long(0), "isLightOn": Byte(0),
        "sections": sections, "block_entities": list(block_entities), "block_ticks": list(block_ticks), "fluid_ticks": [],
        "PostProcessing": [], "structures": {"starts": {}, "References": {}}, "Heightmaps": {},
    }


# ---- region files ---------------------------------------------------------------------------

def write_region(path, chunks):
    """chunks: {(local_x, local_z): nbt dict} with 0 <= local < 32."""
    header = bytearray(8192)
    body = io.BytesIO()
    sector = 2
    for (lx, lz), nbt in sorted(chunks.items()):
        data = zlib.compress(nbt_bytes(nbt), 6)
        blob = struct.pack(">IB", len(data) + 1, 2) + data
        blob += b"\0" * (-len(blob) % 4096)
        n = len(blob) // 4096
        assert n < 256, "chunk too big for one region entry"
        i = 4 * (lx + lz * 32)
        header[i:i + 4] = struct.pack(">I", (sector << 8) | n)
        body.write(blob)
        sector += n
    with open(path, "wb") as f:
        f.write(header)
        f.write(body.getvalue())


def read_chunk(path, lx, lz):
    data = open(path, "rb").read()
    loc, = struct.unpack(">I", data[4 * (lx + lz * 32):4 * (lx + lz * 32) + 4])
    if not loc:
        return None
    off = (loc >> 8) * 4096
    n, comp = struct.unpack(">IB", data[off:off + 5])
    assert comp == 2
    return read_nbt(zlib.decompress(data[off + 5:off + 4 + n]))


def write_level_dat(path, name, spawn, border_centre, border_size, seed=20261116, player=None):
    """player: optional (x, y, z, yaw, pitch) to start the single player there, flying (for test views)."""
    void = {"type": "minecraft:flat", "settings": {"layers": [], "biome": "minecraft:plains",
                                                   "features": Byte(0), "lakes": Byte(0), "structure_overrides": []}}
    data = {
        "DataVersion": DATA_VERSION,
        "version": 19133, "initialized": Byte(1), "LevelName": name, "GameType": 1, "Difficulty": Byte(1),
        "hardcore": Byte(0), "allowCommands": Byte(1), "SpawnX": spawn[0], "SpawnY": spawn[1], "SpawnZ": spawn[2],
        "SpawnAngle": Float(0), "Time": Long(0), "DayTime": Long(6000), "LastPlayed": Long(0),
        "raining": Byte(0), "thundering": Byte(0), "rainTime": 0, "thunderTime": 0, "clearWeatherTime": 0,
        "Version": {"Id": DATA_VERSION, "Name": "1.21.1", "Series": "main", "Snapshot": Byte(0)},
        "DataPacks": {"Enabled": ["vanilla"], "Disabled": []},
        "BorderCenterX": float(border_centre[0]), "BorderCenterZ": float(border_centre[1]),
        "BorderSize": float(border_size), "BorderWarningBlocks": 5.0, "BorderWarningTime": 15.0,
        "BorderDamagePerBlock": 0.2, "BorderSafeZone": 5.0, "BorderSizeLerpTarget": float(border_size),
        "BorderSizeLerpTime": Long(0),
        "GameRules": {"doMobSpawning": "false", "doWeatherCycle": "false", "doFireTick": "false",
                      "mobGriefing": "false", "commandBlockOutput": "false", "spawnRadius": "0"},
        "WorldGenSettings": {
            "seed": Long(seed), "generate_features": Byte(0), "bonus_chest": Byte(0),
            "dimensions": {
                "minecraft:overworld": {"type": "minecraft:overworld", "generator": void},
                "minecraft:the_nether": {"type": "minecraft:the_nether", "generator": {
                    "type": "minecraft:noise", "settings": "minecraft:nether",
                    "biome_source": {"type": "minecraft:multi_noise", "preset": "minecraft:nether"}}},
                "minecraft:the_end": {"type": "minecraft:the_end", "generator": {
                    "type": "minecraft:noise", "settings": "minecraft:end",
                    "biome_source": {"type": "minecraft:the_end"}}},
            },
        },
    }
    if player:
        x, y, z, yaw, pitch = player
        data["Player"] = {"DataVersion": DATA_VERSION, "Pos": [float(x), float(y), float(z)],
                          "Rotation": [Float(yaw), Float(pitch)], "Motion": [0.0, 0.0, 0.0],
                          "Dimension": "minecraft:overworld", "playerGameType": 3, "Health": Float(20),
                          "abilities": {"flying": Byte(1), "mayfly": Byte(1), "instabuild": Byte(0),
                                        "invulnerable": Byte(1), "mayBuild": Byte(0),
                                        "flySpeed": Float(0.05), "walkSpeed": Float(0.1)}}
    with gzip.open(path, "wb") as f:
        f.write(nbt_bytes({"Data": data}))
