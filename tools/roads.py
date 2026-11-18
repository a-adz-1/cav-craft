"""Road shapes: bends rounded off and clean block edges, shared by layers (the road surface) and features
(lines painted along it)."""
import numpy as np
from PIL import Image, ImageDraw

# the drive from Upper Woodcote Road down to The Heights Primary School: a proper two-way road with pavements
SCHOOL_ROADS = {"w37000897": 6}
# The Heights Primary School forecourt, laid out from the aerial photo and squared to the grid like the school:
# the drive runs on into an aisle with the staff car park to the west and the pavilion car park to the east; a
# zebra leads from the drive's pavement to a paved plaza at the school gate, and a 4 m path runs on south
# between the school fence and the playing field. Inclusive boxes (x0, x1, z0, z1) of a surface class.
HEIGHTS_CLEAR = [(1798, 1915, 2349, 2385),         # mapped car park, aisles and paths in here are replaced
                 (1763, 1829, 2415, 2441),         # the field path cut across the squared school grounds
                 (1860, 1920, 2376, 2460)]         # the tennis club, squared up below
HEIGHTS_BOX = HEIGHTS_CLEAR[0]
HEIGHTS_TENNIS = (1871, 1908, 2383, 2450)         # four courts, two by two, in a red surround
HEIGHTS_SITE = [
    ("minor_road", 1862, 1867, 2350, 2377), ("minor_road", 1801, 1867, 2362, 2367),
    ("minor_road", 1862, 1897, 2371, 2376),
    ("parking", 1802, 1838, 2357, 2361), ("parking", 1802, 1838, 2368, 2372), ("parking", 1870, 1895, 2366, 2370),
    ("footway", 1858, 1861, 2350, 2361), ("footway", 1841, 1861, 2368, 2380), ("footway", 1829, 1841, 2376, 2381),
    ("footway", 1830, 1833, 2381, 2449), ("footway", 1759, 1833, 2442, 2443), ("footway", 1759, 1762, 2428, 2443),
    ("tennis",) + HEIGHTS_TENNIS,
]
HEIGHTS_BAYS = [(1802, 1838, 2357, 2361, 1), (1802, 1838, 2368, 2372, -1), (1870, 1895, 2366, 2370, 1)]  # nose dz
HEIGHTS_ZEBRA = (1857, 1859, 2362, 2367)
HEIGHTS_SKIP = {"w450242573", "w1266297624"}      # the mapped aisle loop and the thin diagonal path they replace


def smooth(pts, n=2):
    """Chaikin corner cutting: each kink in the mapped centre line becomes a short curve. Ends stay put
    (a closed ring, like a roundabout, is rounded all the way round)."""
    p = np.asarray(pts, float)
    if len(p) < 3:
        return p
    closed = np.allclose(p[0], p[-1])
    for _ in range(n):
        a, b = p[:-1], p[1:]
        q = np.empty((2 * len(a), 2))
        q[0::2], q[1::2] = 0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b
        p = np.vstack([q, q[:1]]) if closed else np.vstack([p[:1], q, p[-1:]])
    return p


def stroke(pts, w, ss=4):
    """Cells covered by a line w wide through pts (cell coordinates), drawn 4 times finer and kept where at
    least half the cell is covered, with round ends and joins: even edges at any angle. Yields (z0, x0, mask)
    pieces."""
    p = np.asarray(pts, float)
    for i in range(0, len(p) - 1, 40):                      # long roads in pieces, to keep the pictures small
        q = p[i:i + 41]
        lo = np.floor(q.min(0) - w / 2 - 1).astype(int)
        size = np.ceil(q.max(0) + w / 2 + 1).astype(int) - lo
        im = Image.new("L", (int(size[0]) * ss, int(size[1]) * ss), 0)
        d = ImageDraw.Draw(im)
        s = [tuple(v) for v in (q - lo) * ss]
        d.line(s, fill=255, width=int(round(w * ss)))
        r = w * ss / 2
        for x, y in s:
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        m = np.asarray(im.resize((int(size[0]), int(size[1])), Image.BOX)) >= 128
        yield int(lo[1]), int(lo[0]), m


def paint(a, pts, w, value, keep=None):
    """Sets the stroke's cells of array a to value (inside the array; not where keep is set)."""
    H, W = a.shape
    for z0, x0, m in stroke(pts, w):
        za, zb, xa, xb = max(z0, 0), min(z0 + m.shape[0], H), max(x0, 0), min(x0 + m.shape[1], W)
        if za >= zb or xa >= xb:
            continue
        m = m[za - z0:zb - z0, xa - x0:xb - x0]
        if keep is not None:
            m = m & ~keep[za:zb, xa:xb]
        a[za:zb, xa:xb][m] = value


if __name__ == "__main__":
    a = np.zeros((40, 40), np.uint8)
    paint(a, [(5, 5), (34, 30)], 6, 1)                       # a diagonal 6 wide: every row 6 to 9 cells across
    rows = a[10:26].sum(1)
    assert rows.min() >= 6 and rows.max() <= 9, rows
    c = smooth([(0, 0), (10, 0), (10, 10)])
    assert np.allclose(c[0], (0, 0)) and np.allclose(c[-1], (10, 10)) and len(c) > 6
    print("roads ok")
