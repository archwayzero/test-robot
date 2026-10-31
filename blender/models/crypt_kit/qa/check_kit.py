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
SPLIT_SEAM_MAX = 1.6   # a bed joint between two offset courses, against an ordinary bed joint
ASHLAR_BAND = []
SEAM_MAX = 1.5    # floor edge-seam ratio, see seam()
BAND_SEAM_MAX = 1.2   # band A seam ratio, see band_seams(). Wrap and as-built pairs must look like an interior bed joint
RUBBLE_MIN_STEP = 0.25  # m, range of the underside depth of a low ceiling
RUBBLE_VCOL_MIN = 0.5   # COLOR_0 red, lowest vertex of a low ceiling (0.29 before pass 4)
RUBBLE_FACET_MAX = 0.35  # m2, largest triangle of a low ceiling (0.38 before pass 4)
RUBBLE_GAP_MAX = 0.28   # m, visible underside above the collision plane (0.39 before pass 4)
RUBBLE_SET_MAX = 0.15   # m, side surface behind the collision box (0.265 before pass 4)
RUBBLE_STEEP_MAX = 0.02  # near-vertical area over plan area, inside the cell: plates and skirts
WALL_LAG_MAX = 0.20     # autocorrelation at lags of 1-7 m, alternated walls
WALL_DIFF_MIN = 0.25    # m, back minus front U offset of a course, away from any whole metre
WALL_DIFF_SPREAD = 0.10  # m, two courses of a span must differ by this in that difference (mod 4, sign free)
WALL_JOINT_MIN = 0.05   # m, between head joints of touching courses on a wall face
LM_RES = 1024

TOP = 4.15        # vault crown, wall top, arch block top, ceiling insert tops (contract, PR #44)
CROWN_ARCH = 3.9  # arch soffit crown
RELIEF_CROWN = 0.20     # item 1: ring proud of the web at the crown, m
RELIEF_HAUNCH = 0.12    # ... radially, at 30-60 deg above the springing
RELIEF_LOW = 0.10       # ... radially, at 25 deg, just above where the web enters the room (23.9 deg)

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
        near(G, "wall top", hi[1], TOP)
    if "wall" in col:
        lo, hi = bbox(col["wall"]["pos"])
        for s, v in ((-1, lo[2]), (1, hi[2])):
            rec(G, "wall collision face exactly z=%+.1f" % (s * 0.3), abs(v - s * 0.3) <= EXACT, "%.7f" % v)
            a = faces_at(col["wall"], 2, s * 0.3)
            rec(G, "wall collision plane z=%+.1f area 16.6" % (s * 0.3), abs(a - 4.0 * TOP) < 1e-3, "%.3f" % a)
        near(G, "wall collision top", hi[1], TOP)
    if "pier" in vis:
        p = vis["pier"]["pos"]
        lo, hi = bbox(p)
        shaft = p[p[:, 1] < 1.85]
        rec(G, "pier shaft 1-3 mm proud of the wall faces (covers the wall butt joint)",
            0.001 <= np.ptp(shaft[:, 2]) / 2 - 0.3 <= 0.003, "%.4f m" % (np.ptp(shaft[:, 2]) / 2 - 0.3))
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
    if "pier" in col:
        c = col["pier"]["pos"]
        c = c[c[:, 1] < 1.85]
        for ax, lab in ((0, "x"), (2, "z")):
            rec(G, "pier shaft collision exactly 0.6 in %s" % lab, abs(np.ptp(c[:, ax]) - 0.6) <= EXACT, "%.7f" % np.ptp(c[:, ax]))
    if "arch" in vis:
        p = vis["arch"]["pos"]
        lo, hi = bbox(p)
        near(G, "arch bottom (springing)", lo[1], 2.2)
        near(G, "arch top (block top)", hi[1], TOP)
        near(G, "arch depth", hi[2] - lo[2], 0.6)
        near(G, "arch length", hi[0] - lo[0], 4.0)
        mid = p[np.abs(p[:, 2]) < 0.27]       # soffit vertices, inside the worn arrises
        r = np.hypot(mid[:, 0], mid[:, 1] - 2.2)
        near(G, "arch intrados radius mean", r.mean(), 1.7)
        rec(G, "arch intrados is a semicircle (radius spread)", np.ptp(r) <= 2 * TOL, "%.4f" % np.ptp(r))
        near(G, "arch crown (soffit y at x=0)", mid[:, 1].max(), CROWN_ARCH)
        near(G, "arch soffit x at springing", np.abs(mid[:, 0]).max(), 1.7)
        d["arch_soffit_crown"] = float(mid[:, 1].max())
    if "vault_bay" in vis:
        p = vis["vault_bay"]["pos"]
        lo, hi = bbox(p)
        near(G, "vault springing (lowest y)", lo[1], 2.2)
        near(G, "vault crown (highest y)", hi[1], TOP)
        c = p[np.hypot(p[:, 0], p[:, 2]) < 1e-3]
        rec(G, "vault has a vertex on the cell axis", len(c) > 0)
        if len(c):
            near(G, "vault crown at cell centre", c[:, 1].max(), TOP)
        cor = p[(np.abs(p[:, 0]) > 1.69) & (np.abs(p[:, 2]) > 1.69)]
        if len(cor):
            near(G, "hidden web foot at springing (behind wall/arch)", cor[:, 1].min(), 2.2)
        land = [surface_y(vis["vault_bay"], sx * 1.7, sz * 1.7) for sx in (-1, 1) for sz in (-1, 1)]
        rec(G, "visible groin landing at the room corner in 2.90-3.05", min(land) >= 2.90 and max(land) <= 3.05,
            "y %.3f..%.3f at plan (+-1.7, +-1.7)" % (min(land), max(land)))
        rec(G, "vault covers the clear span", min(hi[0], -lo[0], hi[2], -lo[2]) >= 1.7 - TOL,
            "%.4f" % min(hi[0], -lo[0], hi[2], -lo[2]))
    for nm, under in (("ceiling_crouch", 1.3), ("ceiling_crawl", 0.75)):
        if nm in vis:
            lo, hi = bbox(vis[nm]["pos"])
            near(G, "%s underside" % nm, lo[1], under)
            near(G, "%s top" % nm, hi[1], TOP)
            near(G, "%s size x" % nm, hi[0] - lo[0], 4.0)
            near(G, "%s size z" % nm, hi[2] - lo[2], 4.0)
            q = vis[nm]["pos"]
            q = q[(np.abs(q[:, 0]) < 1.6) & (np.abs(q[:, 2]) < 1.6) & (q[:, 1] < under + 0.45)]
            rec(G, "%s underside has depth steps >= %.2f m" % (nm, RUBBLE_MIN_STEP), np.ptp(q[:, 1]) >= RUBBLE_MIN_STEP,
                "%.3f m over %d vertices" % (np.ptp(q[:, 1]), len(q)))
        if nm in col:
            lo, hi = bbox(col[nm]["pos"])
            rec(G, "%s collision underside exact" % nm, abs(lo[1] - under) <= EXACT, "%.7f" % lo[1])
            near(G, "%s collision top" % nm, hi[1], TOP)
    return d


def surface_y(m, x, z):
    """Highest y of the mesh over a plan point, from the triangles."""
    t = m["pos"][m["tris"]]
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    d = (b[:, 0] - a[:, 0]) * (c[:, 2] - a[:, 2]) - (b[:, 2] - a[:, 2]) * (c[:, 0] - a[:, 0])
    ok = np.abs(d) > 1e-12
    w1 = np.zeros(len(t))
    w2 = np.zeros(len(t))
    w1[ok] = ((x - a[ok, 0]) * (c[ok, 2] - a[ok, 2]) - (z - a[ok, 2]) * (c[ok, 0] - a[ok, 0])) / d[ok]
    w2[ok] = ((b[ok, 0] - a[ok, 0]) * (z - a[ok, 2]) - (b[ok, 2] - a[ok, 2]) * (x - a[ok, 0])) / d[ok]
    hit = ok & (w1 >= -1e-6) & (w2 >= -1e-6) & (w1 + w2 <= 1 + 1e-6)
    return float((a[hit, 1] + w1[hit] * (b[hit, 1] - a[hit, 1]) + w2[hit] * (c[hit, 1] - a[hit, 1])).max()) if hit.any() else -9.0


def section_at_face(m, face=1.7, step=0.01):
    """Web section where it enters the room: (x, y) polyline of the highest surface over the plan line z = +-face, averaged
    over both sides of the cell and both quadrants, from the triangles (not the vertices)."""
    t = m["pos"][m["tris"]]
    out = {}
    for axis, side in ((2, 1), (2, -1), (0, 1), (0, -1)):
        other = 2 - axis
        pts = []
        p, q, e = t[:, :, other], t[:, :, axis] * side, t[:, :, 1]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            a, b = q[:, i], q[:, j]
            hit = (a - face) * (b - face) < 0
            f = (face - a[hit]) / (b[hit] - a[hit])
            pts.append(np.stack([p[hit, i] + f * (p[hit, j] - p[hit, i]), e[hit, i] + f * (e[hit, j] - e[hit, i])], 1))
            on = np.abs(a - face) < 1e-5
            pts.append(np.stack([p[on, i], e[on, i]], 1))
        out[(axis, side)] = np.vstack(pts)
    return out


def check_relief(vis):
    """Item 1, from the GLB. Arch soffit = fit of the soffit vertices; web = the vault mesh cut by the arch face plane."""
    G = "1b relief"
    if "arch" not in vis or "vault_bay" not in vis:
        rec(G, "arch and vault present", False)
        return {}
    a = vis["arch"]["pos"]
    mid = a[np.abs(a[:, 2]) < 0.27]
    r_arch = np.hypot(mid[:, 0], mid[:, 1] - 2.2)
    theta_a = np.degrees(np.arctan2(mid[:, 1] - 2.2, mid[:, 0]))
    sec = section_at_face(vis["vault_bay"])
    table = {}
    vertical = None
    for th in (90, 60, 45, 30, 25):
        worst, worst_v = 9.0, 9.0
        for key, pts in sec.items():
            for sign in (1, -1):
                ang = np.radians(th)
                # web radius on this ray, per side of the cell, from the section polyline
                x, y = pts[:, 0] * sign, pts[:, 1] - 2.2
                keep = (x >= -1e-6) if th < 90 else (np.abs(x) < 0.5)
                if keep.sum() < 3:
                    worst = -9.0
                    continue
                t_w = np.degrees(np.arctan2(y[keep], x[keep]))
                r_w = np.hypot(x[keep], y[keep])
                o = np.argsort(t_w)
                rw = float(np.interp(th, t_w[o], r_w[o]))
                o2 = np.argsort(theta_a)
                ra = float(np.interp(th, theta_a[o2], r_arch[o2]))
                worst = min(worst, rw - ra)
                worst_v = min(worst_v, rw * np.sin(ang) - ra * np.sin(ang))
        table[th] = worst
        if th == 90:
            vertical = worst_v
    rec(G, "ring proud of web at the crown >= %.2f" % RELIEF_CROWN, table[90] >= RELIEF_CROWN, "%.4f m" % table[90])
    for th in (60, 45, 30):
        rec(G, "ring proud at %d deg (radial) >= %.2f" % (th, RELIEF_HAUNCH), table[th] >= RELIEF_HAUNCH, "%.4f m" % table[th])
    rec(G, "ring proud at 25 deg (radial) >= %.2f" % RELIEF_LOW, table[25] >= RELIEF_LOW, "%.4f m" % table[25])
    # the ring needs a face to stand on: the arch's flat face must reach above the web everywhere, or there is a gap
    face = a[(np.abs(np.abs(a[:, 2]) - 0.3) < 1e-4) & (np.hypot(a[:, 0], a[:, 1] - 2.2) > 1.9)]
    o = np.argsort(face[:, 0])
    gap = 9.0
    for pts in sec.values():
        q = pts[np.abs(pts[:, 0]) < 1.7]
        gap = min(gap, float((np.interp(q[:, 0], face[o, 0], face[o, 1]) - q[:, 1]).min()))
    rec(G, "arch face reaches above the web (no gap)", gap >= 0, "min %.4f m" % gap)
    return {str(k): round(v, 4) for k, v in table.items()}


def lowest_y(m, x, z, t):
    """Lowest y of the mesh over a plan point."""
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    d = (b[:, 0] - a[:, 0]) * (c[:, 2] - a[:, 2]) - (b[:, 2] - a[:, 2]) * (c[:, 0] - a[:, 0])
    ok = np.abs(d) > 1e-12
    w1 = np.where(ok, ((x - a[:, 0]) * (c[:, 2] - a[:, 2]) - (z - a[:, 2]) * (c[:, 0] - a[:, 0])) / np.where(ok, d, 1), -1)
    w2 = np.where(ok, ((b[:, 0] - a[:, 0]) * (z - a[:, 2]) - (b[:, 2] - a[:, 2]) * (x - a[:, 0])) / np.where(ok, d, 1), -1)
    hit = (w1 >= -1e-6) & (w2 >= -1e-6) & (w1 + w2 <= 1 + 1e-6)
    return float((a[hit, 1] + w1[hit] * (b[hit, 1] - a[hit, 1]) + w2[hit] * (c[hit, 1] - a[hit, 1])).min()) if hit.any() else None


def check_rubble(g, b, vis):
    """Item 5, from the GLB."""
    G = "5 rubble"
    for nm, under in (("ceiling_crouch", 1.3), ("ceiling_crawl", 0.75)):
        node = next((n for n in g["nodes"] if n.get("name") == nm), None)
        if nm not in vis or node is None:
            rec(G, "%s present" % nm, False)
            continue
        prim = g["meshes"][node["mesh"]]["primitives"][0]
        if "COLOR_0" in prim["attributes"]:
            c = accessor(g, b, prim["attributes"]["COLOR_0"]).astype(float)
            c = c / {5121: 255.0, 5123: 65535.0, 5126: 1.0}[g["accessors"][prim["attributes"]["COLOR_0"]]["componentType"]]
            rec(G, "%s COLOR_0 crevice R >= %.1f" % (nm, RUBBLE_VCOL_MIN), c[:, 0].min() >= RUBBLE_VCOL_MIN,
                "min %.3f, mean %.3f" % (c[:, 0].min(), c[:, 0].mean()))
        else:
            rec(G, "%s COLOR_0 crevice R >= %.1f" % (nm, RUBBLE_VCOL_MIN), False, "no COLOR_0")
        m = vis[nm]
        t = m["pos"][m["tris"]]
        n_ = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        area = 0.5 * np.linalg.norm(n_, axis=1)
        rec(G, "%s largest facet <= %.2f m2" % (nm, RUBBLE_FACET_MAX), area.max() <= RUBBLE_FACET_MAX,
            "%.3f m2; %.0f %% of the area in facets over 0.2 m2" % (area.max(), 100 * area[area > 0.2].sum() / area.sum()))
        ys = []
        for x in np.linspace(-1.93, 1.93, 26):
            for z in np.linspace(-1.91, 1.95, 26):
                y = lowest_y(m, x, z, t)
                if y is not None:
                    ys.append(y - under)
        ys = np.array(ys)
        rec(G, "%s visible underside to collision <= %.2f m" % (nm, RUBBLE_GAP_MAX), ys.max() <= RUBBLE_GAP_MAX and len(ys) > 600,
            "max %.3f, mean %.3f, over %d points" % (ys.max(), ys.mean(), len(ys)))
        p = m["pos"]
        up = p[p[:, 1] > under + 0.45]
        back = 2.0 - np.abs(up[:, [0, 2]]).max(1)
        rec(G, "%s side set back <= %.2f m" % (nm, RUBBLE_SET_MAX), back.max() <= RUBBLE_SET_MAX, "max %.3f m" % back.max())
        c_ = t.mean(1)
        low = (c_[:, 1] < under + 0.45) & (np.abs(c_[:, 0]) < 1.85) & (np.abs(c_[:, 2]) < 1.85)
        unit = np.abs(n_[:, 1]) / np.maximum(np.linalg.norm(n_, axis=1), 1e-12)
        steep = area[low & (unit < 0.26)].sum() / 3.7 ** 2
        rec(G, "%s no plates: near-vertical area / plan <= %.2f" % (nm, RUBBLE_STEEP_MAX), steep <= RUBBLE_STEEP_MAX, "%.3f" % steep)
        key = {}
        ids = np.array([key.setdefault(tuple(q), len(key)) for q in np.round(p, 3).tolist()])
        tid = ids[m["tris"]]
        edge = {}
        for a_, b_, c_i in tid.tolist():
            for u, v in ((a_, b_), (b_, c_i), (c_i, a_)):
                if u != v:
                    edge[(min(u, v), max(u, v))] = edge.get((min(u, v), max(u, v)), 0) + 1
        pts = np.round(p, 3)
        first = {}
        for i, k_ in enumerate(ids.tolist()):
            first.setdefault(k_, i)
        open_e = [e for e, k_ in edge.items() if k_ == 1 and min(pts[first[e[0]], 1], pts[first[e[1]], 1]) < TOP - 0.01]
        rec(G, "%s closed surface below the top edge" % nm, not open_e, "%d open edges %s" % (len(open_e), [
            (pts[first[e[0]]].tolist(), pts[first[e[1]]].tolist()) for e in open_e[:2]]))


def check_soiling(g, b, vis):
    G = "4b soiling"
    for nm in ("wall", "pier"):
        ok, detail = False, "no COLOR_0"
        node = next((n for n in g["nodes"] if n.get("name") == nm), None)
        if node is not None and "mesh" in node:
            prim = g["meshes"][node["mesh"]]["primitives"][0]
            if "COLOR_0" in prim["attributes"]:
                c = accessor(g, b, prim["attributes"]["COLOR_0"]).astype(float)
                ct = g["accessors"][prim["attributes"]["COLOR_0"]]["componentType"]
                c = c / {5121: 255.0, 5123: 65535.0, 5126: 1.0}[ct]
                y = accessor(g, b, prim["attributes"]["POSITION"])[:, 1]
                lo, up = c[y < 0.05, 0].mean(), c[(y > 1.3) & (y < 1.8), 0].mean()
                ok = lo < up - 0.2 and c.max() <= 1.0
                detail = "R at floor %.2f, at 1.5 m %.2f" % (lo, up)
        rec(G, "%s has height-varying COLOR_0" % nm, ok, detail)


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
    Returns (p90 ratio, the old mean-based ratio). Only the p90 ratio is tested; the other is printed so a reviewer sees both.

    p90, not the mean: band A's wrap is a bed joint by design, and joint rows always differ more than rows in mid-stone.
    <= 1 means the wrap is no rougher than the roughest tenth of interior row pairs.
    """
    a = np.moveaxis(a, axis, 0)
    wrap = np.abs(a[0] - a[-1]).mean()
    inner = np.abs(a[1:] - a[:-1]).reshape(a.shape[0] - 1, -1).mean(1)
    return float(wrap / (np.percentile(inner, 90) + 1e-9)), float(wrap / (inner.mean() + 1e-9))


def wall_table(vis):
    """Per long face, from the GLB: {y0: (y1, u offset of the course, V low, V high)}. front = the face at glTF z=+0.3."""
    m = vis["wall"]
    t = m["pos"][m["tris"]]
    uv = m["uv1"][m["tris"]]
    out = {}
    for key, side in (("f", 1), ("b", -1)):
        rows = {}
        for k in np.flatnonzero(np.all(np.abs(t[:, :, 2] - side * 0.3) < 1e-4, axis=1)):
            r = rows.setdefault(round(float(t[k, :, 1].min()), 3), [float(t[k, :, 1].max()), [], []])
            r[0] = max(r[0], float(t[k, :, 1].max()))
            r[1].extend(uv[k, :, 0].tolist())
            r[2].extend(uv[k, :, 1].tolist())
        out[key] = {y: (r[0], 0.5 * (min(r[1]) + max(r[1])) % 1.0, min(r[2]), max(r[2])) for y, r in sorted(rows.items())}
    return out


def v_to_z(v):
    """glTF V counts from the top of the image, like the atlas rows."""
    r0, r1 = ATLAS["band_a_rows"]
    return (r1 - v * ATLAS["atlas_size"]) / (r1 - r0) * 2.0


def check_wall_courses(vis):
    """Item 3, from the GLB's wall mesh."""
    G = "3b courses"
    if "wall" not in vis or "band_a_course_edges_m" not in ATLAS:
        rec(G, "wall and course table present", False)
        return None
    tab = wall_table(vis)
    edges = ATLAS["band_a_course_edges_m"]
    n = len(edges) - 1
    want = [round(e, 3) for e in edges[:-1]] + [round(2.0 + e, 3) for e in edges[:-1]] + [4.0]
    for key in "fb":
        got = sorted(tab[key])
        rec(G, "wall face %s split on every bed joint" % key, got == want, "%d rows of %d" % (len(got), len(want)))
        worst = 0.0
        for y0, (y1, o, v0, v1) in tab[key].items():
            if y0 >= 4.0:
                continue
            base = 2.0 if y0 >= 2.0 - 1e-6 else 0.0
            lo, hi = sorted((v_to_z(v0), v_to_z(v1)))
            worst = max(worst, abs(lo - (y0 - base)), abs(hi - (y1 - base)))
        rec(G, "wall face %s V follows the course heights exactly" % key, worst <= 0.002, "worst %.4f m" % worst)
    if sorted(tab["f"]) != want or sorted(tab["b"]) != want:
        return None
    table = ATLAS["wall_course_u_offsets"]
    worst = 0.0
    for key in "fb":
        for span in (0, 1):
            for c in range(n):
                worst = max(worst, abs(((tab[key][round(edges[c] + 2.0 * span, 3)][1] - table[key][span][c]) + 0.5) % 1.0 - 0.5))
    rec(G, "wall U offsets equal atlas.json", worst <= 2e-3, "worst %.5f tile" % worst)
    near_whole, near_each = 9.0, 9.0
    for span in (0, 1):
        ds = []
        for c in range(n):
            y = round(edges[c] + 2.0 * span, 3)
            d = 4.0 * (tab["b"][y][1] - tab["f"][y][1]) % 4.0
            near_whole = min(near_whole, abs(((d + 0.5) % 1.0) - 0.5))
            ds.append(d)
        for i in range(n):
            for j in range(i):
                g = abs((ds[i] - ds[j] + 2.0) % 4.0 - 2.0)
                near_each = min(near_each, g)
    rec(G, "wall face difference stays off whole metres", near_whole >= WALL_DIFF_MIN, "min %.3f m (>= %.2f)" % (near_whole, WALL_DIFF_MIN))
    rec(G, "wall face differences spread over the courses", near_each >= WALL_DIFF_SPREAD, "min %.3f m (>= %.2f)" % (near_each, WALL_DIFF_SPREAD))
    return tab


def course_pairs(tab):
    """Touching courses on a wall face: (course below, course above, tile U shift of the upper over the lower)."""
    edges = ATLAS["band_a_course_edges_m"]
    n = len(edges) - 1
    out = []
    for key in "fb":
        for span in (0, 1):
            for c in range(1, n):
                out.append((c - 1, c, tab[key][round(edges[c] + 2.0 * span, 3)][1] - tab[key][round(edges[c - 1] + 2.0 * span, 3)][1]))
        out.append((n - 1, 0, tab[key][2.0][1] - tab[key][round(edges[n - 1], 3)][1]))
    return out


def check_head_joints(tab):
    """Head joints of touching courses on the wall, from atlas.json's stones and the GLB's offsets. Only meaningful for the
    generated band: a replacement map is not bound by it."""
    G = "3b courses"
    if tab is None or "band_a_stones_m" not in ATLAS or ATLAS.get("replacement_maps"):
        return
    st = np.array(ATLAS["band_a_stones_m"])
    z = ATLAS["band_a_course_edges_m"]
    joints = [st[np.abs(st[:, 2] - z[c]) < 1e-3, 0] for c in range(len(z) - 1)]
    worst = 9.0
    for lo, hi, du in course_pairs(tab):
        g = np.abs(np.mod(joints[hi][:, None] - joints[lo][None, :] - du * 4.0 + 2.0, 4.0) - 2.0)
        worst = min(worst, float(g.min()))
    rec(G, "wall head joints do not line up across a bed joint", worst >= WALL_JOINT_MIN, "closest %.3f m (>= %.2f)" % (worst, WALL_JOINT_MIN))


def gauss_reflect(L, s):
    r = int(4 * s) + 2
    P = np.pad(L, r, mode="reflect")
    h, w = P.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    return np.fft.irfft2(np.fft.rfft2(P) * np.exp(-2 * (np.pi * s) ** 2 * (fx ** 2 + fy ** 2)), s=(h, w))[r:-r, r:-r]


def wall_strip(band, tab, span, alternate):
    """Unlit luminance of three walls in a row, one 2 m span, built from the GLB's offsets: front, back, front. Row 0 = top."""
    h, w = band.shape[:2]
    L = band @ np.array([.2126, .7152, .0722])
    edges = ATLAS["band_a_course_edges_m"]
    keys = "fbf" if alternate else "fff"
    out = np.zeros((h, 3 * w))
    z = 2.0 * (h - 0.5 - np.arange(h)) / h
    for i, key in enumerate(keys):
        for c in range(len(edges) - 1):
            o = tab[key][round(edges[c] + 2.0 * span, 3)][1]
            rows = (z >= edges[c]) & (z < edges[c + 1])
            # tile i covers x = 4i .. 4i+4, s = x - 4i - 2, u = s / 4 + o
            out[rows, i * w:(i + 1) * w] = np.roll(L[rows], -int(round((o - 0.5) * w)), axis=1)
    return out


def strip_lags(strip, ppm, metres):
    L = strip - gauss_reflect(strip, 0.165 * ppm)
    L = L - L.mean(1, keepdims=True)
    x0, n_x = int(0.076 * ppm), int(3.17 * ppm)
    a = L[:, x0:x0 + n_x].ravel()
    out = {}
    for m_ in metres:
        lag = int(round(m_ * ppm))
        out[m_] = float(np.corrcoef(a, L[:, x0 + lag:x0 + lag + n_x].ravel())[0, 1])
    return out


def check_wall_lags(tab, band):
    """Repetition without a render, on the same crop and formula as measure_look.py: the base colour alone, no light or soiling."""
    G = "3b courses"
    if tab is None:
        return {}
    ppm = band.shape[1] / 4.0
    metres = [1, 2, 3, 4, 5, 6, 7, 8]
    res = {}
    for span in (0, 1):
        res[span] = strip_lags(wall_strip(band, tab, span, True), ppm, metres)
        worst = max(abs(res[span][m_]) for m_ in metres[:-1])
        rec(G, "wall span %d lags 1-7 m < %.2f, unlit" % (span, WALL_LAG_MAX), worst < WALL_LAG_MAX,
            "worst %.3f; %s" % (worst, ", ".join("%g m %.3f" % (m_, res[span][m_]) for m_ in metres)))
    un = strip_lags(wall_strip(band, tab, 1, False), ppm, metres)
    print("wall unalternated, unlit, upper span: " + ", ".join("%g m %.3f" % (m_, un[m_]) for m_ in metres))
    return res


def band_seams(G, nm, band, du):
    """Old test: wrap against the p90 of interior row pairs. That let a real step through, because p90 sits well below a joint.
    New test (printed with the old one): wrap, and the pairs the wall really shows at z=2 and z=4, against the MEDIAN INTERIOR BED
    JOINT, i.e. the peak row difference at each interior course line. 1 means the seam looks like an ordinary bed joint."""
    h, w = band.shape[:2]
    inner = np.abs(band[1:] - band[:-1]).mean((1, 2))
    edges = np.cumsum(ATLAS["band_a_courses_m"])[:-1]
    win = max(int(0.03 * h), 2)
    pos = [int(round(h * (1 - e / 2.0))) for e in edges]
    joint = float(np.median([inner[max(q - win, 0):q + win].max() for q in pos]))
    wrap_v = float(np.abs(band[0] - band[-1]).mean())
    wrap_u = float(np.abs(band[:, 0] - band[:, -1]).mean())
    old = wrap_v / (np.percentile(inner, 90) + 1e-9)
    rec(G, "%s band A wrap V / bed joint" % nm, wrap_v / joint <= BAND_SEAM_MAX,
        "%.3f (limit %.1f); old p90 ratio %.3f (limit 1.5); median bed joint %.5f" % (wrap_v / joint, BAND_SEAM_MAX, old, joint))
    rec(G, "%s band A wrap U / bed joint" % nm, wrap_u / joint <= BAND_SEAM_MAX, "%.3f" % (wrap_u / joint))
    if du is None:
        return
    # the rows that meet at each wall split, at the U offsets the wall really has
    edges_m = ATLAS["band_a_course_edges_m"]
    worst, where = 0.0, ""
    for lo, hi, shift in du:
        below = h - 1 - int(np.floor(h * edges_m[lo + 1] / 2.0 - 0.5)) if lo + 1 < len(edges_m) - 1 else 0
        above = h - 1 - int(np.ceil(h * edges_m[hi] / 2.0 - 0.5))
        r = float(np.abs(band[below % h] - np.roll(band[above % h], -int(round(shift * w)), axis=0)).mean()) / joint
        if r > worst:
            worst, where = r, "courses %d/%d, shift %.2f" % (lo, hi, shift)
    rec(G, "%s wall course splits / bed joint" % nm, worst <= SPLIT_SEAM_MAX, "worst %.3f (limit %.1f) at %s" % (worst, SPLIT_SEAM_MAX, where))


def check_materials(g, b, vis):
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
    tmp = tempfile.mkdtemp()
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
    calls = sum(len(m["primitives"]) for m in g["meshes"])
    rec(G, "draw calls (all primitives) <= 14", calls <= 14, calls)
    print("texture memory margin %.3f MB of %.1f" % (MAX_MEM_MB - mb, MAX_MEM_MB))
    rec(G, "6 images (3 maps x 2 materials)", len(imgs) == 6, list(imgs))

    # tile seams. Floor: whole image in both axes. Ashlar: band A in U and V (the atlas's other bands do not tile, by design)
    G = "4 tile"
    for nm in ("stone_floor_color", "stone_floor_normal", "stone_floor_orm"):
        if nm in imgs:
            for ax, lab in ((0, "V"), (1, "U")):
                r, old = seam(imgs[nm], ax)
                rec(G, "%s edge seam %s" % (nm, lab), r <= SEAM_MAX, "p90 ratio %.3f, old mean ratio %.3f" % (r, old))
    r0, r1 = ATLAS["band_a_rows"]
    tab = wall_table(vis) if "wall" in vis else None
    du = None
    edges_m = ATLAS.get("band_a_course_edges_m", [])
    want = sorted([round(e, 3) for e in edges_m[:-1]] + [round(2.0 + e, 3) for e in edges_m[:-1]] + [4.0])
    if tab and sorted(tab["f"]) == want and sorted(tab["b"]) == want:
        du = course_pairs(tab)
    for nm in ("stone_ashlar_color", "stone_ashlar_normal", "stone_ashlar_orm"):
        if nm in imgs:
            a = imgs[nm]
            f = a.shape[0] / ATLAS["atlas_size"]
            band = a[int(r0 * f):int(r1 * f)]
            band_seams(G, nm, band, du)
            if nm == "stone_ashlar_color":
                ASHLAR_BAND.append(band)
    return sizes, mb


def main():
    if not os.path.exists(GLB):
        print("no such glb", GLB)
        sys.exit(1)
    g, b = read_glb(GLB)
    vis, col = check_nodes(g, b)
    dims = check_dims(vis, col)
    dims["relief_m_by_angle"] = check_relief(vis)
    check_soiling(g, b, vis)
    check_rubble(g, b, vis)
    courses = check_wall_courses(vis)
    check_head_joints(courses)
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
    sizes, mb = check_materials(g, b, vis)
    lags = check_wall_lags(courses, ASHLAR_BAND[0]) if ASHLAR_BAND else {}
    dims["wall_lags_unlit"] = {str(k): {str(m_): round(v, 3) for m_, v in d.items()} for k, d in lags.items()}
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
