# Progress

## Decisions (defaults picked 2026-11-16, user away)
- Target Java world format 1.21.1 (DataVersion 3955): any newer Java opens and upgrades it; Chunker converts it.
- 1 block = 1 m, x = east, z = south. Origin: BNG easting/northing offset chosen in build (see tools/config).
- Y = metres above Ordnance Datum, no offset (Thames ≈ y 34–36, Emmer Green ≈ y 100). Bedrock floor at y −64.
- Buildings: walls + flat/pitched roofs from DSM, no interiors.
- Single-player world.

## Plan
1. [x] Setup: venv, folders
2. [x] Boundary polygon (OSM Caversham + south bank strip + Caversham Lakes)
3. [x] OSM data for the box (Overpass)
4. [x] EA DTM/DSM/VOM mosaic over the box
5. [x] Ground + surface blocks + water → Anvil region writer, top-down render check
6. [x] Buildings from footprints + LiDAR heights
7. [x] Trees from VOM
8. [x] Bridges, roads, paths detail
9. [x] Caversham Lakes beach (as in docs/caversham-lakes-beach.webp)
9b. [x] Block-built swans on the Thames (no mods)
10. [x] Working Caversham Lock (command blocks)
11. [ ] Spawn, credits sign, level.dat polish
12. [ ] (later, user's call) Bedrock conversion via Chunker

## Log
- 2026-11-16 Setup: venv (.venv: numpy tifffile imagecodecs pyproj shapely pillow osmium scipy), CLAUDE.md, this file.
- 2026-11-16 OSM: Overpass was overloaded, so Geofabrik Berkshire + Oxfordshire extracts in .downloads/osm;
  tools/osm_extract.py → build/osm.json (BNG metres). No "Caversham" boundary in OSM: the red line is Reading
  borough north of the Thames.
- 2026-11-16 LiDAR: tools/lidar_mosaic.py mosaics splitwater's EA tiles (SU6570/6575/7070/7075 + sonning 1 km tiles)
  over box E 468000–475000, N 172800–178200 (tools/box.py) → build/lidar.npz, no gaps.
- 2026-11-16 Layers: tools/layers.py → build/layers.npz (mask, surface class, ground y, water y, building ids).
  Mask = Reading borough north of the Thames (Thames + Henley Road as barriers) + Caversham Lakes (east of the
  borough, south of Henley Road, north of N 175400) + the Thames along it + 30 m of south bank.
  Preview: docs/preview-layers.png (tools/preview.py). Water levels: Thames 36 above Caversham weir, 34–35 below.
  Caversham Lakes beach: Wikipedia puts the venue at 51.467,-0.936 = BNG 474006,174762.
- User asks (mid-build): lock operated by a button; swans → no swan mob in vanilla, so block-built swans on the
  river (no mods); lock must work in Bedrock → stateless commands (fill water/air/plain blocks) + repeaters only.
- 2026-11-16 World writer: tools/anvil.py (NBT, 1.18+ chunk sections, region files, level.dat; void flat
  generator so nothing generates outside Caversham), self-check tools/test_anvil.py. tools/build_world.py builds
  terrain (stone/dirt/surface by OSM class, plants, crops), water (glass where it meets the world edge),
  buildings (walls + windows from footprints, roofs shaped by the DSM, materials by building type). Whole world
  builds in ~10 s on 24 cores → world/Cavcraft (~190 MB, 46.8k chunks). tools/render_world.py reads the .mca files
  back and draws them from above.
- 2026-11-16 Trees: features.find_trees — one per VOM canopy peak (25.8k), real height + crown radius, oak/birch/
  spruce/dark oak, leaves persistent so they never decay.
- Not yet verified in real Minecraft (needs the game run; user's Prism instance is 1.21.11 NeoForge).
- 2026-11-16 Bridges: features.bridge_setup — OSM bridge ways get decks at the DSM height (30th percentile across
  the deck, median-smoothed along it), stone brick walls / iron railings, headroom cleared. Caversham, Reading and
  Christchurch bridges + island footbridges.
- 2026-11-16 Water levels: water cut at OSM weirs + lock gates (Caversham Weir carried on to the north bank to
  close the side channel). Thames 36.46 m above the weir → y 36, 35.35 m below → y 35 (build/levels.json).
- 2026-11-16 Lock (tools/lock.py): chamber straightened east–west at the OSM lock, x 4043–4076, z 4164–4169,
  starts full with the upper gate open. Two button lines on the south wall at x 4045, z 4172 ("Down to Reading
  Bridge") and z 4176 ("Up to Caversham Bridge"): button → repeaters → 3 relays → command blocks (shut gate,
  drain/fill top layer, open far gate) ~1.6 s apart. Commands are plain `fill` with no block states so Bedrock
  can run them. Oak boat in the chamber (entities/ region file).
- 2026-11-16 Swans: 14 block-built swans (white wool, orange beak) on open Thames water, some with a cygnet.
- 2026-11-16 Beach: user says it's on the river side of the lakes → the island lake between the rowing lake and
  the Thames (x≈6069 z≈3535). Sand down into shallow water, loungers, parasols, 4 huts, buoy rope.
