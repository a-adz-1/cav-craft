"""Caversham Lock, rebuilt as a working Minecraft lock.

The chamber is straightened to run east-west (so plain /fill boxes can drain and fill it) at the OSM lock's
position: 34 x 6 blocks, upper gate on the west (River Thames above the weir, y 36), lower gate on the east
(below the weir, y 35). It starts full with the upper gate open and the lower gate shut.

Two button-started lines on the south wall: a button powers a row of repeaters; three relay blocks along it
each switch on the command blocks beside them, ~1.6 s apart:
  "Down": shut upper gate -> drain the top layer -> open lower gate
  "Up":   shut lower gate -> fill the top layer -> open upper gate
Only commands written the same way in Java and Bedrock are used (fill with plain block names, no states),
so the converted Bedrock world can run them too. Pressing a button twice does nothing harmful.
"""
import os
import uuid

import numpy as np

import anvil

X0, X1 = 4043, 4076          # chamber (inclusive)
Z0, Z1 = 4164, 4169
GATE_UP, GATE_DOWN = X0 - 1, X1 + 1
SITE = (4036, 4082, 4157, 4178)   # x0, x1, z0, z1: becomes lock walls/side, then carved
WEST_POOL = (4028, GATE_UP - 1, 4164, 4176)
EAST_POOL = (GATE_DOWN + 1, 4090, 4156, 4169)


def setup(G, P, levels):
    up, down = levels["up"], levels["down"]
    bed = down - 3
    top = up + 1
    ground, water, surface = G["ground"], G["water"], G["surface"]
    paved = 9   # surfaces.SURFACE.index("paved")
    wet = 2     # "water"
    x0, x1, z0, z1 = SITE
    site = np.s_[z0:z1 + 1, x0:x1 + 1]
    ground[site] = top
    water[site] = -999
    surface[site] = paved
    G["building"][site] = 0
    G["h_wall"][site] = 0

    def carve(xa, xb, za, zb, lvl):
        s = np.s_[za:zb + 1, xa:xb + 1]
        ground[s] = bed
        water[s] = lvl
        surface[s] = wet

    # nothing from the house builder (front walls, fences, paths' gaps) may stand in the carved lock site
    rects = [SITE, WEST_POOL, EAST_POOL]
    for k in [k for k in G["h_blocks"] if any(r[0] <= k[0] <= r[1] and r[2] <= k[2] <= r[3] for r in rects)]:
        del G["h_blocks"][k]
    carve(*WEST_POOL, up)
    carve(*EAST_POOL, down)
    carve(X0, X1, Z0, Z1, up)                 # chamber, full
    carve(GATE_UP, GATE_UP, Z0, Z1, up)       # upper gate open
    carve(GATE_DOWN, GATE_DOWN, Z0, Z1, -999)  # lower gate: planks stamped below
    G["mask"][site] = True

    planks = P("spruce_planks")
    stone, relay = P("stone_bricks"), P("stone_bricks")
    rep_fast = P("repeater", facing="west", delay=1)
    rep = P("repeater", facing="west", delay=4)
    button = P("stone_button", face="wall", facing="west")
    cmd = P("command_block", facing="up", conditional="false")
    sign = P("oak_sign", rotation=4)
    y = top + 1   # standing on the wall top

    def fill(a, b, block, extra=""):
        return f"fill {a[0]} {a[1]} {a[2]} {b[0]} {b[1]} {b[2]} {block}{extra}"

    seqs = {
        4172: ("Down to", "Reading Bridge", [
            [fill((GATE_UP, bed + 1, Z0), (GATE_UP, top, Z1), "spruce_planks")],
            [fill((X0, up, Z0), (X1, up, Z1), "air", " replace water")],
            [fill((GATE_DOWN, bed + 1, Z0), (GATE_DOWN, down, Z1), "water"),
             fill((GATE_DOWN, down + 1, Z0), (GATE_DOWN, top, Z1), "air")]]),
        4176: ("Up to", "Caversham Bridge", [
            [fill((GATE_DOWN, bed + 1, Z0), (GATE_DOWN, top, Z1), "spruce_planks")],
            [fill((X0, up, Z0), (X1, up, Z1), "water", " replace air")],
            [fill((GATE_UP, bed + 1, Z0), (GATE_UP, up, Z1), "water"),
             fill((GATE_UP, top, Z0), (GATE_UP, top, Z1), "air")]]),
    }
    blocks = {}            # (x, y, z) -> palette index
    entities = {}          # (x, y, z) -> block entity
    for z, (line1, line2, steps) in seqs.items():
        x = 4046
        blocks[(x - 1, y, z)] = button
        blocks[(x, y, z)] = stone
        blocks[(x, y + 1, z)] = sign
        entities[(x, y + 1, z)] = sign_entity(x, y + 1, z, ["Lock", line1, line2, "press button"])
        blocks[(x + 1, y, z)] = rep_fast
        rx = x + 2
        for i, cmds in enumerate(steps):
            if i:
                for k in range(4):
                    blocks[(rx + k, y, z)] = rep
                rx += 4
            blocks[(rx, y, z)] = relay
            for c, dz in zip(cmds, (-1, 1)):
                blocks[(rx, y, z + dz)] = cmd
                entities[(rx, y, z + dz)] = command_entity(rx, y, z + dz, c)
            rx += 1
    test = os.environ.get("LOCK_TEST", "")
    if test:
        # test build: a redstone block in place of a button's block, and a scheduled tick on the line's first
        # repeater so it fires that many ticks after the chunk loads ("down", "up", or "downup": down at 2 s,
        # up at 16 s)
        when = {"down": {4172: 40}, "up": {4176: 40}, "downup": {4172: 40, 4176: 320}}[test]
        for z, t in when.items():
            blocks[(4046, y, z)] = P("redstone_block")
            G.setdefault("block_ticks", {}).setdefault((4047 // 16, z // 16), []).append(
                {"i": "minecraft:repeater", "x": 4047, "y": y, "z": z, "t": t, "p": 0})
    # balance beams: white with black ends, one on each wall at each gate, pointing away from the chamber
    for gx, d in ((GATE_UP, -1), (GATE_DOWN, 1)):
        for zz in (Z0 - 1, Z1 + 1):
            for k in range(5):
                blocks[(gx + d * k, y, zz)] = P("black_concrete") if k == 4 else P("white_concrete")
            blocks[(gx, y + 1, zz)] = P("white_concrete")
    gate = {(GATE_DOWN, yy, zz): planks for yy in range(bed + 1, top + 1) for zz in range(Z0, Z1 + 1)}
    blocks.update(gate)

    def stamp(b, x0, z0, g, w, s, Y):
        for (x, yy, z), blk in blocks.items():
            if x0 <= x < x0 + 16 and z0 <= z < z0 + 16:
                b[yy + 64, z - z0, x - x0] = blk

    G["stamps"].append(stamp)
    for (x, yy, z), e in entities.items():
        G["block_entities"].setdefault((x // 16, z // 16), []).append(e)
    # a boat waiting in the chamber
    add_entity(G, boat((X0 + X1) / 2 + 0.5, up + 0.9, (Z0 + Z1) / 2 + 0.5))
    print(f"lock: chamber x {X0}-{X1} z {Z0}-{Z1}, levels {up}/{down}, buttons at x {4045} z 4172/4176")


def command_entity(x, y, z, command):
    return {"id": "minecraft:command_block", "x": x, "y": y, "z": z, "Command": command,
            "auto": anvil.Byte(0), "powered": anvil.Byte(0), "conditionMet": anvil.Byte(0),
            "TrackOutput": anvil.Byte(0), "SuccessCount": 0, "UpdateLastExecution": anvil.Byte(1),
            "CustomName": '"Caversham Lock"'}


def sign_entity(x, y, z, lines):
    msgs = ['"%s"' % t for t in lines] + ['""'] * (4 - len(lines))
    blank = {"messages": ['""'] * 4, "color": "black", "has_glowing_text": anvil.Byte(0)}
    return {"id": "minecraft:sign", "x": x, "y": y, "z": z, "is_waxed": anvil.Byte(1),
            "front_text": {"messages": msgs, "color": "black", "has_glowing_text": anvil.Byte(0)},
            "back_text": blank}


def uuid_ints():
    u = uuid.uuid4().int
    return anvil.int_array([((u >> s) & 0xffffffff) - (1 << 32 if (u >> s) & 0x80000000 else 0)
                            for s in (96, 64, 32, 0)])


def boat(x, y, z, rot=90.0):
    return {"id": "minecraft:boat", "Type": "oak", "Pos": [float(x), float(y), float(z)],
            "Motion": [0.0, 0.0, 0.0], "Rotation": [anvil.Float(rot), anvil.Float(0)], "UUID": uuid_ints(),
            "OnGround": anvil.Byte(0), "Air": anvil.Short(300), "FallDistance": anvil.Float(0),
            "Fire": anvil.Short(-1), "Invulnerable": anvil.Byte(0), "PortalCooldown": 0}


def add_entity(G, e):
    x, _, z = e["Pos"]
    G.setdefault("entities", {}).setdefault((int(x) // 16, int(z) // 16), []).append(e)
