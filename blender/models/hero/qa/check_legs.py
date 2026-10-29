"""Step C: measure the leg landmarks on hero_model.blend and compare with reference_landmarks.json.
usage: blender -b blender/models/hero/hero_model.blend -P blender/models/hero/qa/check_legs.py [-- <out.txt>]
Model landmarks come from the geometry (face attributes lm_part / lm_t written by conform.py mark which loft
ring / tine row a face belongs to): ring centroids for knee / hock / ankle, row centroids for the tine centre
lines, slab cross-sections for thicknesses. Side-view quantities use the (y, z) projection like the reference.
The near (character's left, -X) leg is measured; the rest pose is symmetric."""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector
R = "/home/archwayzero/game/"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTTXT = argv[0] if argv else R + ".captures/T011/v4/check_legs.txt"
ref = json.load(open(R + ".captures/T011/v4/reference_landmarks.json"))
T = ref["targets"]
obj = bpy.data.objects["hero"]
me = obj.data
bm = bmesh.new(); bm.from_mesh(me)
bm.faces.ensure_lookup_table()
lp = bm.faces.layers.float["lm_part"]; lt = bm.faces.layers.float["lm_t"]
SIDE = -1
rows = []
def row(name, ref_v, mod_v, ok, tol, unit=""):
    rows.append((name, ref_v, mod_v, "PASS" if ok else "FAIL", tol, unit))
def fmt(v):
    if isinstance(v, (list, tuple)): return "(" + ", ".join(f"{x:+.3f}" for x in v) + ")"
    if isinstance(v, float): return f"{v:.4f}"
    return str(v)

legf = [f for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * SIDE > 0]
def part(f): return int(round(f[lp]))
def yz(v): return Vector((v.y, v.z))

# ---- rings: verts shared by the row tagged t_prev and the row tagged t (loft parts 4, 5, 6)
loft = [f for f in legf if part(f) in (4, 5, 6)]
ts = sorted({round(f[lt], 5) for f in loft})
def ring(t):
    i = ts.index(round(t, 5))
    a = {v for f in loft if abs(f[lt] - ts[i - 1]) < 1e-5 for v in f.verts}
    b = {v for f in loft if abs(f[lt] - ts[i]) < 1e-5 for v in f.verts}
    s = a & b
    return sum((v.co for v in s), Vector()) / len(s), len(s)
K, nk = ring(0.0)
J, nj = ring(min(ts, key=lambda t: abs(t - 0.4855)))
A, na = ring(1.0)
# hip: centre of the Tripo hip disc (body verts on the outer hip), same landmark as the reference
disc = [v.co for v in bm.verts if 0.165 < -SIDE * v.co.x < 0.195 and 0.815 < v.co.z < 0.93 and -0.03 < v.co.y < 0.15
        and not any(f.material_index == 1 for f in v.link_faces)]
Hp = Vector((SIDE * 0.11, (min(c.y for c in disc) + max(c.y for c in disc)) / 2, (min(c.z for c in disc) + max(c.z for c in disc)) / 2))
H = A.z
def ang_v(a, b):        # side view, + = going back (-Y) while going down
    return math.degrees(math.atan2(-(b.y - a.y), -(b.z - a.z)))
thigh = (yz(K) - yz(Hp)).length; shin = (yz(J) - yz(K)).length; meta = (yz(A) - yz(J)).length
a_t, a_s, a_m = ang_v(Hp, K), ang_v(K, J), ang_v(J, A)
knee_ang, hock_ang = a_s - a_t, a_m - a_s
row("thigh length hip->knee (m)", T["thigh_len_m"], thigh, abs(thigh / T["thigh_len_m"] - 1) <= 0.05, "5%")
row("shin length knee->hock (m)", T["shin_len_m"], shin, abs(shin / T["shin_len_m"] - 1) <= 0.05, "5%")
row("metatarsal hock->ankle (m)", T["meta_len_m"], meta, abs(meta / T["meta_len_m"] - 1) <= 0.05, "5%")
row("knee angle = shin slant vs thigh (deg)", T["knee_angle_deg"], knee_ang, abs(knee_ang - T["knee_angle_deg"]) <= 5, "5 deg")
row("hock angle (deg)", T["hock_angle_deg"], hock_ang, abs(hock_ang - T["hock_angle_deg"]) <= 5, "5 deg")
row("  info: far-leg knee angle (vs plate edge)", ref["far"]["knee_angle_deg (vs plate edge)"], knee_ang, True, "info")
row("  info: thigh angle from vertical (pose)", ref["near"]["thigh_angle_from_vertical_deg"], a_t, True, "info")
row("  info: shin angle from vertical (pose)", ref["far"]["shin_angle_from_vertical_deg"], a_s, True, "info (far=planted)")
row("ankle height H (m)", T["H_m"], H, abs(H / T["H_m"] - 1) <= 0.05, "5%")

# ---- shin thickness (side view, perpendicular to knee->ankle) from a 3 mm slab cross-section, contiguous run
alle = list({e for f in legf for e in f.edges})
axis = (yz(A) - yz(K)); Ln = axis.length; u = axis / Ln; n = Vector((-u.y, u.x))
def section(c, u, n, faces):
    """exact side-view silhouette width at point c perpendicular to u: every face projected to (y, z) is cut by
    the line through c (direction n); the cut intervals are merged (gap <= 1 mm ~ half a reference pixel) and
    the merged interval containing (or nearest to) the axis point is returned."""
    iv = []
    for f in faces:
        P = [yz(v.co) for v in f.verts]
        d = [(p - c).dot(u) for p in P]
        hits = []
        for i in range(len(P)):
            j = (i + 1) % len(P)
            if (d[i] > 0) != (d[j] > 0) and d[i] != d[j]:
                hits.append((P[i] + (P[j] - P[i]) * (d[i] / (d[i] - d[j])) - c).dot(n))
        if len(hits) >= 2:
            iv.append((min(hits), max(hits)))
    if not iv:
        return 0.0
    iv.sort()
    merged = [list(iv[0])]
    for a_, b_ in iv[1:]:
        if a_ <= merged[-1][1] + 0.001:
            merged[-1][1] = max(merged[-1][1], b_)
        else:
            merged.append([a_, b_])
    k = min(range(len(merged)), key=lambda i: 0 if merged[i][0] <= 0 <= merged[i][1]
            else min(abs(merged[i][0]), abs(merged[i][1])))
    return merged[k][1] - merged[k][0]
for key, t in (("25%", 0.25), ("50%", 0.5), ("85%", 0.85)):
    th = section(yz(K) + axis * t, u, n, legf)
    if os.environ.get("CHECK_DEBUG"):
        c = yz(K) + axis * t
        dd = []
        for e in alle:
            a_, b_ = yz(e.verts[0].co), yz(e.verts[1].co)
            da_, db_ = (a_ - c).dot(u), (b_ - c).dot(u)
            if (da_ > 0) != (db_ > 0) and da_ != db_:
                dd.append(round(((a_ + (b_ - a_) * (da_ / (da_ - db_))) - c).dot(n), 4))
        print(key, sorted(dd))
    rt = T["shin_thickness_m"][key]
    row(f"shin thickness at {key} (m, side view)", rt, th, abs(th / rt - 1) <= 0.15, "15%")

# ---- tines: centre lines from the row centroids (rows tagged lm_t = arclength fraction)
from mathutils.bvhtree import BVHTree
_lb = bmesh.new()
for f in loft:
    _lb.faces.new([_lb.verts.new(v.co) for v in f.verts])
_lb.normal_update()
bvh = BVHTree.FromBMesh(_lb)
FOOT = T["foot_H"]
def landmarks(pts):
    irear = min(range(len(pts)), key=lambda i: pts[i][0])
    best, ia = None, 1
    for i in range(1, irear):
        dx = pts[i + 1][0] - pts[i - 1][0]; dy = pts[i + 1][1] - pts[i - 1][1]
        s = abs(dy / dx) if dx else 9e9
        if best is None or s < best: best, ia = s, i
    zmin = min(p[1] for p in pts)
    ilow = min(i for i in range(len(pts)) if pts[i][1] <= zmin + 0.01)
    return {"root": pts[0], "arch_top": pts[ia], "rearmost": pts[irear], "lowest": pts[ilow], "tip": pts[-1]}
def plen(p): return sum(math.dist(p[i], p[i - 1]) for i in range(1, len(p)))
for name, pid in (("outer", 10), ("middle", 11), ("inner", 12)):
    fs = [f for f in legf if part(f) == pid]
    buckets = {}
    for f in fs:
        buckets.setdefault(round(f[lt], 5), []).append(f)
    keys = sorted(buckets)
    # skip leading rows cut by the union (not a clean ring of 6 quads): their centroids are biased
    while keys and not (len(buckets[keys[0]]) == 6 and all(len(f.verts) == 4 for f in buckets[keys[0]])):
        keys.pop(0)
    pts3 = []
    for k in keys:
        vs = {v for f in buckets[k] for v in f.verts}
        pts3.append(sum((v.co for v in vs), Vector()) / len(vs))
    # root = where the centre line leaves the leg loft surface (drop the embedded rows inside the shin)
    i0 = 0
    while i0 < len(pts3) - 3:
        loc, nrm, _, _ = bvh.find_nearest(pts3[i0])
        if loc is not None and (pts3[i0] - loc).dot(nrm) > 0:
            break
        i0 += 1
    pts3 = pts3[i0:]; keys = keys[i0:]
    # root = where the centre line (extended back from the first clean rows) meets the leg surface
    d = (pts3[0] - pts3[1]).normalized()
    hit, _, _, dist_ = bvh.ray_cast(pts3[0], d, 0.05)
    root3 = hit if hit is not None else pts3[0]
    pts = [((p.y - A.y) / H, (p.z - A.z) / H) for p in [root3] + pts3]
    lm = landmarks(pts)
    rf = FOOT[name]
    for k in ("root", "arch_top", "rearmost", "lowest", "tip"):
        d = math.dist(lm[k], rf[k])
        if f"{name}.{k}" in ref.get("not_measurable", {}):
            row(f"  info: {name} tine {k} (not measurable in the reference)", tuple(rf[k]), tuple(lm[k]), True, "info")
            continue
        row(f"{name} tine {k} (f, dz in H rel. ankle)", tuple(rf[k]), tuple(lm[k]), d <= 0.1, "0.1 H")
    L = plen(pts)
    row(f"{name} tine path length (H)", rf["path_len_H"], L, abs(L / rf["path_len_H"] - 1) <= 0.10, "10%")
    # profile thickness at 1/4, 1/2, 3/4 of the rows: extent across the centre line in the side plane
    for key, frac in (("root_third", 0.25), ("mid", 0.5), ("tip_third", 0.75)):
        i = min(len(keys) - 2, max(1, int(len(keys) * frac)))
        tg = (yz(pts3[i + 1]) - yz(pts3[i - 1])).normalized(); nn = Vector((-tg.y, tg.x))
        vs = {v for f in buckets[keys[i]] for v in f.verts}
        ds = [(yz(v.co) - yz(pts3[i])).dot(nn) for v in vs]
        th = max(ds) - min(ds)
        vals = [ref[leg]["foot_H"][name]["thickness_m"][key] for leg in ("near", "far")]
        vals = [x for x in vals if 0.002 < x < 0.009]
        if not vals:      # both reference values contaminated by the neighbouring tine: mean of the clean ones
            vals = [ref[leg]["foot_H"][name]["thickness_m"][k2] for leg in ("near", "far")
                    for k2 in ("root_third", "tip_third")]
            vals = [x for x in vals if 0.002 < x < 0.009]
        rt = sum(vals) / len(vals)
        row(f"{name} tine thickness {key} (m, profile)", rt, th, abs(th / rt - 1) <= 0.15 or abs(th - rt) <= 0.0011,
            "15% or 1 px")

# ---- connectivity per side: one component from the cut (hip) through the tines
for side in (-1, 1):
    fs = {f for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * side > 0}
    seen, comps = set(), []
    for f0 in sorted(fs, key=lambda f: f.index):
        if f0 in seen: continue
        comp = {f0}; stack = [f0]; seen.add(f0)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in fs and g not in seen:
                        seen.add(g); comp.add(g); stack.append(g)
        comps.append(comp)
    parts = {int(round(f[lp])) for f in comps[0]}
    top = max(v.co.z for f in comps[0] for v in f.verts)
    ok = len(comps) == 1 and {1, 4, 7, 10, 11, 12} <= parts and abs(top - 0.78) < 1e-3
    row(f"leg {'left' if side < 0 else 'right'}: connected components hip->tines", 1,
        f"{len(comps)} comp, parts {sorted(parts)}, top z {top:.3f}", ok, "1")
nme = [e for e in bm.edges if not e.is_manifold and e.link_faces and all(f.material_index == 1 for f in e.link_faces)]
nm = len(nme)
for e in nme[:8]:
    print("non-manifold leg edge at", tuple(round(c, 4) for c in (e.verts[0].co + e.verts[1].co) / 2),
          "faces", len(e.link_faces), "parts", sorted({int(round(f[lp])) for f in e.link_faces}))
row("leg non-manifold edges", 0, nm, nm == 0, "0")

# ---- budgets / contract
tris = sum(len(f.verts) - 2 for f in bm.faces)
row("triangles", "<= 20000", tris, tris <= 20000, "budget")
zs = [v.co.z for v in bm.verts]
row("head top z (m)", 1.75, max(zs), abs(max(zs) - 1.75) < 0.002, "2 mm")
row("lowest z (m)", 0.0, min(zs), abs(min(zs)) < 1e-4, "0.1 mm")
row("materials", "<= 2", len(me.materials), len(me.materials) <= 2, "budget")
imgs = [i for i in bpy.data.images if i.size[0] > 0]
mx = max([max(i.size) for i in imgs] or [0]); mem = sum(i.size[0] * i.size[1] * 4 for i in imgs) / 2 ** 20
row("max texture size (px)", "<= 2048", mx, mx <= 2048, "budget")
row("texture memory RGBA8 (MB)", "<= 64", round(mem, 1), mem <= 64, "budget")
hand = [v.co for v in bm.verts if abs(v.co.x) > 0.19 and 0.6 < v.co.z < 1.0
        and not any(f.material_index == 1 for f in v.link_faces)]
from mathutils.kdtree import KDTree
lv = [v.co.copy() for v in {v for f in bm.faces if f.material_index == 1 for v in f.verts}]
kd = KDTree(len(lv))
for i, c in enumerate(lv): kd.insert(c, i)
kd.balance()
hc = min(kd.find(c)[2] for c in hand)
row("hand clearance to legs (m)", ">= 0.02", hc, hc >= 0.02, "contract")
cont = [c.y for c in lv if c.z < 0.004]
row("feet under the hip midpoint: contact y span contains hip y", f"hip y {Hp.y:.3f}",
    f"contact {min(cont):+.3f}..{max(cont):+.3f}", min(cont) <= Hp.y <= max(cont), "contract")
row("  info: miss distance hip y - contact front (m)", 0.0, Hp.y - max(cont), True, "info")

w = max(len(r[0]) for r in rows)
lines = [f"{'quantity':<{w}}  {'reference':>34}  {'model':>34}  result  tol"]
for name, rv, mv, res, tol, _ in rows:
    lines.append(f"{name:<{w}}  {fmt(rv):>34}  {fmt(mv):>34}  {res:<6}  {tol}")
npass = sum(1 for r in rows if r[3] == "PASS" and r[4] != "info"); nall = sum(1 for r in rows if r[4] != "info")
lines.append(f"SUMMARY {npass}/{nall} PASS  (knee ring verts {nk}, hock {nj}, ankle {na}; hip {tuple(round(c,4) for c in Hp)}, "
             f"knee {tuple(round(c,4) for c in K)}, hock {tuple(round(c,4) for c in J)}, ankle {tuple(round(c,4) for c in A)})")
txt = "\n".join(lines)
print(txt)
os.makedirs(os.path.dirname(OUTTXT), exist_ok=True)
open(OUTTXT, "w").write(txt + "\n")
