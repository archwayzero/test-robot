#!/usr/bin/env python3
"""crypt_kit pipeline: build, export, check, one heavy job at a time, each through the memory guard.

  python3 blender/models/crypt_kit/run_pipeline.py [--import]

--import also runs the Godot import that produces the .import files and extracted textures beside the GLB, then applies
VRAM compression to the extracted textures and imports again (see import_settings.py). Stops at the first failing step.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KIT = "blender/models/crypt_kit"
GLB = "godot/assets/crypt_kit/model/crypt_kit.glb"
GUARD = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--"]
BL = ["blender", "-b", "--python-exit-code", "1"]
STEPS = [
    BL + ["--factory-startup", "-P", f"{KIT}/build.py"],
    BL + [f"{KIT}/crypt_kit_model.blend", "-P", "tools/blender/export_gltf.py", "--", "--out", GLB, "--no-anim"],
    BL + ["--factory-startup", "-P", f"{KIT}/qa/check_kit.py"],
]
# Three imports: a texture the GLB re-extracts can come back from the second one still lossless (seen on stone_ashlar_color),
# hence the last one and the --verify.
GODOT = ["godot", "--headless", "--path", "godot", "--import"]
SET = ["python3", f"{KIT}/import_settings.py"]
IMPORT = [GODOT, SET, GODOT, SET, GODOT, SET + ["--verify"]]


def main():
    steps = STEPS + (IMPORT if "--import" in sys.argv else [])
    for step in steps:
        cmd = step if step[0] == "python3" else GUARD + step
        print("==", " ".join(cmd), flush=True)
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode:
            sys.exit(r.returncode)


main()
