#!/usr/bin/env python3
"""Screenshots the built world in the user's own Minecraft (Prism instance), for checking by eye.

    .venv/bin/python tools/mc_view.py world/Cavcraft out.png x y z yaw pitch

Copies the world into the instance's saves as Cavcraft-test with the player placed (spectator) at x y z
looking yaw/pitch, launches it, waits for the chunks to draw, screenshots the game's window, then closes the game. Yaw: 0 south, 90 west, 180 north, -90 east.
"""
import gzip
import os
import shutil
import signal
import subprocess
import sys
import time

import anvil

INST = os.path.expanduser("~/.local/share/PrismLauncher/instances/1.21.11 Paper")
SAVE = os.path.join(INST, "minecraft/saves/Cavcraft-test")
LOG = os.path.join(INST, "minecraft/logs/latest.log")
GAME = r"^/\S*/java .*minecraft-1\.21\.11-client"   # the game itself, not shells whose text mentions it

def headless_ok():
    return subprocess.run(["pgrep", "-x", "prismlauncher"], capture_output=True).returncode != 0 and \
        subprocess.run(["pgrep", "-f", GAME], capture_output=True).returncode != 0


world, out = sys.argv[1], sys.argv[2]
x, y, z, yaw, pitch = map(float, sys.argv[3:8])
wait = float(sys.argv[8]) if len(sys.argv) > 8 else 25
daytime = int(sys.argv[9]) if len(sys.argv) > 9 else None   # e.g. 18000 for midnight

if not headless_ok():
    sys.exit("the user's own Prism/Minecraft is open: not starting a game (it would be closed afterwards)")
while subprocess.run(["pgrep", "-f", GAME], capture_output=True).returncode == 0:
    time.sleep(1)   # the last game is still closing
shutil.rmtree(SAVE, ignore_errors=True)
shutil.copytree(world, SAVE)
lvl = anvil.read_nbt(gzip.open(os.path.join(SAVE, "level.dat")).read())["Data"]
anvil.write_level_dat(os.path.join(SAVE, "level.dat"), "Cavcraft-test", (lvl["SpawnX"], lvl["SpawnY"], lvl["SpawnZ"]),
                      (lvl["BorderCenterX"], lvl["BorderCenterZ"]), lvl["BorderSize"], player=(x, y, z, yaw, pitch))
if daytime is not None:
    anvil.write_level_dat(os.path.join(SAVE, "level.dat"), "Cavcraft-test", (lvl["SpawnX"], lvl["SpawnY"], lvl["SpawnZ"]),
                          (lvl["BorderCenterX"], lvl["BorderCenterZ"]), lvl["BorderSize"], player=(x, y, z, yaw, pitch),
                          daytime=daytime)
start = time.time()
# like Splitwater's and Fortress United's tools/headless-run.sh: inside a headless gamescope the game renders with
# the PC locked (a normal window stops drawing then). Prism only allows one copy, so that works only when the
# user's own Prism isn't open; otherwise fall back to a normal window and a desktop screenshot.
headless = subprocess.run(["pgrep", "-x", "prismlauncher"], capture_output=True).returncode != 0
launch = ["prismlauncher", "--launch", "1.21.11 Paper", "--world", "Cavcraft-test"]
if headless:
    launch = ["gamescope", "--backend", "headless", "-W", "1600", "-H", "900", "--"] + launch
gs = subprocess.Popen(launch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def close():
    subprocess.run(["pkill", "-f", GAME])
    if headless:
        time.sleep(3)
        os.killpg(gs.pid, signal.SIGTERM)   # gamescope, the Prism inside it and anything else it started
while time.time() - start < 180:
    time.sleep(2)
    if os.path.exists(LOG) and os.path.getmtime(LOG) > start and "joined the game" in open(LOG, errors="ignore").read():
        break
else:
    close()
    sys.exit("game never joined the world")
time.sleep(wait)
raw = os.path.abspath(out + ".full.png")
if headless:
    # the session's display name, from the game's own environment (gamescope sets it for its children)
    pid = subprocess.run(["pgrep", "-f", GAME], capture_output=True, text=True).stdout.split()[0]
    env = dict(v.split("=", 1) for v in open(f"/proc/{pid}/environ").read().split("\0") if "=" in v)
    subprocess.run(["gamescopectl", "screenshot", raw],
                   env={**os.environ, "GAMESCOPE_WAYLAND_DISPLAY": env["GAMESCOPE_WAYLAND_DISPLAY"]},
                   capture_output=True)
    for _ in range(20):
        if os.path.exists(raw):
            break
        time.sleep(0.5)
else:
    subprocess.run(["spectacle", "-b", "-n", "-a", "-o", raw], check=True)   # the game's window only
close()
from PIL import Image
im = Image.open(raw)
im.save(out)
os.remove(raw)
errs = [l for l in open(LOG, errors="ignore") if ("ERROR" in l or "Exception" in l) and "text2speech" not in l
        and "Narrator" not in l and "DragonFight" not in l]
print("log errors:", len(errs))
for l in errs[:10]:
    print(l.rstrip()[:200])
