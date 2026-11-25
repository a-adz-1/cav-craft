"""Fresh viewpoints for the streets the survey rated low: points along the street away from the old views,
looking at the frontages both sides. Writes 6_low_a/b/c/views.tsv."""
import csv, glob, json, math, os, re
from pyproj import Transformer
T = Transformer.from_crs(27700, 4326, always_xy=True)
TB = Transformer.from_crs(4326, 27700, always_xy=True)
SV = ".downloads/ref/sv"
low, old = [], {}
for f in sorted(glob.glob(SV + "/[0-5]_*/result.json")):
    for k, e in json.load(open(f)).items():
        if e.get("confidence") == "low" and k not in low:
            low.append(k)
    for r in csv.DictReader(open(os.path.dirname(f) + "/views.tsv"), delimiter="\t"):
        m = re.search(r"viewpoint=([\d.-]+),([\d.-]+)", r["url"])
        old.setdefault(r["street"], []).append(TB.transform(float(m[2]), float(m[1])))
lines = {}
for l in json.load(open("build/osm.json"))["lines"]:
    t = l["tags"]
    if t.get("highway") and t.get("name") in low:
        lines.setdefault(t["name"], []).append(l["pts"])
rows = []
for s in low:
    pts = []
    for p in lines.get(s, []):
        for (ax, ay), (bx, by) in zip(p, p[1:]):
            L = math.hypot(bx - ax, by - ay)
            for k in range(int(L // 20) + 1):          # every 20 m along each segment
                t = k * 20 / max(L, 1)
                pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, math.degrees(math.atan2(bx - ax, by - ay))))
    # farthest from the old views first, then from each other; 3 points per street
    pick = []
    for _ in range(3):
        far = lambda q: min([math.hypot(q[0] - o[0], q[1] - o[1]) for o in old.get(s, []) + [(c[0], c[1]) for c in pick]] or [1e9])
        cand = [q for q in pts if far(q) > 18]
        if not cand:
            break
        pick.append(max(cand, key=far))
    for i, (x, y, brg) in enumerate(pick):
        lon, lat = T.transform(x, y)
        for side in (90, 270):                         # look square at each side's houses
            h = int((brg + side) % 360)
            rows.append((s, f"n{i}_{h:03d}", f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lon:.6f}&heading={h}&pitch=5&fov=90"))
streets = list(dict.fromkeys(r[0] for r in rows))
for j, name in enumerate("abc"):
    d = f"{SV}/6_low_{name}"
    os.makedirs(d + "/img", exist_ok=True)
    mine = streets[j::3]
    with open(d + "/views.tsv", "w") as f:
        f.write("street\tview\turl\n")
        for r in rows:
            if r[0] in mine:
                f.write("\t".join(r) + "\n")
    print(d, len(mine), "streets")
print("low:", len(low), "with new views:", len(streets))
