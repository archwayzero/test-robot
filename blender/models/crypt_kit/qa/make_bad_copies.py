"""Failure demonstration for check_kit.py: writes deliberately altered GLB copies under .captures/t015/bad/.

  python3 tools/qa/memguard.py -- blender -b --factory-startup -P blender/models/crypt_kit/qa/make_bad_copies.py

Each copy changes exactly one thing; check_kit.py must fail on each, on the matching check. Runs in Blender because one copy
re-encodes a texture.
"""
import json
import os
import struct
from pathlib import Path

import bpy
import numpy as np

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


def replace_image(js, b, name, fn):
    """Decode a GLB image, apply fn to its h x w x 3 array (row 0 = top), put the re-encoded PNG at the end of the buffer."""
    im = next(i for i in js["images"] if i["name"] == name)
    bv = js["bufferViews"][im["bufferView"]]
    tmp = str(OUT / "_tmp.png")
    Path(tmp).write_bytes(bytes(b[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]))
    src = bpy.data.images.load(tmp)
    src.colorspace_settings.name = "Non-Color"
    w, h = src.size
    px = np.empty(w * h * 4, "f4")
    src.pixels.foreach_get(px)
    bpy.data.images.remove(src)
    a = np.flipud(px.reshape(h, w, 4)).copy()
    a[..., :3] = fn(a[..., :3])
    out = bpy.data.images.new("o", w, h, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    out.pixels.foreach_set(np.flipud(np.clip(a, 0, 1)).ravel())
    out.filepath_raw, out.file_format = tmp, "PNG"
    out.save()
    bpy.data.images.remove(out)
    data = Path(tmp).read_bytes()
    os.remove(tmp)
    b.extend(b"\0" * (-len(b) % 4))
    bv["byteOffset"], bv["byteLength"] = len(b), len(data)
    b.extend(data)
    js["buffers"][0]["byteLength"] = len(b) + (-len(b) % 4)


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

    js, b = read()   # old 3.9 crown: web squashed, ring flush at the crown (fails relief and crown)
    edit_positions(js, b, node(js, "vault_bay")["mesh"], lambda x, y, z: (x, 2.2 + (y - 2.2) * 1.702 / 1.948, z))
    write(OUT / "web_flush_crown.glb", js, b)

    js, b = read()   # crown correct, haunches sunk 22 cm: ring is painted on at the haunch (fails relief only)
    edit_positions(js, b, node(js, "vault_bay")["mesh"],
                   lambda x, y, z: (x, y - 0.22 * max(0.0, 1.0 - abs(y - 3.45) / 0.5), z))
    write(OUT / "web_sunk_haunch.glb", js, b)

    js, b = read()   # wall top back at the old 3.9
    edit_positions(js, b, node(js, "wall")["mesh"], lambda x, y, z: (x, min(y, 3.9), z))
    write(OUT / "wall_top_old.glb", js, b)

    js, b = read()   # one extra draw call
    m = js["meshes"][node(js, "floor")["mesh"]]["primitives"]
    m.append(dict(m[0]))
    write(OUT / "extra_draw_call.glb", js, b)

    js, b = read()   # height soiling lost
    for n in ("wall", "pier"):
        js["meshes"][node(js, n)["mesh"]]["primitives"][0]["attributes"].pop("COLOR_0")
    write(OUT / "no_soiling.glb", js, b)

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

    js, b = read()   # ashlar seam broken: band A brightens by 16/255 towards its bottom, a step at the wrap that the old p90 test missed
    atl = json.loads((SRC.parents[4] / "blender/models/crypt_kit/atlas.json").read_text())
    r0, r1 = atl["band_a_rows"]

    def ramp(a):
        n = (r1 - r0) // 8
        a[r1 - n:r1] += (16 / 255) * np.linspace(0, 1, n)[:, None, None]
        return a
    replace_image(js, b, "stone_ashlar_color", ramp)
    write(OUT / "ashlar_seam_broken.glb", js, b)

    js, b = read()   # the groin no longer lands where the assembler rules say: webs dropped 0.3 m at the corners
    edit_positions(js, b, node(js, "vault_bay")["mesh"],
                   lambda x, y, z: (x, y - 0.3 * (abs(x) > 1.6 and abs(z) > 1.6 and y > 2.3), z))
    write(OUT / "groin_landing_low.glb", js, b)

    js, b = read()   # rubble flattened to one plane: the old warped surface failing again
    edit_positions(js, b, node(js, "ceiling_crouch")["mesh"], lambda x, y, z: (x, 1.3 if y < 1.8 else y, z))
    write(OUT / "rubble_flat.glb", js, b)

    js, b = read()   # pier sunk back behind the wall
    edit_positions(js, b, node(js, "pier")["mesh"],
                   lambda x, y, z: (x * 0.995 if y < 1.89 else x, y, z * 0.995 if y < 1.89 else z))
    write(OUT / "pier_behind_wall.glb", js, b)

    js, b = read()   # pier collision follows the 2 mm proud shaft: it must stay exactly 0.6, or capsules catch on wall lines
    edit_positions(js, b, node(js, "pier-colonly")["mesh"], lambda x, y, z: (x * 1.0067, y, z * 1.0067))
    write(OUT / "pier_collision_wide.glb", js, b)

    js, b = read()   # non-tileable image where a tile belongs (also pushes texture memory over budget)
    imgs = {i["name"]: i for i in js["images"]}
    imgs["stone_floor_color"]["bufferView"] = imgs["stone_ashlar_color"]["bufferView"]
    write(OUT / "floor_not_tileable.glb", js, b)


main()
