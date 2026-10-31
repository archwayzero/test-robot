#!/usr/bin/env python3
"""Measure wall_lamp from the exported GLB and fail on any deviation from the contract. No Blender or Godot needed.

  python3 blender/models/wall_lamp/qa/check_lamp.py [--glb path] [--quiet]

Exit 0 all pass, 1 any fail. Positions are in the GLB's own space (Godot local): x right, y up, +z out of the wall.
"""
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT = ROOT / "godot/assets/wall_lamp/model/wall_lamp.glb"
EMITTER = (0.0, 0.25, 0.35)
EMITTER_TOL = 0.005
NODES = {"wall_lamp", "wall_lamp_iron", "wall_lamp_flame", "light_emitter"}
MAX_TRIS, MAX_PRIMS, MAX_TEX, MAX_MB = 1000, 2, 2048, 16


def read_glb(path):
    d = Path(path).read_bytes()
    jl = struct.unpack_from("<I", d, 12)[0]
    j = json.loads(d[20:20 + jl].decode())
    off = 20 + jl
    return j, d[off + 8:]


def accessor_vec3(j, b, idx):
    a = j["accessors"][idx]
    v = j["bufferViews"][a["bufferView"]]
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride", 12)
    return [struct.unpack_from("<3f", b, off + i * stride) for i in range(a["count"])]


def png_size(j, b, im):
    v = j["bufferViews"][im["bufferView"]]
    return struct.unpack(">II", b[v.get("byteOffset", 0) + 16:v.get("byteOffset", 0) + 24])


def trs(node):
    """Translation of a node, or None if it rotates or scales (the asset has neither)."""
    if "matrix" in node:
        return None
    if any(abs(a - b) > 1e-6 for a, b in zip(node.get("rotation", (0, 0, 0, 1)), (0, 0, 0, 1))):
        return None
    if any(abs(a - 1) > 1e-6 for a in node.get("scale", (1, 1, 1))):
        return None
    return node.get("translation", [0, 0, 0])


def run(path):
    res = []

    def check(name, ok, detail=""):
        res.append((name, bool(ok), str(detail)))

    j, b = read_glb(path)
    nodes = j.get("nodes", [])
    by = {n.get("name"): n for n in nodes}
    check("node names exact", set(by) == NODES and len(nodes) == len(NODES), sorted(by))
    if set(by) != NODES:
        return res
    roots = j["scenes"][j.get("scene", 0)]["nodes"]
    root = by["wall_lamp"]
    check("one root, wall_lamp", [nodes[r].get("name") for r in roots] == ["wall_lamp"], [nodes[r].get("name") for r in roots])
    kids = {nodes[c]["name"] for c in root.get("children", [])}
    check("children of root", kids == NODES - {"wall_lamp"}, sorted(kids))
    off = {k: trs(by[k]) for k in NODES}
    check("no rotation or scale on any node", all(v is not None for v in off.values()), off)
    if any(v is None for v in off.values()):
        return res
    check("root at origin", math.dist(off["wall_lamp"], (0, 0, 0)) < 1e-6, off["wall_lamp"])
    world = {k: [off["wall_lamp"][i] + (0 if k == "wall_lamp" else off[k][i]) for i in range(3)] for k in NODES}
    err = math.dist(world["light_emitter"], EMITTER)
    check("emitter within 5 mm", err <= EMITTER_TOL, "at (%.4f, %.4f, %.4f), error %.2f mm" % (*world["light_emitter"], err * 1000))

    tris, prims, verts = 0, 0, {}
    mats = {}
    for k in ("wall_lamp_iron", "wall_lamp_flame"):
        if "mesh" not in by[k]:
            check(k + " has a mesh", False)
            return res
        mesh_prims = j["meshes"][by[k]["mesh"]]["primitives"]
        prims += len(mesh_prims)
        mats[k] = [p.get("material") for p in mesh_prims]
        pts = []
        for p in mesh_prims:
            tris += j["accessors"][p["indices"]]["count"] // 3
            pts += [tuple(c + o for c, o in zip(v, world[k])) for v in accessor_vec3(j, b, p["attributes"]["POSITION"])]
            check(k + " has normals and UVs", "NORMAL" in p["attributes"] and "TEXCOORD_0" in p["attributes"])
        verts[k] = pts
    check("meshes only on iron and flame", sum("mesh" in n for n in nodes) == 2)
    check("triangles <= 1000", tris <= MAX_TRIS, tris)
    check("primitives <= 2", prims <= MAX_PRIMS, prims)

    it, fl = verts["wall_lamp_iron"], verts["wall_lamp_flame"]
    lo = [min(p[i] for p in it + fl) for i in range(3)]
    hi = [max(p[i] for p in it + fl) for i in range(3)]
    check("bounds", True, "x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f, size %.3f x %.3f x %.3f m"
          % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
    check("wall face at z = 0, nothing behind it", abs(lo[2]) < 0.001, "min z %.4f" % lo[2])
    plate = [p for p in it if p[2] - lo[2] < 0.001]
    px = [min(p[0] for p in plate), max(p[0] for p in plate)]
    py = [min(p[1] for p in plate), max(p[1] for p in plate)]
    check("origin at mid back plate within 5 mm", abs(sum(px) / 2) < 0.005 and abs(sum(py) / 2) < 0.005,
          "plate x %.3f..%.3f y %.3f..%.3f" % (*px, *py))
    flo = [min(p[i] for p in fl) for i in range(3)]
    fhi = [max(p[i] for p in fl) for i in range(3)]
    check("flame surrounds the emitter", all(flo[i] < world["light_emitter"][i] < fhi[i] for i in range(3)),
          "flame x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (flo[0], fhi[0], flo[1], fhi[1], flo[2], fhi[2]))

    ms = j.get("materials", [])
    check("exactly 2 materials", len(ms) == 2, [m.get("name") for m in ms])
    names = {m.get("name"): i for i, m in enumerate(ms)}
    check("each mesh its own material", mats["wall_lamp_iron"] == [names.get("wall_lamp_iron")]
          and mats["wall_lamp_flame"] == [names.get("wall_lamp_flame")], mats)
    if len(ms) == 2 and {"wall_lamp_iron", "wall_lamp_flame"} <= set(names):
        iron, flame = ms[names["wall_lamp_iron"]], ms[names["wall_lamp_flame"]]
        check("flame emissive present", max(flame.get("emissiveFactor", [0, 0, 0])) > 0 and "emissiveTexture" in flame,
              flame.get("emissiveFactor"))
        check("iron not emissive", max(iron.get("emissiveFactor", [0, 0, 0])) == 0 and "emissiveTexture" not in iron)
        check("iron is textured PBR", "baseColorTexture" in iron.get("pbrMetallicRoughness", {})
              and "metallicRoughnessTexture" in iron["pbrMetallicRoughness"] and "normalTexture" in iron)

    check("no lights", not j.get("extensions", {}).get("KHR_lights_punctual")
          and not any("KHR_lights_punctual" in n.get("extensions", {}) for n in nodes))
    ext = list(j.get("extensionsUsed", [])) + list(j.get("extensionsRequired", [])) + list(j.get("extensions", {}))
    for m in ms:
        ext += list(m.get("extensions", {}))
    check("no extensions", not ext, ext)
    check("no animations, skins or cameras", not (j.get("animations") or j.get("skins") or j.get("cameras")))

    sizes = [png_size(j, b, im) for im in j.get("images", [])]
    mb = sum(w * h * 4 * 4 / 3 for w, h in sizes) / (1024 * 1024)
    check("textures <= 2048 px, <= 16 MB uncompressed", all(max(s) <= MAX_TEX for s in sizes) and mb <= MAX_MB,
          "%s, %.2f MB" % (sizes, mb))
    return res


def main():
    path = sys.argv[sys.argv.index("--glb") + 1] if "--glb" in sys.argv else DEFAULT
    res = run(path)
    fails = [r for r in res if not r[1]]
    if "--quiet" not in sys.argv:
        for n, ok, d in res:
            print("%-4s %-44s %s" % ("ok" if ok else "FAIL", n, d))
    print("%d checks, %d failed: %s" % (len(res), len(fails), [f[0] for f in fails] or "none"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
