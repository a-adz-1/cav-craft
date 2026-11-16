# Cavcraft

Caversham as a Minecraft Java world, 1 block = 1 metre, built from OpenStreetMap and Environment Agency LiDAR.
All of Caversham (Heights, Emmer Green, Caversham Park Village, Lower Caversham), the Thames with its bridges and
islands, Caversham Lakes with the beach, and a working Caversham Lock. Not Reading: the world stops just past the
south bank. Y in the world = metres above sea level (Ordnance Datum).

## Play it
Copy `world/Cavcraft` (or unzip `build/Cavcraft.zip`) into your Minecraft `saves` folder. Made for 1.21.1 format;
any newer Java Edition upgrades it on first open (tested in 1.21.11). Creative mode, cheats on, no mob spawning,
no generated terrain outside Caversham.

- Spawn: north end of Caversham Bridge.
- Caversham Lock: x 4043–4076, z 4164–4169 (`/tp 4040 38 4174`). Buttons on the south wall: "Down to Reading
  Bridge" and "Up to Caversham Bridge". There's a boat in the chamber.
- Caversham Lakes beach: `/tp 6060 37 3520`.

## Rebuild
    uv venv .venv && uv pip install --python .venv/bin/python numpy tifffile imagecodecs pyproj shapely pillow osmium scipy
    # data: Geofabrik berkshire + oxfordshire .osm.pbf in .downloads/osm, EA LiDAR tiles (splitwater/.downloads/ea)
    PROJ_NETWORK=ON .venv/bin/python tools/osm_extract.py .downloads/osm/*.osm.pbf build/osm.json
    .venv/bin/python tools/lidar_mosaic.py ~/Projects/splitwater/.downloads/ea build/lidar.npz
    .venv/bin/python tools/layers.py build/osm.json build/lidar.npz build/layers.npz
    .venv/bin/python tools/build_world.py world/Cavcraft        # ~15 s
    .venv/bin/python tools/test_anvil.py                        # format self-check
    .venv/bin/python tools/render_world.py world/Cavcraft out.png 0.25   # top-down check from the saved files
    .venv/bin/python tools/mc_view.py world/Cavcraft shot.png x y z yaw pitch   # screenshot in real Minecraft

See BRIEF.md for the goals and PROGRESS.md for what was done and decided. Credits: CREDITS.md.
