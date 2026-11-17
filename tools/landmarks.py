"""Caversham's landmark buildings, built from their photos (tools/look.py <osm id> makes a reference sheet).

Each entry overrides the house builder for that OSM building: wall and roof materials, stone dressings
(quoins and string courses), window style, and extra parts: a tower (battlemented, spired or with a copper
cupola) standing where the LiDAR surface is highest, and colonnades. All plain Minecraft blocks.
"""
import numpy as np

# walls/roof use the names in houses.WALLS / houses.ROOFS
LANDMARKS = {
    # Emmer Green water tower: built by features.structures instead
    "w171331924": {"name": "water tower", "skip": True},
    # St Peter's, Church Road: knapped flint with stone dressings, old red clay tiles, square west tower with
    # string courses, belfry lancets and a battlemented parapet
    "w139149858": {"name": "St Peter's Church", "walls": "flint", "roof": "red_tile", "dress": "stone_bricks",
                   "windows": "lancet", "band": 5,
                   "tower": {"size": 5, "top": "battlement", "walls": "andesite", "dress": "stone_bricks"}},
    # Caversham Library, Church Street/Hemdean Road (1907): red brick and Bath-stone bands, big mullioned
    # windows, Dutch gables, clock tower with a green copper cupola
    "w140485466": {"name": "Caversham Library", "walls": "red_brick", "roof": "slate", "dress": "smooth_sandstone",
                   "windows": "tall", "band": 4,
                   "tower": {"size": 4, "top": "cupola", "walls": "bricks", "dress": "smooth_sandstone",
                             "extra": -4}},
    # Caversham Baptist Church, Prospect Street: red brick with buff bands, tall lancets, gabled tower
    "w139051670": {"name": "Caversham Baptist Church", "walls": "red_brick", "roof": "slate",
                   "dress": "smooth_sandstone", "windows": "lancet", "band": 4,
                   "tower": {"size": 4, "top": "pyramid", "walls": "bricks", "dress": "smooth_sandstone"}},
    # Caversham Heights Methodist Church, Highmoor Road: red brick, clay tile, corner tower with a tiled spire
    "w139821746": {"name": "Caversham Heights Methodist Church", "walls": "red_brick", "roof": "red_tile",
                   "dress": "smooth_sandstone", "windows": "lancet",
                   "tower": {"size": 3, "top": "spire", "walls": "bricks", "dress": "bricks", "extra": 8}},
    # St John the Baptist, Gosbrook Road (behind railings): red and grey brick
    "w138758862": {"name": "St John the Baptist", "walls": "red_brick", "roof": "slate", "dress": "stone_bricks",
                   "windows": "lancet"},
    # The Fox and Hounds, Gosbrook Road: red brick, brown tile, black-and-white Tudor gable, black pub fascia
    # with gold lettering over white-framed windows
    "w137356792": {"name": "The Fox and Hounds", "walls": "red_brick", "roof": "brown_tile", "dress": "bricks",
                   "windows": "house", "shopfront": "black_concrete", "tudor_gable": True},
    # The White Horse, Emmer Green: red brick, old tile, green signboard fascia
    "w160047093": {"name": "The White Horse", "walls": "red_brick", "roof": "red_tile", "dress": "bricks",
                   "windows": "house", "shopfront": "green_concrete"},
    # The Black Horse, Kidmore End Road
    "w171190554": {"name": "The Black Horse", "walls": "white_render", "roof": "red_tile", "dress": "bricks",
                   "windows": "house", "shopfront": "black_concrete"},
    # Reading Rowing Club: white-clad boathouse, shallow slate roof, boat bays to the river
    "w136161988": {"name": "Reading Rowing Club", "walls": "white_render", "roof": "slate", "dress": "white_concrete",
                   "windows": "house", "shopfront": "blue_concrete"},
    # Caversham Hall (civic): red brick
    "w138758857": {"name": "Caversham Hall", "walls": "red_brick", "roof": "slate", "dress": "smooth_sandstone",
                   "windows": "tall", "band": 4},
    # Caversham Court riverside gazebo: brick-and-flint chequer below, red brick room above with leaded
    # windows, pyramid clay-tile roof with a weathervane
    "w139149993": {"name": "Caversham Court gazebo", "walls": "red_brick", "roof": "red_tile", "dress": "andesite",
                   "windows": "house", "roof_kind": "hip", "band": 2, "vane": True},
    # Reading Canoe Club boathouse on The Warren
    "w139149866": {"name": "Reading Canoe Club", "walls": "timber", "roof": "slate", "dress": None,
                   "windows": "house", "shopfront": "green_concrete"},
    # St Barnabas, Emmer Green (1924): red brick, dark plain-tile roof, big traceried west window, bellcote
    "w155061436": {"name": "St Barnabas Emmer Green", "walls": "red_brick", "roof": "dark_tile", "dress": "bricks",
                   "windows": "lancet",
                   "tower": {"size": 2, "top": "pyramid", "walls": "bricks", "dress": "bricks", "extra": 2}},
    # Our Lady and St Anne, South View Avenue: red brick with stone dressings, tall battlemented tower
    # with paired belfry lancets
    "w137356789": {"name": "Our Lady and St Anne", "walls": "red_brick", "roof": "dark_tile",
                   "dress": "smooth_sandstone", "windows": "lancet", "band": 6,
                   "tower": {"size": 4, "top": "battlement", "walls": "bricks", "dress": "smooth_sandstone",
                             "extra": 4}},
    # Caversham Methodist Church, Ardler Road: red brick, stone-capped buttresses, battlemented tower
    "w552926965": {"name": "Caversham Methodist Church", "walls": "red_brick", "roof": "dark_tile",
                   "dress": "smooth_sandstone", "windows": "lancet",
                   "tower": {"size": 3, "top": "battlement", "walls": "bricks", "dress": "bricks", "extra": 3}},
    # Fry's Island: Caversham Boat Services' white weatherboarded clubhouse with a black-and-white gable,
    # and the Island Bohemian Club
    "w32781426": {"name": "Caversham Boat Services", "walls": "white_render", "roof": "slate", "dress": "spruce_planks",
                  "windows": "house", "tudor_gable": True, "roof_kind": "gable"},
    "w32781427": {"name": "Island Bohemian Club", "walls": "white_render", "roof": "slate", "dress": None,
                  "windows": "house", "roof_kind": "gable"},
    # Caversham Wharf and Regents Riverside: yellow stock-brick riverside flats with slate roofs, turrets and
    # balconies
    "w556518929": {"name": "Caversham Wharf", "walls": "sandstone", "roof": "slate", "dress": "smooth_quartz",
                   "windows": "tall", "roof_kind": "hip", "band": 3},
    "w136161991": {"name": "Regents Riverside", "walls": "sandstone", "roof": "slate", "dress": "smooth_quartz",
                   "windows": "tall", "roof_kind": "hip", "band": 3},
    # The Victorian house at the heart of the Peppard Road school site: red brick, white stone bays and
    # balustrade, two copper-domed turrets
    "w160826605": {"name": "Peppard Road school (domed house)", "walls": "red_brick", "roof": "slate", "roof_kind": "hip",
                   "dress": "smooth_quartz", "windows": "tall", "band": 4,
                   "tower": {"size": 3, "top": "cupola", "walls": "bricks", "dress": "smooth_quartz", "extra": -2}},
    # Travellers Rest, Henley Road: dark brown tile roof, black-and-white Tudor gables and dormers, brick
    # chimneys, red parasols
    "w161702612": {"name": "Travellers Rest", "walls": "red_brick", "roof": "brown_tile", "dress": "bricks",
                   "windows": "house", "tudor_gable": True, "shopfront": "red_concrete", "roof_kind": "hip"},
    # Prince of Wales (OSM: The Last Crumb), Prospect Street: white-painted, black plinth, slate
    "w156146312": {"name": "Prince of Wales", "walls": "white_render", "roof": "slate", "dress": "black_concrete",
                   "windows": "house", "shopfront": "black_concrete", "roof_kind": "gable"},
    # Red Cow, Star Road: low red brick cottage pub, tile roof, gabled porches
    "w137733621": {"name": "Red Cow", "walls": "red_brick", "roof": "dark_tile", "dress": "bricks",
                   "windows": "house", "shopfront": "red_concrete", "roof_kind": "gable"},
    # Old Grove House, Emmer Green (St Barnabas Road): Victorian flint-and-red-brick house, three steep
    # tiled gables, tall chimneys; flint garden wall with clipped yews along the road
    "w155061715": {"name": "Old Grove House", "walls": "flint", "roof": "red_tile", "dress": "bricks",
                   "windows": "house", "band": 3, "roof_kind": "gable", "yews": True},
    # BBC Written Archives Centre, Peppard Road: low white-rendered building, slate, brick chimneys
    "w77517874": {"name": "BBC Written Archives Centre", "walls": "white_render", "roof": "slate", "dress": None,
                  "windows": "house", "roof_kind": "hip"},
    # Caversham Park (the mansion, BBC Monitoring until 2018): pale Bath stone, Corinthian colonnade on the
    # south front, balustraded parapet, three tall storeys
    "w160047105": {"name": "Caversham Park", "walls": "sandstone", "roof": "flat", "dress": "smooth_quartz",
                   "windows": "tall", "storey": 4, "parapet": "sandstone_wall", "colonnade": "south",
                   "terrace": True},
    # Emmer Green shopping parade, Milestone Way: three-storey flat-roofed red-brown brick block, flats over a
    # row of shops under a long white canopy
    "w171946174": {"name": "Emmer Green parade", "walls": "red_brick", "roof": "flat", "dress": None,
                   "windows": "house", "shopfront": "white_concrete", "canopy": "smooth_quartz_slab"},
    # Coral, Kidmore End Road corner: red brick, dark tile mansard with dormers, blue fascia
    "w160047130": {"name": "Coral (Emmer Green)", "walls": "red_brick", "roof": "dark_tile", "dress": None,
                   "windows": "house", "shopfront": "blue_concrete", "roof_kind": "hip"},
    # Kings Meadow House, King's Meadow Road (Environment Agency, whose LiDAR shaped this world): five storeys of
    # red brick, flat roof, rows of arched windows, a tall glazed bay in the middle of the front
    "w136162171": {"name": "Environment Agency (Kings Meadow House)", "walls": "red_brick", "roof": "flat",
                   "dress": None, "windows": "tall", "band": 3},
    # Reading Bridge House: the tall white concrete office tower beside it, ribbon windows
    "w77508239": {"name": "Reading Bridge House", "walls": "white_render", "roof": "flat", "dress": None,
                  "windows": "tall", "shopfront": "white_concrete"},
    # Clearwater Court, Vastern Road (Thames Water): pale stone, columns, blue glass, five storeys
    "w77508260": {"name": "Thames Water (Clearwater Court)", "walls": "sandstone", "roof": "flat",
                  "dress": "smooth_quartz", "windows": "tall", "band": 3},
    # 203-217a Peppard Road: Georgian red-brick cottage terrace, slate roof, tall chimneys
    "w163753434": {"name": "Peppard Road cottages", "walls": "red_brick", "roof": "slate", "dress": None,
                   "windows": "house", "roof_kind": "gable"},
}

TOWER_BLOCKS = {"andesite": "andesite", "bricks": "bricks"}


def is_landmark(osm_id):
    return osm_id in LANDMARKS


def tower(P, blocks, cells, fl, top_y, peak, spec, roof_full, roof_stair):
    """A square tower centred on the LiDAR peak (x, z) of size n up to top_y, with its crown."""
    px, pz = peak
    n = spec["size"]
    h0 = n // 2
    xs = range(px - h0, px - h0 + n)
    zs = range(pz - h0, pz - h0 + n)
    wall = P(spec["walls"])
    dress = P(spec["dress"])
    top = top_y + spec.get("extra", 0)
    for x in xs:
        for z in zs:
            ring = x in (xs[0], xs[-1]) or z in (zs[0], zs[-1])
            corner = x in (xs[0], xs[-1]) and z in (zs[0], zs[-1])
            for y in range(fl + 1, top + 1):
                if ring:
                    blk = dress if corner or (y - fl) % 6 == 0 else wall
                    mid = (x == xs[n // 2] or z == zs[n // 2]) and not corner
                    if mid and top - 4 <= y <= top - 2:
                        blk = P("air")                              # belfry openings
                    elif mid and (y - fl) % 6 in (2, 3) and y < top - 5:
                        blk = P("glass")
                    blocks[(x, y, z)] = blk
                else:
                    blocks[(x, y, z)] = P("air")
            if not ring:
                blocks[(x, top - 5, z)] = P("oak_planks")          # bell floor
    kind = spec["top"]
    if kind == "battlement":
        for x in xs:
            for z in zs:
                if x in (xs[0], xs[-1]) or z in (zs[0], zs[-1]):
                    blocks[(x, top + 1, z)] = dress
                    if (x + z) % 2 == 0:
                        blocks[(x, top + 2, z)] = dress
                else:
                    blocks[(x, top, z)] = P("stone_brick_slab")
        blocks[(px, top + 3, pz)] = P("lightning_rod")
    elif kind in ("spire", "pyramid"):
        steep = 2 if kind == "spire" else 1
        r = n / 2
        y = top + 1
        k = 0
        while r > 0.2:
            for x in xs:
                for z in zs:
                    if max(abs(x - (px - h0 + (n - 1) / 2)), abs(z - (pz - h0 + (n - 1) / 2))) <= r:
                        blocks[(x, y, z)] = roof_full
            y += 1
            k += 1
            if k % steep == 0:
                r -= 1
        blocks[(px, y, pz)] = P("lightning_rod")
    elif kind == "cupola":
        cu = P("oxidized_cut_copper")
        for x in xs:
            for z in zs:
                blocks[(x, top + 1, z)] = dress
        cx, cz = px, pz
        for dy, rr in ((2, 1), (3, 1), (4, 1), (5, 0)):
            for x in range(cx - rr, cx + rr + 1):
                for z in range(cz - rr, cz + rr + 1):
                    blocks[(x, top + dy, z)] = cu if (dy == 4 or rr == 0 or abs(x - cx) + abs(z - cz) == 2) else P("air")
        blocks[(cx, top + 2, cz)] = P("bell", attachment="floor", facing="north")
        blocks[(cx, top + 6, cz)] = P("lightning_rod")
        # clock faces just under the cupola
        for x, z in ((xs[0] - 1, pz), (xs[-1] + 1, pz), (px, zs[0] - 1), (px, zs[-1] + 1)):
            blocks[(x, top - 1, z)] = P("white_concrete")


def dressings(P, blocks, inside, edge, x0, z0, fl, topgrid, spec):
    """Quoins at every corner and string courses every `band` rows, in the dressing stone."""
    from scipy import ndimage
    dress = P(spec["dress"])
    corner = edge & (ndimage.convolve(inside.astype(int), np.ones((3, 3), int), mode="constant") <= 4)
    band = spec.get("band")
    zz, xx = np.nonzero(edge)
    for zl, xl in zip(zz, xx):
        for y in range(fl + 1, int(topgrid[zl, xl])):
            if corner[zl, xl] or (band and (y - fl) % band == 0):
                blocks[(x0 + xl, y, z0 + zl)] = dress


def colonnade(P, blocks, inside, x0, z0, fl, eave, side):
    """Columns standing 2 m out from the south (or other) front, with an entablature on top."""
    pillar = P("quartz_pillar", axis="y")
    beam = P("smooth_quartz")
    dz = {"south": 1, "north": -1}.get(side, 1)
    cols = np.nonzero(inside.any(axis=0))[0]
    for xl in cols:
        rows = np.nonzero(inside[:, xl])[0]
        zl = rows.max() if dz > 0 else rows.min()
        z = z0 + zl + 2 * dz
        x = x0 + xl
        for y in range(fl + 1, eave):
            if xl % 3 == 0:
                blocks[(x, y, z)] = pillar
        blocks[(x, eave, z)] = beam
        blocks[(x, eave, z - dz)] = beam
        blocks[(x, fl, z)] = P("smooth_quartz")
        blocks[(x, fl, z - dz)] = P("smooth_quartz")

# pubs that OSM has only as points: the building under the point takes this style
PUB_POINTS = {
    "The Griffin": {"walls": "red_brick", "roof": "dark_tile", "dress": "bricks", "windows": "house",
                    "shopfront": "green_concrete", "tudor_gable": True},
    "The Crown": {"walls": "white_render", "roof": "slate", "dress": "black_concrete", "windows": "house",
                  "shopfront": "black_concrete"},
    "The Clifton Arms": {"walls": "red_brick", "roof": "slate", "dress": "bricks", "windows": "house",
                         "shopfront": "blue_concrete"},
    "The Moderation": {"walls": "white_render", "roof": "slate", "dress": "black_concrete", "windows": "house",
                       "shopfront": "black_concrete"},
}


def add_pub_points(layers, buildings):
    """Maps OSM pub points onto the building they stand in, so they get a landmark style."""
    import json
    from box import E0, N1
    osm = json.load(open("build/osm.json"))
    bid = layers["building"]
    n = 0
    for nd in osm["nodes"]:
        name = nd["tags"].get("name")
        if name in PUB_POINTS and nd["tags"].get("amenity") == "pub":
            x, z = int(nd["pt"][0] - E0), int(N1 - nd["pt"][1])
            if 0 <= z < bid.shape[0] and 0 <= x < bid.shape[1] and bid[z, x]:
                b = buildings[bid[z, x]]
                LANDMARKS[b["id"]] = dict(PUB_POINTS[name], name=name, roof_kind="gable")
                n += 1
    print("pubs from OSM points:", n)
