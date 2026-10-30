"""T015 measured targets 1-4, re-measured from the exported GLB only (never from the .blend).

  python3 tools/qa/memguard.py -- blender -b --factory-startup --python-exit-code 1 \
      -P blender/models/crypt_kit/qa/check_kit.py -- [--glb path] [--json out.json] [--no-exit-code]

Blender is only used as a Python with numpy and an image decoder. Exit code 1 when any check fails.
Coordinates below are glTF (Y up); every piece is measured in its node's local space after checking that the local
transform is identity.
"""
import json
import os
import struct
import sys
import tempfile

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


GLB = arg("--glb", os.path.join(ROOT, "godot/assets/crypt_kit/model/crypt_kit.glb"))
ATLAS = json.load(open(os.path.join(HERE, "..", "atlas.json")))
TOL = 0.005       # target 1: +-5 mm
EXACT = 1e-5      # "exact" collision planes: float precision of the file
PIECES = ["floor", "wall", "pier", "arch", "vault_bay", "ceiling_crouch", "ceiling_crawl"]
GUIDE = {"floor": 200, "wall": 400, "pier": 300, "arch": 800, "vault_bay": 1500, "ceiling_crouch": 1200,
         "ceiling_crawl": 1200}
TOTAL_TRIS = 21000
MAX_TEX = 2048
MAX_MEM_MB = 64.0
SEAM_MAX = 1.5    # edge-seam ratio, see seam()
LM_RES = 1024

results = []


def rec(group, name, ok, detail=""):
    results.append({"group": group, "check": name, "ok": bool(ok), "detail": str(detail)})


def near(group, name, value, want, tol=TOL):
    rec(group, name, abs(value - want) <= tol, "%.4f (want %.3f +-%g)" % (value, want, tol))


def read_glb(path):
    d = open(path, "rb").read()
    off, js, bin_ = 12, None, b""
    while off + 8 <= len(d):
        n, t = struct.unpack_from("<II", d, off)
        c = d[off + 8:off + 8 + n]
        if t == 0x4E4F534A:
            js = json.loads(c.decode())
        elif t == 0x004E4942:
            bin_ = c
        off += 8 + n
    return js, bin_


COMP = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def accessor(g, b, i):
    a = g["accessors"][i]
    bv = g["bufferViews"][a["bufferView"]]
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    n = NC[a["type"]]
    dt = np.dtype(COMP[a["componentType"]])
    stride = bv.get("byteStride", n * dt.itemsize)
    if stride == n * dt.itemsize:
        arr = np.frombuffer(b, dt, a["count"] * n, o)
    else:
        arr = np.vstack([np.frombuffer(b, dt, n, o + k * stride) for k in range(a["count"])]).ravel()
    return arr.reshape(-1, n) if n > 1 else arr


def mesh_data(g, b, mesh_i):
    pos, tris, uv1, uv2, mats = [], [], [], [], []
    base = 0
    for p in g["meshes"][mesh_i]["primitives"]:
        a = p["attributes"]
        pp = accessor(g, b, a["POSITION"]).astype(float)
        idx = accessor(g, b, p["indices"]).astype(int).reshape(-1, 3)
        pos.append(pp)
        tris.append(idx + base)
        base += len(pp)
        if "TEXCOORD_0" in a:
            uv1.append(accessor(g, b, a["TEXCOORD_0"]).astype(float))
        if "TEXCOORD_1" in a:
            uv2.append(accessor(g, b, a["TEXCOORD_1"]).astype(float))
        mats.append(p.get("material"))
    return {"pos": np.vstack(pos), "tris": np.vstack(tris), "uv1": np.vstack(uv1) if uv1 else None,
            "uv2": np.vstack(uv2) if uv2 else None, "mats": mats}


def identity(n):
    t = n.get("translation", [0, 0, 0])
    r = n.get("rotation", [0, 0, 0, 1])
    s = n.get("scale", [1, 1, 1])
    return "matrix" not in n and max(abs(x) for x in t) < 1e-6 and max(abs(x - y) for x, y in zip(r, [0, 0, 0, 1])) < 1e-6 \
        and max(abs(x - 1) for x in s) < 1e-6


def check_nodes(g, b):
    nodes = g["nodes"]
    roots = [nodes[i] for i in g["scenes"][g.get("scene", 0)]["nodes"]]
    names = [n.get("name") for n in roots]
    rec("2 nodes", "exactly the seven root nodes", sorted(names) == sorted(PIECES), names)
    vis, col = {}, {}
    for r in roots:
        nm = r.get("name")
        rec("2 nodes", "%s origin/transform identity" % nm, identity(r))
        kids = [nodes[i] for i in r.get("children", [])]
        cn = [k for k in kids if k.get("name", "").endswith("-colonly")]
        rec("2 nodes", "%s has a -colonly child" % nm, len(cn) >= 1 and "mesh" in cn[0], [k.get("name") for k in kids])
        if "mesh" in r:
            vis[nm] = mesh_data(g, b, r["mesh"])
        if cn and "mesh" in cn[0]:
            rec("2 nodes", "%s collision transform identity" % nm, identity(cn[0]))
            col[nm] = mesh_data(g, b, cn[0]["mesh"])
            rec("2 nodes", "%s collision has no material" % nm, all(m is None for m in col[nm]["mats"]))
    return vis, col


def bbox(p):
    return p.min(0), p.max(0)


def faces_at(c, axis, value):
    """Area of collision triangles lying exactly in the plane axis=value."""
    t = c["pos"][c["tris"]]
    on = np.all(np.abs(t[:, :, axis] - value) <= EXACT, axis=1)
    e1, e2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    return 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)[on].sum()


def check_dims(vis, col):
    G = "1 dims"
    d = {}
    if "floor" in vis:
        lo, hi = bbox(vis["floor"]["pos"])
        near(G, "floor visual top y", hi[1], 0.0)
        near(G, "floor thickness", hi[1] - lo[1], 0.2)
        near(G, "floor size x", hi[0] - lo[0], 4.0)
        near(G, "floor size z", hi[2] - lo[2], 4.0)
        near(G, "floor centred x", (hi[0] + lo[0]) / 2, 0.0)
    if "floor" in col:
        lo, hi = bbox(col["floor"]["pos"])
        rec(G, "floor collision top exactly y=0", abs(hi[1]) <= EXACT, "%.7f" % hi[1])
        a = faces_at(col["floor"], 1, 0.0)
        rec(G, "floor collision plane y=0 area 16", abs(a - 16) < 1e-3, "%.3f" % a)
    if "wall" in vis:
        lo, hi = bbox(vis["wall"]["pos"])
        near(G, "wall length", hi[0] - lo[0], 4.0)
        near(G, "wall thickness", hi[2] - lo[2], 0.6)
        near(G, "wall bottom", lo[1], 0.0)
        near(G, "wall top", hi[1], 3.9)
    if "wall" in col:
        lo, hi = bbox(col["wall"]["pos"])
        for s, v in ((-1, lo[2]), (1, hi[2])):
            rec(G, "wall collision face exactly z=%+.1f" % (s * 0.3), abs(v - s * 0.3) <= EXACT, "%.7f" % v)
            a = faces_at(col["wall"], 2, s * 0.3)
            rec(G, "wall collision plane z=%+.1f area 15.6" % (s * 0.3), abs(a - 15.6) < 1e-3, "%.3f" % a)
        near(G, "wall collision top", hi[1], 3.9)
    if "pier" in vis:
        p = vis["pier"]["pos"]
        lo, hi = bbox(p)
        shaft = p[p[:, 1] < 1.85]
        near(G, "pier shaft width x", np.ptp(shaft[:, 0]), 0.6)
        near(G, "pier shaft width z", np.ptp(shaft[:, 2]), 0.6)
        near(G, "pier bottom", lo[1], 0.0)
        near(G, "pier top (springing 2.2)", hi[1], 2.2)
        near(G, "capital width x", hi[0] - lo[0], 0.75)
        near(G, "capital width z", hi[2] - lo[2], 0.75)
        near(G, "pier centred", np.abs(hi + lo)[[0, 2]].max() / 2, 0.0)
        wide = p[np.abs(p[:, 0]) > 0.31]
        near(G, "capital bottom (shaft top 1.9)", p[p[:, 1] > 1.8][:, 1].min(), 1.9)
        rec(G, "capital only above 1.9", wide[:, 1].min() >= 1.9 - TOL, "%.4f" % wide[:, 1].min())
    if "arch" in vis:
        p = vis["arch"]["pos"]
        lo, hi = bbox(p)
        near(G, "arch bottom (springing)", lo[1], 2.2)
        near(G, "arch top", hi[1], 3.9)
        near(G, "arch depth", hi[2] - lo[2], 0.6)
        near(G, "arch length", hi[0] - lo[0], 4.0)
        mid = p[np.abs(p[:, 2]) < 0.27]       # soffit vertices, inside the worn arrises
        r = np.hypot(mid[:, 0], mid[:, 1] - 2.2)
        near(G, "arch intrados radius mean", r.mean(), 1.7)
        rec(G, "arch intrados is a semicircle (radius spread)", np.ptp(r) <= 2 * TOL, "%.4f" % np.ptp(r))
        near(G, "arch crown (soffit y at x=0)", mid[:, 1].max(), 3.9)
        near(G, "arch soffit x at springing", np.abs(mid[:, 0]).max(), 1.7)
        d["arch_soffit_crown"] = float(mid[:, 1].max())
    if "vault_bay" in vis:
        p = vis["vault_bay"]["pos"]
        lo, hi = bbox(p)
        near(G, "vault springing (lowest y)", lo[1], 2.2)
        near(G, "vault crown (highest y)", hi[1], 3.9)
        c = p[np.hypot(p[:, 0], p[:, 2]) < 1e-3]
        rec(G, "vault has a vertex on the cell axis", len(c) > 0)
        if len(c):
            near(G, "vault crown at cell centre", c[:, 1].max(), 3.9)
        cor = p[(np.abs(p[:, 0]) > 1.69) & (np.abs(p[:, 2]) > 1.69)]
        if len(cor):
            near(G, "groin lands at springing at the corner", cor[:, 1].min(), 2.2)
        rec(G, "vault covers the clear span", min(hi[0], -lo[0], hi[2], -lo[2]) >= 1.7 - TOL,
            "%.4f" % min(hi[0], -lo[0], hi[2], -lo[2]))
    for nm, under in (("ceiling_crouch", 1.3), ("ceiling_crawl", 0.75)):
        if nm in vis:
            lo, hi = bbox(vis[nm]["pos"])
            near(G, "%s underside" % nm, lo[1], under)
            near(G, "%s top" % nm, hi[1], 3.9)
            near(G, "%s size x" % nm, hi[0] - lo[0], 4.0)
            near(G, "%s size z" % nm, hi[2] - lo[2], 4.0)
        if nm in col:
            lo, hi = bbox(col[nm]["pos"])
            rec(G, "%s collision underside exact" % nm, abs(lo[1] - under) <= EXACT, "%.7f" % lo[1])
            near(G, "%s collision top" % nm, hi[1], 3.9)
    return d


def raster_overlap(uv, tris, res=LM_RES):
    """Count lightmap pixels touched by two triangles from different charts. uv in 0..1. Returns (overlap px, used px)."""
    # charts: triangles sharing UV2 vertices
    parent = list(range(len(uv)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    key = {}
    for i, q in enumerate(np.round(uv * 1e6).astype(np.int64)):
        k = (q[0], q[1])
        if k in key:
            parent[find(i)] = find(key[k])
        else:
            key[k] = i
    for t in tris:
        parent[find(t[1])] = find(t[0])
        parent[find(t[2])] = find(t[0])
    owner = np.full((res, res), -1, dtype=np.int64)
    multi = np.zeros((res, res), dtype=bool)
    tri_owner = np.full((res, res), -1, dtype=np.int64)
    same = 0
    for ti, t in enumerate(tris):
        a, b, c = uv[t] * res
        x0, x1 = int(max(np.floor(min(a[0], b[0], c[0])), 0)), int(min(np.ceil(max(a[0], b[0], c[0])), res - 1))
        y0, y1 = int(max(np.floor(min(a[1], b[1], c[1])), 0)), int(min(np.ceil(max(a[1], b[1], c[1])), res - 1))
        if x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xx + 0.5, yy + 0.5
        d = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(d) < 1e-12:
            continue
        w1 = ((px - a[0]) * (c[1] - a[1]) - (py - a[1]) * (c[0] - a[0])) / d
        w2 = ((b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])) / d
        ins = (w1 >= 0) & (w2 >= 0) & (w1 + w2 <= 1)
        if not ins.any():
            continue
        ch = find(t[0])
        sub = owner[y0:y1 + 1, x0:x1 + 1]
        sub_t = tri_owner[y0:y1 + 1, x0:x1 + 1]
        multi[y0:y1 + 1, x0:x1 + 1] |= ins & (sub >= 0) & (sub != ch)
        same += int((ins & (sub >= 0) & (sub == ch) & (sub_t != ti)).sum())
        sub[ins] = ch
        sub_t[ins] = ti
    return int(multi.sum()), int((owner >= 0).sum()), same


def check_uv2(vis):
    G = "4 uv2"
    for nm, m in vis.items():
        uv = m["uv2"]
        if uv is None:
            rec(G, "%s has TEXCOORD_1" % nm, False)
            continue
        rec(G, "%s has TEXCOORD_1" % nm, True)
        rec(G, "%s UV2 inside 0..1" % nm, uv.min() >= 0 and uv.max() <= 1, "%.3f..%.3f" % (uv.min(), uv.max()))
        over, used, same = raster_overlap(uv, m["tris"])
        rec(G, "%s UV2 non-overlapping" % nm, over == 0 and same <= 0.01 * max(used, 1),
            "%d overlap px between charts, %d inside a chart, %d used of %d" % (over, same, used, LM_RES ** 2))


def load_image(g, b, i, tmp):
    im = g["images"][i]
    bv = g["bufferViews"][im["bufferView"]]
    raw = b[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
    path = os.path.join(tmp, "img%d.png" % i)
    open(path, "wb").write(raw)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return np.flipud(px.reshape(h, w, 4))[..., :3], w, h


def seam(a, axis):
    """Mean |first - last| across the wrap, relative to the p90 of the same difference between adjacent rows/cols inside.

    p90, not the mean: band A's wrap is a bed joint by design, and joint rows always differ more than rows in mid-stone.
    <= 1 means the wrap is no rougher than the roughest tenth of interior row pairs.
    """
    a = np.moveaxis(a, axis, 0)
    wrap = np.abs(a[0] - a[-1]).mean()
    inner = np.abs(a[1:] - a[:-1]).reshape(a.shape[0] - 1, -1).mean(1)
    return float(wrap / (np.percentile(inner, 90) + 1e-9))


def check_materials(g, b):
    G = "4 materials"
    mats = g.get("materials", [])
    names = [m.get("name") for m in mats]
    rec(G, "<= 2 materials, exact names", len(mats) <= 2 and set(names) <= {"stone_ashlar", "stone_floor"}, names)
    rec(G, "no glTF extensions (standard PBR only)", not g.get("extensionsUsed") and not any(m.get("extensions") for m in mats),
        g.get("extensionsUsed"))
    for m in mats:
        pbr = m.get("pbrMetallicRoughness", {})
        ok = all(k in pbr for k in ("baseColorTexture", "metallicRoughnessTexture")) and "normalTexture" in m \
            and "occlusionTexture" in m
        rec(G, "%s has base colour, normal, ORM" % m.get("name"), ok)
        orm_a = g["textures"][pbr["metallicRoughnessTexture"]["index"]]["source"] if ok else -1
        orm_b = g["textures"][m["occlusionTexture"]["index"]]["source"] if ok else -2
        rec(G, "%s O and RM share one image" % m.get("name"), orm_a == orm_b)
        rec(G, "%s opaque, single sided" % m.get("name"), m.get("alphaMode", "OPAQUE") == "OPAQUE"
            and not m.get("doubleSided", False))
    tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(GLB)) if False else None)
    total = 0
    sizes = {}
    imgs = {}
    for i, im in enumerate(g.get("images", [])):
        a, w, h = load_image(g, b, i, tmp)
        imgs[im.get("name")] = a
        sizes[im.get("name")] = "%dx%d" % (w, h)
        total += int(w * h * 4 * 4 / 3)
        rec(G, "texture %s side 1024 or 2048" % im.get("name"), w == h and w in (1024, 2048), "%dx%d" % (w, h))
    mb = total / 2 ** 20
    rec(G, "texture memory <= 64 MB (uncompressed + mips)", mb <= MAX_MEM_MB, "%.2f MB" % mb)
    rec(G, "6 images (3 maps x 2 materials)", len(imgs) == 6, list(imgs))

    # tile seams. Floor: whole image in both axes. Ashlar: band A in U and V (the atlas's other bands do not tile, by design)
    G = "4 tile"
    for nm in ("stone_floor_color", "stone_floor_normal", "stone_floor_orm"):
        if nm in imgs:
            for ax, lab in ((0, "V"), (1, "U")):
                r = seam(imgs[nm], ax)
                rec(G, "%s edge seam %s" % (nm, lab), r <= SEAM_MAX, "ratio %.3f" % r)
    r0, r1 = ATLAS["band_a_rows"]
    for nm in ("stone_ashlar_color", "stone_ashlar_normal", "stone_ashlar_orm"):
        if nm in imgs:
            a = imgs[nm]
            f = a.shape[0] / ATLAS["atlas_size"]
            band = a[int(r0 * f):int(r1 * f)]
            for ax, lab in ((0, "V"), (1, "U")):
                r = seam(band, ax)
                rec(G, "%s band A edge seam %s" % (nm, lab), r <= SEAM_MAX, "ratio %.3f" % r)
    return sizes, mb


def main():
    if not os.path.exists(GLB):
        print("no such glb", GLB)
        sys.exit(1)
    g, b = read_glb(GLB)
    vis, col = check_nodes(g, b)
    dims = check_dims(vis, col)
    total = 0
    tri_row = {}
    all_meshes = sum(len(accessor(g, b, p["indices"])) // 3 for m in g["meshes"] for p in m["primitives"])
    for nm in PIECES:
        n = len(vis[nm]["tris"]) if nm in vis else 0
        c = len(col[nm]["tris"]) if nm in col else 0
        tri_row[nm] = {"visual": n, "collision": c, "guide": GUIDE[nm]}
        total += n
        rec("3 tris", "%s within guide" % nm, 0 < n <= GUIDE[nm], "%d / %d (+%d collision)" % (n, GUIDE[nm], c))
    rec("3 tris", "total <= 21,000 (all meshes incl. collision)", all_meshes <= TOTAL_TRIS, all_meshes)
    check_uv2(vis)
    sizes, mb = check_materials(g, b)
    fails = [r for r in results if not r["ok"]]
    for r in results:
        print("%-4s %-13s %-52s %s" % ("ok" if r["ok"] else "FAIL", r["group"], r["check"], r["detail"]))
    print("CHECK_KIT %s: %d checks, %d failed; %s" % ("PASS" if not fails else "FAIL", len(results), len(fails), GLB))
    if arg("--json"):
        json.dump({"results": results, "tris": tri_row, "textures": sizes, "tex_mb": mb, "dims": dims},
                  open(arg("--json"), "w"), indent=1)
    if fails and "--no-exit-code" not in argv:
        sys.exit(1)


main()
