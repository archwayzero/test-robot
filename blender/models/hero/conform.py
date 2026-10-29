"""T011 hero conform: Tripo upper body (provided) + generated digitigrade legs -> hero_model.blend.

Build (re-runnable, deterministic), then export:
  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b -P blender/models/hero/conform.py
  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- \
    blender -b blender/models/hero/hero_model.blend -P tools/blender/export_gltf.py -- \
    --out godot/assets/hero/model/hero.glb --no-anim

Steps:
  1. Import source/hero.glb (untouched), merge split vertices, drop the encoded custom normals, remove the
     stump caps (two clean 18-vertex boundary loops at mid-thigh).
  2. Decimate the upper body just enough that body + legs <= TRI_TARGET (face, hands and stumps protected).
  3. Rotate 180 deg about Z (front -> Blender +Y -> Godot -Z), scale so the hood top is at 1.75 m.
  4. Generate the legs (bmesh) in the same mesh, one closed piece per rigid part so per-bone rigid weights stay easy.
     Proportions measured on reference/hero/full_body.png (791 px = 1.75 m), checked per angle against
     reference/hero/turnaround/ (pass 3); H = ankle/tine-root height = 0.24 m (full_body.md's "hock height"):
       thigh plate   extruded from the stump loop down to the knee (z 0.47; seam closed) with a raised cuff ridge,
                     a segment groove and a narrowed outer side (hand clearance)              -> thigh bone
       knee pod      rounded capsule at the plate's front-bottom, z 0.41-0.56 (45/90 deg)     -> shin bone
       shin          S-shaped tapered strut knee (z 0.46) -> hock (z 0.33), nearly vertical    -> shin bone
       metatarsal    hock bulb -> shaft down and back -> thin core -> ankle block (z = H);
                     ~43 deg rest bend at the hock                                            -> metatarsal bone
       spring        3-turn coil around the core just above the ankle                         -> metatarsal bone
       3 tines       nested reverse-C blades: leave the ankle BACKWARD at ~hock height, rearmost 0.88/0.73/0.60 H
                     behind, sweep down, tips hook FORWARD (+0.38 H on the ground / +0.16 H / -0.05 H, raised
                     and splayed sideways so they stay separate)                              -> foot/toe bone
     Edge loops at the knee, hock and ankle. The surface centroid is asserted to lie over the ground contact.
  5. Leg UVs (one island per tube/cap, shelf-packed), second PBR material with Cycles-baked procedural textures
     (base colour 1024, normal 1024, roughness/metallic 512). Metal/rust colours, roughness and metallic are sampled
     from the Tripo textures around the stump. Rust coverage is calibrated on a baked noise map (empirical
     quantiles, re-baked until it matches): the top of the cuff matches the Tripo thigh just above the seam
     (visible outer/front half), grading over 1.5-6.5 cm below the seam to the reference's heavier plate rust
     (50 %, reference ochre tone); knee pod, shins and blades stay sparse (per-part face attribute, removed).
  6. Body textures: base colour 4096 -> 2048 (budget), roughness/metallic 2048 -> 1024 (texture-memory budget),
     normal kept at 2048.
  7. Save hero_model.blend (images packed). Export separately (command above).
"""
import array
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source", "hero.glb")
OUT = os.path.join(HERE, "hero_model.blend")
TEX = os.path.join(HERE, "textures")

HEAD_TOP = 1.75          # m, hood top
SCALE = 1.12             # upper-body scale (proportions measured against reference/hero/full_body.png)
TRI_TARGET = 19800       # total, leaves margin under the 20,000 character budget
STUMP_MAX_Z = 0.03       # source units: stump boundary loops live below this
LEG_TEX = {"basecolor": 1024, "normal": 1024, "rm": 512}

# ---- leg layout (m). F = forward offset from the stump centre (+Y = front), z = height.
PLATE_BOTTOM_Z = 0.47
PLATE_X_MAX = 0.175      # outer |x| of the plate body (hand inner surface is at |x| ~0.22)
RIDGE_X_MAX = 0.180      # outer |x| of the cuff ridge
# H = ankle (tine root, spring) height = the "hock height" of reference/hero/full_body.md (105-110 px of 791 px
# for 1.75 m -> 0.235-0.243 m). Knee pod spans z 0.425-0.557 there; the spring sits ~0.15 m behind the knee pod.
POD_TOP = (-0.006, 0.545)             # knee pod axis top (forward offset from the plate front, z)
POD_BOT = (-0.036, 0.425)             # knee pod axis bottom
POD_R = (0.030, 0.037)                # half lateral, half depth
KNEE = (-0.034, 0.462)                # knee pivot (inside the pod's lower half)
SHIN_D = (-0.008, -0.134)             # knee -> hock (forward, z): nearly vertical, S-shaped
SHIN_S = [(0, 0), (-0.30, 0.38), (0.30, 0.72), (1, 1)]   # S control points as fractions of SHIN_D
SHIN_R = (0.023, 0.030)               # shin half lateral, half depth at the knee (tapers to ~55 %)
ANKLE_Z = 0.240                       # = H
ANKLE_BACK = -0.120                   # ankle forward offset from the knee pivot (reference ~-0.15; -0.12 keeps
                                      # the ground contact under the centre of mass)
SPRING_T = (0.665, 0.965)             # spring span along the metatarsal (fraction hock -> ankle)
SPRING_R, SPRING_WIRE, SPRING_TURNS, SPRING_SEG = 0.0165, 0.0036, 3.0, 6
# tines: (name, control points (forward of the ankle, height) in H, lateral at root, lateral at tip (x side), samples)
TINES = [("outer", [(0.26, 1.25), (0.02, 1.21), (-0.35, 1.13), (-0.60, 1.02), (-0.78, 0.88), (-0.87, 0.73),
                    (-0.87, 0.59), (-0.78, 0.44), (-0.66, 0.33), (-0.52, 0.27), (-0.32, 0.10), (-0.12, 0.01), (0.10, 0.0),
                    (0.38, 0.0)], 0.006, 0.024, 19),
         ("middle", [(0.13, 1.12), (-0.10, 1.06), (-0.38, 0.97), (-0.57, 0.87), (-0.69, 0.76), (-0.74, 0.63),
                     (-0.71, 0.50), (-0.64, 0.40), (-0.53, 0.31), (-0.36, 0.17), (-0.16, 0.085), (0.05, 0.065), (0.16, 0.08)],
          0.0, 0.004, 15),
         ("inner", [(0.02, 0.98), (-0.18, 0.93), (-0.38, 0.84), (-0.53, 0.72), (-0.60, 0.58), (-0.58, 0.44),
                    (-0.47, 0.28), (-0.34, 0.15), (-0.20, 0.075), (-0.05, 0.045)], -0.006, -0.018, 12)]
TINE_W = (0.009, 0.0045)  # half width (lateral) root -> tip
TINE_T = (0.0058, 0.0032) # half thickness (in profile) root -> tip
# rust coverage (fraction of the surface classified as rust, same classifier as the Tripo sampling):
#   top 3 cm below the seam = the Tripo thigh just above it (measured), grading over the next 5 cm to the
#   reference's heavier plate rust; shins/blades sparse. Thresholds come from the baked noise's empirical quantiles.
RUST_FRAC_PLATE = 0.50
RUST_THR_SHIN = 0.66
RUST_PART = {"thigh plate": 1.0}      # other parts (knee pod, shin, metatarsal, spring, tines): sparse rust
# reference plate rust tone (linear), eyeballed from the orange patches of full_body.png / legs_090.png
REF_RUST_LO, REF_RUST_HI = (0.15, 0.065, 0.012), (0.33, 0.15, 0.022)
RUST_EDGE = 0.025                     # smoothstep width of the rust patch edge (crisp patches)
SEAM_FULL, SEAM_BLEND = 0.015, 0.065  # m below the seam: Tripo density down to 1.5 cm, plate density from 6.5 cm


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
caps = [f for f in bm.faces if all(v.co.z < 0.004 for v in f.verts)]
bmesh.ops.delete(bm, geom=caps, context="FACES_ONLY")
for v in [v for v in bm.verts if not v.link_faces]:
    bm.verts.remove(v)
log("source tris", src_tris, "caps removed", len(caps))


def stump_loops(bm, max_z):
    """Return {side: ordered vert loop} for the two stump boundary loops."""
    out = {}
    bnd = [e for e in bm.edges if e.is_boundary and max(v.co.z for v in e.verts) < max_z]
    for side in (1, -1):
        es = [e for e in bnd if e.verts[0].co.x * side > 0]
        adj = {}
        for e in es:
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        assert all(len(n) == 2 for n in adj.values()), "stump loop is not a simple loop"
        start = next(iter(adj))
        loop, prev, cur = [start], None, start
        while True:
            nxt = [v for v in adj[cur] if v is not prev][0]
            if nxt is start:
                break
            loop.append(nxt)
            prev, cur = cur, nxt
        assert len(loop) == len(adj), "stump boundary has several loops"
        out[side] = loop
    return out


# ----------------------------------------------------------------------------------------------- legs
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


def resample_by_curvature(pts, n, k_turn=0.05):
    """Resample a dense polyline to n points, denser where it turns (weight = length + k_turn * angle)."""
    w = [0.0]
    for i in range(1, len(pts)):
        seg = (pts[i] - pts[i - 1]).length
        ang = 0.0
        if 0 < i < len(pts) - 1:
            a, b = pts[i] - pts[i - 1], pts[i + 1] - pts[i]
            if a.length > 1e-9 and b.length > 1e-9:
                ang = a.angle(b)
        w.append(w[-1] + seg + k_turn * ang)
    out = []
    j = 0
    for s in range(n):
        target = w[-1] * s / (n - 1)
        while j < len(w) - 2 and w[j + 1] < target:
            j += 1
        span = w[j + 1] - w[j]
        u = 0.0 if span <= 0 else min(1.0, max(0.0, (target - w[j]) / span))
        out.append(pts[j].lerp(pts[j + 1], u))
    return out


def polyline_length(pts):
    return sum((pts[i] - pts[i - 1]).length for i in range(1, len(pts)))


class Builder:
    def __init__(self, bm, mat_index):
        self.bm = bm
        self.uv = bm.loops.layers.uv.active
        self.mat = mat_index
        self.islands = []      # list of (list of (loop, Vector2 local uv in m))
        self.faces = []
        self.sharp = []
        self.parts = {}        # part name -> triangle count
        self.geo = {}          # measured leg geometry for the log
        # per-part rust factor (face attribute read by the bake material, removed afterwards)
        self.rl = bm.faces.layers.float.get("rustpart") or bm.faces.layers.float.new("rustpart")

    def count(self, part, faces):
        self.parts[part] = self.parts.get(part, 0) + sum(len(f.verts) - 2 for f in faces)
        for f in faces:
            f[self.rl] = RUST_PART.get(part, 0.0)

    def ring_strip(self, rings, sharp_rings=(), sharp_long=False):
        """Quads between consecutive rings (lists of verts, equal length, closed). One UV island."""
        n = len(rings[0])
        # local UV: u = arclength around the ring, centred; v = distance along
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
        isl, faces = [], []
        for i in range(len(rings) - 1):
            for k in range(n):
                k1 = (k + 1) % n
                f = self.bm.faces.new((rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]))
                f.material_index = self.mat
                f.smooth = True
                for loop, uv in zip(f.loops, (uvs[i][k], uvs[i][k + 1], uvs[i + 1][k + 1], uvs[i + 1][k])):
                    isl.append((loop, uv))
                faces.append(f)
        self.islands.append(isl)
        self.faces += faces
        for i in sharp_rings:
            for k in range(n):
                self.sharp.append(self.bm.edges.get((rings[i][k], rings[i][(k + 1) % n])))
        if sharp_long:
            for i in range(len(rings) - 1):
                for k in range(n):
                    self.sharp.append(self.bm.edges.get((rings[i][k], rings[i + 1][k])))
        return faces

    def cap(self, ring, outward, sharp=True, bulge=0.0):
        """Triangle fan (poke) closing a ring; normal oriented along `outward`; centre pushed out by `bulge` m."""
        f = self.bm.faces.new(ring)
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
        isl = []
        for nf in res["faces"]:
            nf.material_index = self.mat
            nf.smooth = True
            for loop in nf.loops:
                d = loop.vert.co - c
                isl.append((loop, Vector((d.dot(ax), d.dot(ay)))))
            self.faces.append(nf)
        self.islands.append(isl)
        if sharp:
            n = len(ring)
            for k in range(n):
                self.sharp.append(self.bm.edges.get((ring[k], ring[(k + 1) % n])))
        return res["faces"]

    def tube_rings(self, centers, lat, radii, sides, phase):
        """Rings of `sides` verts around a path in a vertical plane; lat = lateral unit axis."""
        rings = []
        for i, c in enumerate(centers):
            t = (centers[min(i + 1, len(centers) - 1)] - centers[max(i - 1, 0)]).normalized()
            nrm = t.cross(lat).normalized()
            rx, rf = radii[i]
            ring = []
            for j in range(sides):
                a = 2 * math.pi * j / sides + phase
                ring.append(self.bm.verts.new(c + lat * (rx * math.cos(a)) + nrm * (rf * math.sin(a))))
            rings.append(ring)
        return rings

    def closed_tube(self, part, centers, lat, radii, sides, phase, bulge=(0.0, 0.0), sharp_long=False):
        """Closed tube (ring strip + two poked caps), normals outward. One rigid piece."""
        rings = self.tube_rings(centers, lat, radii, sides, phase)
        faces = self.ring_strip(rings, sharp_long=sharp_long)
        faces += self.cap(rings[0], centers[0] - centers[1], sharp=not bulge[0], bulge=bulge[0])
        faces += self.cap(rings[-1], centers[-1] - centers[-2], sharp=not bulge[1], bulge=bulge[1])
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        self.count(part, faces)
        return rings


def superellipse(theta, a, b, n):
    c, s = math.cos(theta), math.sin(theta)
    return (a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s))


def build_legs(bm, loops, mat_index):
    B = Builder(bm, mat_index)
    for _key, loop in loops.items():
        xs = [v.co.x for v in loop]
        ys = [v.co.y for v in loop]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        side = 1 if cx > 0 else -1  # from the geometry (the loop keys predate the 180 deg turn)
        X = Vector((side, 0, 0))    # outward lateral axis for this side
        a0, b0 = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
        z0 = sum(v.co.z for v in loop) / len(loop)
        # start the loop at the back-most vertex (UV seam at the back), outward-consistent direction
        i0 = min(range(len(loop)), key=lambda i: loop[i].co.y)
        loop = loop[i0:] + loop[:i0]
        if (loop[1].co.x - loop[0].co.x) * side < 0:
            loop = [loop[0]] + loop[:0:-1]
        thetas = [math.atan2(v.co.y - cy, (v.co.x - cx)) for v in loop]

        # ---- thigh plate (down to the knee). Rings: (z, scale, superellipse exponent, forward offset, outer |x|)
        # cuff joint at the seam: a 2 mm tuck under the Tripo edge, a raised 1 cm ridge band, a step back in;
        # then the plate with one segment groove and the boxy bottom.
        spec = [(z0 - 0.002, 0.985, 2.8, 0.000, RIDGE_X_MAX),    # tuck (joint line)
                (z0 - 0.005, 1.065, 3.0, 0.000, RIDGE_X_MAX),    # ridge top edge
                (z0 - 0.015, 1.065, 3.2, 0.000, RIDGE_X_MAX),    # ridge bottom edge
                (z0 - 0.018, 1.025, 3.3, 0.000, PLATE_X_MAX),    # step in below the ridge
                (0.578, 1.06, 3.5, 0.004, PLATE_X_MAX),
                (0.573, 1.02, 3.5, 0.004, PLATE_X_MAX),          # segment groove
                (0.568, 1.07, 3.5, 0.005, PLATE_X_MAX),
                (PLATE_BOTTOM_Z, 1.10, 3.6, 0.010, PLATE_X_MAX),
                (PLATE_BOTTOM_Z, 0.80, 3.4, 0.010, PLATE_X_MAX)]
        rings = [loop]
        for z, sc, n, df, xmax in spec:
            sc_out = min(sc, max(0.5, (xmax - abs(cx)) / a0))   # narrow the outer half only
            ring = []
            for th in thetas:
                ox, oy = superellipse(th, a0, b0 * sc, n)
                ox *= sc_out if ox * side > 0 else sc
                ring.append(bm.verts.new((cx + ox, cy + oy + df, z)))
            rings.append(ring)
        faces = B.ring_strip(rings, sharp_rings=(2, 3, 8, 9))
        axis = []
        for i in range(len(rings) - 1):
            zc = (rings[i][0].co.z + rings[i + 1][0].co.z) / 2
            axis += [Vector((cx, cy, zc))] * len(loop)
        # the strip has one winding; judge it on the first (outer) segment and flip the whole strip if inward
        s = 0.0
        for f, p in zip(faces[:len(loop)], axis):
            f.normal_update()
            s += f.normal.dot(f.calc_center_median() - p)
        if s < 0:
            bmesh.ops.reverse_faces(bm, faces=faces)
        faces += B.cap(rings[-1], Vector((0, 0, -1)), sharp=False)
        B.count("thigh plate", faces)
        plate_front = max(v.co.y for v in rings[8]) - cy
        B.geo["plate_max_x"] = max(B.geo.get("plate_max_x", 0.0), max(abs(v.co.x) for r in rings[1:] for v in r))

        def P(f, z):
            return Vector((cx, cy + f, z))

        # ---- knee pod: rounded capsule at the plate's front-bottom, top forward of the plate front, bottom
        # below the plate (reference 45/90 deg; the 225/270 deg spur/fin is an AI invention and is ignored)
        pt = P(plate_front + POD_TOP[0], POD_TOP[1])
        pb = P(plate_front + POD_BOT[0], POD_BOT[1])
        prof = [(0.0, 0.62), (0.14, 0.95), (0.45, 1.0), (0.80, 0.92), (1.0, 0.60)]
        B.closed_tube("knee pod", [pb.lerp(pt, t) for t, _ in prof], X,
                      [(POD_R[0] * k, POD_R[1] * k) for _, k in prof], 8, math.pi / 8,
                      bulge=(0.011, 0.011))

        # ---- shin: S-shaped tapered strut knee -> hock (forward under the knee, then back), thick at the top
        K = P(plate_front + KNEE[0], KNEE[1])
        J = K + Vector((0, SHIN_D[0], SHIN_D[1]))
        sh_ctrl = [K + Vector((0, f * SHIN_D[0], z * SHIN_D[1])) for f, z in SHIN_S]
        sh_dense = catmull(sh_ctrl, 120)
        sh_t = [-0.10, 0.06, 0.32, 0.60, 0.90, 1.0]          # loops: knee (0.06), hock (0.90 / 1.0)
        sh_r = [(0.92, 0.92), (1.0, 1.0), (0.84, 0.86), (0.70, 0.72), (0.60, 0.62), (0.56, 0.58)]

        def along(dense, t):
            if t <= 0:
                return dense[0] + (dense[0] - dense[3]).normalized() * (-t) * polyline_length(dense)
            L = polyline_length(dense) * t
            acc = 0.0
            for i in range(1, len(dense)):
                seg = (dense[i] - dense[i - 1]).length
                if acc + seg >= L:
                    return dense[i - 1].lerp(dense[i], (L - acc) / seg)
                acc += seg
            return dense[-1]
        B.closed_tube("shin", [along(sh_dense, t) for t in sh_t], X,
                      [(SHIN_R[0] * a, SHIN_R[1] * b) for a, b in sh_r], 6, math.pi / 6)

        # ---- metatarsal hock -> ankle (down and back): hock bulb, shaft, thin spring core, ankle block
        A = P(K.y - cy + ANKLE_BACK, ANKLE_Z)
        dm = (A - J).normalized()
        LM = (A - J).length
        mt = [(-0.13, 0.013), (-0.05, 0.021), (0.06, 0.020), (0.60, 0.014), (0.66, 0.008),
              (0.97, 0.008), (1.04, 0.018), (1.15, 0.012)]
        B.closed_tube("metatarsal", [J + dm * (LM * t) for t, _ in mt], X,
                      [(r, r * 1.08) for _, r in mt], 6, math.pi / 6, bulge=(0.006, 0.005))

        # ---- coil spring around the core (rigid with the metatarsal): helix, triangular wire section
        e1 = X
        e2 = dm.cross(X).normalized()
        s0 = J + dm * (LM * SPRING_T[0])
        s_len = LM * (SPRING_T[1] - SPRING_T[0])
        nseg = int(SPRING_TURNS * SPRING_SEG)
        hp = []
        for i in range(nseg + 1):
            t = i / nseg
            ph = 2 * math.pi * SPRING_TURNS * t
            hp.append((s0 + dm * (s_len * t) + (e1 * math.cos(ph) + e2 * math.sin(ph)) * SPRING_R, ph))
        srings = []
        for i, (p, ph) in enumerate(hp):
            tg = (hp[min(i + 1, nseg)][0] - hp[max(i - 1, 0)][0]).normalized()
            rad = (e1 * math.cos(ph) + e2 * math.sin(ph))
            bn = tg.cross(rad).normalized()
            rad = bn.cross(tg).normalized()
            srings.append([bm.verts.new(p + (rad * math.cos(a) + bn * math.sin(a)) * SPRING_WIRE)
                           for a in (2 * math.pi * j / 3 for j in range(3))])
        sf = B.ring_strip(srings, sharp_long=False)
        sf += B.cap(srings[0], hp[0][0] - hp[1][0], sharp=False)
        sf += B.cap(srings[-1], hp[-1][0] - hp[-2][0], sharp=False)
        bmesh.ops.recalc_face_normals(bm, faces=sf)
        B.count("spring", sf)

        # ---- three nested reverse-C tines per foot (reference/hero/full_body.md, in hock heights H = ankle z):
        # leave the ankle BACKWARD, arch at ~hock height, rearmost point behind, sweep down, tips hook FORWARD.
        Hh = ANKLE_Z
        fa = A.y - cy
        tine_paths = []
        for name, ctrl, lat0, lat1, nsamp in TINES:
            dense = catmull([Vector((0, fa + f * Hh, z * Hh)) for f, z in ctrl], 300)
            path = resample_by_curvature(dense, nsamp, k_turn=0.03)
            tine_paths.append((name, path, lat0, lat1, polyline_length(dense)))
        lens, rear, tipsF, tipsZ = [], [], [], []
        for name, path, lat0, lat1, L in tine_paths:
            cum = [0.0]
            for i in range(1, len(path)):
                cum.append(cum[-1] + (path[i] - path[i - 1]).length)
            Lp = cum[-1]
            cen = [Vector((cx + side * (lat0 + (lat1 - lat0) * (c / Lp) ** 1.2), cy + p.y, p.z))
                   for p, c in zip(path, cum)]
            rad = []
            for i, c in enumerate(cum):
                t = c / Lp
                w = TINE_W[0] * (1 - t) + TINE_W[1] * t
                th = TINE_T[0] * (1 - t) + TINE_T[1] * t
                k = 0.55 if i == len(cum) - 1 else 1.0         # pointed tip
                rad.append((w * k * math.sqrt(2), th * k * math.sqrt(2)))
            trings = B.tube_rings(cen, X, rad, 4, math.pi / 4)
            tf = B.ring_strip(trings, sharp_long=True)
            tf += B.cap(trings[0], cen[0] - cen[1])
            tf += B.cap(trings[-1], cen[-1] - cen[-2])
            bmesh.ops.recalc_face_normals(bm, faces=tf)
            B.count("tines", tf)
            lens.append(L)
            rear.append(min(p.y for p in path) - fa)
            tipsF.append(path[-1].y - fa)
            tipsZ.append(path[-1].z)
            B.tine_rings = getattr(B, "tine_rings", []) + [trings]
        # contact exactly on y = 0: the outer tine's lowest vertex
        outer_rings = B.tine_rings[-3]
        drop = min(v.co.z for r in outer_rings for v in r)
        for trs in B.tine_rings[-3:]:
            for r in trs:
                for v in r:
                    v.co.z -= drop
        B.geo.setdefault("contact_F", []).extend(
            v.co.y for r in outer_rings for v in r if v.co.z < 0.004)
        B.geo["cy"] = round(cy, 4)
        B.geo["K"] = (round(K.y - cy, 3), round(K.z, 3))
        B.geo["J"] = (round(J.y - cy, 3), round(J.z, 3))
        B.geo["A"] = (round(A.y - cy, 3), round(A.z - drop, 3))
        B.geo["shin_len"] = round(polyline_length(sh_dense), 3)
        B.geo["meta_len"] = round(LM, 3)
        B.geo["bend_deg"] = round(math.degrees((sh_dense[-1] - sh_dense[-8]).angle(dm)), 1)
        B.geo["pod"] = (round((pt - pb).length + 0.022, 3), 2 * POD_R[0], 2 * POD_R[1],
                        round(pb.z - 0.011, 3), round(pt.z + 0.011, 3))
        B.geo["tine_len_H"] = [round(L / Hh, 2) for L in lens]
        B.geo["tine_rear_H"] = [round(r / Hh, 2) for r in rear]
        B.geo["tip_F_H"] = [round(f / Hh, 2) for f in tipsF]
        B.geo["tip_z_m"] = [round(z - drop, 4) for z in tipsZ]
        B.geo["plate_front_F"] = round(plate_front, 3)
        B.geo["drop"] = round(drop, 4)
    return B


def pack_islands(B, pad=0.004):
    """Shelf-pack the builder's islands into [0,1]^2 with uniform scale (texel density equal everywhere)."""
    rects = []
    for isl in B.islands:
        us = [uv.x for _, uv in isl]
        vs = [uv.y for _, uv in isl]
        rects.append((min(us), min(vs), max(us) - min(us), max(vs) - min(vs)))
    order = sorted(range(len(rects)), key=lambda i: -rects[i][3])

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
    for i, isl in enumerate(B.islands):
        mu, mv = rects[i][0], rects[i][1]
        px, py = pos[i]
        for loop, uv in isl:
            loop[B.uv].uv = (px + (uv.x - mu) * lo, py + (uv.y - mv) * lo)
    return lo


# ---------------------------------------------------------------------- budget: decimate the upper body
loops = stump_loops(bm, STUMP_MAX_Z)
ring_n = {s: len(l) for s, l in loops.items()}
probe = bm.copy()
probe_tris0 = sum(len(f.verts) - 2 for f in probe.faces)
build_legs(probe, stump_loops(probe, STUMP_MAX_Z), 1)
leg_tris = sum(len(f.verts) - 2 for f in probe.faces) - probe_tris0
probe.free()
body_tris0 = sum(len(f.verts) - 2 for f in bm.faces)
log("stump loops", ring_n, "legs tris", leg_tris, "body tris (caps removed)", body_tris0)

bm.to_mesh(me)
bm.free()
body_target = TRI_TARGET - leg_tris
if body_tris0 > body_target:
    # weight 1 = may decimate, 0 = protect (face/hood front, hands, stump rings)
    vg = obj.vertex_groups.new(name="decimate")
    for v in me.vertices:
        c = v.co
        protect = (c.z > 0.78 and c.y < 0.02) or (abs(c.x) > 0.17 and c.z < 0.40) or c.z < 0.05
        vg.add([v.index], 0.0 if protect else 1.0, "REPLACE")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    ratio = body_target / body_tris0
    for _ in range(4):
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

# ------------------------------------------------------------------------------- orient, scale, place
bm = bmesh.new()
bm.from_mesh(me)
loops = stump_loops(bm, STUMP_MAX_Z)
assert {s: len(l) for s, l in loops.items()} == ring_n, "decimation changed the stump loops"
STUMP_SRC = sum(v.co.z for l in loops.values() for v in l) / sum(len(l) for l in loops.values())
z_stump = HEAD_TOP - (TOP_SRC - STUMP_SRC) * SCALE
M = (Matrix.Translation((0, 0, z_stump)) @ Matrix.Diagonal((SCALE, SCALE, SCALE, 1.0))
     @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Translation((0, 0, -STUMP_SRC)))
bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
for f in bm.faces:
    f.smooth = True
log("stump height", round(z_stump, 4))

# hand clearance: inner surface of the hands/forearms (body verts beside the hips, outside the hip shell)
hand_min_x = min(abs(v.co.x) for v in bm.verts if 0.70 < v.co.z < 0.95 and abs(v.co.x) > 0.20)

# --------------------------------------------------------------------------------------- legs + material
leg_mat = bpy.data.materials.new("hero_legs")
me.materials.append(leg_mat)
B = build_legs(bm, loops, 1)
uv_scale = pack_islands(B)
log("leg UV scale (uv units per m)", round(uv_scale, 3), "->", round(uv_scale * LEG_TEX["basecolor"]), "px/m")
log("leg parts tris (both legs)", B.parts, "sum", sum(B.parts.values()))
log("leg geometry (F from stump centre, z)", B.geo)
log("hand inner |x|", round(hand_min_x, 4), "plate max |x|", round(B.geo["plate_max_x"], 4),
    "clearance", round(hand_min_x - B.geo["plate_max_x"], 4))
assert hand_min_x - B.geo["plate_max_x"] >= 0.02, "hands closer than 2 cm to the thigh plates"
# feet under the centre of mass: area-weighted surface centroid (proxy for the CoM) inside the ground-contact span
_acc, _area = Vector(), 0.0
for f in bm.faces:
    a = f.calc_area()
    _acc += f.calc_center_median() * a
    _area += a
com_y = (_acc / _area).y
cf = B.geo.pop("contact_F")
log("centre of mass y (surface centroid)", round(com_y, 4), "ground contact y span", round(min(cf), 4),
    "..", round(max(cf), 4))
assert min(cf) <= com_y <= max(cf), "feet are not under the centre of mass"
if os.environ.get("HERO_GEO_ONLY"):
    raise SystemExit(0)
bm.edges.index_update()
sharp_idx = {e.index for e in B.sharp if e is not None}
bm.to_mesh(me)
bm.free()
sharp = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
vals = [False] * len(me.edges)
for i in sharp_idx:
    vals[i] = True
sharp.data.foreach_set("value", vals)
me.update()

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
            if not (z_lo <= p.z <= z_hi and 0.04 < abs(p.x) < 0.19) or (keep and not keep(p)):
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
if "rustpart" in me.attributes:
    me.attributes.remove(me.attributes["rustpart"])
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
