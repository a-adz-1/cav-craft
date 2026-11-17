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
