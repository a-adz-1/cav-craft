#!/usr/bin/env python3
"""Screenshots the built world in the user's own Minecraft (Prism instance), for checking by eye.

    .venv/bin/python tools/mc_view.py world/Cavcraft out.png x y z yaw pitch

Copies the world into the instance's saves as Cavcraft-test with the player placed (spectator) at x y z
looking yaw/pitch, launches it, waits for the chunks to draw, screenshots the game's window, then closes the game. Yaw: 0 south, 90 west, 180 north, -90 east.
"""
import gzip
import os
import shutil
import subprocess
import sys
import time

import anvil

INST = os.path.expanduser("~/.local/share/PrismLauncher/instances/1.21.11 Paper")
SAVE = os.path.join(INST, "minecraft/saves/Cavcraft-test")
LOG = os.path.join(INST, "minecraft/logs/latest.log")

world, out = sys.argv[1], sys.argv[2]
x, y, z, yaw, pitch = map(float, sys.argv[3:8])
wait = float(sys.argv[8]) if len(sys.argv) > 8 else 25

shutil.rmtree(SAVE, ignore_errors=True)
shutil.copytree(world, SAVE)
lvl = anvil.read_nbt(gzip.open(os.path.join(SAVE, "level.dat")).read())["Data"]
anvil.write_level_dat(os.path.join(SAVE, "level.dat"), "Cavcraft-test", (lvl["SpawnX"], lvl["SpawnY"], lvl["SpawnZ"]),
                      (lvl["BorderCenterX"], lvl["BorderCenterZ"]), lvl["BorderSize"], player=(x, y, z, yaw, pitch))
start = time.time()
subprocess.Popen(["prismlauncher", "--launch", "1.21.11 Paper", "--world", "Cavcraft-test"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while time.time() - start < 180:
    time.sleep(2)
    if os.path.exists(LOG) and os.path.getmtime(LOG) > start and "joined the game" in open(LOG, errors="ignore").read():
        break
else:
    sys.exit("game never joined the world")
time.sleep(wait)
raw = out + ".full.png"
subprocess.run(["spectacle", "-b", "-n", "-a", "-o", raw], check=True)   # the game's window only
subprocess.run(["pkill", "-f", "minecraft-1.21.11-client"])
from PIL import Image
im = Image.open(raw)
im.save(out)
os.remove(raw)
errs = [l for l in open(LOG, errors="ignore") if ("ERROR" in l or "Exception" in l) and "text2speech" not in l
        and "Narrator" not in l and "DragonFight" not in l]
print("log errors:", len(errs))
for l in errs[:10]:
    print(l.rstrip()[:200])
