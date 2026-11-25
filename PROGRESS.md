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
9. [x] Caversham Lakes beach (as in the owner's reference photo)
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
- 2026-11-17 Caversham Weir built along its OSM line: concrete wall to the upper water level, slab walkway, iron-bar railing, a sluice frame with gate every 5 m.
- 2026-11-17 Smooth-stone sills under and lintels over every window on brick-walled buildings.
- 2026-11-17 Leisure: 9 playgrounds (bark, red swing frame with chain swings, slide with ladder), nets on 18 tennis courts, 10 outdoor swimming pools (quartz edge, light-blue tank).
- 2026-11-17 Flat roofs: stone parapet round every flat-roofed building, a plant room on big ones; apartment blocks (≥8 m) get balconies (slab + glass rail) on the street side every storey.
- 2026-11-17 49 surface car parks: white bay lines (5 m bays, 6 m aisles, along the car park's long axis) and cars in ~12% of bays.
- 2026-11-17 Regression: full clean rebuild from the OSM extracts and EA tiles (osm_extract → lidar_mosaic → layers → survey catalogue → styles → build_world) in 2 min, anvil self-check ok, lock Down+Up test re-run on the final world: both directions work.
- 2026-11-17 Countryside: hedgerows round farmland edges; woodland floor (bushes, large ferns, blue flowers, fallen logs) through all OSM woods.
- 2026-11-17 Porches: stone hood over Victorian doors, tiled lean-to porch on 1930s/postwar houses, timber canopy on 1960s+ estates.

## Status (end of 2026-11-17 session)
Java world complete and installed (Prism "1.21.11 Paper" → saves/Cavcraft; build/Cavcraft.zip 42 MB).
Every building surveyed into docs/buildings.csv; 159 streets classified from Mapillary + Commons photos;
~35 landmarks from photos; lock verified both ways. Not done: Bedrock conversion (user's call), interiors beyond
stairs/furniture, shop signs with real names.
Next ideas: real shop names on fascias (OSM shop names → signs), more landmarks (Highdown School, Emmer Green
shops parade), Christchurch Meadows paddling pool, allotment sheds, Caversham Park mansion's south terrace.
- 2026-11-17 Shop names: 51 shopfronts get a wall sign on the fascia with the real name from OSM (outline tag or the shop point inside it): Tesco Express, Alto Lounge, Stir Fry Caversham, Clay's Hyderabadi Kitchen, Age UK... Build now drops any block entity whose block a later stamp overwrote (the game logged 8 'Invalid block entity' errors before; now 0).

### 2026-11-17: odd roofs fixed
- Cause: the first-return DSM includes trees over roofs, so some garages and small houses got 14-22 m spiky roofs; there was also no pitch limit.
- fit_roof now caps the ridge at 45 deg from the eaves and at 13 m for houses. Garages, sheds and service buildings stay single-storey (eave 2.5 m, ridge at most 4.5 m). Houses with no LiDAR roof (built after the survey) get a plain two-storey gable.
- Measured over all 9,626 buildings: roofs steeper than ~55 deg went from 75 to 7; houses sunk to a 3 m box went from 151 to 32 (those left are big non-house buildings).
- Checked with a new oblique render (render_world.py `out.npz` + a projection) because the screen was locked and the game couldn't open a window: Warren-side roofs that had tree spikes are now plain stepped hips.
- mc_view.py: it looked for the game by searching for text that also appears in shell command lines, so it could wait forever. It now matches only the java process, and closes the game if it never joins.

### 2026-11-17: Emmer Green centre
- From Mapillary/Commons photos: the Milestone Way shopping parade (three-storey flat-roofed brick, shops under a long white canopy: new `canopy` landmark option), the Coral corner shop (red brick, dark tile, blue fascia) and the 203-217a Peppard Road Georgian cottage terrace (red brick, slate).
- Highdown School: the only photo is an interior one, so it keeps the general school style. The Christchurch Meadows pool is already built by leisure().

### 2026-11-17: allotments
- features.allotments(): the 5.6 ha of allotments are now 5 m plots split by grass paths, with 177 two-by-two spruce sheds with doors onto the paths, compost bins, water butts and bean canes. Checked in an oblique render of the Henley Road allotments.
- Caversham Park: a 6 m paved stone terrace at floor level along the south front, with a sandstone balustrade and steps down to the lawn in the middle (new `terrace` landmark option). No photos exist in Mapillary or Commons, so it's built from the outline.
- Roofs: a gable (one straight ridge) is now allowed only when the roof region is at least 75% of its oriented bounding rectangle. 727 gables had been laid across L- and T-shaped outlines, leaving half-roofs hanging off the wings; they now get hips that follow each wing (gables 2738 -> 2066, hips 5310 -> 5910).

### 2026-11-17: garages
- Garages and lock-ups no longer get house windows. A garage gets a 2-wide white up-and-over door on the wall nearest the road; a block of lock-ups (`garages`) gets a row of doors with a brick pier between each. Read back from the region files: the Harley Road lock-ups (w137356891) have 9 door cells along the road side.

### 2026-11-17: shared roofs on semis and terraces
- houses.shared_roofs(): every house is fitted first. Attached houses whose floors are within 1 m are grouped (terraces stepping down a hill keep their steps), and each group gets its median eave and ridge height and its commonest roof kind, so a pair of semis no longer comes out a block or two apart. 3,594 houses in 1,162 groups.
- Read back from the world files over 1 km x 1.5 km of central Caversham: level attached pairs whose roof tops differ by 2+ blocks went from 15 to 3, and by 1 block from 84 to 34 (most of what's left is chimneys).

### 2026-11-17: road crossings
- features.crossings(): from OSM crossing and signal nodes inside the world, with nodes mapped on the pavement edge snapped onto the road. 9 zebras (crossing_ref=zebra or crossing=uncontrolled/marked) get white stripes painted per road block, running with the traffic across the full road width, and a Belisha beacon (alternating black and white wall posts, shroomlight globe) on each kerb. 50 signal crossings and junction signals get a black traffic-light pole on each kerb. Most OSM crossings in the box are south of the river in Reading, so outside the world.

### 2026-11-17: playtesting while the PC is locked
- mc_view.py now runs the game inside a headless gamescope, the same way as Splitwater's and Fortress United's tools/headless-run.sh. A normal window stops drawing while the session is locked; gamescope's doesn't. It takes the screenshot with `gamescopectl screenshot` (display name read from the game's own environment), then closes the whole gamescope process group. If the user's own Prism is open, it falls back to a normal window and spectacle, because Prism allows only one copy.
- Verified in-game with the screen locked:
  - Roofs by the river: no spikes, and the garage is single-storey.
  - The Emmer Green parade looks like its photo, with the white canopy over the shops.
  - The lock works both ways. A LOCK_TEST=down build drains the chamber with the upper gate shut and the lower gate open. A downup build refills it with the lower gate shut and the upper gate open.

### 2026-11-17: the weir, the island paths, Winter Wonderland, Thames Water and the EA (user's requests)
- **Caversham Weir** (features.weirs, from Commons photos): concrete sluice bays between stone-brick piers every 5 m, a 4-wide raised footbridge with iron railings both sides, tall white gate frames with a top beam on the upstream side, the white control hut on the frames over the middle, and white water below (a band of bubble columns over soul sand, which churns at the surface).
- **Lock island, weir and View Island paths** (features.island_paths): 97 black Victorian lamp posts, 9 benches facing the water, 417 railing blocks along the water's edge, and one of View Island's chainsaw-carved wooden heads in the trees.
- **Reading Winter Wonderland** on Hills Meadow car park (features.winter_wonderland; it runs 7 Nov 2026 to 3 Jan 2027). Built from the user's photos:
  - The white observation wheel, 32 m across, with 20 white gondolas, a coloured light ring and red-and-white legs.
  - An ice rink of packed and blue ice under an open-sided white tent.
  - 32 chalets with lit eaves, the harlequin helter-skelter, the yellow Coaster, the jungle funhouse with its blue spiral slide, striped prize stalls, a Catch-a-Fish pool, the Apres Bar deck, candy canes and lit Christmas trees.
  - Red carpet down the avenue, and the red oval entrance arch with a nutcracker on each post.
  - Snow underfoot "for magic" (the user's call). The fair is fenced; the rest of the car park keeps its bays and cars.
- **South bank extension** (layers.py: mask x 3690-3945, z 4150-4312): Thames Water's Clearwater Court, the Environment Agency's Kings Meadow House and Reading Bridge House as landmarks from Mapillary photos, King's Meadow Road from the lock to them, and a thank-you signpost outside each (features.data_signs).
- Checked in-game (headless): the weir from downstream and from its deck (bubbles churning), Winter Wonderland from above and through the arch, the EA building, and Clearwater Court from the river.

### 2026-11-17: car parks, war memorial, river boats, furnished houses
- Car parks: bays now come off each mapped parking aisle: a 5 m line every 3 m either side, with 2 x 3 cars nose-in in about a third of the bays. Aisles within 20 deg of the block grid are squared up, so the lines run straight. Car parks with no mapped aisles use the old rows, also squared up. From above, the Emmer Green car park now shows clean rows of bays round its loop aisle.
- War memorial (Christchurch Meadows), rebuilt from the Commons photos: a 2 x 2 pale-stone column with a carved band near the top, on a two-step plinth on an octagonal flagstone base, with poppy wreaths (red carpet, since poppies won't stand on stone). The old version was a white quartz cross.
- 40 free-floating rowing boats on the Thames and the lakes, away from the banks and bridges. These are ordinary boat entities, so they're rideable in Java and survive conversion to Bedrock. Vanilla can't make boats move by themselves.
- Houses you can live in (houses.furnish):
  - Downstairs: a kitchen run along a wall (smoker, sink cauldron, worktop, barrel cupboard) and a dining table with two chairs.
  - Upstairs: a whole double bed, head and foot, with its head against a wall, and a bookshelf.
  - A lantern hangs from each ceiling, and the hall inside the front door is always kept clear.
  - Windows are grey stained glass instead of tinted glass: it still reads dark from outside but lets daylight in.
  - Counted around Gosbrook Road: 83 doors, 70 beds, 64 kitchens, 44 tables. Checked in-game from inside a house.

### 2026-11-17: churches at night, barges, Whittington's Tea Barge
- Churches (lancet windows): stained glass in blue, red, yellow, purple and light blue, and an open nave with no upper floors. Inside are oak pews either side of a central aisle facing the east-end altar, which has lit candles. Hidden light blocks inside make the windows glow at night, and hidden floodlights stand 2 m off the walls at ground level and at +6, +11 and +16 to reach towers and gables. Checked at night: St Peter's is floodlit with glowing windows.
- 25 block-built narrowboats moored along straight stretches of the Thames bank. Each has a black hull, a painted cabin with windows and a stern door (walk-in, wooden floor), a tiller, and pots and logs on the roof. Light blocks are used rather than lanterns so they work in Bedrock too.
- Whittington's Tea Barge, from the user's photos: moored on Hills Meadow's bank upstream of the weir, next to Winter Wonderland. The bank is slanted there, so it gets a straight paved quay. It's a 22 x 5 wide-beam with a dark green hull and roof, a cream cabin, blue curtains, a gangplank to a side door, tea tables and chairs inside, and a counter with cakes. White tables and chairs stand on the quay, with a "Whittington's Tea Barge" sign. Checked in-game, inside and out.
- Whittington's, after the user's feedback ("quite extreme", the big paved quay): there's no quay now. It moors at the straightest 20 m of Hills Meadow's bank, and only the water left between it and the bank is decked over as a wooden pontoon on posts. The hull and roof are darker green; tables and chairs stand on the pontoon and bank beside it.

### 2026-11-17: GitHub, gift card, cinema, school treasure
- Public repo https://github.com/a-adz-1/cav-craft. Before the first push, the beach photo the user had shared (someone else's photo) was stripped from history; the local branch `backup-before-public` keeps the original. The README opens with download-and-play steps for families. Release v0.1 carries Cavcraft.zip.
- Gift card (tools/card.py):
  - Front: a credit-card-size original grass-block "CAV CRAFT" logo and a creeper-green QR code with a creeper face, at error correction H. It's checked with zbarimg to decode to the GitHub URL.
  - Back: an 11-item achievement checklist.
  - docs/card/cavcraft-cards-a4.pdf has 10 cards a side with cut marks, the back page mirrored for long-edge duplex.
- Pop-up cinema at Caversham Court Gardens (from the user's photo): a black inflatable screen with a sea-lantern face that glows at night, speaker stacks, striped deckchairs, red and blue beanbags, festoon lanterns and a sign. Trees are kept off it. Checked at night.
- School treasure: at 13 school grounds, a small lit Christmas tree with a chest under it (diamond, cake, cookies, fireworks, gold, glow berries) and a "You found the CAVCRAFT TREASURE!" sign.
- Christmas in Caversham centre (features.xmas_centre): 32 strings of glowing lights (froglights, shroomlight and sea lanterns on chains, drooping in the middle) hung across Church Street, Prospect Street and Bridge Street every 12 m, from building to building at first-floor height. A big lit town tree with a star stands at the junction. Checked at night.
- Whittington's: bottle green (dark prismarine) hull and roof, as in the photos (green concrete renders olive); dark waterline strake.
- Winter Wonderland at night: hidden light blocks every 6 m across the fair, so the snow, chalets and rides glow. Checked at night from above, and it looks great.
- Environment Agency: a tall glazed bay (light blue glass framed in red brick, mullions every storey) up the middle of the road-facing wall (new `glass_bay` landmark option).

### 2026-11-17: on the family Multiverse server
- The server is Paper 1.21.11 at 10.0.0.36 with Multiverse-Core 5.6.1. Cavcraft was downloaded there from the v0.1 release into /home/minecraft/server/Cavcraft and loaded with `mv import Cavcraft normal`. The server read the flat void settings from level.dat (FLAT, no structures).
- Read-only: gamemode adventure (no breaking or placing; buttons, doors, boats and chests still work), peaceful, no PvP, no hunger. The spawn_monsters, spawn_phantoms, spawn_patrols and spawn_wandering_traders game rules are off; spawn_mobs, mob_griefing and weather were already off from level.dat. 1.21.11 uses the new snake_case game rule names.
- Multiverse-Inventories leaves ungrouped worlds separate (default-ungrouped-worlds: false), the same as rivercraft, so inventories don't carry over.
- The server log after import is clean.

### 2026-11-17: smooth bridges (user: "the cav bridge will need smoothing out")
- Bridge decks used to step straight up off the road, and the road ramps used blackstone slabs, which look like rubble.
- Each road bridge's deck now eases to the street at both ends, at most 1 block per 4 m. It's anchored to the first dry street cell beyond each end; before, Caversham Bridge sagged onto Fry's Island because its mapped ends are over water.
- Where the deck is only 1 above the road, the road is raised instead. Every remaining 1-block step on or next to a deck gets a half-slab ramp, placed last so the headroom clearing doesn't wipe it, including in chunks that only border a deck.
- Road ramps everywhere now use polished deepslate slabs: smooth and dark like the tarmac.
- Checked by walking every road bridge's centre line in the written world: Caversham Bridge is smooth end to end. Reading Bridge has one 1-block step at the zebra on its north end and a 2-block step where it meets a footbridge deck.
- Builds now run at nice 10 with 4 cores left free, after the PC hung while the user played. mc_view refuses to start while the user's own Prism or Minecraft is open: it would close their game.
- Server copy swapped to the smoothed build: `mv unload Cavcraft --no-save`, region/ and entities/ replaced from the release, and the server's own level.dat kept (adventure, peaceful, game rules), then `mv load Cavcraft`. Log clean; temp files removed.

### 2026-11-17: road review (user: "never drop down by more than 1 block at a time, as smooth as possible like a real road")
- New tools/road_check.py reads the built world and finds the walking height of every road and pavement cell, with slabs as half blocks. Cells with something standing on them (buildings, cars, lamps, bridge structure) are skipped. It reports every neighbouring pair by step size and exits 1 if any step is over the limit (ROAD_LIMIT, default 1).
- What it found:
  - 128 places with a 1.5-block jump. The road ramp slabs were worked out per chunk with wrap-around, so steps across chunk borders got no slab. The fix is build_world.ramp_cells, computed once for the whole world, with a self-check.
  - Full 1-block steps where a road climbed on two cells in a row. tools/grade.py now limits every road to half a block per metre: the midpoint of the upper and lower envelopes, then rounded, which guarantees no two full steps in a row. layers.py grades the roads (2,705 cells moved, max 0.9 m), and features grades them again after bridges raise some road, before anything is placed on it.
  - Winter Wonderland's snow had replaced ramp slabs there; snow now stays off them.
  - Reading Bridge: a footbridge mapped beside the road deck sat 2 above it. Road bridges are now built first, and a pavement bridge beside a road takes the nearest road cell's deck height.
- Result: across 2.1 M neighbouring road/pavement pairs, every step is 0 or half a block (0 drops over 1, 0 full-block steps). Both road bridges are smooth end to end. Caversham Bridge's separately mapped pavements meet the bank with at most a 1-block step.
- Server copy swapped to the graded-roads build (same method: unload --no-save, replace region/ and entities/, keep the server's level.dat, load). Still adventure mode; log clean.
- 2026-11-17 Bridge "forts": the parapet wall ran right round each deck, including across the road where the street runs off it (Reading Bridge north end, both ends of Northbrook Road), so the ends looked like battlements. Now there's no parapet where the deck meets a street. 0 walls standing in streets, road_check still 0 drops over 1. Server: adjrobinson given LuckPerms mv.bypass.gamemode.Cavcraft so creative (flying) survives Multiverse's world gamemode.
- 2026-11-17 Server copy swapped to the no-fort bridges build (same method). Log clean. 206 Kidmore Road (semi w151096536, 206 is the half towards 202/204) front path: /execute in minecraft:cavcraft run minecraft:tp @s 2547.5 74 1943.5 -125 0 (minecraft:tp, as Essentials' /tp rejects @s).
- 2026-11-17 Footpaths (user, from Kidmore Road: "there's a footpath along here, we need to do better with foot paths"). Houses set more than 14 m back from the road (a wide verge or slip road in front, like the 200s on Kidmore Road) had no front path, drive or garden boundary: front_paths gave up past 20 m. Now a 2 m pavement runs along such rows 8 m out from the doors, joining each house to its neighbours (819 doors), and the usual front paths, drives and hedges follow it. OSM footways, cycleways and pedestrian ways with no surface tag are now paved (they were dirt paths). road_check still 0 drops over 1.
- 2026-11-17 Houses review (user: "no diagonal houses, rebuild them, make them look like real houses, add footpaths, add house numbers"; "a lot of the doors close and you can still get in"):
  - Square houses: layers.square_houses turns each attached group of house-type buildings (a terrace, a pair of semis, a house and its garage: outlines sharing corners) about its centre to the nearest right angle, so walls are flat, not stair-stepped. 17,851 outlines in 11,467 groups (whole extract). Groups over 1,500 m² (flats, schools, shop blocks) keep their angle. Squared houses are drawn after the rest, into free cells only.
  - Sealed doors: a front door only goes in a straight wall cell (one outside face, wall either side, a room behind), because on a stair-stepped corner you could walk round a closed door. 27 doors checked on Kidmore Road: none has a gap beside it.
  - No flowers or shrubs within 2 blocks of a doorstep.
  - House numbers: buildings.json keeps addr: tags, and address points inside a building pass their number to it (5,377 numbered). A dark oak plaque with the number hangs on the wall beside each front door (5,262 placed). Houses with no number in OSM have none.
- 2026-11-17 Realism pass, part 1 (the school first):
  - **The Heights Primary School** (landmark w1062444336). It was built after the LiDAR survey, so it came out as a 1 m wall round an empty floor. Now:
    - a two-storey flat-roofed school squared to the grid: buff brick, tall window bands, a stone band between floors, coloured panels upstairs
    - a glazed entrance with a canopy, "THE HEIGHTS / PRIMARY / SCHOOL" over the door, lamp posts either side
    - grounds (features.heights_school), turned with the building: a weldmesh fence with a brick-pillared gate and name sign, a tarmac yard with hopscotch, a four-square court and a painted snake, the games court in green with white lines and a 3-high fence, lamp posts, lights round and inside the building
  - **School drive** from Upper Woodcote Road (w37000897) is a 6 m road with pavements both sides (layers.SCHOOL_ROADS).
  - **New buildings with no LiDAR height** (fit_roof): any building now gets two storeys with a flat roof.
  - **Squaring**: buildings were counted twice (area and closed line), which doubled group sizes; fixed. Schools, shops, churches and pavilions are squared too, never into a road or pavement. 20,755 outlines.
  - **Play parks** (features.play_parks): a fenced play area at every mapped playground and in every park with none. 23 built, including Albert Road Recreation Ground. Each has swings, a slide tower, a climbing frame, a roundabout, safety tiles, benches, a lamp and a sign.
  - **Zebra crossings** squared to the grid: 3-wide stripes kerb to kerb, white slabs over ramp steps, red tactile paving at each end.
  - **Chains**: the block is iron_chain in 1.21.11, so the earlier chains were missing. Fixed.
  - **New tool, tools/eye_view.py**: player's-eye pictures from the region files, for checking while the game is busy.
  - **Server**: the kids can fly in adventure mode (essentials.fly) and Cavcraft allow-flight is true. Their spawn points are outside 206 Kidmore Road.
- 2026-11-17 Realism pass, part 2 (finishing the review list):
  - **Town-centre blocks squared**: groups over 1,500 m² now turn to the grid too when their walls all agree on one angle (16 more blocks in the map, up to 20,000 m²). Terraces that bend round a corner keep their angle, because turning them as one would push the ends into the road.
  - **More house numbers**: unnumbered houses on the same side of the same street as numbered ones carry the numbering on, filling gaps (12, ?, ?, 18) and running past either end of a numbered run in the same step (odds/evens, or 1-by-1). That added 326 houses, about 5,700 numbered in all. Streets where OSM has fewer than two numbers on a side stay blank, because there's nothing to count from.
  - **Pavements follow OSM sidewalk tags**: sidewalk=no/none/separate, sidewalk=left/right and sidewalk:left/right/both are all read. A side with no pavement, or with its own mapped footway, gets none (OSM marks about 570 roads with no pavement on one or both sides, and about 400 with a separately mapped footway).
  - **House styles**: every street already has a style from the photo survey (159 classified from Mapillary and Commons, the rest from the nearest photographed street of the same era), so no new photos were needed.
  - Checked: road_check 0 drops over 1; eye_view on Hemdean Road shows pavements, low brick front walls and houses matching the Mapillary sheet; the big Church Street block has straight walls. eye_view now finds plural textures (bricks, tiles).

## Status: review list done (2026-11-17)
All of the user's review items are done: school and drive, square houses and town blocks, sealed doors, footpaths and pavements (with sidewalk tags), house numbers (where OSM can give them), play parks, zebra crossings. Only the Bedrock conversion is still open, and that's the user's call.
- 2026-11-18 Release v0.1 zip updated and server copy swapped to the realism pass 2 build (same method: unload --no-save, replace region/ and entities/, keep the server's level.dat, load). Nobody was online. Log clean, still peaceful.
- 2026-11-18 Caversham Heights pass, part 1 (user: "focus on cav heights, make the roads smooth, make any road markings make sense, review the heights school and church images"; "the road up to the school needs editing too"):
  - **Smooth roads** (tools/roads.py, layers): every road's mapped centre line is rounded at its bends (Chaikin) and drawn 4x finer, keeping cells at least half covered, so edges are even at any angle and widths don't wobble. Footpaths never paint across a road. Road heights are smoothed along the road (Gaussian, 4 m), so each one-block step is one clean line across the road. road_check still 0 drops over 1.
  - **Turning circles**: OSM turning_circle nodes become a round head 15 across at the end of the close (turning_loop: 20 across with a grass island).
  - **Road markings** (features.streets): the centre line stops 7 m short of junctions between main roads, crossings, signals, mini-roundabouts and the road's own ends. Every side road gets a dashed give-way line where it meets a road at least as big (569). Mini-roundabouts get a white dot.
  - **The Heights Primary School site**, laid out from an Esri aerial photo (new tools/aerial.py) and squared to the grid like the school:
    - the drive runs into a forecourt aisle with the staff car park to the west and the pavilion car park to the east, marked bays and parked cars, and a zebra with beacons from the drive's pavement to a paved plaza at the school gate
    - a 4 m path runs south from the plaza between the school fence and the field, replacing OSM's thin diagonal path; the field path runs along the south fence
    - the fence now leaves the car park outside; the gate is on the east side at the plaza
    - roof: grey parapet, sedum green roof, rows of solar panels on the west half; a white canopy on the south side
    - the tennis club: red surround, four green courts two by two with lines and nets, a mesh fence
  - **Squared houses read the right LiDAR**: a house turned to the grid used to read heights from under its turned outline, which is partly garden. Each cell now reads from where that part of the house really stands (buildings.json "turn"), so roof heights, bungalows and towers come out right.
  - **Attached houses share one look**: both halves of a pair of semis and every house in a terrace get the same walls and roof. Mock-Tudor houses get a white upper floor under the beams.
  - **Churches**: Caversham Heights Methodist (from street photos): red brick with stone bands, dark tile roof, a 5 m corner tower with a spire. St Andrew's, Albert Road (new landmark, from a Commons photo): brown stone, pale dressings, slate roof, lancets, a bellcote.
  - New tools: tools/aerial.py (aerial photo of a box), tools/top_view.py (the built world from above in true colours). eye_view textures now live in .downloads/tex.
- 2026-11-19 Caversham Heights pass, part 2: house styles street by street from Street View.
  - 85 Heights streets looked at on Google Street View (2 to 5 points per street, both sides). For each one the survey records the share of each wall finish, upper floors that differ (render over brick), mock-Tudor, roof colours, bungalows, detached/semi/terrace, era, front boundary, verges and the road itself. It's in docs/heights_survey.json: 10 high confidence, 39 medium, 34 low (hedges hide the houses), 2 none.
  - tools/styles.py turns each street's measured shares into its style (12 slots in proportion), keeps the era family for bays and details, and takes the surveyed front boundary (hedge, low wall or open-plan lawn). 109 streets are now measured; closes nobody looked at take the nearest measured street.
  - Bungalows come from the real LiDAR heights, and agree with Street View: Kelvedon Way 100% low vs 95% seen, Gurney Close 81% vs 85%, Haldane Road 79% vs 80%, Kidmore Road 6% vs 5%.
  - Streets the survey saw a centre line on get one, as well as the main roads.
  - road_check 0 drops over 1.
- 2026-11-19 Pushed, release v0.1 zip updated and server copy swapped to the Caversham Heights build (same method). Nobody was online. Log clean.
- 2026-11-19 Street View survey of the rest of Caversham, section by section (user: "do the main caversham center review, do the rest of cav section by section", "keep the photos"):
  - The town is split into sections (town centre, Lower Caversham, Hemdean/St Anne's, Emmer Green, Caversham Park; the Heights again, this time keeping photos), each a folder in .downloads/ref/sv/ with views.tsv (street, view, Street View URL), img/ (every screenshot, 935 so far), result.json and notes.md; README.md and BRIEF.txt explain the layout and how the helpers worked. The text files are copied to docs/street_view/ so they're in git; the photos stay in .downloads (git ignores it).
  - Done: the town centre, Lower Caversham, Hemdean/St Anne's, Caversham Park c in full; parts of Emmer Green, Caversham Park and the Heights redo. Then Google Maps went blank in the app's browser pane (net::ERR_BLOCKED_BY_CLIENT) for every helper. docs/street_view/RERUN.md lists the 162 streets still to do; their entries say "not surveyed".
  - tools/styles.py reads every section's result.json as well as docs/heights_survey.json, keeps the more confident reading where a street was surveyed twice, ignores material names it doesn't know, keeps the "town" type (shopfronts) on streets that are mostly shops, and gives shopping streets the fascia colours the survey saw (Prospect Street: dark green, black, red).
  - 318 streets now have their own Street View reading. road_check 0 drops over 1.
- 2026-11-19 Heights survey redone with photos (user: "keep the photos"): all 85 Caversham Heights streets again, in 0_heights_a/b/c, 413 screenshots kept. Google Maps loads in the browser pane again. 1,306 photos kept in all; 320 streets have their own Street View reading. Still to do: 82 streets in Emmer Green and Caversham Park (docs/street_view/RERUN.md). road_check 0 drops over 1.
- 2026-11-19 Rerun of the last 82 streets (Emmer Green, Caversham Park) stopped: Google Maps went blank in the browser pane again (net::ERR_BLOCKED_BY_CLIENT on its scripts), no new photos. Each section's notes.md says so; docs/street_view/RERUN.md still lists the 82. Nothing to merge, world unchanged.
- 2026-11-19 Pushed, and release v0.1 now has the world with the Heights redo (Street View styles from 320 streets). Server not swapped yet.
- 2026-11-19 Street View screenshots kept local on purpose (user): .gitignore now blocks images anywhere under docs/street_view and any sv/*/img folder; CLAUDE.md says never commit, upload or publish them.
- 2026-11-19 docs/area.png (a Google Maps screenshot of the outline) taken out of git, kept in .downloads/ref/google/; BRIEF.md points there. No Google images left in the working tree.
- 2026-11-19 History purged (user OK): docs/area.png (Google Maps screenshot) and docs/caversham-lakes-beach.webp removed from every commit with filter-branch, main and tag v0.1 force-pushed. Both images kept in .downloads/ref/; the old history is backed up in .downloads/cavcraft-backup.git. A fresh clone of GitHub has neither file. GitHub still answers old commit 05b05ef by its hash until its own cleanup; only GitHub Support can remove it sooner.
- 2026-11-19 Street View survey finished: the last 82 streets (Emmer Green, Caversham Park) done now that Google Maps loads again. 458 streets: 399 surveyed, 59 (no coverage: private roads, closes) take their nearest surveyed neighbour's style. Photos stay local in .downloads/ref/sv/*/img; text results in docs/street_view/. World rebuilt; road_check 0 drops over 1.
- 2026-11-25 Pushed; release v0.1 has the world with the finished Street View survey; server swapped to it (region/entities replaced, server level.dat kept, loads cleanly).
- 2026-11-25 Houses you can live in (user: glass everywhere, glass stopping you going upstairs, doors you can walk round, numbers missing):
  - Windows only in outside walls (one side open to the garden): none in party walls, walls between a house and its extension, or stepped corners; 2 wide with 3 of wall between. Glass down a third (audit box Kidmore Rd: 15,541 -> 10,161 blocks, glass inside buildings 1,691 -> 0). Brick between the storeys stays brick, so windows don't run into one strip.
  - Stairs: a free cell at the foot, 3 steps and a free landing on the first floor, all kept clear (the hall behind the front door used to wipe the first step; furniture could block the landing). 6,555 of 6,615 two-storey houses have a full staircase.
  - Garden sheds are 3x3 with a room inside and the door into it (they were solid 3x2 lumps with a door onto planks).
  - House numbers on every house: rows with one or no known numbers are counted along the street (odds/evens, opposite to the other side); 3,333 guessed (direction along the street assumed, so a guessed number can be a few off; 10 that would repeat a real number get a letter, 12a), 8,899 plaques in all. White glowing text on the dark oak plaque, beside the door on the free side, or over the door if both sides are taken.
  - Survey: 76 streets were rated low; 6_low_a/b/c (docs/street_view) have fresh viewpoints for 69 of them and LOW_BRIEF.txt. Not run yet: Google Maps is blank in the browser pane again.
  - road_check 0 drops over 1.

### 2026-11-25 — House fixes live
Pushed 643d1ae, uploaded the rebuilt world to release v0.1 (43 MB), and swapped it onto the server (unload, new region/entities, poi removed, load; log clean). Google Maps works in the pane again, so the second-look survey of the 69 unclear streets (6_low_a/b/c) is running.
- 2026-11-25 Second look at the 69 unclear streets (6_low_a/b/c, new viewpoints along each street): 20 now medium, 20 still low, 29 none (no Street View there, or every view landed on the next street). styles.py keeps the more confident reading, so 20 streets now have a better one. Photos stay in .downloads; text results in docs/street_view/6_low_*.
- 2026-11-25 Parks and pitches (features.leisure), for every mapped one, not just Clayfield Copse:
  - Tennis: 17 courts now have green surfaces with white doubles/singles/service/centre lines, a red surround, a net across the middle, and a mesh fence around each group of courts with a gate on the south side. No grass tufts on them. Caversham Park Tennis Club (Clayfield Copse) has its six courts in two rows of three.
  - Football: goals (posts and crossbar, 7 wide) at both ends. Basketball: hoops on posts. Pitches mostly covered by a bigger one are skipped (hidden_pitches, 3 of them).
  - Pitch axes now come from the outline's tightest rectangle (rect_axes). The old SVD tilted them because the closing corner counted twice, so halfway lines and nets ran crooked.
  - Skate parks: concrete with a quarter pipe at each end and a box with a rail.
  - From the map's points: 17 sculptures (wooden carvings or stone, a sign with the name, e.g. Clayfield Copse's Squirrel and Spider's Web), 4 shelters, 7 picnic tables.
  - Tennis clubs no longer get a play park dropped in the middle.
  - road_check: 0 drops over 1.
- 2026-11-25 Parks build pushed (0c4778a), uploaded to release v0.1 and swapped onto the server; log clean.
- 2026-11-25 Park pass (looked at Christchurch Meadows, Caversham Court Gardens, Balmore Walk, View Island, Mapledurham Playing Fields, Clayfield Copse from above; read up on Caversham Court and Christchurch Meadows):
  - Big tennis outlines now hold as many courts as fit (a court with run-off is about 34 x 17): Christchurch Meadows 2, the Peppard Road club 8, the Walled Garden site 4; 29 courts in all, up from 17. Before, a big outline got one court in a sea of red.
  - Statues mapped as memorials get built too: Caversham Court's two Griffins at the top of the steps (19 sculptures/statues in all).
  - Checked and left alone: park trees come from the LiDAR canopy, so they're real; Caversham Court's walls, hedges and 1663 gazebo, Christchurch Meadows' paddling pool, play area and war memorial, and View Island's paths were already built. The magenta in the top views is only the preview's missing colour for allotment crops and berry bushes.
  - road_check: 0 drops over 1.
- 2026-11-25 Landmarks pass: checked which notable places in OSM weren't styled yet (pubs, schools, wells, memorials).
  - The Griffin and The Crown restyled from Mapillary photos (tools/look.py). They were already styled from OSM points by landmarks.PUB_POINTS, which overrides LANDMARKS, so the new looks went there. Griffin: red brick, white upper storey with black-and-white gables, grey fascia, dark tiles. Crown: yellow brick, dark teal painted upper storey (new wall finish painted_teal = cyan terracotta), teal fascia, red clay hipped roof (PUB_POINTS can now set roof_kind).
  - Landmarks can now set a different upper-storey finish ("upper").
  - St Anne's Holy Well, Priest Hill: a flint well-head round water, with a name sign. The King's Spy Oak (a real LiDAR tree) gets a name sign. Name signs now go on the first side clear of buildings (before, one replaced a house window).
  - Not done yet: Queen Anne's School (no single building in the list), The Clifton Arms (no clear photo), Highdown School (still the general school style).
  - road_check: 0 drops over 1.
