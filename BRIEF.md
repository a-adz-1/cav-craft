# Cavcraft — project brief

A Minecraft world of Caversham (Reading, UK), built from real data the same
way Splitwater's river world was: OpenStreetMap for what's where, Environment
Agency LiDAR for how high it is. 1 block = 1 metre. Playable on **Java and
Bedrock**.

Status: **not started** — this is the brief only.

## What's in the world

- **All of Caversham**, as outlined in red in [docs/area.png](docs/area.png):
  Caversham Heights, Emmer Green, Caversham Park Village, Lower Caversham,
  Caversham centre. Plus **Caversham Lakes**, which sit just outside that
  line to the east (Henley Road side) — extend the boundary to take them in.
  Include their **beach** (sand down to the water); check OSM for
  `natural=beach` / `leisure=beach_resort` there, else trace it from aerial
  imagery.
- **The Thames**, with its bridges (Caversham Bridge, Reading Bridge, Christchurch
  footbridge), islands (Piper's, Fry's, View Island) and the Splitwater
  Caversham reach — so you can cross it.
- **Not Reading.** The south bank stops a thin strip past the river (just
  enough for the bridges to land); the world edge is there, not the town.
- **A working Caversham Lock**: gates that open and close, and the chamber
  filling and emptying so a boat goes up or down a level. Same buttons work on
  both editions (see below).
- Real ground shape from the EA 1 m DTM (bare earth).
- Buildings on their OSM footprints, real eave/ridge height from DSM − DTM.
- Trees from the VOM / DSM canopy peaks, real height and crown size.
- Water at its real level (above and below the lock weir), roads, paths,
  parks, woods and fields from OSM tags mapped to blocks.

## Reuse from Splitwater (`~/Projects/splitwater`)

- `tools/course/build_course.py` — Overpass dump → buildings, parks, woods,
  trees, bridges, water edges (the OSM-tag handling is the part worth lifting).
- `tools/course/add_lidar.py` — DTM/DSM/VOM GeoTIFF reading, WGS84 → British
  National Grid via OSTN15 (`pyproj`), building heights, tree peaks.
- `tools/course/add_paths.py` — footpaths.
- Data already downloaded in `splitwater/.downloads/`: EA tiles SU6570, SU6575,
  SU7070, SU7075 (DTM + first-return DSM) and OSM dumps in `.downloads/osm/`.
  Check Caversham Park and Caversham Lakes sit inside those tiles (the lakes
  are near the SU7075 edge) — fetch the neighbouring tile if not.

Difference from Splitwater: there it's a strip along a river for a Godot
mesh; here it's a full area, written out as a Minecraft world.

## Rough pipeline

1. Draw the boundary: the red line in `docs/area.png` (OSM likely has it as
   an admin/suburb boundary — use that rather than tracing the picture),
   pushed out to the south bank of the Thames plus a few metres, and out
   east around Caversham Lakes. Store it as a polygon in BNG metres.
2. Pull OSM for the box (Overpass), mosaic the EA tiles over it.
3. Per 1 m column: ground height, surface block (from OSM landuse/highway/
   water tags), water level.
4. Stamp buildings, trees, bridges, the lock.
5. Write a **Java** world (Anvil `.mca` regions) with a Python library such as
   `amulet-core`, or look at **Arnis** (open-source OSM → Minecraft generator)
   first — it may do steps 2–5 already and just need our LiDAR heights fed in.
6. Convert to **Bedrock** (`.mcworld`) with **Chunker** (open-source Java ↔
   Bedrock converter) or Amulet. Generate once, convert, never hand-edit both.
7. Open in both, walk round, fix what looks wrong.

## The lock

- Gates: piston doors (or fence-gate/door blocks) at each end of the chamber.
- Water level: the chamber fills and drains between the upper and lower river
  levels. Pistons + water sources and sponges work in both editions but are
  fiddly; command blocks (`/fill` water ↔ air in layers, with a delay) are
  simpler and look like a real fill.
- Controls: a lever or button on each gate, like the real lock keeper's panel.
- Java and Bedrock redstone don't behave quite the same (piston timing,
  quasi-connectivity, command syntax) — test the lock in both after
  converting; it may need a Bedrock-specific version.

## Constraints

- Height: both editions build −64…320. Caversham is ~35–110 m above datum, so
  ground Y = metres AOD + offset fits with room for buildings.
- Blocks: stick to blocks that exist in both editions so the conversion is
  clean.
- Licences: OSM is ODbL (credit "© OpenStreetMap contributors"; a shared
  world is a derived database → share-alike). EA LiDAR is OGL v3 (credit the
  EA). Put both in a `CREDITS.md` and a sign at spawn.
- Personal/family use. No Mojang assets redistributed; the world file only.
- Git: author `a-adz-1 <a-adz-1@proton.me>`; commit checkpoints so changes can
  be reverted.

## Open questions (answer before starting)

- Which Minecraft version (Java and Bedrock)? The converter needs to support it.
- Detail level for buildings: plain boxes with roofs, or try for windows/doors?
- Where it's played: single-player, or a server (and if so, Java or Bedrock —
  Geyser lets Bedrock players join a Java server instead of converting)?
