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
11. [x] Spawn, credits sign, level.dat polish
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
- 2026-11-16 VERIFIED IN REAL MINECRAFT: tools/mc_view.py copies the world into the user's Prism instance
  (1.21.11 NeoForge) as saves/Cavcraft-test, places a spectator camera via level.dat Player, launches, screenshots
  the game monitor, quits. World loads and upgrades from 1.21.1 cleanly (only a harmless "DragonFight missing"
  log line). Spawn moved onto grass by Caversham Bridge (was in the river).
- 2026-11-16 Lock tested: LOCK_TEST=down build puts a redstone block + scheduled tick on the Down line; in game
  the repeaters fire, upper gate shuts with planks, lower gate opens. (Button presses themselves not tested —
  no way to send input to the game from here.)
- 2026-11-16 Trees: crowns were flat-topped and merged into sheets; now rounded with a patchy outer shell.
- 2026-11-16 Street detail: dashed white centre lines on primary/secondary/tertiary roads, 3068 lamp posts
  (dark oak fence + lantern) every 30 m beside lit roads, credits sign by the spawn. No trees on the beach.
- 2026-11-16 Delivered: world/Cavcraft, build/Cavcraft.zip (32 MB), installed in the user's Prism instance
  "1.21.11 Paper" as saves/Cavcraft. README.md says how to play/rebuild. Screenshots from the real game in
  docs/screenshots/ (caversham-bridge, lakes-beach, street, overview).

## Status for the morning
Done: plan items 1–11. Verified in real Minecraft 1.21.11: loads clean, terrain/water/buildings/trees/bridges/
beach/swans render, lock fires (via the test trigger).
Not verified: pressing the lock buttons by hand (input can't be sent to the game from here); the "Up" line
(same build as "Down"); lamps at night; anything in Bedrock (not converted yet, by request).

## Ideas next
- Bedrock: convert with Chunker when the user is happy; check command blocks survive, cheats on.
- Buildings: interiors/floors, doors, front gardens; churches (St Peter's) and landmarks by hand.
- Animals in fields (sheep/cows as entities); ducks impossible without mods, swans are block-built.
- (done) Hedges, walls, fences from OSM barrier lines (16.9k blocks).
- 2026-11-16 Barriers: OSM hedges (2-high leaves), walls (cobblestone wall), fences (oak fence), gapped at roads, water, houses. Reinstalled + rezipped.
- 2026-11-16 User: "have you walked through the whole of cav getting all the buildings like splitwater did for
  Henley… as realistic as blocks can get", then "using all those tools, website APIs etc", "do it till the
  tokens run out". Plan: survey (catalogue + Mapillary + Commons) → per-street styles → better house builder →
  hand-built landmarks.
- 2026-11-16 tools/survey.py catalogue → docs/buildings.csv: 9,634 buildings on 457 streets (street from
  addr:street or nearest named road). Fixed duplicate buildings (closed ways were read twice).
- 2026-11-16 tools/houses.py replaces the old building code: roof fitted per building to the DSM (flat /
  hipped / gabled by best fit; 3401 hip, 4509 gable, 1713 flat), measured eave + ridge, stairs-block slopes,
  gable walls up to the ridge, tinted-glass windows per storey, floors every 3 blocks, a front door on the side
  nearest the street, a chimney on pitched houses, optional Tudor beams; materials from
  docs/street_styles.json (survey) or defaults by kind. mc_view now captures the game window only.
- 2026-11-17 Mapillary: indexed all 24,293 street photos in the area (.downloads/ref/mapillary_index.json);
  survey.py sheets picks up to 6 photos per street that look at its houses → contact sheets; 99 of 457 streets
  have usable photos (the rest, mostly closes in Emmer Green and Caversham Park Village, have no coverage).
  tools/batch_sheets.py packs them 6 streets per image; all 17 batches looked at by eye.
- 2026-11-17 Style families (docs/style_families.json): victorian_terrace, victorian_villa, cottage,
  interwar_semi, interwar_detached, postwar_council, estate_6070, modern, town — walls, upper-storey render or
  tile-hanging, roof material, Tudor gables, brick quoins. docs/street_survey.csv: 104 streets classified (93 from
  photos, 11 from local knowledge, marked). tools/styles.py → docs/street_styles.json; unphotographed streets take
  their nearest surveyed street's family.
- 2026-11-17 Houses: semis/terraces share one roof across party walls (no more pyramid halves); eaves measured
  2 m inside the walls, min 5.6 m for two-storey houses (bungalows lower); upper-floor windows; brick front walls
  (Victorian) and privet hedges (interwar) on the pavement edge, open lawns for 1960s estates; walls and fences
  now connect (were lone posts). Roofs: 5379 hipped, 2593 gabled, 1651 flat.
- 2026-11-17 Landmarks (tools/landmarks.py, photos via tools/look.py <osm id>): St Peter's (flint, red clay tile,
  battlemented tower with belfry openings, stone quoins), Caversham Library (red brick + Bath-stone bands, clock
  tower with green copper cupola and bell), Caversham Baptist Church (red brick, buff bands, pyramid-capped
  tower), Caversham Heights Methodist (red brick, spired corner tower), St John the Baptist, Caversham Park
  mansion (pale stone, colonnade, balustrade). Churches get lancet windows, civic buildings tall mullioned ones.
  Landmark roofs are gabled with the ridge taken below the tower's height. Reinstalled + rezipped.
- Next: more landmarks (Caversham Court gazebo, Reading Rowing Club, Fox and Hounds, Prospect pub, schools,
  Heights water tower), Caversham Park front, shopfronts on Church Street / Prospect Street / Bridge Street.
- 2026-11-17 User: "Don't stop until the credits run out… don't ask me again" (saved to memory).
- 2026-11-17 Shopfronts: shops, pubs, cafés and town-family buildings near main roads get a glazed ground floor
  (panes + dark oak mullions) and a coloured fascia on the road side (100 buildings). Pubs from photos: Fox and
  Hounds (brick, Tudor gable, black fascia), White Horse (green fascia), Black Horse; Reading Rowing Club (white
  boathouse); Caversham Hall. Fixed: buildings were kept only if their first corner was inside the world, which
  dropped Reading Rowing Club; now by centre.
- 2026-11-17 Caversham Park: colonnade now runs the full height of the front. Emmer Green water tower
  (white concrete drum on a grey shaft, height from LiDAR) replaces its house-style stand-in; Caversham war
  memorial (stone cross on a stepped base) by Caversham Bridge. Reinstalled + rezipped.
- 2026-11-17 Caversham Court riverside gazebo (brick + flint bands, pyramid tile roof, vane) and Reading Canoe Club boathouse. Landmarks keep a pitched roof even when the LiDAR pitch is shallow; no chimneys on landmarks.
- 2026-11-17 Roof stairs: each faces up its own slope, and only on straight runs of roof edge; diagonal (off-grid) houses get full blocks on the zigzag instead of a comb of stairs.
- 2026-11-17 Churches from Commons photos (tools/look_title.py): St Barnabas Emmer Green (bellcote), Our Lady and St Anne (tall battlemented tower, stone dressings), Caversham Methodist Ardler Road (battlemented tower).
- 2026-11-17 Fry's Island: Caversham Boat Services' white clubhouse with Tudor gable, Island Bohemian Club; Caversham Wharf and Regents Riverside as pale-stone hipped flats; 70 moored boats (six woods) along the Thames banks, clear of bridges and the lock (checked in game).
- 2026-11-17 Schools get their own style (brick, tall mullioned windows); the domed Victorian house on the
  Peppard Road school site (copper cupola, white bays). Garden fences (spruce) between neighbouring plots
  where the nearest house changes, ≤25 m from houses, away from the road (278k blocks). Pavements: 2 m either
  side of every street over grass; front walls/hedges now sit at the back of the pavement.
- 2026-11-17 Street furniture from OSM points: 46 post boxes, 123 bus stops (shelters where tagged), 166 benches,
  157 bins, bollards, gates, phone boxes, cycle racks, info boards, recycling. Bay windows (3 wide, 1 out,
  two storeys, tiled cap) beside the front door on ~1,000 Victorian and 1930s houses. mc_view waits for the
  previous game to close.
- 2026-11-17 Night check (mc_view takes a daytime arg): lamps every 25 m alternating sides now light the streets. Tried lit house windows (light blocks + stained glass): not visible at block scale, dropped.
- 2026-11-17 Waterside: seagrass in the shallows, lily pads on lakes and ponds, long grass along banks; Redgrave Pinsent Rowing Lake gets 7 buoy lines (13.5 m lanes, buoys every 10 m, orange outer lines); white touchlines + halfway line on 24 football/rugby pitches.
- 2026-11-17 Street checks (Church Street, Emmer Green): garden fences now back gardens only (fronts open, as on the 1960s estates); paved front paths from 9,254 front doors to the pavement, with a gap in the front wall or hedge.
- 2026-11-17 Road bridges get concrete arches: over each run of water one arch per ≤45 m, springing at the waterline and rising to 2 below the deck (Caversham Bridge, Reading Bridge, island bridges); footbridges stay light decks.
- 2026-11-17 Lock: white balance beams with black ends at all four gate corners. LOCK_TEST=downup test build
  (Down fires at 2 s, Up at 16 s), checked from above: Down ran (upper gate shut, chamber at the lower level,
  lower gate open), then Up ran (lower gate shut, chamber full, upper gate open). BOTH directions verified.
  Front-wall/fence blocks from the house builder were landing inside the lock pool; now cleared from the site.
- 2026-11-17 Lock keeper's hut from Commons photos (dark timber, white windows, hipped mud-brick-tile roof, brick plinth) beside the upper gate; black bollards every 6 m along both lock walls.
- 2026-11-17 New family riverside_villa for The Warren (from Commons river photos): white render, Tudor gables, slate/tile, bays, hedges.
- 2026-11-17 Commons street survey: 57 more streets matched to Geograph photo titles, all looked at (build/cs_*.jpg) and classified; docs/street_survey.csv now covers 160 streets.
- 2026-11-17 grey_terrace family (Star Road and the Lower Caversham streets nearest it): tuff-brick walls, red brick quoins and a red band at every floor, slate, bays, brick front walls.
- 2026-11-17 Pubs from photos: Travellers Rest (Tudor gables, hipped tile), Prince of Wales (white, black plinth), Red Cow (low red brick); OSM point-only pubs mapped onto the building under them: The Griffin (brick + green fascia), The Crown, The Clifton Arms.
- 2026-11-17 Chimneys on attached houses sit on the party wall, so terraces get a stack between each pair of houses, like the real thing.
- 2026-11-17 OSM walls 2 high (garden walls like Caversham Court's), retaining walls 1 high; checked Caversham Court from the river.
- 2026-11-17 House interiors: oak staircase along an inside wall up through a stairwell to the first floor; crafting table + furnace (kitchen) downstairs, bed + bookshelf upstairs. Checked inside one house in game.
- 2026-11-17 Animals: cows and sheep (persistent, so they never despawn) in OSM meadows, ~1.5 per hectare, up to 6 per field; 21 placed (Mapledurham fields west, Emmer Green, Caversham Park). Checked a sheep loads in game.
- 2026-11-17 Old Grove House, Emmer Green (flint + red brick bands, steep tiled gables) with its flint road wall and row of clipped yew drums (from Geograph photos); BBC Written Archives Centre (low white render, hipped slate).
- 2026-11-17 Street trees: 1,705 LiDAR canopy peaks over roads/pavements had trunks in the road; trunks now move to the nearest verge or garden (crowns still overhang, as real ones do).
- 2026-11-17 Driveways: a 3-wide gravel drive beside each front path; 3,333 block-built parked cars (concrete body in common car colours, grey glass cabin) on about half the drives.
- 2026-11-17 Roads and pavements levelled across their width (9 m mean of road heights), so hills step along a road, not across it. Load check: spawn ready <1 s, no lag warnings, world 185 MB.
- 2026-11-17 Road ramps: a half slab (blackstone on tarmac, andesite on pavements) on the low side of every one-block step along a road, so hills are smooth to walk.
- 2026-11-17 Christchurch Bridge: 39 m white mast (white concrete, end rod tip) at the Reading end, 8 chain stay cables fanning to anchor points along the bent deck. Mast end chosen from Commons photos (the Caversham end runs down onto the Meadows).
- 2026-11-17 Churchyards and cemeteries (incl. Caversham/Henley Road cemetery): rows of headstones (stone walls) and ledger slabs, 9.4k; Thames & Kennet Marina: 40 moored boats round the basin.
- 2026-11-17 Gardens: flower beds (tulips, cornflowers, alliums, lilac...) and azalea shrubs in the 2 m along house fronts; 440 timber sheds at the far end of back gardens.
- 2026-11-17 Street name signs: 960 signs on posts at the ends of named roads (≥60 m apart), facing the road, long names over two lines; checked one reads correctly in game.
