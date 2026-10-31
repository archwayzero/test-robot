#!/usr/bin/env python3
"""Show check_lamp can fail: alter copies of the real GLB's JSON under .captures/t016/bad/ and run the check on each.

  python3 blender/models/wall_lamp/qa/demo_failures.py

Exit 0 only if the real GLB passes and every copy fails on the check it was altered to break.
"""
import copy
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CHECK = Path(__file__).with_name("check_lamp.py")
GLB = ROOT / "godot/assets/wall_lamp/model/wall_lamp.glb"
BAD = ROOT / ".captures/t016/bad"


def write(path, j, b):
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 28 + len(js) + len(b)) + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(b), 0x004E4942) + b)


def node(j, name):
    return next(n for n in j["nodes"] if n["name"] == name)


def rename(j):
    node(j, "light_emitter")["name"] = "emitter"


def move_emitter(j):
    node(j, "light_emitter")["translation"][2] += 0.006


def shift_root(j):
    node(j, "wall_lamp")["translation"] = [0, 0, 0.02]


def add_light(j):
    j.setdefault("extensionsUsed", []).append("KHR_lights_punctual")
    j["extensions"] = {"KHR_lights_punctual": {"lights": [{"type": "point", "intensity": 1}]}}
    node(j, "light_emitter")["extensions"] = {"KHR_lights_punctual": {"light": 0}}


def extension(j):
    j["materials"][0].setdefault("extensions", {})["KHR_materials_emissive_strength"] = {"emissiveStrength": 5}
    j["extensionsUsed"] = ["KHR_materials_emissive_strength"]


def no_emissive(j):
    for m in j["materials"]:
        m.pop("emissiveTexture", None)
        m.pop("emissiveFactor", None)


def extra_material(j):
    j["materials"].append({"name": "third"})


def extra_primitive(j):
    j["meshes"][0]["primitives"].append(copy.deepcopy(j["meshes"][0]["primitives"][0]))


def over_budget(j):
    mesh = node(j, "wall_lamp_iron")["mesh"]
    prim = j["meshes"][mesh]["primitives"][0]
    j["accessors"][prim["indices"]]["count"] = 3003


def scale_node(j):
    node(j, "wall_lamp_iron")["scale"] = [1.2, 1.2, 1.2]


def flipped_to_wall(j):
    node(j, "wall_lamp")["rotation"] = [0, 1, 0, 0]


CASES = [("renamed_node", rename, "node names exact"), ("emitter_6mm_off", move_emitter, "emitter within 5 mm"),
         ("root_moved", shift_root, "root at origin"), ("has_light", add_light, "no lights"),
         ("has_extension", extension, "no extensions"), ("no_emissive", no_emissive, "flame emissive present"),
         ("third_material", extra_material, "exactly 2 materials"), ("third_primitive", extra_primitive, "primitives <= 2"),
         ("over_budget", over_budget, "triangles <= 1000"), ("scaled_node", scale_node, "no rotation or scale on any node"),
         ("turned_180", flipped_to_wall, "no rotation or scale on any node")]


def main():
    BAD.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(CHECK.parent))
    from check_lamp import read_glb
    j0, b = read_glb(GLB)
    r = subprocess.run([sys.executable, str(CHECK), "--quiet"], capture_output=True, text=True)
    print("real GLB  ", r.stdout.strip())
    bad = r.returncode != 0
    for name, alter, expect in CASES:
        j = copy.deepcopy(j0)
        alter(j)
        p = BAD / (name + ".glb")
        write(p, j, b)
        r = subprocess.run([sys.executable, str(CHECK), "--quiet", "--glb", str(p)], capture_output=True, text=True)
        out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]
        hit = r.returncode == 1 and expect in out
        bad |= not hit
        print("%-4s %-18s %s" % ("ok" if hit else "MISS", name, out))
    sys.exit(1 if bad else 0)


main()
