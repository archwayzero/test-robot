#!/usr/bin/env python3
"""wall_lamp pipeline: build, export, check, then a clean Godot import. One heavy job at a time, each through the memory guard.

  python3 blender/models/wall_lamp/run_pipeline.py [--import]

--import deletes the gitignored godot/.godot only, imports (writes the extracted textures with default settings), applies VRAM
compression (import_settings.py), imports again (compresses them) and verifies ASTC from the .ctex headers.

The import scans the whole project, and an unimported GLB of another asset left in the tree (T015's crypt_kit.glb, untracked on
this branch) gets .import files and extracted textures beside it. Files under godot/assets/crypt_kit that did not exist before
the run are removed afterwards, so the import leaves that folder exactly as it found it.
Stops at the first failing step.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAMP = "blender/models/wall_lamp"
GLB = "godot/assets/wall_lamp/model/wall_lamp.glb"
GUARD = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--"]
BL = ["blender", "-b", "--python-exit-code", "1"]
STEPS = [
    BL + ["--factory-startup", "-P", f"{LAMP}/build.py"],
    BL + [f"{LAMP}/wall_lamp_model.blend", "-P", "tools/blender/export_gltf.py", "--", "--out", GLB, "--no-anim"],
]
CHECK = ["python3", f"{LAMP}/qa/check_lamp.py"]
CACHE = ROOT / "godot/.godot"
GODOT = ["godot", "--headless", "--path", "godot", "--import"]
SET = ["python3", f"{LAMP}/import_settings.py"]
IMPORT = [GODOT, SET, GODOT, SET + ["--verify"]]
OTHERS = ROOT / "godot/assets/crypt_kit"


def main():
    for step in STEPS:
        run(step)
    if (ROOT / CHECK[1]).exists():
        run(CHECK)
    if "--import" in sys.argv:
        before = set(OTHERS.rglob("*"))
        print("== delete", CACHE, flush=True)
        shutil.rmtree(CACHE, ignore_errors=True)
        try:
            for step in IMPORT:
                run(step)
        finally:
            for f in sorted(set(OTHERS.rglob("*")) - before):
                print("== remove import by-product", f.relative_to(ROOT), flush=True)
                f.unlink()


def run(step):
    cmd = step if step[0] == "python3" else GUARD + step
    print("==", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        sys.exit(r.returncode)


main()
