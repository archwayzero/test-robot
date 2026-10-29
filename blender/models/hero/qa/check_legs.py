"""Step C: measure the leg landmarks on hero_model.blend and compare with reference_landmarks.json.
usage: blender -b blender/models/hero/hero_model.blend -P blender/models/hero/qa/check_legs.py [-- <out.txt>]
Model landmarks come from the geometry (face attributes lm_part / lm_t written by conform.py mark which loft
ring / tine row a face belongs to): ring centroids for knee / hock / ankle, row centroids for the tine centre
lines, slab cross-sections for thicknesses. Side-view quantities use the (y, z) projection like the reference.
The near (character's left, -X) leg is measured; the rest pose is symmetric.
usage tail: [-- <out.txt> [<glb>]]; the glb (default godot/assets/hero/model/hero.glb) is checked for leg non-manifold edges."""
import bpy, bmesh, json, math, os, sys
import re as _re
CUT_Z = float(_re.search(r"^CUT_Z = ([0-9.]+)", open("/home/archwayzero/game/blender/models/hero/conform.py").read(), _re.M).group(1))
from mathutils import Vector
R = "/home/archwayzero/game/"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTTXT = argv[0] if argv else R + ".captures/T011/v6/check_legs.txt"
ref = json.load(open(R + "blender/models/hero/qa/reference_landmarks.json"))
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

# ---- thigh plate depth (side view): horizontal slice of the plate (parts 1 plate, 2 groove, 3 rim) at the reference rows
plate_f = [f for f in legf if part(f) in (1, 2, 3)]
PPM_REF = 793 / 1.75
for key, dref in ref["plate"]["depth_side_m"].items():
    yrow = float(key.split("(y ")[1].rstrip(")"))
    zq = (801.0 - yrow) / PPM_REF
    ys = []
    for f in plate_f:
        P = [v.co for v in f.verts]
        for i in range(len(P)):
            a_, b_ = P[i], P[(i + 1) % len(P)]
            if (a_.z - zq) * (b_.z - zq) < 0:
                ys.append(a_.lerp(b_, (zq - a_.z) / (b_.z - a_.z)).y)
    dep = max(ys) - min(ys) if ys else 0.0
    row(f"thigh plate depth at {key.split(' (')[0]} (z {zq:.3f}) (m, side view)", dref, dep, abs(dep / dref - 1) <= 0.03, "3%")

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
def section_iv(c, u, n, faces):
    """like section(), but returns the chosen merged interval (lo, hi) along n relative to c (None if empty)"""
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
        return None
    iv.sort()
    merged = [list(iv[0])]
    for a_, b_ in iv[1:]:
        if a_ <= merged[-1][1] + 0.001:
            merged[-1][1] = max(merged[-1][1], b_)
        else:
            merged.append([a_, b_])
    k = min(range(len(merged)), key=lambda i: 0 if merged[i][0] <= 0 <= merged[i][1]
            else min(abs(merged[i][0]), abs(merged[i][1])))
    return merged[k]
loft2d = [f for f in legf if part(f) in (4, 5, 6)]
def inside2d(p):
    """p (3D) inside the side-view silhouette of the knee..ankle loft (section across the knee->ankle line)"""
    q = yz(p)
    c = yz(K) + u * (q - yz(K)).dot(u)
    iv = section_iv(c, u, n, loft2d)
    return iv is not None and iv[0] <= (q - c).dot(n) <= iv[1]
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
    low = pts[ilow]
    if ilow > 0:      # model rows are sparser than the traced pixels: interpolate the crossing of zmin + 0.01
        a_, b_ = pts[ilow - 1], pts[ilow]
        u_ = (a_[1] - (zmin + 0.01)) / (a_[1] - b_[1]) if a_[1] != b_[1] else 1.0
        low = (a_[0] + (b_[0] - a_[0]) * u_, a_[1] + (b_[1] - a_[1]) * u_)
    return {"root": pts[0], "arch_top": pts[ia], "rearmost": pts[irear], "lowest": low, "tip": pts[-1]}
def plen(p): return sum(math.dist(p[i], p[i - 1]) for i in range(1, len(p)))
TINE_SIDES = 8
CONTAM_PX = 3.0   # two ~2.7 px dark lines closer than this merge into one dip
def _seg_dist(p, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(p[0] - ax - dx * t, p[1] - ay - dy * t)
def contaminated(leg, name, key):
    """same sample index as ref_landmarks.tine_thickness; True if another tine's centre line passes within CONTAM_PX"""
    tines = ref["landmarks_px"][leg]["tines"]
    path = tines[name]
    i = {"root_third": max(2, len(path) // 4), "mid": len(path) // 2, "tip_third": len(path) * 3 // 4}[key]
    p = path[i]
    return any(_seg_dist(p, o[j - 1], o[j]) < CONTAM_PX for on, o in tines.items() if on != name
               for j in range(1, len(o)))
tine_xs = {}
for name, pid in (("outer", 10), ("middle", 11), ("inner", 12)):
    fs = [f for f in legf if part(f) == pid]
    buckets = {}
    for f in fs:
        buckets.setdefault(round(f[lt], 5), []).append(f)
    keys = sorted(buckets)
    # rings between consecutive rows (row k = quads between ring k and ring k+1, tagged with ring k's arclength
    # fraction); a ring is clean when both rows are intact rings of TINE_SIDES quads (not cut by the union)
    def clean_row(k):
        return len(buckets[k]) == TINE_SIDES and all(len(f.verts) == 4 for f in buckets[k])
    trings = []
    for j in range(1, len(keys)):
        sv = {v for f in buckets[keys[j - 1]] for v in f.verts} & {v for f in buckets[keys[j]] for v in f.verts}
        if sv:
            trings.append((keys[j], sum((v.co for v in sv), Vector()) / len(sv), sv,
                           len(sv) == TINE_SIDES and clean_row(keys[j - 1]) and clean_row(keys[j])))
    def ring_at(frac):
        cands = [i for i, r in enumerate(trings) if r[3] and 0 < i < len(trings) - 1]
        i = min(cands, key=lambda i: abs(trings[i][0] - frac))
        tg = (yz(trings[i + 1][1]) - yz(trings[i - 1][1])).normalized(); nn = Vector((-tg.y, tg.x))
        ds = [(yz(v.co) - yz(trings[i][1])).dot(nn) for v in trings[i][2]]
        xs = [v.co.x for v in trings[i][2]]
        return max(ds) - min(ds), max(xs) - min(xs), trings[i][0]
    # centre line: every row's centroid (rows partly merged into a neighbouring tine are kept: their centroid moves by
    # less than the blade half thickness, ~0.013 H). Pass 6: rows cut by the union with the leg are kept too when
    # their centroid lies OUTSIDE the leg loft (a root lying on the shin surface is visible from where it surfaces);
    # the leading rows whose centroid is inside the loft (wings of a blade crossing the spring core) are dropped.
    pts3 = []
    for k in keys:
        vs = {v for f in buckets[k] for v in f.verts}
        pts3.append(sum((v.co for v in vs), Vector()) / len(vs))
    def outside(p):
        loc, nrm, _, _ = bvh.find_nearest(p)
        return loc is not None and (p - loc).dot(nrm) > 0
    i0 = 0
    while i0 < len(pts3) - 3 and not (outside(pts3[i0]) and outside(pts3[i0 + 1])):
        i0 += 1
    pts3 = pts3[i0:]; keys = keys[i0:]
    # root = where the centre line, extended back from the first outside row, enters the leg's SIDE-VIEW silhouette
    # (knee/shin/spring/ankle loft, 2D like the reference trace; a 3D ray would pass through the hole the union cut
    # in the spring where the blade crosses it). 0.5 mm steps, up to 6 cm.
    d = (pts3[0] - pts3[1]).normalized()
    root3 = pts3[0]
    for k_ in range(1, 121):
        q = pts3[0] + d * (0.0005 * k_)
        if inside2d(q):
            root3 = q
            break
    pts = [((p.y - A.y) / H, (p.z - A.z) / H) for p in [root3] + pts3]
    if os.environ.get("CHECK_DEBUG"):
        print("CENTRE", name, [(round(a_, 3), round(b_, 3)) for a_, b_ in pts])
        print("BUCKETS", name, [(round(k, 3), len(buckets[k])) for k in sorted(buckets)])
    lm = landmarks(pts)
    rf = FOOT[name]
    for k in ("root", "arch_top", "rearmost", "lowest", "tip"):
        d = math.dist(lm[k], rf[k])
        if f"{name}.{k}" in ref.get("merged_end", {}):
            # the reference tine's end runs on top of another tine's line: the visible end is where the two lines
            # meet. Model: the last row before the tine disappears into its neighbour; it must lie on the
            # reference's shared stretch.
            far = ref["landmarks_px"]["far"]; ax_, ay_ = far["ankle"]; Hpx = ref["far"]["H_px"]
            sh = [((ax_ - x) / Hpx, (ay_ - y) / Hpx) for x, y in far["tines"][name][ref["merged_end"][f"{name}.{k}"]:]]
            dd = min(_seg_dist(lm[k], sh[j - 1], sh[j]) for j in range(1, len(sh)))
            row(f"{name} tine {k} = merge into the outer: distance to the shared stretch (H)", 0.0, dd, dd <= 0.05, "0.05 H")
            continue
        if f"{name}.{k}" in ref.get("not_measurable", {}):
            row(f"  info: {name} tine {k} (not measurable in the reference)", tuple(rf[k]), tuple(lm[k]), True, "info")
            continue
        row(f"{name} tine {k} (f, dz in H rel. ankle)", tuple(rf[k]), tuple(lm[k]), d <= 0.05, "0.05 H")
    L = plen(pts)
    row(f"{name} tine path length (H)", rf["path_len_H"], L, abs(L / rf["path_len_H"] - 1) <= 0.10, "10%")
    # profile thickness / front width at 1/4, 1/2, 3/4 of the tine's arclength, measured on a clean ring
    # (the ring plane is perpendicular to the centre line: thickness = side-plane extent, width = X extent)
    meas = {}
    for key, frac in (("root_third", 0.25), ("mid", 0.5), ("tip_third", 0.75)):
        th, wd, tr = ring_at(frac)
        meas[key] = (th, wd)
        # reference value: both legs, minus the samples contaminated by a neighbouring tine (another traced tine
        # centre line within CONTAM_PX of the sample point: the two dark lines merge into one dip)
        vals = [ref[leg]["foot_H"][name]["thickness_m"][key] for leg in ("near", "far")
                if not contaminated(leg, name, key) and 0.002 < ref[leg]["foot_H"][name]["thickness_m"][key] < 0.012]
        if f"{name}.thickness_{key}" in ref.get("not_measurable", {}):
            row(f"  info: {name} tine thickness {key} (not measurable in the reference)",
                ref["far"]["foot_H"][name]["thickness_m"][key], th, True, "info")
            continue
        if not vals:      # both contaminated: mean of all clean root/tip-third samples (blade base thickness)
            vals = [ref[leg]["foot_H"][t]["thickness_m"][k2] for leg in ("near", "far") for t in ("outer", "middle", "inner")
                    for k2 in ("root_third", "tip_third") if not contaminated(leg, t, k2)]
        rt = sum(vals) / len(vals)
        row(f"{name} tine thickness {key} (m, profile)", rt, th, abs(th / rt - 1) <= 0.15 or abs(th - rt) <= 0.0011,
            "15% or 1 px")
    rw = ref["tine_width_front_m (legs_000 rows 380-420)"]
    th, wd = meas["mid"]
    row(f"{name} tine front width mid (m, blade)", rw, wd, abs(wd / rw - 1) <= 0.15, "15%")
    th, wd = meas["root_third"]
    row(f"{name} tine blade aspect root third (width / profile thickness)", "3.0 .. 4.5", wd / th,
        3.0 <= wd / th <= 4.5, "3-4.5")
    th, wd = meas["mid"]
    row(f"  info: {name} tine blade aspect mid", "", wd / th, True, "info")
    tine_xs[name] = [v.co.x for f in fs for v in f.verts if v.co.z < A.z - 0.02]

allx = [x for v in tine_xs.values() for x in v]
row("foot bundle front width below the ankle (m, all three tines)", ref["tine_width_front_m (legs_000 rows 380-420)"],
    max(allx) - min(allx), abs((max(allx) - min(allx)) / ref["tine_width_front_m (legs_000 rows 380-420)"] - 1) <= 0.15,
    "15%")

# ---- projected ribbon widths at the rear arch in the 45 deg turnaround view, measured like the reviewer measures the
# images: horizontal dark runs on the 864x480 frame (orthographic, qa/render.py 'legs': camera at azimuth 45 deg,
# 480 px over 0.967 m = 496.4 px/m). Here every leg face of the near leg is sliced by the horizontal plane of the
# scanline (the camera is level within 1.6 deg), the slices are projected on the camera's horizontal axis and
# overlapping intervals are merged into runs, exactly what the image shows as one dark run (verified against
# Cycles renders, +-1 px). 9 scanlines from the inner tine's rearmost point up 0.30 H. In the 45 deg view the
# outer and middle tines overlap into one "rear ribbon" run and the inner tine is the separate "front ribbon" run,
# as in legs_045.png (near foot rows 365-395: front 9-10 px, rear 11-14 px; far foot 9-11 / 12-13 px).
PPM45 = 480 / 0.967
rw45 = ref["tine_rear_arch_width_045_px"]
def runs_at(z0, az_deg):
    az = math.radians(az_deg)
    right = Vector((-math.cos(az), -math.sin(az), 0))     # camera at (-sin a, cos a) * d looking at the origin
    ivs = []
    for f in legf:
        P = [v.co for v in f.verts]
        xs = []
        for i in range(len(P)):
            a_, b_ = P[i], P[(i + 1) % len(P)]
            if (a_.z - z0) * (b_.z - z0) < 0:
                xs.append(a_.lerp(b_, (z0 - a_.z) / (b_.z - a_.z)).dot(right) * PPM45)
        if xs:
            ivs.append((min(xs), max(xs), part(f)))
    ivs.sort(key=lambda r: (r[0], r[1], r[2]))
    out = []
    for lo, hi, p in ivs:
        if out and lo <= out[-1][1] + 0.5:       # touching within half a pixel = one dark run
            out[-1][1] = max(out[-1][1], hi); out[-1][2].add(p)
        else:
            out.append([lo, hi, {p}])
    return out
inner_f = [f for f in legf if part(f) == 12 and f.calc_center_median().z < A.z]
z_rear = min({v for f in inner_f for v in f.verts}, key=lambda v: (v.co.y, v.index)).co.z
fw, rw, per = [], [], {10: [], 11: [], 12: []}
for j in range(9):
    z0 = z_rear + j * 0.30 * H / 8
    rs = runs_at(z0, 45)
    fr = [r for r in rs if 12 in r[2] and 10 not in r[2]]
    rr = [r for r in rs if 10 in r[2]]
    if fr: fw.append(fr[0][1] - fr[0][0])
    if rr: rw.append(rr[0][1] - rr[0][0])
fw.sort(); rw.sort()
fmed = fw[len(fw) // 2] if fw else 0.0
rmed = rw[len(rw) // 2] if rw else 0.0
row(f"front ribbon (inner tine) dark-run width at the rear arch, 45 deg view (px, median of {len(fw)}/9 scanlines)",
    f"{rw45['front ribbon'][0]}-{rw45['front ribbon'][1]}", round(fmed, 1), len(fw) >= 7 and
    rw45['front ribbon'][0] <= fmed <= rw45['front ribbon'][1], "ref range")
row(f"rear ribbon (outer + middle) dark-run width at the rear arch, 45 deg view (px, median of {len(rw)}/9 scanlines)",
    f"{rw45['rear ribbon'][0]}-{rw45['rear ribbon'][1]}", round(rmed, 1), len(rw) >= 7 and
    max(11, rw45['rear ribbon'][0]) <= rmed <= rw45['rear ribbon'][1], ">= 11 px, ref range")
row("  info: 45 deg dark-run widths per scanline (front / rear, px)", "",
    " ".join(f"{x:.1f}" for x in fw) + " / " + " ".join(f"{x:.1f}" for x in rw), True, "info")
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
    ok = len(comps) == 1 and {1, 4, 7, 10, 11, 12} <= parts and abs(top - CUT_Z) < 1e-3
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
# dropped by the orchestrator (pass 5): the rest pose keeps the reference angles, the rigger sets the idle pose
row("  info: feet under the hip midpoint (dropped): contact y span vs hip y", f"hip y {Hp.y:.3f}",
    f"contact {min(cont):+.3f}..{max(cont):+.3f}", True, "info")

# ---- exported glb: leg faces welded at 1e-6 must be manifold (export splits verts at UV/normal seams)
GLB = argv[1] if len(argv) > 1 else R + "godot/assets/hero/model/hero.glb"
if os.path.exists(GLB):
    for o in list(bpy.data.objects):
        o.select_set(False)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=GLB)
    gobj = [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]
    gm = gobj.data
    li = [i for i, m in enumerate(gm.materials) if m and m.name.startswith("hero_legs")]
    gb = bmesh.new(); gb.from_mesh(gm)
    bmesh.ops.remove_doubles(gb, verts=gb.verts, dist=1e-6)
    gne = [e for e in gb.edges if not e.is_manifold and e.link_faces and all(f.material_index in li for f in e.link_faces)]
    for e in gne[:8]:
        print("glb non-manifold leg edge at", tuple(round(c, 4) for c in (e.verts[0].co + e.verts[1].co) / 2),
              "faces", len(e.link_faces))
    gtris = sum(len(f.verts) - 2 for f in gb.faces)
    row("glb: leg non-manifold edges after weld 1e-6", 0, len(gne), len(gne) == 0 and bool(li), "0")
    row("glb: triangles", "<= 20000", gtris, gtris <= 20000, "budget")
else:
    row("glb: leg non-manifold edges after weld 1e-6", 0, "glb missing", False, "0")

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
