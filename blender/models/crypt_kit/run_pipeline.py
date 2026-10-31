#!/usr/bin/env python3
"""crypt_kit pipeline: build, export, check, one heavy job at a time, each through the memory guard.

  python3 blender/models/crypt_kit/run_pipeline.py [--import] [--maps <folder>]

--maps uses the replacement maps in that folder (MAPS.md). --import also runs the Godot import that produces the .import files
and extracted textures beside the GLB, then applies VRAM compression to the extracted textures and imports again (see
import_settings.py). Stops at the first failing step.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KIT = "blender/models/crypt_kit"
GLB = "godot/assets/crypt_kit/model/crypt_kit.glb"
GUARD = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--"]
BL = ["blender", "-b", "--python-exit-code", "1"]
MAPS = sys.argv[sys.argv.index("--maps") + 1:sys.argv.index("--maps") + 2] if "--maps" in sys.argv else []
STEPS = [
    BL + ["--factory-startup", "-P", f"{KIT}/build.py"] + (["--", "--maps", MAPS[0]] if MAPS else []),
    BL + [f"{KIT}/crypt_kit_model.blend", "-P", "tools/blender/export_gltf.py", "--", "--out", GLB, "--no-anim"],
    BL + ["--factory-startup", "-P", f"{KIT}/qa/check_kit.py"],
]
# Two imports from a clean cache. The first has no extracted textures to configure: it only writes them and their .import files
# with default settings. The second, after import_settings.py, compresses them. A third import does not help if the cache is
# stale: a texture whose md5 it has already recorded can stay lossless however often Godot runs, so the gitignored cache is
# deleted first (nothing else under godot/ is touched). --verify then reads the .ctex headers, the real result.
CACHE = ROOT / "godot/.godot"
GODOT = ["godot", "--headless", "--path", "godot", "--import"]
SET = ["python3", f"{KIT}/import_settings.py"]
IMPORT = [GODOT, SET, GODOT, SET + ["--verify"]]


def main():
    for step in STEPS:
        run(step)
    if "--import" in sys.argv:
        print("== delete", CACHE, flush=True)
        shutil.rmtree(CACHE, ignore_errors=True)
        for step in IMPORT:
            run(step)


def run(step):
    cmd = step if step[0] == "python3" else GUARD + step
    print("==", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        sys.exit(r.returncode)


main()
