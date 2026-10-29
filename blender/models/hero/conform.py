"""T011 hero conform (pass 7): Tripo upper body (provided) + continuous digitigrade legs -> hero_model.blend.

Build (re-runnable, deterministic), then export:
  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b -P blender/models/hero/conform.py
  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- \
    blender -b blender/models/hero/hero_model.blend -P tools/blender/export_gltf.py -- \
    --out godot/assets/hero/model/hero.glb --no-anim
Check: blender -b blender/models/hero/hero_model.blend -P blender/models/hero/qa/check_legs.py

Steps:
  1. Import source/hero.glb (untouched), merge split vertices, drop the encoded custom normals.
  2. Cut the Tripo thighs at the hip line (z = CUT_Z = 0.79 m after scaling, below the hip disc and under the
     hand): everything of the thighs below it is removed; one clean boundary loop per side remains.
  3. Build ONE continuous leg per side (bmesh), welded to that loop, measured on reference/hero/full_body.png
     (landmark sheet: qa/ref_landmarks.py -> qa/reference_landmarks.json; 453 px/m):
       - thigh plate: lofted from the cut loop. The first ring continues the Tripo surface along its tangent
         (measured against the body section 1.5 cm above the cut) and eases into the plate section (flush join: no
         lip, no groove); two telescoping segment lines at the reference z 0.737 / 0.631 (3 bands as in the
         reference), boxy superellipse sections, a slanted bottom edge (back 2 cm higher) that rolls inwards into
       - the knee / shin: the same surface continues as an 18-sided loft (stations densified with Catmull-Rom, no
         visible kinks): knee bulb under the plate (depth 9 cm), tapering shin slanting back, a back-of-shin bulge
         and a sharp hock (the back edge stops converging and runs down the metatarsal), the metatarsal
         (12-sided), a coil-spring thread (4 turns) and the ankle cap.
       - knee pod: capsule at the plate's front-bottom (front flush with the plate front, 4 mm proud of its side,
         bottom 2.2 cm below the knee), boolean-unioned; its union boundary is a sharp crease (own outline).
       - three reverse-C tines per foot nested into one blade bundle (lateral offsets +-1 mm): flat blades
         (rounded-rectangle section, 24 -> 20 mm wide (outer widest), ~5-6 mm thick, outer rear arch 9 mm; the last
         0.4 H a constant flat ribbon with a blunt end), centrelines = the traced reference polylines of the planted
         foot (in ankle heights H), one ring pinned on each rear arch, boolean-unioned (welded). The outer tine's
         root grows out of the back of the metatarsal: buried start, narrow / thin where it meets the surface,
         lying on the surface while the trace runs along it, then widening (no proud squared top).
       - cleanup after the union: merge near-coincident vertices (1e-5), dissolve_degenerate, triangulate the
         boolean n-gons, delete back-to-back duplicate triangles and fix zero-area slivers, so the exported glb is
         manifold after any weld.
     Edge loops at the hip (cut loop), the plate grooves, the knee, the hock, the ankle and along the tines.
     Face attributes kept in the .blend for measurement / weighting (not exported): lm_part (1 plate, 2 groove,
     3 rim, 4 shin, 5 spring, 6 ankle, 7 pod, 10/11/12 outer/middle/inner tine), lm_t (position along the part).
  4. Decimate the upper body so body + legs <= TRI_TARGET (face, hands and the cut loops protected).
  5. Rotate 180 deg about Z (front -> Blender +Y -> Godot -Z), scale so the hood top is at 1.75 m, join, weld.
  6. Leg UVs (one island per loft section / part, shelf-packed), second PBR material with Cycles-baked procedural
     textures (base colour 1024, normal 1024, roughness/metallic 512); rust coverage calibrated on the baked noise:
     Tripo-matched next to the seam, the reference's heavy ochre on the plates, dark segment lines, sparse rust
     on the darker shins and feet.
  7. Body textures: base colour 4096 -> 2048, roughness/metallic 2048 -> 1024, normal kept at 2048.
  8. Save hero_model.blend (images packed). Export separately (command above).
"""
import array
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source", "hero.glb")
OUT = os.path.join(HERE, "hero_model.blend")
TEX = os.path.join(HERE, "textures")

HEAD_TOP = 1.75          # m, hood top
SCALE = 1.12             # upper-body scale (proportions measured against reference/hero/full_body.png)
TRI_TARGET = 19950       # total, leaves margin under the 20,000 character budget
CUT_Z = 0.79            # m (final): Tripo thighs are cut here (one simple loop per side, below the hip disc)
LEG_TEX = {"basecolor": 1024, "normal": 1024, "rm": 512}

# ---- measured leg layout (reference_landmarks.json; near leg unless noted). Rest pose = neutral standing.
HIP = (0.0686, 0.8708)   # hip joint (y, z): centre of the Tripo hip disc (reference: disc centre, z 0.881)
THIGH_LEN = 0.4245       # hip -> knee (reference near leg)
THIGH_FWD_DEG = 2.0      # rest-pose thigh tilt forward (pose-dependent; the reference near leg is 9 deg BACK)
SPLAY_THIGH_DEG = 3.0    # front view: the plates splay outwards (legs_000)
SPLAY_SHIN_DEG = 5.0
KNEE_TO_ANKLE = 0.2606   # mean of the near (0.2626) and far (0.2587) legs
HOCK_T = 0.4855          # hock position along knee -> ankle (shin 0.1266 / metatarsal 0.1342)
ANKLE_Z = 0.2229         # H = ankle height of the planted reference foot (101 px)
PLATE_GROOVE_Z = (0.737, 0.631)       # segment lines (reference z, near plate); the first visible line below the seam
PLATE_BOTTOM_UP = (0.016, 0.035)      # plate bottom above the knee centre along the thigh: front, back
# shin side profile: (t along knee->ankle, depth, width, forward offset of the centre from the knee-ankle line);
# depth/offset from the near reference shin edges, width from the front view (legs_000)
# pass 5: back-of-shin bulge (+4 mm at t 0.38-0.43) and a sharper hock: the back edge stops converging at the hock and
# runs parallel down the metatarsal (reference near back edge (182,626) -> (186,633) -> (194,640): -14.6 / -10.9 /
# -13.9 mm from the knee-ankle line at t 0.43 / 0.50 / 0.59); pass 6: hock / upper metatarsal depth 32 -> 29 mm
# (reference side-view thickness at 50 %: 28.7 mm; the outer tine root now lies on the back there)
SHIN_ST = [(0.00, 0.090, 0.076, 0.000), (0.13, 0.082, 0.070, -0.0045), (0.25, 0.064, 0.058, -0.0070),
           (0.38, 0.042, 0.042, -0.0005), (0.43, 0.037, 0.038, 0.0020), (HOCK_T, 0.029, 0.035, 0.0045),
           (0.58, 0.029, 0.033, 0.0040)]
META_ST = [(0.65, 0.028, 0.031, 0.0040), (0.76, 0.024, 0.028, 0.0030), (0.84, 0.022, 0.026, 0.0020)]
SHIN_SIDES = 18          # upper shin loft (knee bulb .. hock); the metatarsal / spring / ankle stay 12-sided
SHIN_SUBDIV = 0.07       # extra interpolated rings (Catmull-Rom through the stations) where a span exceeds this t
SPRING_T = (0.865, 0.985)
SPRING_CORE, SPRING_AMP, SPRING_TURNS, SPRING_RPT = 0.0085, 0.0045, 4.0, 6
ANKLE_ST = [(1.00, 0.021, 0.022, 0.0), (1.035, 0.017, 0.018, 0.0)]
# knee pod: front flush with the plate front, 4 mm proud of the plate side, bottom 2.2 cm below the knee centre
# (reference near pod outline y 551..602 vs knee centre y 592), creased along the union boundary
POD = {"up": (-0.012, 0.080), "fwd_gap": 0.012, "r_fwd": 0.026, "r_lat": 0.036, "out": 0.020, "cap": 0.010}
# tines: traced centrelines of the planted (far) reference foot, px; ankle (141, 699), H = 101 px
REF_ANKLE_PX, REF_H_PX = (141.0, 699.0), 101.0
TINE_PX = {
    "outer": [(118, 643), (127, 658), (131, 664), (139, 673), (150, 681), (160, 686), (170, 689), (181, 691), (191, 694),
              (201, 699), (210, 704), (219, 716), (223, 726), (225, 734), (222, 746), (216, 758), (208, 768), (196, 778),
              (186, 786), (176, 793), (166, 798), (158, 800), (140, 800), (120, 800), (104, 800)],
    "middle": [(132, 683), (140, 684), (150, 685), (160, 689), (170, 692), (181, 694), (191, 697), (200, 702), (208, 708),
               (215, 718), (219, 728), (218, 740), (213, 756), (205, 768), (195, 778), (186, 786), (180, 790)],
    "inner": [(143, 697), (150, 696), (160, 696), (170, 698), (180, 703), (190, 710), (197, 720), (200, 730), (201, 742),
              (200, 754), (196, 766), (190, 776), (184, 781)],
}
# pass 7: px shift towards the heel (+x) per traced point, applied on top of the trace. The inner tine's rear arch
# sat ~8 mm too far forward in profile: legs_045 near foot shows a 2-4 px gap between the front (inner) and rear
# (outer + middle) ribbons, the model had 5-8 px. Root, arch top, tip and the planted-foot landmarks stay within 0.05 H.
TINE_SHIFT_PX = {"inner": [0, 0, 0, 0, 1.2, 3.0, 4.2, 4.3, 4.4, 3.5, 1.9, 0.7, 0]}
# flat blades nested into one bundle (legs_000/045/225: one ~14 mm blade per foot in the front view):
# (lateral offset outward m, half width lateral root/tip, half thickness in profile root/tip, samples, part id,
#  (arch half thickness, arch start, arch end) or None). Rounded-rectangle section (superellipse TINE_N[name], TINE_SIDES).
# pass 6: front width re-measured on legs_000 rows 380-420 (near blade 11-13 px, mean 11.8 px at 496 px/m = 0.024 m):
# blades 24 -> 20 mm wide (outer widest, so at 225 deg it reads as the broad ribbon with the inner tines inside it)
TINE_SPEC = {"outer": (0.001, (0.0124, 0.0104), (0.0028, 0.0028), 26, 10, (0.0045, 0.40, 0.70)),
             "middle": (-0.001, (0.0120, 0.0100), (0.0028, 0.0023), 17, 11, None),
             "inner": (-0.001, (0.0118, 0.0099), (0.0027, 0.0033), 14, 12, None)}
TINE_SIDES = 8
# superellipse exponent per tine: the inner tine (the separate front ribbon at 45 deg) is a squarer flat strip so its
# 8-vertex section keeps its corners (an n = 3 octagon cuts them: 45 deg projection 7.5 px instead of 9-10 px)
TINE_N = {"outer": 3.0, "middle": 3.0, "inner": 10.0}
# rear-arch widening (pass 6): extra half width (m) around each tine's rearmost row, smoothstep over +-ARCH_WIDEN_H
# of arclength. legs_045 shows the ribbons broader at the rear arches (front ribbon 9-10 px, rear 11-14 px at 496 px/m)
# than a 20-22 mm blade gives there; profile thickness and the front-view widths elsewhere are unchanged.
ARCH_WIDEN = {"outer": 0.0010, "middle": 0.0008, "inner": 0.0012}
ARCH_WIDEN_H = 0.35
TINE_FLAT_END_H = 0.4    # last 0.4 H of every tine: constant-section flat ribbon, blunt end (no needle taper)
# outer tine root (pass 6): blended into the back of the metatarsal instead of entering through the shin axis.
# The centre line starts buried ROOT_SINK below the back surface ROOT_RUN (t along knee->ankle) above the root,
# reaches the surface at the back-surface point nearest the reference root, then lies on the surface (glued) while
# the traced line stays within ROOT_GLUE of it; width / thickness ramp up from ROOT_W0 / ROOT_T0 over ROOT_RAMP_H.
ROOT_RUN, ROOT_SINK, ROOT_GLUE, ROOT_LIFT = 0.09, 0.0065, 0.012, 0.0015
ROOT_W0, ROOT_T0, ROOT_RAMP_H = 0.0040, 0.0010, 0.40
MID_ROOT_W0, MID_ROOT_RAMP_H = 0.012, 0.35   # middle / inner: 12 mm wide where they leave the spring core
# rust coverage (fraction of the surface classified as rust, same classifier as the Tripo sampling)
RUST_FRAC_PLATE = 0.37                # measured on the near reference plate (qa/ref_rust.py)
RUST_THR_SHIN = 0.66
REF_RUST_LO, REF_RUST_HI = (0.056, 0.032, 0.010), (0.159, 0.084, 0.021)   # measured (linear)
RUST_EDGE = 0.025
SEAM_FULL, SEAM_BLEND = 0.012, 0.050  # m below the seam: Tripo density down to 1.2 cm, plate density from 5 cm
PLATE_BOTTOM_Z = 0.47                 # lowest plate height (rust calibration region)


def log(*a):
    print("[conform]", *a, flush=True)


# ----------------------------------------------------------------------------------------------- import
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
for o in list(bpy.data.objects):
    if o is not obj:
        bpy.data.objects.remove(o)
obj.name = obj.data.name = "hero"
me = obj.data
src_tris = sum(len(p.vertices) - 2 for p in me.polygons)
if "custom_normal" in me.attributes:
    me.attributes.remove(me.attributes["custom_normal"])
body_mat = me.materials[0]
body_mat.name = "hero_body"

bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
TOP_SRC = max(v.co.z for v in bm.verts)
# final transform: 180 deg about Z (front -> +Y), uniform scale, hood top at HEAD_TOP
M = (Matrix.Translation((0, 0, HEAD_TOP - TOP_SRC * SCALE)) @ Matrix.Diagonal((SCALE, SCALE, SCALE, 1.0))
     @ Matrix.Rotation(math.pi, 4, "Z"))
CUT_SRC = (CUT_Z - (HEAD_TOP - TOP_SRC * SCALE)) / SCALE
LEG_X_SRC = 0.2 / SCALE  # thigh region |x| (the hands hang outside it)


def cut_thighs(bm):
    """Bisect the thighs at CUT_SRC and delete everything of them below. Returns {side: ordered loop verts}."""
    reg = [f for f in bm.faces if all(abs(v.co.x) < LEG_X_SRC for v in f.verts)
           and min(v.co.z for v in f.verts) < CUT_SRC]
    geom = list({e for f in reg for e in f.edges}) + reg + list({v for f in reg for v in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=(0, 0, CUT_SRC), plane_no=(0, 0, 1))
    below = [f for f in bm.faces if all(abs(v.co.x) < LEG_X_SRC for v in f.verts)
             and max(v.co.z for v in f.verts) <= CUT_SRC + 1e-7]
    bmesh.ops.delete(bm, geom=below, context="FACES")
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    return cut_loops(bm, CUT_SRC, 1e-6)


def cut_loops(bm, zc, tol):
    """{side: ordered boundary loop at height zc}, each starting at its back-most vertex."""
    out = {}
    bnd = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - zc) < tol for v in e.verts)]
    for side in (1, -1):
        es = [e for e in bnd if e.verts[0].co.x * side > 0]
        adj = {}
        for e in es:
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        assert adj and all(len(n) == 2 for n in adj.values()), "cut loop is not a simple loop"
        start = min(adj, key=lambda v: (v.co.y, v.co.x))
        loop, prev, cur = [start], None, start
        while True:
            if prev is None:
                nxt = min(adj[cur], key=lambda v: (v.co.x, v.co.y))
            else:
                nxt = [v for v in adj[cur] if v is not prev][0]
            if nxt is start:
                break
            loop.append(nxt)
            prev, cur = cur, nxt
        assert len(loop) == len(adj), "cut boundary has several loops on one side"
        out[side] = loop
    return out


loops_src = cut_thighs(bm)
log("source tris", src_tris, "cut loops", {s: len(l) for s, l in loops_src.items()})


def loop_tangents(loop, side, dz=0.015, max_slope=0.6):
    """Per cut-loop vertex: the downward direction of the Tripo surface just above the cut, in final coordinates
    (the leg loft continues along it: flush join). Measured against the body cross-section dz above the cut, at the
    same angle around the loop centre (robust to the thin bisect triangles); slope clamped to max_slope."""
    z1 = CUT_SRC + dz / SCALE
    cx = sum(v.co.x for v in loop) / len(loop)
    cy = sum(v.co.y for v in loop) / len(loop)
    rmax = max(math.hypot(v.co.x - cx, v.co.y - cy) for v in loop)
    pts = []
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - z1) * (b.z - z1) >= 0 or a.x * side <= 0:
            continue
        p = a.lerp(b, (z1 - a.z) / (b.z - a.z))
        if math.hypot(p.x - cx, p.y - cy) <= 1.3 * rmax:
            pts.append((math.atan2(p.y - cy, p.x - cx), p))
    pts.sort(key=lambda q: (q[0], q[1].x, q[1].y))
    R3 = M.to_3x3()
    out = []
    for v in loop:
        th = math.atan2(v.co.y - cy, v.co.x - cx)
        near = sorted(pts, key=lambda q: (abs((q[0] - th + math.pi) % (2 * math.pi) - math.pi), q[1].x, q[1].y))[:2]
        p = (near[0][1] + near[1][1]) / 2 if len(near) == 2 else Vector((v.co.x, v.co.y, z1))
        d = R3 @ (v.co - p)
        h = math.hypot(d.x, d.y)
        if h > max_slope * -d.z:
            d = Vector((d.x / h * max_slope * -d.z, d.y / h * max_slope * -d.z, d.z))
        out.append(d.normalized())
    return out


TANG_SRC = {s: loop_tangents(l, 1 if s > 0 else -1) for s, l in loops_src.items()}
for _s, _t in sorted(TANG_SRC.items()):
    _sl = [math.hypot(d.x, d.y) / -d.z for d in _t]
    log("cut loop", _s, "surface slope below the cut (horizontal / vertical): max", round(max(_sl), 3),
        "median", round(sorted(_sl)[len(_sl) // 2], 3))


# ----------------------------------------------------------------------------------------------- helpers
def catmull(pts, n):
    """Uniform Catmull-Rom through pts (Vectors), n samples, end points included."""
    P = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    segs = len(pts) - 1
    out = []
    for i in range(n):
        t = i / (n - 1) * segs
        k = min(int(t), segs - 1)
        u = t - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def resample_by_curvature(pts, n, k_turn=0.05, anchor=None):
    """Resample a dense polyline to n points, denser where it turns (weight = length + k_turn * angle).
    anchor (index into pts): the pair of consecutive samples whose midpoint is nearest to it is shifted (both by the
    same weight) so that the midpoint lies exactly on it (end samples never move)."""
    w = [0.0]
    for i in range(1, len(pts)):
        seg = (pts[i] - pts[i - 1]).length
        ang = 0.0
        if 0 < i < len(pts) - 1:
            a, b = pts[i] - pts[i - 1], pts[i + 1] - pts[i]
            if a.length > 1e-9 and b.length > 1e-9:
                ang = a.angle(b)
        w.append(w[-1] + seg + k_turn * ang)
    targets = [w[-1] * s / (n - 1) for s in range(n)]
    if anchor is not None:
        wa = w[anchor]
        k = min(range(1, n - 2), key=lambda i: (abs((targets[i] + targets[i + 1]) / 2 - wa), i))
        dlt = wa - (targets[k] + targets[k + 1]) / 2
        targets[k] += dlt
        targets[k + 1] += dlt
    out = []
    j = 0
    for target in targets:
        while j < len(w) - 2 and w[j + 1] < target:
            j += 1
        span = w[j + 1] - w[j]
        u = 0.0 if span <= 0 else min(1.0, max(0.0, (target - w[j]) / span))
        out.append(pts[j].lerp(pts[j + 1], u))
    return out


def polyline_length(pts):
    return sum((pts[i] - pts[i - 1]).length for i in range(1, len(pts)))


def superellipse(theta, a, b, n):
    c, s = math.cos(theta), math.sin(theta)
    return (a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s))


def frame(T):
    """Lateral (world +X sense) and forward (+Y sense) unit axes perpendicular to the tangent T."""
    T = T.normalized()
    X = Vector((1, 0, 0))
    L = (X - T * X.dot(T)).normalized()
    F = T.cross(L).normalized()
    if F.y < 0:
        F = -F
    return L, F


def angles_from(start, n, direction):
    return [start + direction * 2 * math.pi * j / n for j in range(n)]


def fractions(phis, direction):
    p0 = phis[0]
    return [((p - p0) * direction) % (2 * math.pi) / (2 * math.pi) for p in phis]


class Builder:
    def __init__(self, bm, mat_index):
        self.bm = bm
        self.uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        self.mat = mat_index
        self.islands = []
        self.lay = {k: bm.faces.layers.float.get(k) or bm.faces.layers.float.new(k)
                    for k in ("rustpart", "dark", "lm_part", "lm_t")}
        self.parts = {}

    def tag(self, faces, part, t=0.0, rust=0.0, dark=0.0, name=None):
        for f in faces:
            f[self.lay["lm_part"]] = part
            f[self.lay["lm_t"]] = t
            f[self.lay["rustpart"]] = rust
            f[self.lay["dark"]] = dark
        if name:
            self.parts[name] = self.parts.get(name, 0) + sum(len(f.verts) - 2 for f in faces)

    def face(self, verts, mat=None):
        f = self.bm.faces.new(verts)
        f.material_index = self.mat if mat is None else mat
        f.smooth = True
        return f

    def ring_strip(self, rings):
        """Quads between consecutive rings (equal length, closed); one UV island. Returns face rows."""
        n = len(rings[0])
        perims, cum = [], []
        for r in rings:
            d = [(r[(k + 1) % n].co - r[k].co).length for k in range(n)]
            c = [0.0]
            for x in d:
                c.append(c[-1] + x)
            perims.append(c[-1])
            cum.append(c)
        vpos = [0.0]
        for i in range(1, len(rings)):
            vpos.append(vpos[-1] + sum((rings[i][k].co - rings[i - 1][k].co).length for k in range(n)) / n)
        wmax = max(perims)
        uvs = [[Vector((cum[i][k] - perims[i] / 2 + wmax / 2, vpos[i])) for k in range(n + 1)]
               for i in range(len(rings))]
        isl, rows = [], []
        for i in range(len(rings) - 1):
            row = []
            for k in range(n):
                k1 = (k + 1) % n
                f = self.face((rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]))
                for loop, uv in zip(f.loops, (uvs[i][k], uvs[i][k + 1], uvs[i + 1][k + 1], uvs[i + 1][k])):
                    isl.append((loop, uv))
                row.append(f)
            rows.append(row)
        self.islands.append(isl)
        return rows

    def planar_island(self, faces, origin, ax, ay):
        isl = []
        for f in faces:
            for loop in f.loops:
                d = loop.vert.co - origin
                isl.append((loop, Vector((d.dot(ax), d.dot(ay)))))
        self.islands.append(isl)

    def zipper(self, A, fa, B, fb):
        """Triangles between ring A (fractions fa) and ring B (fractions fb), both starting at fraction 0."""
        faces = []
        n, m = len(A), len(B)
        i = j = 0
        while i < n or j < m:
            a_next = fa[i + 1] if i + 1 < n else 1.0
            b_next = fb[j + 1] if j + 1 < m else 1.0
            if i < n and (j >= m or a_next <= b_next):
                faces.append(self.face((A[i % n], A[(i + 1) % n], B[j % m])))
                i += 1
            else:
                faces.append(self.face((A[i % n], B[(j + 1) % m], B[j % m])))
                j += 1
        return faces

    def cap(self, ring, outward, bulge=0.0):
        f = self.face(ring)
        f.normal_update()
        if f.normal.dot(outward) < 0:
            f.normal_flip()
        res = bmesh.ops.poke(self.bm, faces=[f])
        if bulge:
            for v in res["verts"]:
                v.co += outward.normalized() * bulge
        c = sum((v.co for v in ring), Vector()) / len(ring)
        ax = (ring[0].co - c).normalized()
        ay = outward.normalized().cross(ax)
        for nf in res["faces"]:
            nf.material_index = self.mat
            nf.smooth = True
        self.planar_island(res["faces"], c, ax, ay)
        return res["faces"]

    def section_ring(self, C, T, phis, a, b, n, slant=0.0):
        """Ring around centre C in the plane perpendicular to T at world angles phis (atan2(y, x) sense);
        a = lateral half width, b = forward half depth; slant tilts the plane (front moves along +T)."""
        L, F = frame(T)
        Td = T.normalized()
        ring = []
        for ph in phis:
            u, v = superellipse(ph, a, b, n)
            ring.append(self.bm.verts.new(C + L * u + F * v + Td * (slant * v / b)))
        return ring

    def tube(self, centers, lat, radii, sides, phase, n=2.0):
        """closed rings along centers; radii (lateral, normal) half sizes; n = superellipse exponent (2 = ellipse,
        > 2 = rounded rectangle)"""
        rings = []
        for i, c in enumerate(centers):
            t = (centers[min(i + 1, len(centers) - 1)] - centers[max(i - 1, 0)]).normalized()
            nrm = t.cross(lat).normalized()
            rx, rf = radii[i]
            ring = []
            for j in range(sides):
                u, v = superellipse(2 * math.pi * j / sides + phase, rx, rf, n)
                ring.append(self.bm.verts.new(c + lat * u + nrm * v))
            rings.append(ring)
        return rings


# ----------------------------------------------------------------------------------------------- legs
def leg_skeleton(cx, side):
    """Hip, knee, ankle (world, final coordinates) and the shin direction for one side."""
    Hp = Vector((cx, HIP[0], HIP[1]))
    st, ft = math.radians(SPLAY_THIGH_DEG), math.radians(THIGH_FWD_DEG)
    dt = Vector((side * math.sin(st), math.sin(ft) * math.cos(st), -math.cos(ft) * math.cos(st))).normalized()
    K = Hp + dt * THIGH_LEN
    ss = math.radians(SPLAY_SHIN_DEG)

    def shin_dir(th):
        return Vector((side * math.sin(ss), -math.sin(th) * math.cos(ss), -math.cos(th) * math.cos(ss)))
    lo, hi = 0.0, 1.4
    for _ in range(60):   # shin slant (from vertical, backwards) so the ankle lands at ANKLE_Z
        th = (lo + hi) / 2
        if (K + shin_dir(th) * KNEE_TO_ANKLE).z > ANKLE_Z:
            hi = th
        else:
            lo = th
    da = shin_dir(th)
    A = K + da * KNEE_TO_ANKLE
    Fs = frame(da)[1]
    return Hp, dt, K, da, A, Fs, math.degrees(th)


def shin_point(K, da, Fs, t, off):
    return K + da * (KNEE_TO_ANKLE * t) + Fs * off


def build_leg(B, loop_co, side, tang):
    """One continuous leg, closed (top capped with material 2, removed after the union):
    thigh plate -> rim -> knee bulb -> shin -> hock -> metatarsal -> spring -> ankle."""
    bm = B.bm
    xs = [c.x for c in loop_co]
    ys = [c.y for c in loop_co]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    z0 = sum(c.z for c in loop_co) / len(loop_co)
    thetas = [math.atan2(c.y - cy, c.x - cx) for c in loop_co]
    unw = [thetas[0]]
    for th in thetas[1:]:
        unw.append(unw[-1] + (th - unw[-1] + math.pi) % (2 * math.pi) - math.pi)
    direction = 1 if unw[-1] > unw[0] else -1
    Hp, dt, K, da, A, Fs, shin_deg = leg_skeleton(cx, side)
    Lt, Ft = frame(dt)
    geo = {"hip": Hp, "knee": K, "ankle": A, "shin_abs_deg": shin_deg, "dt": dt, "Ft": Ft, "da": da, "Fs": Fs}

    top = [bm.verts.new(c) for c in loop_co]
    rings = [top]

    def tangent_loop(dz):
        """the cut loop continued dz below along the Tripo surface tangent"""
        return [Vector(c) + d * (dz / -d.z) for c, d in zip(loop_co, tang)]

    def flush_ring(dz):
        return [bm.verts.new(p) for p in tangent_loop(dz)]

    def plate_centre(z):
        s = (Hp.z - z) / -dt.z
        return Hp + dt * s + Ft * (-0.013 * s / THIGH_LEN)

    def plate_ring(z, hb, hw, n, slant=0.0, blend=None):
        r = B.section_ring(plate_centre(z), dt, thetas, hw, hb, n, slant=slant)
        if blend is not None:      # blend towards the Tripo surface continued along its tangent (flush, no lip)
            for v, p in zip(r, tangent_loop(z0 - z)):
                v.co = v.co.lerp(p, blend)
        return r

    zg1, zg2 = PLATE_GROOVE_Z
    zb = K.z - dt.z * (PLATE_BOTTOM_UP[0] + PLATE_BOTTOM_UP[1]) / 2
    slant_b = (PLATE_BOTTOM_UP[1] - PLATE_BOTTOM_UP[0]) / 2   # front lower (moves along the downward axis)
    # pass 6: plate half depth hb reduced to the reference side depths 139 / 150 / 155 mm at z 0.66 / 0.55 / bottom
    # (the first eased ring is kept for the flush join; the taper runs between the seam and segment line 1)
    spec = [
        (lambda: flush_ring(0.004), 1),                       # the Tripo surface continued (flush, no lip/groove)
        (lambda: plate_ring(z0 - 0.012, 0.081, 0.070, 3.0, blend=0.55), 1),   # eases into the plate section
        (lambda: plate_ring(zg1 + 0.004, 0.0735, 0.066, 3.2), 1),
        (lambda: plate_ring(zg1, 0.0685, 0.062, 3.2), 2),                                 # segment line 1
        (lambda: plate_ring(zg1 - 0.004, 0.0705, 0.067, 3.3), 1),
        (lambda: plate_ring(zg2 + 0.004, 0.0705, 0.062, 3.4), 1),
        (lambda: plate_ring(zg2, 0.0675, 0.059, 3.4), 2),                                # segment line 2
        (lambda: plate_ring(zg2 - 0.004, 0.0730, 0.064, 3.5), 1),
        (lambda: plate_ring(zb, 0.0775, 0.054, 3.6, slant=slant_b), 1),                 # bottom edge (slanted)
        (lambda: plate_ring(zb + 0.006, 0.0730, 0.050, 3.4, slant=slant_b), 3),         # inner lip
    ]
    kinds = []
    for mk, kind in spec:
        rings.append(mk())
        kinds.append(kind)
    rows = B.ring_strip(rings)
    for i, row in enumerate(rows):
        # the segment groove rows: the two strips touching a groove ring
        groove = kinds[i] == 2 or (i > 0 and kinds[i - 1] == 2)
        part = 2 if groove else kinds[i]
        B.tag(row, part, t=i / len(rows), rust=1.0, dark=1.0 if groove else 0.0, name="thigh plate")
    capf = B.face(top, mat=2)
    capf.normal_update()
    if capf.normal.z < 0:
        capf.normal_flip()

    # ---- knee / shin / metatarsal / spring / ankle: one 16 -> 12 sided loft starting inside the plate rim
    NS = SHIN_SIDES
    phS = angles_from(thetas[0], NS, direction)
    ph12 = angles_from(thetas[0], 12, direction)
    zr = zb + 0.012 * -dt.z                      # recessed 1.2 cm inside the rim
    t_top = (zr - K.z) / (da.z * KNEE_TO_ANKLE)   # negative: above the knee on the shin line
    C0 = shin_point(K, da, Fs, t_top, 0.0)
    r0 = B.section_ring(C0, dt, phS, 0.072 / 2, 0.084 / 2, 2.4, slant=slant_b * 0.6)
    zf = B.zipper(rings[-1], fractions(thetas, direction), r0, [j / NS for j in range(NS)])
    B.planar_island(zf, plate_centre(zb), Lt, Ft)
    B.tag(zf, 3, rust=1.0, name="thigh plate")

    # stations densified with Catmull-Rom (t, depth, width, offset all interpolated) so the side outline has
    # no visible kinks; every station stays an exact edge loop (knee t = 0, hock t = HOCK_T)
    st = [(t_top, 0.084, 0.072, 0.0)] + SHIN_ST + META_ST[:1]
    dense = []
    for i in range(len(SHIN_ST)):
        a, b = st[i + 1], st[i + 2] if i + 2 < len(st) else None
        dense.append(a)
        if b is None or a[0] >= HOCK_T - 1e-6:      # no extra rings below the hock
            continue
        nsub = int((b[0] - a[0]) / SHIN_SUBDIV)
        p0, p3 = st[i], st[min(i + 3, len(st) - 1)]
        for k in range(1, nsub + 1):
            u = k / (nsub + 1)
            dense.append(tuple(0.5 * ((2 * a[c]) + (-p0[c] + b[c]) * u + (2 * p0[c] - 5 * a[c] + 4 * b[c] - p3[c]) * u * u
                                      + (-p0[c] + 3 * a[c] - 3 * b[c] + p3[c]) * u ** 3) for c in range(4)))
    ctrl = [shin_point(K, da, Fs, t, off) for t, _, _, off in dense] + \
        [shin_point(K, da, Fs, t, off) for t, _, _, off in META_ST]
    srings, ts = [r0], [t_top]
    for i, (t, dep, wid, off) in enumerate(dense):
        prev = ctrl[i - 1] if i > 0 else C0
        T = ctrl[i + 1] - prev
        srings.append(B.section_ring(ctrl[i], T, phS, wid / 2, dep / 2, 2.3 if t < 0.3 else 2.2))
        ts.append(round(t, 5))
    rows = B.ring_strip(srings)
    for i, row in enumerate(rows):
        B.tag(row, 4, t=ts[i], name="knee/shin")
    lower, mts = [], []
    for j, (t, dep, wid, off) in enumerate(META_ST):
        lower.append(B.section_ring(ctrl[len(dense) + j], da, ph12, wid / 2, dep / 2, 2.2))
        mts.append(t)
    zf = B.zipper(srings[-1], [j / NS for j in range(NS)], lower[0], [j / 12 for j in range(12)])
    B.planar_island(zf, ctrl[len(dense) - 1], *frame(da))
    B.tag(zf, 4, t=0.62, name="knee/shin")
    # spring: helical thread on a thin core (4 turns), then the ankle block and a rounded cap
    L12, F12 = frame(da)
    nsp = int(SPRING_TURNS * SPRING_RPT)
    for i in range(nsp + 1):
        t = SPRING_T[0] + (SPRING_T[1] - SPRING_T[0]) * i / nsp
        C = shin_point(K, da, Fs, t, 0.0)
        helix = 2 * math.pi * SPRING_TURNS * i / nsp
        ring = []
        for ph in ph12:
            bump = max(0.0, math.cos(ph * direction - helix)) ** 3
            r = SPRING_CORE + SPRING_AMP * bump
            ring.append(bm.verts.new(C + L12 * (math.cos(ph) * r) + F12 * (math.sin(ph) * r)))
        lower.append(ring)
        mts.append(t)
    for t, dep, wid, off in ANKLE_ST:
        lower.append(B.section_ring(shin_point(K, da, Fs, t, off), da, ph12, wid / 2, dep / 2, 2.2))
        mts.append(t)
    rows = B.ring_strip(lower)
    for i, row in enumerate(rows):
        t = mts[i]
        part = 6 if t >= SPRING_T[1] - 1e-6 else (5 if t >= SPRING_T[0] - 0.03 else 4)
        B.tag(row, part, t=t, name={4: "knee/shin", 5: "spring", 6: "ankle"}[part])
    capf = B.cap(lower[-1], da, bulge=0.006)
    B.tag(capf, 6, t=1.05, name="ankle")
    geo["plate_front"] = plate_centre(zb) + Ft * 0.0775
    return geo


def build_parts(B, geo, side):
    """Knee pod and the three tines of one leg (closed tubes, unioned with the leg afterwards)."""
    K, A, dt, Ft, da = geo["knee"], geo["ankle"], geo["dt"], geo["Ft"], geo["da"]
    U = -dt
    X = Vector((1, 0, 0))
    # knee pod: capsule parallel to the thigh, its front flush with the plate front (POD fwd_gap)
    pc = (geo["plate_front"] - K).dot(Ft) + POD["fwd_gap"] - POD["r_fwd"]
    out = Vector((side * POD["out"], 0, 0))      # on the outer front corner of the plate (visible from the side)
    p0 = K + U * POD["up"][0] + Ft * pc + out
    p1 = K + U * POD["up"][1] + Ft * pc + out
    prof = [(0.0, 0.55), (0.10, 0.90), (0.35, 1.0), (0.75, 0.97), (0.92, 0.80), (1.0, 0.50)]
    cen = [p0.lerp(p1, t) for t, _ in prof]
    rings = B.tube(cen, X, [(POD["r_lat"] * k, POD["r_fwd"] * k) for _, k in prof], 10, 0.0)
    faces = [f for r in B.ring_strip(rings) for f in r]
    faces += B.cap(rings[0], cen[0] - cen[1], bulge=POD["cap"])
    faces += B.cap(rings[-1], cen[-1] - cen[-2], bulge=POD["cap"])
    bmesh.ops.recalc_face_normals(B.bm, faces=faces)
    B.tag(faces, 7, name="knee pod")
    geo["pod"] = (p0, p1)

    # tines: traced reference centrelines in ankle heights, placed at this ankle (rest pose: planted foot)
    H = ANKLE_Z
    Y = Vector((0, 1, 0))
    Z = Vector((0, 0, 1))
    geo["tines"] = {}
    Fs = geo["Fs"]

    def axis_x(z):        # lateral position of the knee->ankle axis at height z (the shin splays outwards)
        s = max(0.0, min(KNEE_TO_ANKLE, (z - K.z) / da.z))
        return (K + da * s).x

    def back_surface(t):  # back surface of the shin / metatarsal loft at t (stations interpolated as lofted)
        st = SHIN_ST + META_ST
        dep, off = st[-1][1], st[-1][3]
        for (t0, d0, _, o0), (t1, d1, _, o1) in zip(st, st[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                dep, off = d0 + (d1 - d0) * u, o0 + (o1 - o0) * u
                break
        return shin_point(K, da, Fs, t, off) - Fs * (dep / 2)

    def t_of(p):
        return (p - K).dot(da) / KNEE_TO_ANKLE

    for name, px in TINE_PX.items():
        lat, hw, ht, nsamp, pid, arch = TINE_SPEC[name]
        sh = TINE_SHIFT_PX.get(name, [0] * len(px))
        pts = [A + Y * ((REF_ANKLE_PX[0] - x - d) / REF_H_PX * H) + Z * ((REF_ANKLE_PX[1] - y + 1.0) / REF_H_PX * H)
               for (x, y), d in zip(px, sh)]   # +1 px: the traced line centre is 1 px above the ground
        pts = [Vector((axis_x(p.z) + side * lat, p.y, p.z)) for p in pts]
        c_root = 0.0
        if name == "outer":
            # blended root: buried start up the back of the metatarsal -> surface at the reference root -> glued
            def yzd(p, q):
                return math.hypot(p.y - q.y, p.z - q.z)
            t_r = min((0.30 + 0.001 * i for i in range(600)), key=lambda t: (yzd(back_surface(t), pts[0]), t))
            lead = []
            for k_ in range(3, 0, -1):
                tt = t_r - ROOT_RUN * k_ / 3
                b = back_surface(tt)
                lead.append(Vector((axis_x(b.z) + side * lat, b.y, b.z)) + Fs * (ROOT_SINK * k_ / 3))
            b = back_surface(t_r)
            Rp = Vector((axis_x(b.z) + side * lat, b.y, b.z))
            glued, gluing = [], True
            for p in pts[1:]:
                b = back_surface(t_of(p))
                gap = (b - p).dot(Fs)              # > 0: the traced point is behind (outside) the back surface
                if gluing and gap < ROOT_GLUE and t_of(p) < 1.0:
                    glued.append(Vector((axis_x(b.z) + side * lat, b.y, b.z)) - Fs * ROOT_LIFT)
                else:
                    gluing = False
                    glued.append(p)
            log("outer tine root", side, "t_r", round(t_r, 4), "root (f, dz H)",
                (round((Rp.y - A.y) / H, 3), round((Rp.z - A.z) / H, 3)), "glued points", sum(
                    1 for p, q in zip(glued, pts[1:]) if (p - q).length > 1e-9))
            ctrl = lead + [Rp] + glued
            dense = catmull(ctrl, 600)
            c_root = None
        else:                 # leave the spring core: extend 1.6 cm back along the tine's own start direction
            inner = pts[0] + (pts[0] - pts[1]).normalized() * 0.016
            dense = catmull([inner] + pts, 400)
        # resample (denser at turns); the two rings around the rear arch are placed symmetrically about its rearmost
        # point, so the row between them (its centre) sits on the rearmost point instead of half a spacing off
        path = resample_by_curvature(dense, nsamp, k_turn=0.025, anchor=min(range(1, len(dense) - 1),
                                                                           key=lambda i: (dense[i].y, i)))
        cum = [0.0]
        for i in range(1, len(path)):
            cum.append(cum[-1] + (path[i] - path[i - 1]).length)
        Lp = cum[-1]
        if c_root is None:    # arclength where the outer centre line reaches the surface (nearest sample to Rp)
            c_root = cum[min(range(len(path)), key=lambda i: (path[i] - Rp).length)]
        L_taper = Lp - TINE_FLAT_END_H * H     # root -> start of the constant flat end
        c_rear = cum[min(range(len(path)), key=lambda i: (path[i].y, i))]
        rad = []
        for i, c in enumerate(cum):
            t = c / Lp
            tw = min(1.0, c / L_taper)
            k = 0.85 if i == len(cum) - 1 else 1.0          # blunt end: full width, thickness eased 15 %, flat cap
            th = ht[0] + (ht[1] - ht[0]) * tw
            if arch:          # thicker rear arch (outer tine): smooth ramps 0.1 on either side of [start, end]
                a_th, a0, a1 = arch
                w = min(1.0, max(0.0, min((t - (a0 - 0.1)) / 0.1, ((a1 + 0.1) - t) / 0.1)))
                w = w * w * (3 - 2 * w)
                th += (a_th - th) * w
            wd = hw[0] + (hw[1] - hw[0]) * tw
            aw = max(0.0, 1.0 - abs(c - c_rear) / (ARCH_WIDEN_H * H))
            wd += ARCH_WIDEN[name] * aw * aw * (3 - 2 * aw)
            if name == "outer":   # root ramp: narrow and thin where it grows out of the metatarsal
                r = min(1.0, max(0.0, (c - c_root) / (ROOT_RAMP_H * H)))
                r = r * r * (3 - 2 * r)
                wd = ROOT_W0 / 2 + (wd - ROOT_W0 / 2) * r
                th = ROOT_T0 + (th - ROOT_T0) * r
            else:                 # grows out of the spring / ankle core narrower than the core, then widens
                r = min(1.0, c / (0.016 + MID_ROOT_RAMP_H * H))
                r = r * r * (3 - 2 * r)
                wd = MID_ROOT_W0 / 2 + (wd - MID_ROOT_W0 / 2) * r
            rad.append((wd, th * k))
        trings = B.tube(path, X, rad, TINE_SIDES, 0.0, n=TINE_N[name])
        faces = []
        for i, row in enumerate(B.ring_strip(trings)):
            B.tag(row, pid, t=cum[i] / Lp, name="tines")
            faces += row
        c0 = B.cap(trings[0], path[0] - path[1])
        c1 = B.cap(trings[-1], path[-1] - path[-2])
        B.tag(c0, pid, t=0.0, name="tines")
        B.tag(c1, pid, t=1.0, name="tines")
        bmesh.ops.recalc_face_normals(B.bm, faces=faces + c0 + c1)
        geo["tines"][name] = path


def pack_islands(islands, pad=0.004):
    """Shelf-pack islands (lists of (loop, local uv in m, uv layer)) into [0,1]^2 with uniform scale."""
    rects = []
    for isl in islands:
        us = [uv.x for _, uv, _ in isl]
        vs = [uv.y for _, uv, _ in isl]
        rects.append((min(us), min(vs), max(us) - min(us), max(vs) - min(vs)))
    order = sorted(range(len(rects)), key=lambda i: (-round(rects[i][3], 6), i))

    def place(scale):
        x = y = shelf_h = 0.0
        pos = {}
        for i in order:
            w, h = rects[i][2] * scale, rects[i][3] * scale
            if x + w + pad > 1.0:
                x, y, shelf_h = 0.0, y + shelf_h + pad, 0.0
            if w + 2 * pad > 1.0 or y + h + pad > 1.0:
                return None
            pos[i] = (x + pad, y + pad)
            x += w + pad
            shelf_h = max(shelf_h, h)
        return pos

    lo, hi = 0.1, 20.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if place(mid):
            lo = mid
        else:
            hi = mid
    pos = place(lo)
    for i, isl in enumerate(islands):
        mu, mv = rects[i][0], rects[i][1]
        px, py = pos[i]
        for loop, uv, lay in isl:
            loop[lay].uv = (px + (uv.x - mu) * lo, py + (uv.y - mv) * lo)
    return lo


def new_object(name, bmx, mats):
    mesh = bpy.data.meshes.new(name)
    bmx.to_mesh(mesh)
    for m in mats:
        mesh.materials.append(m)
    o = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(o)
    return o


# ------------------------------------------------------------------------- legs (final coordinates)
leg_mat = bpy.data.materials.new("hero_legs")
cap_mat = bpy.data.materials.new("cut_cap_tmp")
lbm, pbm = bmesh.new(), bmesh.new()
B, PB = Builder(lbm, 1), Builder(pbm, 1)
GEO = {}
for s_src in sorted(loops_src):
    pos = [M @ v.co for v in loops_src[s_src]]
    side = 1 if sum(p.x for p in pos) > 0 else -1
    GEO[side] = build_leg(B, pos, side, TANG_SRC[s_src])
    build_parts(PB, GEO[side], side)
leg_faces_closed = [f for f in lbm.faces]
bmesh.ops.recalc_face_normals(lbm, faces=leg_faces_closed)
pack_scale = pack_islands([[(l, uv, B.uv) for l, uv in isl] for isl in B.islands]
                          + [[(l, uv, PB.uv) for l, uv in isl] for isl in PB.islands])
leg_obj = new_object("legs_tmp", lbm, [body_mat, leg_mat, cap_mat])
parts_obj = new_object("parts_tmp", pbm, [body_mat, leg_mat, cap_mat])
lbm.free()
pbm.free()
mod = leg_obj.modifiers.new("union", "BOOLEAN")
mod.operation = "UNION"
mod.solver = "EXACT"
mod.object = parts_obj
mod.use_self = True
bpy.context.view_layer.objects.active = leg_obj
for o in bpy.context.scene.objects:
    o.select_set(o is leg_obj)
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(parts_obj)
lbm = bmesh.new()
lbm.from_mesh(leg_obj.data)
bmesh.ops.delete(lbm, geom=[f for f in lbm.faces if f.material_index == 2], context="FACES_ONLY")
for v in [v for v in lbm.verts if not v.link_faces]:
    lbm.verts.remove(v)
# boolean slivers: collapse degenerate edges/faces (zero-area triangles at the tine/pod intersections)
n_f0 = len(lbm.faces)
# near-coincident boolean vertices (not sharing an edge) would be merged by any weld downstream (glTF round trip,
# engine import): merge them here, away from the cut loop (welded to the body later)
n_v0 = len(lbm.verts)
bmesh.ops.remove_doubles(lbm, verts=[v for v in lbm.verts if abs(v.co.z - CUT_Z) > 1e-4], dist=1e-4)
log("leg remove_doubles 1e-4: verts", n_v0, "->", len(lbm.verts))
bmesh.ops.dissolve_degenerate(lbm, dist=1e-5, edges=list(lbm.edges))
for v in [v for v in lbm.verts if not v.link_faces]:
    lbm.verts.remove(v)
log("dissolve_degenerate: faces", n_f0, "->", len(lbm.faces))


def tri_area(a, b, c):
    return (b - a).cross(c - a).length / 2


def fix_slivers(bmx, eps=1e-8, top_z=None):
    """Zero-area triangles inside the boolean n-gons (collinear vertices) get dropped by the glTF round trip and
    leave holes: triangulate only the faces whose loop triangulation contains one, then remove each sliver by
    rotating its longest edge (collinear 'cap') or collapsing its shortest edge ('needle')."""
    bad_faces = {lt[0].face for lt in bmx.calc_loop_triangles()
                 if tri_area(*(l.vert.co for l in lt)) < eps}
    bad_faces |= {f for f in bmx.faces if len(f.verts) > 4}      # boolean n-gons (may overlap back to back)
    bmx.verts.index_update()
    if bad_faces:
        bmesh.ops.triangulate(bmx, faces=sorted(bad_faces, key=lambda f: f.index),
                              quad_method="BEAUTY", ngon_method="BEAUTY")
    # a triangle duplicated inside a quad: triangulate that quad first (so the copies become two triangle faces)
    cnt = {}
    for lt in bmx.calc_loop_triangles():
        cnt.setdefault(frozenset(l.vert.index for l in lt), set()).add(lt[0].face)
    quads = {f for fs in cnt.values() if len(fs) > 1 for f in fs if len(f.verts) == 4}
    if quads:
        bmesh.ops.triangulate(bmx, faces=sorted(quads, key=lambda f: f.index), quad_method="BEAUTY")
    # two boolean faces covering the same small triangle with opposite winding: the copies cancel, delete both
    seen, dup = {}, []
    bmx.faces.index_update()
    for f in bmx.faces:
        if len(f.verts) != 3:
            continue
        key = frozenset(v.index for v in f.verts)
        if key in seen:
            dup += [seen.pop(key), f]
        else:
            seen[key] = f
    if dup:
        bmesh.ops.delete(bmx, geom=dup, context="FACES_ONLY")
        bmesh.ops.delete(bmx, geom=[e for e in bmx.edges if not e.link_faces], context="EDGES")
        for v in [v for v in bmx.verts if not v.link_faces]:
            bmx.verts.remove(v)
    log("slivers: back-to-back duplicate triangles removed", len(dup))
    fixed = 0
    for it in range(200):
        bmx.faces.index_update()
        slivers = [f for f in bmx.faces if len(f.verts) == 3 and tri_area(*(v.co for v in f.verts)) < eps]
        if not slivers:
            break
        f = slivers[0]
        es = sorted(f.edges, key=lambda e: (e.calc_length(), e.index))
        lon = es[-1]
        apex = [v for v in f.verts if v not in lon.verts][0]       # the (near-)collinear middle vertex
        on_top = top_z is not None and abs(apex.co.z - top_z) < 1e-4
        done = False
        if it % 2 == 0 and len(lon.link_faces) == 2 and not on_top:
            # cap: flip the long edge across to the neighbour's apex (if that makes both triangles non-degenerate)
            g = [x for x in lon.link_faces if x is not f][0]
            if len(g.verts) == 3:
                other = [v for v in g.verts if v not in lon.verts][0]
                a0, a1 = lon.verts
                if tri_area(apex.co, other.co, a0.co) > eps and tri_area(apex.co, other.co, a1.co) > eps:
                    done = bool(bmesh.ops.rotate_edges(bmx, edges=[lon], use_ccw=False)["edges"])
        if not done and not on_top:
            # merge the middle vertex onto the nearer end of the long edge (it lies on that line: no shape change)
            tgt = min(lon.verts, key=lambda v: ((v.co - apex.co).length, v.index))
            bmesh.ops.pointmerge(bmx, verts=[apex, tgt], merge_co=tgt.co.copy())
            done = True
        if not done:
            break
        fixed += 1
    left = sum(1 for lt in bmx.calc_loop_triangles() if tri_area(*(l.vert.co for l in lt)) < eps)
    return len(bad_faces), fixed, left


_nb, _fx, _left = fix_slivers(lbm, top_z=CUT_Z)
log("slivers: faces triangulated", _nb, "slivers fixed", _fx, "left", _left)
assert _left == 0, "zero-area triangles left in the legs"
for f in lbm.faces:
    f.smooth = True
lbm.to_mesh(leg_obj.data)
leg_tris = sum(len(f.verts) - 2 for f in lbm.faces)
_lp = lbm.faces.layers.float["lm_part"]
_cnt = {}
for f in lbm.faces:
    _cnt[(int(round(f[_lp])), f.material_index)] = _cnt.get((int(round(f[_lp])), f.material_index), 0) + 1
log("faces per (lm_part, material) after the union", dict(sorted(_cnt.items())))
lbm.free()
leg_obj.data.materials.pop()        # drop the temporary cap material slot
log("leg parts tris (both legs, before the union)", {**B.parts, **PB.parts})
log("legs tris after the union", leg_tris, "UV scale", round(pack_scale, 3), "->",
    round(pack_scale * LEG_TEX["basecolor"]), "px/m")

# ---------------------------------------------------------------------- budget: decimate the upper body
bm.to_mesh(me)
bm.free()
body_tris0 = sum(len(p.vertices) - 2 for p in me.polygons)
body_target = TRI_TARGET - leg_tris
log("body tris after the cut", body_tris0, "target", body_target)
if body_tris0 > body_target:
    vg = obj.vertex_groups.new(name="decimate")
    for v in me.vertices:
        c = v.co
        protect = ((c.z > 0.78 and c.y < 0.02) or (abs(c.x) > 0.17 and c.z < 0.40)
                   or (c.z < CUT_SRC + 0.01 and abs(c.x) < LEG_X_SRC))
        vg.add([v.index], 0.0 if protect else 1.0, "REPLACE")
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.scene.objects:
        o.select_set(o is obj)
    ratio = body_target / body_tris0
    for _ in range(6):
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        mod.vertex_group = "decimate"
        mod.vertex_group_factor = 1.0
        dg = bpy.context.evaluated_depsgraph_get()
        n = sum(len(p.vertices) - 2 for p in obj.evaluated_get(dg).data.polygons)
        if n <= body_target:
            bpy.ops.object.modifier_apply(modifier=mod.name)
            break
        obj.modifiers.remove(mod)
        ratio *= body_target / n * 0.998
    if "decimate" in obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups["decimate"])
body_tris1 = sum(len(p.vertices) - 2 for p in me.polygons)
log("body tris after decimate", body_tris1)

# ------------------------------------------------------------------------- orient, scale, join, weld
me.transform(M)
me.update()
for p in me.polygons:
    p.use_smooth = True
me.materials.append(leg_mat)
bpy.ops.object.select_all(action="DESELECT")
leg_obj.select_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.join()
bm = bmesh.new()
bm.from_mesh(me)
cut_vs = [v for v in bm.verts if abs(v.co.z - CUT_Z) < 1e-4 and abs(v.co.x) < 0.2]
n_before = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=cut_vs, dist=1e-5)
welded = n_before - len(bm.verts)
n_loop = sum(len(l) for l in loops_src.values())
log("cut loop verts", n_loop, "welded", welded)
assert welded == n_loop, "legs not welded to the cut loops"
assert not [e for e in bm.edges if e.is_boundary and abs(e.verts[0].co.z - CUT_Z) < 1e-4
            and abs(e.verts[1].co.z - CUT_Z) < 1e-4], "open edges left at the cut"

# leg connectivity: one connected component of leg faces per side
for side in (1, -1):
    fs = {f for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * side > 0}
    comps, seen = 0, set()
    for f0 in sorted(fs, key=lambda f: f.index):
        if f0 in seen:
            continue
        comps += 1
        stack = [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in fs and g not in seen:
                        seen.add(g)
                        stack.append(g)
    log("leg side", side, "connected components", comps, "faces", len(fs))
    assert comps == 1, "leg is not one connected surface"

# drop the lowest part (tines) by the 1-2 mm so the lowest vertex is exactly on y = 0
leg_v = sorted({v for f in bm.faces if f.material_index == 1 for v in f.verts}, key=lambda v: v.index)
zmin = min(v.co.z for v in leg_v)
for v in leg_v:            # faded to zero at half the ankle height (sub-millimetre)
    if v.co.z < ANKLE_Z * 0.5:
        v.co.z -= zmin * (1.0 - v.co.z / (ANKLE_Z * 0.5))
log("ground drop", round(zmin, 5))

# hand clearance: min distance from the hands/forearms to the leg surface
kd = KDTree(len(leg_v))
for i, v in enumerate(leg_v):
    kd.insert(v.co, i)
kd.balance()
hand_v = [v for v in bm.verts if abs(v.co.x) > 0.19 and 0.6 < v.co.z < 1.0
          and not any(f.material_index == 1 for f in v.link_faces)]
hand_clear = min(kd.find(v.co)[2] for v in hand_v)
log("hand clearance (min hand -> leg distance)", round(hand_clear, 4))
assert hand_clear >= 0.02, "hands closer than 2 cm to the legs"

contact = [v.co.y for v in leg_v if v.co.z < 0.004]
log("contact strip y", round(min(contact), 4), "..", round(max(contact), 4), "| hip midpoint y", HIP[0],
    "| inside:", min(contact) <= HIP[0] <= max(contact))
for side, g in sorted(GEO.items()):
    log("side", side, "hip", tuple(round(c, 4) for c in g["hip"]), "knee", tuple(round(c, 4) for c in g["knee"]),
        "ankle", tuple(round(c, 4) for c in g["ankle"]), "shin slant from vertical", round(g["shin_abs_deg"], 2))

# sharp edges: leg edges with a dihedral angle above 55 deg (plate rim, caps) and the knee pod union boundary
bm.edges.index_update()
sharp_idx = set()
_lpj = bm.faces.layers.float["lm_part"]
n_pod_crease = 0
for e in bm.edges:
    if len(e.link_faces) == 2 and all(f.material_index == 1 for f in e.link_faces):
        pod = [int(round(f[_lpj])) == 7 for f in e.link_faces]
        if pod[0] != pod[1]:              # knee pod union boundary: crease, so the pod reads as its own part
            sharp_idx.add(e.index)
            n_pod_crease += 1
        elif e.calc_face_angle(0.0) > math.radians(55):
            sharp_idx.add(e.index)
log("knee pod crease edges", n_pod_crease)
bm.to_mesh(me)
bm.free()
sharp = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
vals = [False] * len(me.edges)
for i in sharp_idx:
    vals[i] = True
sharp.data.foreach_set("value", vals)
me.update()
if os.environ.get("HERO_GEO_ONLY"):
    obj.location = (0, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=os.environ["HERO_GEO_ONLY"], compress=True)
    raise SystemExit(0)
z_stump = CUT_Z


# ----------------------------------------------------------------- body textures: fit the budgets
os.makedirs(TEX, exist_ok=True)
bnt = body_mat.node_tree
for node in bnt.nodes:
    if node.type != "TEX_IMAGE" or not node.image:
        continue
    im = node.image
    name = im.name.rsplit(".", 1)[0]
    if name == "hero_basecolor":
        target, ext, fmt = 2048, "jpg", "JPEG"
    elif name == "hero_rm":
        target, ext, fmt = 1024, "png", "PNG"
    else:
        continue                       # normal map stays 2048 as delivered
    cs = im.colorspace_settings.name
    im.scale(target, target)
    path = os.path.join(TEX, f"hero_body_{name.split('_', 1)[1]}.{ext}")
    im.filepath_raw = path
    im.file_format = fmt
    im.save(filepath=path, quality=92)
    new = bpy.data.images.load(path)
    new.colorspace_settings.name = cs
    node.image = new
    bpy.data.images.remove(im)
    log("body texture", name, "->", target, path)


# ------------------------------------------------- sample the Tripo paint around the stump (seam blend)
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def median(xs):
    s = sorted(xs)
    return s[len(s) // 2] if s else 0.0


BARY = [(1 / 3, 1 / 3), (0.6, 0.2), (0.2, 0.6), (0.2, 0.2), (0.45, 0.45), (0.1, 0.45), (0.45, 0.1)]


def visible_half(p):
    """Outer or front half of a thigh (the hidden inner/back faces are mostly bare metal on the Tripo thigh)."""
    return abs(p.x) > 0.10 or p.y > 0.05


def sample_region(mat_index, z_lo, z_hi, images, keep=None):
    """Per image: list of RGB samples (raw pixel values) at fixed barycentric points of the triangles of
    material `mat_index`, keeping the points that lie in z_lo..z_hi and 0.04 < |x| < 0.19 (hip/thigh ring)."""
    me.calc_loop_triangles()
    uvd = me.uv_layers.active.data
    bufs = []
    for im in images:
        W, H = im.size
        buf = array.array("f", [0.0]) * (W * H * 4)
        im.pixels.foreach_get(buf)
        bufs.append((W, H, buf))
    out = [[] for _ in images]
    for tri in me.loop_triangles:
        if tri.material_index != mat_index:
            continue
        cs = [me.vertices[i].co for i in tri.vertices]
        if max(c.z for c in cs) < z_lo or min(c.z for c in cs) > z_hi:
            continue
        uvs = [uvd[li].uv for li in tri.loops]
        for b1, b2 in BARY:
            p = cs[0] * (1 - b1 - b2) + cs[1] * b1 + cs[2] * b2
            if not (z_lo <= p.z <= z_hi and 0.03 < abs(p.x) < 0.20) or (keep and not keep(p)):
                continue
            u = uvs[0].x * (1 - b1 - b2) + uvs[1].x * b1 + uvs[2].x * b2
            v = uvs[0].y * (1 - b1 - b2) + uvs[1].y * b1 + uvs[2].y * b2
            for k, (W, H, buf) in enumerate(bufs):
                x = min(W - 1, max(0, int((u % 1.0) * W)))
                y = min(H - 1, max(0, int((v % 1.0) * H)))
                i = (y * W + x) * 4
                out[k].append((buf[i], buf[i + 1], buf[i + 2]))
    return out


def is_rust(c):        # sRGB base colour sample: warm hue, not black (includes the brown rust staining)
    return c[0] > 0.16 and c[0] > 1.7 * c[2]


def paint_stats(base, rm=None):
    rust_i = [i for i, c in enumerate(base) if is_rust(c)]
    rs = set(rust_i)
    metal_i = [i for i in range(len(base)) if i not in rs]
    st = {"n": len(base), "rust_frac": len(rust_i) / max(1, len(base))}
    if rust_i:   # dark and bright rust tones (linear): medians of the lower half / top 30 % by luminance
        lin = sorted((tuple(srgb_to_lin(x) for x in base[i]) for i in rust_i),
                     key=lambda c: (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2], c))
        lo, hi = lin[:max(1, len(lin) // 2)], lin[int(len(lin) * 0.7):]
        st["rust_lo"] = tuple(median([c[k] for c in lo]) for k in range(3))
        st["rust_hi"] = tuple(median([c[k] for c in hi]) for k in range(3))
    for name, idx in (("metal", metal_i), ("rust", rust_i)):
        st[name] = tuple(srgb_to_lin(median([base[i][k] for i in idx])) for k in range(3)) if idx else None
        if rm is not None:
            st[name + "_rough"] = median([rm[i][1] for i in idx]) if idx else None
            st[name + "_metal"] = median([rm[i][2] for i in idx]) if idx else None
    return st


body_imgs = {n.image.name.rsplit(".", 1)[0]: n.image for n in bnt.nodes if n.type == "TEX_IMAGE" and n.image}
s_base, s_rm = sample_region(0, z_stump - 0.001, z_stump + 0.07,
                             [body_imgs["hero_body_basecolor"], body_imgs["hero_body_rm"]])
TRIPO = paint_stats(s_base, s_rm)
TRIPO_VIS = paint_stats(sample_region(0, z_stump - 0.001, z_stump + 0.07, [body_imgs["hero_body_basecolor"]],
                                     keep=visible_half)[0])
log("Tripo rust fraction: all around", round(TRIPO["rust_frac"], 3), "visible outer/front half",
    round(TRIPO_VIS["rust_frac"], 3), "n", TRIPO_VIS["n"])
log("Tripo paint around the stump", {k: (tuple(round(x, 4) for x in v) if isinstance(v, tuple) else
                                         (round(v, 3) if isinstance(v, float) else v)) for k, v in TRIPO.items()})
# fallbacks in case the region holds no rust/metal samples
T_METAL = TRIPO["metal"] or (0.014, 0.009, 0.005)
T_RUST = TRIPO["rust"] or (0.08, 0.048, 0.017)
T_MROUGH = TRIPO["metal_rough"] if TRIPO["metal_rough"] is not None else 0.6
T_RROUGH = TRIPO["rust_rough"] if TRIPO["rust_rough"] is not None else 0.85
T_MMETAL = TRIPO["metal_metal"] if TRIPO["metal_metal"] is not None else 0.7
T_RMETAL = TRIPO["rust_metal"] if TRIPO["rust_metal"] is not None else 0.2
T_RUST_LO = TRIPO.get("rust_lo") or T_RUST
T_RUST_HI = TRIPO.get("rust_hi") or T_RUST
Q_SEAM = min(0.6, max(0.02, TRIPO_VIS["rust_frac"]))


# ------------------------------------------------------------------- leg material: bake procedural maps
def build_proc_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    out = N("ShaderNodeOutputMaterial")
    bsdf = N("ShaderNodeBsdfPrincipled")
    L(bsdf.outputs[0], out.inputs[0])
    geo = N("ShaderNodeNewGeometry")
    sep = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs[0])

    def noise(scale, detail, rough, vec=None):
        n = N("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        L(vec or geo.outputs["Position"], n.inputs["Vector"])
        return n

    def math_(op, a, b=None, clamp=False):
        m = N("ShaderNodeMath")
        m.operation = op
        m.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[i].default_value = x
            else:
                L(x, m.inputs[i])
        return m.outputs[0]

    def mix(fac, a, b):
        m = N("ShaderNodeMix")
        m.data_type = "RGBA"
        L(fac, m.inputs["Factor"])
        for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(val, tuple):
                sock.default_value = val
            else:
                L(val, sock)
        return m.outputs[2]

    def mixf(fac, a, b):
        m = N("ShaderNodeMix")
        m.data_type = "FLOAT"
        L(fac, m.inputs["Factor"])
        for sock, val in ((m.inputs[2], a), (m.inputs[3], b)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                L(val, sock)
        return m.outputs[0]

    def smoothstep(x, lo, hi):
        m = N("ShaderNodeMapRange")
        m.interpolation_type = "SMOOTHSTEP"
        m.clamp = True
        L(x, m.inputs["Value"])
        for sock, val in ((m.inputs["From Min"], lo), (m.inputs["From Max"], hi)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                L(val, sock)
        return m.outputs["Result"]

    def scaled(c, k, cap=1.0):
        return (min(cap, c[0] * k), min(cap, c[1] * k), min(cap, c[2] * k), 1.0)

    # rust mask: next to the seam matched to the Tripo paint (ridge band included), grading to the reference's
    # heavier plate rust; shins/blades sparse. Thresholds are Value nodes, set from the baked noise quantiles.
    rust_big = noise(8.0, 8.0, 0.65).outputs["Fac"]
    rust_fine = noise(40.0, 4.0, 0.6).outputs["Fac"]
    rust_n = math_("ADD", math_("MULTIPLY", rust_big, 0.8), math_("MULTIPLY", rust_fine, 0.2))
    z = sep.outputs["Z"]
    attr = N("ShaderNodeAttribute")
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "rustpart"
    plate = attr.outputs["Fac"]
    near_seam = smoothstep(z, z_stump - SEAM_BLEND, z_stump - SEAM_FULL)
    v_seam = N("ShaderNodeValue")
    v_seam.name = "thr_seam"
    v_plate = N("ShaderNodeValue")
    v_plate.name = "thr_plate"
    thr_plate = mixf(near_seam, v_plate.outputs[0], v_seam.outputs[0])
    thr = mixf(plate, RUST_THR_SHIN, thr_plate)
    rust = smoothstep(rust_n, thr, math_("ADD", thr, RUST_EDGE))
    # colours, anchored on the Tripo medians sampled around the stump
    metal_var = noise(22.0, 4.0, 0.5).outputs["Fac"]
    metal = mix(metal_var, scaled(T_METAL, 0.62), scaled(T_METAL, 1.32))
    rust_var = noise(35.0, 6.0, 0.6).outputs["Fac"]
    rust_tripo = mix(rust_var, scaled(T_RUST_LO, 0.9), scaled(T_RUST_HI, 1.1, 0.8))
    rust_ref = mix(rust_var, REF_RUST_LO + (1.0,), REF_RUST_HI + (1.0,))
    rustc = mix(near_seam, rust_ref, rust_tripo)
    pits = smoothstep(noise(55.0, 3.0, 0.6).outputs["Fac"], 0.60, 0.63)
    rustc = mix(pits, rustc, scaled(T_METAL, 1.6))       # dark pitting inside the rust patches
    base = mix(rust, metal, rustc)
    dattr = N("ShaderNodeAttribute")
    dattr.attribute_type = "GEOMETRY"
    dattr.attribute_name = "dark"
    base = mix(dattr.outputs["Fac"], base, scaled(T_METAL, 0.45))     # dark segment lines in the plate grooves
    L(base, bsdf.inputs["Base Color"])
    rough = mixf(rust, math_("ADD", math_("MULTIPLY", metal_var, 0.16), T_MROUGH - 0.08), T_RROUGH)
    metal_f = mixf(rust, T_MMETAL, T_RMETAL)
    L(rough, bsdf.inputs["Roughness"])
    L(metal_f, bsdf.inputs["Metallic"])
    # bump: fine pitting + raised rust crust
    fine = noise(90.0, 3.0, 0.5).outputs["Fac"]
    height = math_("ADD", math_("MULTIPLY", fine, 0.4), rust)
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.002
    L(height, bump.inputs["Height"])
    L(bump.outputs["Normal"], bsdf.inputs["Normal"])
    # emission outputs used for EMIT bakes
    rm = N("ShaderNodeCombineColor")
    L(rough, rm.inputs[1])
    L(metal_f, rm.inputs[2])
    emit = N("ShaderNodeEmission")
    return nt, out, bsdf, emit, base, rm, rust_n


def bake_leg_textures():
    os.makedirs(TEX, exist_ok=True)
    # temporary object with only the leg faces, so the body material/images can never be baked over
    tmp = obj.copy()
    tmp.data = obj.data.copy()
    tmp.name = "legs_bake_tmp"
    bpy.context.scene.collection.objects.link(tmp)
    tbm = bmesh.new()
    tbm.from_mesh(tmp.data)
    bmesh.ops.delete(tbm, geom=[f for f in tbm.faces if f.material_index != 1], context="FACES")
    tbm.to_mesh(tmp.data)
    tbm.free()
    proc = bpy.data.materials.new("legs_proc_tmp")
    nt, out, bsdf, emit, base, rm, rust_n = build_proc_material(proc)
    tmp.data.materials.clear()
    tmp.data.materials.append(proc)
    tmp.data.materials.append(proc)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    scene.render.bake.margin = 8
    for o in bpy.context.scene.objects:
        o.select_set(o is tmp)
    bpy.context.view_layer.objects.active = tmp
    img_node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = img_node

    def bake_emit(socket, name, size, color, float_buf=False):
        img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=float_buf)
        img.colorspace_settings.name = "sRGB" if color else "Non-Color"
        img_node.image = img
        nt.links.new(socket, emit.inputs[0])
        nt.links.new(emit.outputs[0], out.inputs[0])
        bpy.ops.object.bake(type="EMIT", use_clear=True, margin=8)
        return img

    # 1. calibrate the rust thresholds on the baked raw noise (empirical quantiles in each region)
    noise_img = bake_emit(rust_n, "legs_rustnoise_tmp", 512, False, float_buf=True)
    seam_z = (z_stump - 0.025, z_stump - 0.003)        # top 2.5 cm (enough samples on the cuff rings)
    plate_z = (PLATE_BOTTOM_Z + 0.005, z_stump - SEAM_BLEND)

    def quantile_thr(zr, q):
        vals = sorted(c[0] for c in sample_region(1, zr[0], zr[1], [noise_img], keep=visible_half)[0])
        return vals[min(len(vals) - 1, max(0, int(round((1 - q) * len(vals)))))] - RUST_EDGE / 2   # midpoint

    def frac(img, zr):
        return paint_stats(sample_region(1, zr[0], zr[1], [img], keep=visible_half)[0])["rust_frac"]

    v_seam, v_plate = nt.nodes["thr_seam"], nt.nodes["thr_plate"]
    q, qp = Q_SEAM, RUST_FRAC_PLATE
    for it in range(4):
        v_seam.outputs[0].default_value = quantile_thr(seam_z, q)
        v_plate.outputs[0].default_value = quantile_thr(plate_z, qp)
        base_img = bake_emit(base, "hero_legs_basecolor", LEG_TEX["basecolor"], True)
        got, got_plate = frac(base_img, seam_z), frac(base_img, plate_z)
        log("rust calibration", it, "seam target", round(Q_SEAM, 3), "got", round(got, 3), "| plate target",
            RUST_FRAC_PLATE, "got", round(got_plate, 3), "| thr", round(v_seam.outputs[0].default_value, 4),
            round(v_plate.outputs[0].default_value, 4))
        if (abs(got - Q_SEAM) <= 0.02 and abs(got_plate - RUST_FRAC_PLATE) <= 0.03) or it == 3:
            break
        q = min(0.95, max(0.01, q + (Q_SEAM - got)))
        qp = min(0.95, max(0.01, qp + (RUST_FRAC_PLATE - got_plate)))
        bpy.data.images.remove(base_img)
    bpy.data.images.remove(noise_img)

    imgs = {}
    for key in ("basecolor", "rm", "normal"):
        if key == "basecolor":
            img = base_img
        elif key == "rm":
            img = bake_emit(rm.outputs[0], "hero_legs_rm", LEG_TEX["rm"], False)
        else:
            img = bpy.data.images.new("hero_legs_normal", LEG_TEX["normal"], LEG_TEX["normal"], alpha=False)
            img.colorspace_settings.name = "Non-Color"
            img_node.image = img
            nt.links.new(bsdf.outputs[0], out.inputs[0])
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", use_clear=True, margin=8)
        path = os.path.join(TEX, f"hero_legs_{key}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        imgs[key] = path
        log("baked", key, img.size[0])
    bpy.data.objects.remove(tmp)
    bpy.data.materials.remove(proc)
    for im in [i for i in bpy.data.images if i.name.startswith("hero_legs_")]:
        bpy.data.images.remove(im)
    return imgs


def pbr_material(mat, base_path, rm_path, nrm_path):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])

    def tex(path, color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path)
        n.image.colorspace_settings.name = "sRGB" if color else "Non-Color"
        return n

    b = tex(base_path, True)
    nt.links.new(b.outputs[0], bsdf.inputs["Base Color"])
    r = tex(rm_path, False)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(r.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    n = tex(nrm_path, False)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return b.image, r.image


leg_imgs = bake_leg_textures()
leg_base_img, leg_rm_img = pbr_material(leg_mat, leg_imgs["basecolor"], leg_imgs["rm"], leg_imgs["normal"])
for _a in ("rustpart", "dark"):
    if _a in me.attributes:
        me.attributes.remove(me.attributes[_a])
leg_mat.use_backface_culling = True    # legs are closed and outward-facing; body stays double-sided as delivered
# check the blend: the leg plate just below the cuff band vs the Tripo paint just above the seam
l_base, l_rm = sample_region(1, z_stump - 0.07, z_stump - 0.003, [leg_base_img, leg_rm_img])
LEGS = paint_stats(l_base, l_rm)
log("leg paint below the cuff", {k: (tuple(round(x, 4) for x in v) if isinstance(v, tuple) else
                                     (round(v, 3) if isinstance(v, float) else v)) for k, v in LEGS.items()})

# KHR_materials_volume / transmission leftovers: plain opaque PBR
for m in (body_mat, leg_mat):
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for key in ("Transmission Weight", "Coat Weight", "Sheen Weight", "Subsurface Weight"):
        if key in b.inputs:
            b.inputs[key].default_value = 0.0
    try:
        m.surface_render_method = "DITHERED"
    except AttributeError:
        pass

# ------------------------------------------------------------------------------------------ finish
obj.location = (0, 0, 0)
obj.rotation_euler = (0, 0, 0)
obj.scale = (1, 1, 1)
for img in bpy.data.images:
    if img.source == "FILE" and not img.packed_file:
        img.pack()
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

me.calc_loop_triangles()
vs = [v.co for v in me.vertices]
lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
log("RESULT tris", len(me.loop_triangles), "body", body_tris1, "legs", leg_tris,
    "bbox min", tuple(round(c, 4) for c in lo), "max", tuple(round(c, 4) for c in hi),
    "materials", [m.name for m in me.materials])
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
log("saved", OUT)
