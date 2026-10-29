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
  4. Generate the legs (bmesh) in the same mesh, one closed piece per rigid part so per-bone rigid weights stay easy:
       thigh plate   extruded from the stump loop (seam closed) with a raised cuff ridge at the seam (plate joint),
                     a segment groove and a narrowed outer side (hand clearance)          -> thigh bone
       knee housing  rounded capsule at the front-bottom of the plate, top sticking up    -> shin bone
       shin strut    thin strut knee -> hock, angled back, plus a parallel rod            -> shin bone
       metatarsal    hock bulb -> shaft -> spring coils -> ankle bulb, angled forward     -> metatarsal bone
       3 tines       nested C blades (different curl radii/lengths), tips forward on y=0  -> foot/toe bone
     Edge loops sit above and below the knee, hock and ankle.
  5. Leg UVs (one island per tube/cap, shelf-packed), second PBR material with Cycles-baked procedural textures
     (base colour 1024, normal 1024, roughness/metallic 512). Metal/rust colours, roughness, metallic and the rust
     amount next to the seam are sampled from the Tripo textures around the stump UVs.
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
# knee housing: capsule axis from (front - 0.012, bottom - 0.040) to (front + 0.008, bottom + 0.070)
HOUSING_R = (0.024, 0.028)            # half lateral, half depth
KNEE_BELOW_PLATE = 0.025              # knee pivot below the plate bottom
KNEE_BEHIND_FRONT = 0.010             # knee pivot behind the plate front
SHIN_LEN, SHIN_ANGLE = 0.200, 45.0    # knee -> hock, degrees below horizontal, backwards
META_LEN, META_ANGLE = 0.100, 10.0    # hock -> ankle, degrees forward of vertical
SHIN_R = (0.015, 0.018)               # strut half lateral, half depth (3.0 x 3.6 cm)
ROD_R, ROD_OFFSET = 0.006, 0.026      # parallel rod behind the strut
# tines: (back extent behind the ankle, curl half-width Rx, curl half-height Rz, tip forward of the ankle,
#         start height offset at the ankle, lateral at tip as a multiple of `side`, samples)
TINES = [(0.215, 0.105, 0.110, 0.200, 0.008, 0.035, 19),    # outer curl, outboard
         (0.175, 0.085, 0.088, 0.150, 0.000, 0.000, 18),    # middle
         (0.135, 0.065, 0.066, 0.100, -0.008, -0.035, 17)]  # inner curl, inboard
TINE_W = (0.010, 0.006)   # half width (lateral) root -> tip
TINE_T = (0.0055, 0.003)  # half thickness (in profile) root -> tip
# rust amount on the plate below the seam band (the band itself stays bare metal); next to the seam the
# threshold is raised so the rust coverage matches the Tripo paint sampled around the stump
RUST_THR_PLATE = 0.515
RUST_THR_SHIN = 0.60
RUST_NOISE_SD = 0.052    # spread of the rust noise (calibrated against the baked coverage, see the log)


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

    def count(self, part, faces):
        self.parts[part] = self.parts.get(part, 0) + sum(len(f.verts) - 2 for f in faces)

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

        # ---- thigh plate. Rings: (z, scale, superellipse exponent, forward offset, outer |x| limit)
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

        # ---- knee housing (rounded capsule at the plate's front-bottom, top sticking up)
        hb = P(plate_front - 0.012, PLATE_BOTTOM_Z - 0.040)
        ht = P(plate_front + 0.008, PLATE_BOTTOM_Z + 0.070)
        prof = [(0.0, 0.62), (0.12, 0.95), (0.45, 1.0), (0.82, 0.90), (1.0, 0.55)]
        B.closed_tube("knee housing", [hb.lerp(ht, t) for t, _ in prof], X,
                      [(HOUSING_R[0] * k, HOUSING_R[1] * k) for _, k in prof], 8, math.pi / 8,
                      bulge=(0.010, 0.010))

        # ---- shin strut knee -> hock (backwards), and a parallel rod behind it
        K = P(plate_front - KNEE_BEHIND_FRONT, PLATE_BOTTOM_Z - KNEE_BELOW_PLATE)
        a = math.radians(SHIN_ANGLE)
        d = Vector((0, -math.cos(a), -math.sin(a)))           # down and back
        H = K + d * SHIN_LEN
        nb = Vector((0, d.z, -d.y))                            # in-plane normal pointing back/up
        st = [(-0.10, 0.92), (0.05, 1.0), (0.50, 0.95), (0.92, 1.0), (1.0, 0.86)]   # knee/hock loops
        B.closed_tube("shin strut", [K + d * (SHIN_LEN * t) for t, _ in st], X,
                      [(SHIN_R[0] * k, SHIN_R[1] * k) for _, k in st], 6, math.pi / 6)
        B.closed_tube("shin rod", [K + d * (SHIN_LEN * -0.12) + nb * ROD_OFFSET, H + nb * ROD_OFFSET], X,
                      [(ROD_R, ROD_R), (ROD_R, ROD_R)], 6, 0.0)

        # ---- metatarsal hock -> ankle (forward of vertical): hock bulb, shaft, spring coils, ankle bulb
        m = math.radians(META_ANGLE)
        dm = Vector((0, math.sin(m), -math.cos(m)))
        A = H + dm * META_LEN
        mt = [(-0.22, 0.014, 0.014), (-0.11, 0.024, 0.026), (0.00, 0.026, 0.028), (0.13, 0.016, 0.016),
              (0.74, 0.016, 0.016), (0.86, 0.012, 0.012), (1.00, 0.022, 0.022),
              (1.16, 0.014, 0.014)]
        B.closed_tube("metatarsal", [H + dm * (META_LEN * t) for t, _, _ in mt], X,
                      [(rx, rf) for _, rx, rf in mt], 8, math.pi / 8, bulge=(0.006, 0.004))

        # ---- three nested C tines per foot: back from the ankle, curl down, run forward to the tip on y=0
        lens = []
        for back, rx, rz, tip, dz0, lat_tip, nsamp in TINES:
            fa, za = A.y - cy, A.z
            fb = fa - back + rx                                  # curl centre F
            zc = rz + 0.006                                      # curl centre z (curl bottom 6 mm up)
            start = (fa, za + dz0)

            def E(deg):
                r = math.radians(deg)
                return (fb + rx * math.cos(r), zc + rz * math.sin(r))
            bot = E(270)
            ctrl = [start, E(100), E(140), E(180), E(220), E(255), bot,
                    ((bot[0] + fa + tip) / 2, 0.003), (fa + tip, 0.0)]
            dense = catmull([Vector((0, f, z)) for f, z in ctrl], 240)
            path = resample_by_curvature(dense, nsamp)
            L = polyline_length(path)
            cum = [0.0]
            for i in range(1, len(path)):
                cum.append(cum[-1] + (path[i] - path[i - 1]).length)
            cen = []
            for p, c in zip(path, cum):
                t = c / L
                cen.append(Vector((cx + side * lat_tip * (0.18 + 0.82 * t ** 1.2), cy + p.y, p.z)))
            rad = []
            for c in cum:
                t = c / L
                w = TINE_W[0] * (1 - t) + TINE_W[1] * t
                th = TINE_T[0] * (1 - t) + TINE_T[1] * t
                rad.append((w * math.sqrt(2), th * math.sqrt(2)))
            trings = B.tube_rings(cen, X, rad, 4, math.pi / 4)
            low = min(v.co.z for r in trings for v in r)
            for r in trings:
                for v in r:
                    v.co.z -= low                                # contact exactly on y = 0
            tf = B.ring_strip(trings, sharp_long=True)
            tf += B.cap(trings[0], cen[0] - cen[1])
            tf += B.cap(trings[-1], cen[-1] - cen[-2])
            bmesh.ops.recalc_face_normals(bm, faces=tf)
            B.count("tines", tf)
            lens.append(round(L, 3))
        B.geo["K"] = (round(K.y - cy, 3), round(K.z, 3))
        B.geo["H"] = (round(H.y - cy, 3), round(H.z, 3))
        B.geo["A"] = (round(A.y - cy, 3), round(A.z, 3))
        B.geo["housing"] = (round((ht - hb).length + 0.02, 3), 2 * HOUSING_R[0], 2 * HOUSING_R[1],
                            round(ht.z + 0.010, 3))
        B.geo["tine_len"] = lens
        B.geo["tips_F"] = [round(A.y - cy + t[3], 3) for t in TINES]
        B.geo["curl_back_F"] = [round(A.y - cy - t[0], 3) for t in TINES]
        B.geo["plate_front_F"] = round(plate_front, 3)
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


def sample_region(mat_index, z_lo, z_hi, images):
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
            if not (z_lo <= p.z <= z_hi and 0.04 < abs(p.x) < 0.19):
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
log("Tripo paint around the stump", {k: (tuple(round(x, 4) for x in v) if isinstance(v, tuple) else
                                         (round(v, 3) if isinstance(v, float) else v)) for k, v in TRIPO.items()})
# fallbacks in case the region holds no rust/metal samples
T_METAL = TRIPO["metal"] or (0.014, 0.009, 0.005)
T_RUST = TRIPO["rust"] or (0.08, 0.048, 0.017)
T_MROUGH = TRIPO["metal_rough"] if TRIPO["metal_rough"] is not None else 0.6
T_RROUGH = TRIPO["rust_rough"] if TRIPO["rust_rough"] is not None else 0.85
T_MMETAL = TRIPO["metal_metal"] if TRIPO["metal_metal"] is not None else 0.7
T_RMETAL = TRIPO["rust_metal"] if TRIPO["rust_metal"] is not None else 0.2
# rust threshold next to the seam: the rust noise is ~normal(0.5, RUST_NOISE_SD); pick the threshold whose smoothstep
# midpoint leaves the sampled Tripo rust fraction above it (clamped to sane coverage 2..40 %)
_q = min(0.40, max(0.02, TRIPO["rust_frac"]))
_z = math.sqrt(3) / math.pi * math.log((1 - _q) / _q)       # logistic approximation of the normal quantile
RUST_THR_SEAM = 0.5 + RUST_NOISE_SD * _z - 0.025
log("rust threshold next to the seam", round(RUST_THR_SEAM, 4), "plate", RUST_THR_PLATE, "shin", RUST_THR_SHIN)


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

    # rust mask: plate below the seam band heavy (reference), next to the seam matched to the Tripo paint,
    # the cuff ridge band bare, shins/blades sparse
    rust_big = noise(8.0, 8.0, 0.65).outputs["Fac"]
    rust_fine = noise(40.0, 4.0, 0.6).outputs["Fac"]
    rust_n = math_("ADD", math_("MULTIPLY", rust_big, 0.8), math_("MULTIPLY", rust_fine, 0.2))
    z = sep.outputs["Z"]
    plate = smoothstep(z, PLATE_BOTTOM_Z - 0.03, PLATE_BOTTOM_Z + 0.01)
    near_seam = smoothstep(z, z_stump - 0.13, z_stump - 0.035)
    band = smoothstep(z, z_stump - 0.021, z_stump - 0.018)
    thr_plate = mixf(near_seam, RUST_THR_PLATE, RUST_THR_SEAM)
    thr = mixf(plate, RUST_THR_SHIN, thr_plate)
    thr = mixf(band, thr, 1.2)
    rust = smoothstep(rust_n, thr, math_("ADD", thr, 0.05))
    # colours, anchored on the Tripo medians sampled around the stump
    metal_var = noise(22.0, 4.0, 0.5).outputs["Fac"]
    metal = mix(metal_var, scaled(T_METAL, 0.62), scaled(T_METAL, 1.32))
    rust_var = noise(35.0, 6.0, 0.6).outputs["Fac"]
    rustc = mix(rust_var, scaled(T_RUST, 0.75), scaled(T_RUST, 2.3, 0.5))
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
    return nt, out, bsdf, emit, base, rm


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
    nt, out, bsdf, emit, base, rm = build_proc_material(proc)
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
    imgs = {}
    for key, kind in (("basecolor", "EMIT"), ("rm", "EMIT"), ("normal", "NORMAL")):
        size = LEG_TEX[key]
        img = bpy.data.images.new(f"hero_legs_{key}", size, size, alpha=False, float_buffer=False)
        img.colorspace_settings.name = "sRGB" if key == "basecolor" else "Non-Color"
        img_node.image = img
        if kind == "EMIT":
            L = nt.links
            L.new(base if key == "basecolor" else rm.outputs[0], emit.inputs[0])
            L.new(emit.outputs[0], out.inputs[0])
        else:
            nt.links.new(bsdf.outputs[0], out.inputs[0])
        bpy.ops.object.bake(type=kind, normal_space="TANGENT", use_clear=True, margin=8)
        path = os.path.join(TEX, f"hero_legs_{key}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        imgs[key] = path
        log("baked", key, size)
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
leg_mat.use_backface_culling = True    # legs are closed and outward-facing; body stays double-sided as delivered
# check the blend: the leg plate just below the cuff band vs the Tripo paint just above the seam
l_base, l_rm = sample_region(1, z_stump - 0.07, z_stump - 0.022, [leg_base_img, leg_rm_img])
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
