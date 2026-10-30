#!/usr/bin/env python3
"""Failure demonstration for check_kit.py: writes deliberately altered GLB copies under .captures/t015/bad/.

  python3 blender/models/crypt_kit/qa/make_bad_copies.py

Each copy changes exactly one thing; check_kit.py must fail on each, on the matching check.
"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "godot/assets/crypt_kit/model/crypt_kit.glb"
OUT = ROOT / ".captures/t015/bad"


def read():
    d = SRC.read_bytes()
    off, js, bin_ = 12, None, b""
    while off + 8 <= len(d):
        n, t = struct.unpack_from("<II", d, off)
        c = d[off + 8:off + 8 + n]
        if t == 0x4E4F534A:
            js = json.loads(c.decode())
        else:
            bin_ = bytearray(c)
        off += 8 + n
    return js, bin_


def write(path, js, bin_):
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    b = bytes(bin_) + b"\0" * (-len(bin_) % 4)
    total = 12 + 8 + len(j) + 8 + len(b)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(j), 0x4E4F534A) + j
                     + struct.pack("<II", len(b), 0x004E4942) + b)
    print("wrote", path)


def node(js, name):
    return next(n for n in js["nodes"] if n.get("name") == name)


def edit_positions(js, bin_, mesh, fn):
    """fn(x, y, z) -> (x, y, z) on every vertex of a mesh, in place."""
    for p in js["meshes"][mesh]["primitives"]:
        a = js["accessors"][p["attributes"]["POSITION"]]
        bv = js["bufferViews"][a["bufferView"]]
        o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        lo, hi = [1e9] * 3, [-1e9] * 3
        for i in range(a["count"]):
            v = fn(*struct.unpack_from("<3f", bin_, o + 12 * i))
            struct.pack_into("<3f", bin_, o + 12 * i, *v)
            lo = [min(q, w) for q, w in zip(lo, v)]
            hi = [max(q, w) for q, w in zip(hi, v)]
        a["min"], a["max"] = lo, hi


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    js, b = read()
    node(js, "pier")["name"] = "column"
    write(OUT / "renamed_node.glb", js, b)

    js, b = read()
    node(js, "arch")["translation"] = [0.0, 0.1, 0.0]
    write(OUT / "moved_origin.glb", js, b)

    js, b = read()   # wall collision face 1 cm off
    edit_positions(js, b, node(js, "wall-colonly")["mesh"], lambda x, y, z: (x, y, z + 0.01 if z > 0 else z))
    write(OUT / "wall_collision_off_1cm.glb", js, b)

    js, b = read()   # crouch underside 2 cm low
    m = node(js, "ceiling_crouch")["mesh"]
    edit_positions(js, b, m, lambda x, y, z: (x, y - 0.02, z))
    write(OUT / "crouch_underside_low.glb", js, b)

    js, b = read()   # vault crown 8 mm high
    edit_positions(js, b, node(js, "vault_bay")["mesh"], lambda x, y, z: (x, y + 0.008 * (y > 3.5), z))
    write(OUT / "vault_crown_high.glb", js, b)

    js, b = read()   # no collision child on floor
    n = node(js, "floor")
    n.pop("children")
    write(OUT / "floor_no_collision.glb", js, b)

    js, b = read()   # third material
    js["materials"].append({"name": "extra", "pbrMetallicRoughness": {}})
    js["meshes"][node(js, "wall")["mesh"]]["primitives"][0]["material"] = len(js["materials"]) - 1
    write(OUT / "third_material.glb", js, b)

    js, b = read()   # UV2 collapsed onto one spot of one piece: charts overlap
    p = js["meshes"][node(js, "wall")["mesh"]]["primitives"][0]
    a = js["accessors"][p["attributes"]["TEXCOORD_1"]]
    bv = js["bufferViews"][a["bufferView"]]
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    for i in range(a["count"]):
        u, v = struct.unpack_from("<2f", b, o + 8 * i)
        struct.pack_into("<2f", b, o + 8 * i, u * 0.25 + 0.3, v * 0.25 + 0.3)
    # stack the second half of the vertices on the first half
    for i in range(a["count"] // 2, a["count"]):
        u, v = struct.unpack_from("<2f", b, o + 8 * (i - a["count"] // 2))
        struct.pack_into("<2f", b, o + 8 * i, u + 0.002, v + 0.002)
    write(OUT / "uv2_overlap.glb", js, b)

    js, b = read()   # non-tileable image where a tile belongs (also pushes texture memory over budget)
    imgs = {i["name"]: i for i in js["images"]}
    imgs["stone_floor_color"]["bufferView"] = imgs["stone_ashlar_color"]["bufferView"]
    write(OUT / "floor_not_tileable.glb", js, b)


main()
