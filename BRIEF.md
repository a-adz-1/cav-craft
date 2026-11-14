# Heightscraft — project brief

A Minecraft world of our local area (Caversham / Reading, UK), built from real
data the same way Splitwater's river world was: OpenStreetMap for what's where,
Environment Agency LiDAR for how high it is. 1 block = 1 metre.

Status: **not started** — this is the brief only.

## What's in the world

- Caversham and Reading around the Thames: the Splitwater Caversham reach
  (Caversham Court Gardens, Caversham Bridge, Piper's Island, Fry's Island,
  Reading Rowing Club) and **Caversham Lakes** — both must be in.
- Real ground shape from the EA 1 m DTM (bare earth).
- Buildings on their OSM footprints, real eave/ridge height from DSM − DTM.
- Trees from the VOM / DSM canopy peaks, real height and crown size.
- Water (Thames, Kennet, lakes) at its real level; roads, paths, rail, parks,
  woods and fields from OSM tags mapped to blocks.

## Reuse from Splitwater (`~/Projects/splitwater`)

- `tools/course/build_course.py` — Overpass dump → buildings, parks, woods,
  trees, bridges, water edges (the OSM-tag handling is the part worth lifting).
- `tools/course/add_lidar.py` — DTM/DSM/VOM GeoTIFF reading, WGS84 → British
  National Grid via OSTN15 (`pyproj`), building heights, tree peaks.
- `tools/course/add_paths.py` — footpaths.
- Data already downloaded in `splitwater/.downloads/`: EA tiles SU6570, SU6575,
  SU7070, SU7075 (DTM + first-return DSM) cover Reading/Caversham; OSM dumps in
  `.downloads/osm/`. Check Caversham Lakes sits inside those tiles (it's near
  the SU7075 edge) — fetch the neighbouring tile if not.

Difference from Splitwater: there it's a strip along a river for a Godot
mesh; here it's a full area, written out as Minecraft region files.

## Rough pipeline

1. Pick the bounding box (BNG metres) — Caversham Lakes to the Splitwater
   reach, plus whatever else of Reading we want.
2. Pull OSM for the box (Overpass), mosaic the EA tiles over it.
3. Per 1 m column: ground height, surface block (from OSM landuse/highway/
   water tags), water level.
4. Stamp buildings, trees, bridges.
5. Write a Java Edition world (Anvil `.mca` regions) with a Python library
   such as `amulet-core`, or look at **Arnis** (open-source OSM → Minecraft
   generator) first — it may do steps 2–5 already and just need our LiDAR
   heights fed in.
6. Open in Minecraft, walk round, fix what looks wrong.

## Constraints

- Height: Minecraft Java builds −64…320. Reading is ~35–110 m above datum, so
  ground Y = metres AOD + offset fits with room for buildings.
- Licences: OSM is ODbL (credit "© OpenStreetMap contributors"; a shared
  world is a derived database → share-alike). EA LiDAR is OGL v3 (credit the
  EA). Put both in a `CREDITS.md` and a sign at spawn.
- Personal/family use. No Mojang assets redistributed; the world file only.
- Git: author `a-adz-1 <a-adz-1@proton.me>`; commit checkpoints so changes can
  be reverted.

## Open questions (answer before starting)

- Exact area: just Caversham + the lakes, or all of Reading? (Each 5 km EA
  tile = 25 M columns; size and build time grow fast.)
- Java or Bedrock? Which Minecraft version? (Java is far easier to generate.)
- Detail level for buildings: plain boxes with roofs, or try for windows/doors?
- Where it's played: single-player on this PC, or a server for others too?
