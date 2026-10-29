"""T011 hero conform: Tripo upper body (provided) + generated digitigrade legs -> hero_model.blend.

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b -P blender/models/hero/conform.py

Re-runnable and deterministic. Steps:
  1. Import source/hero.glb (untouched), merge split vertices, drop the encoded custom normals, remove the
     stump caps (two clean 18-vertex boundary loops at mid-thigh).
  2. Decimate the upper body just enough that body + legs <= TRI_TARGET (face, hands and stumps protected).
  3. Rotate 180 deg about Z (front -> Blender +Y -> Godot -Z), scale so the hood top is at 1.75 m.
  4. Generate the legs (bmesh) in the same mesh: thigh plates extruded from the stump loops (closed seam), knee,
     shin angled back, hock, sprung metatarsal, ankle, three C-shaped blade tines per foot touching y=0 at the tips.
  5. Leg UVs (one island per tube/cap, shelf-packed), second PBR material with Cycles-baked procedural textures
     (base colour 1024, normal 1024, roughness/metallic 512).
  6. Body textures: base colour 4096 -> 2048 (budget), roughness/metallic 2048 -> 1024 (texture-memory budget),
     normal kept at 2048.
  7. Save hero_model.blend (images packed). Export separately with tools/blender/export_gltf.py.
"""
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

# Leg profile, F = forward offset from the stump centre (m, +Y), z = height (m).
KNEE_Z = 0.50
PLATE_BOTTOM_Z = 0.47
# (F, z, half-width lateral, half-depth) along the knee -> shin -> hock -> metatarsal -> ankle tube
SHIN_PATH = [
    (0.000, 0.560, 0.030, 0.032),   # top, hidden inside the thigh plate
    (0.002, 0.522, 0.034, 0.040),   # knee loop above
    (0.008, 0.500, 0.040, 0.046),   # knee
    (0.004, 0.476, 0.034, 0.046),   # knee loop below
    (-0.012, 0.448, 0.028, 0.044),  # shin: deep at the top, tapering, curving back
    (-0.035, 0.410, 0.024, 0.038),
    (-0.062, 0.368, 0.020, 0.030),
    (-0.090, 0.331, 0.016, 0.022),
    (-0.106, 0.313, 0.015, 0.018),  # hock loop above
    (-0.118, 0.299, 0.022, 0.024),  # hock (reverse knee)
    (-0.126, 0.285, 0.015, 0.016),  # hock loop below
    (-0.132, 0.273, 0.012, 0.012),  # metatarsal: spring coils
    (-0.137, 0.264, 0.016, 0.016),
    (-0.142, 0.255, 0.012, 0.012),
    (-0.147, 0.246, 0.016, 0.016),
    (-0.151, 0.238, 0.012, 0.012),
    (-0.155, 0.233, 0.015, 0.015),  # ankle loop above
    (-0.160, 0.225, 0.024, 0.024),  # ankle
    (-0.164, 0.209, 0.017, 0.017),  # ankle end
]
# Blade tine centre line (F, z), from inside the ankle back, down and forward to the tip on the ground.
TINE_PATH = [(-0.160, 0.225), (-0.205, 0.222), (-0.250, 0.208), (-0.288, 0.175), (-0.305, 0.125),
             (-0.298, 0.075), (-0.268, 0.035), (-0.215, 0.013), (-0.140, 0.006), (-0.055, 0.004),
             (0.030, 0.003)]
TINE_SAMPLES = 18
TINES = [(-0.050, 0.92, -0.010), (0.0, 1.0, 0.0), (0.050, 0.92, 0.010)]  # (lateral spread at tip, F scale, lateral at ankle)


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


class Builder:
    def __init__(self, bm, mat_index):
        self.bm = bm
        self.uv = bm.loops.layers.uv.active
        self.mat = mat_index
        self.islands = []      # list of (list of (loop, Vector2 local uv in m))
        self.faces = []
        self.sharp = []

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

    def cap(self, ring, outward, sharp=True):
        """Triangle fan (poke) closing a ring; normal oriented along `outward`. Own planar UV island."""
        f = self.bm.faces.new(ring)
        f.normal_update()
        if f.normal.dot(outward) < 0:
            f.normal_flip()
        res = bmesh.ops.poke(self.bm, faces=[f])
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


def superellipse(theta, a, b, n):
    c, s = math.cos(theta), math.sin(theta)
    return (a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s))


def build_legs(bm, loops, mat_index):
    B = Builder(bm, mat_index)
    for side, loop in loops.items():
        X = Vector((side, 0, 0))    # outward lateral axis for this side
        xs = [v.co.x for v in loop]
        ys = [v.co.y for v in loop]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        a0, b0 = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
        z0 = sum(v.co.z for v in loop) / len(loop)
        # start the loop at the back-most vertex (UV seam at the back), outward-consistent direction
        i0 = min(range(len(loop)), key=lambda i: loop[i].co.y)
        loop = loop[i0:] + loop[:i0]
        if (loop[1].co.x - loop[0].co.x) * side < 0:
            loop = [loop[0]] + loop[:0:-1]
        thetas = [math.atan2(v.co.y - cy, (v.co.x - cx)) for v in loop]
        # thigh plate rings: (z, scale, superellipse exponent, forward offset)
        spec = [(z0 - 0.004, 1.06, 2.6, 0.0), (z0 - 0.014, 1.06, 3.0, 0.0), (z0 - 0.020, 1.02, 3.2, 0.0),
                (0.578, 1.06, 3.5, 0.004), (0.573, 1.02, 3.5, 0.004), (0.568, 1.07, 3.5, 0.005),
                (PLATE_BOTTOM_Z, 1.10, 3.6, 0.010), (PLATE_BOTTOM_Z, 0.85, 3.4, 0.010),
                (PLATE_BOTTOM_Z + 0.03, 0.80, 3.0, 0.008)]
        rings = [loop]
        for z, sc, n, df in spec:
            ring = []
            for th in thetas:
                ox, oy = superellipse(th, a0 * sc, b0 * sc, n)
                ring.append(bm.verts.new((cx + ox, cy + oy + df, z)))
            rings.append(ring)
        faces = B.ring_strip(rings, sharp_rings=(2, 3, 7, 8))
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
        B.cap(rings[-1], Vector((0, 0, -1)), sharp=False)

        # knee -> shin -> hock -> metatarsal -> ankle tube (8 sides)
        centers = [Vector((cx, cy + f, z)) for f, z, _, _ in SHIN_PATH]
        radii = [(rx, rf) for _, _, rx, rf in SHIN_PATH]
        srings = B.tube_rings(centers, X, radii, 8, math.pi / 8)
        sf = B.ring_strip(srings)
        c0 = B.cap(srings[0], centers[0] - centers[1])
        c1 = B.cap(srings[-1], centers[-1] - centers[-2])
        bmesh.ops.recalc_face_normals(bm, faces=sf + c0 + c1)

        # three blade tines per foot
        A = Vector((cx, cy + TINE_PATH[0][0], TINE_PATH[0][1]))
        for spread, fsc, lat in TINES:
            # fan out progressively from the ankle to the tip (outward = +side), never crossing
            pts = []
            for i, (f, z) in enumerate(TINE_PATH):
                t = i / (len(TINE_PATH) - 1)
                pts.append(A + Vector(((lat + spread * t ** 1.4) * side, (f - TINE_PATH[0][0]) * fsc,
                                       z - TINE_PATH[0][1])))
            cen = catmull(pts, TINE_SAMPLES)
            L = X
            rad = []
            for i in range(TINE_SAMPLES):
                t = i / (TINE_SAMPLES - 1)
                w = 0.012 * (1 - t) + 0.007 * t       # half width (lateral)
                th = 0.0065 * (1 - t) + 0.0030 * t    # half thickness (in plane)
                rad.append((w * math.sqrt(2), th * math.sqrt(2)))
            # tip touches the ground: shift so the lowest point of the band is exactly z = 0
            trings = B.tube_rings(cen, L, rad, 4, math.pi / 4)
            low = min(v.co.z for r in trings for v in r)
            for r in trings:
                for v in r:
                    v.co.z -= low
            tf = B.ring_strip(trings, sharp_long=True)
            t0 = B.cap(trings[0], cen[0] - cen[1])
            t1 = B.cap(trings[-1], cen[-1] - cen[-2])
            bmesh.ops.recalc_face_normals(bm, faces=tf + t0 + t1)
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

# --------------------------------------------------------------------------------------- legs + material
leg_mat = bpy.data.materials.new("hero_legs")
me.materials.append(leg_mat)
B = build_legs(bm, loops, 1)
uv_scale = pack_islands(B)
log("leg UV scale (uv units per m)", round(uv_scale, 3), "->", round(uv_scale * LEG_TEX["basecolor"]), "px/m")
bm.edges.index_update()
sharp_idx = {e.index for e in B.sharp if e is not None}
bm.to_mesh(me)
leg_face_count = len(B.faces)
bm.free()
sharp = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
vals = [False] * len(me.edges)
for i in sharp_idx:
    vals[i] = True
sharp.data.foreach_set("value", vals)
me.update()


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

    # rust mask: more rust on the thigh plates (z above the plate bottom), sparse on shins and blades
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

    rust_big = noise(8.0, 8.0, 0.65).outputs["Fac"]
    rust_fine = noise(40.0, 4.0, 0.6).outputs["Fac"]
    rust_n = math_("ADD", math_("MULTIPLY", rust_big, 0.8), math_("MULTIPLY", rust_fine, 0.2))
    plate = smoothstep(sep.outputs["Z"], PLATE_BOTTOM_Z - 0.03, PLATE_BOTTOM_Z + 0.01)
    thr = mixf(plate, 0.60, 0.515)
    rust = smoothstep(rust_n, thr, math_("ADD", thr, 0.05))
    # colours
    metal_var = noise(22.0, 4.0, 0.5).outputs["Fac"]
    metal = mix(metal_var, (0.030, 0.029, 0.027, 1), (0.085, 0.080, 0.072, 1))
    rust_var = noise(35.0, 6.0, 0.6).outputs["Fac"]
    rustc = mix(rust_var, (0.15, 0.060, 0.016, 1), (0.42, 0.22, 0.05, 1))
    base = mix(rust, metal, rustc)
    L(base, bsdf.inputs["Base Color"])
    rough = mixf(rust, math_("ADD", math_("MULTIPLY", metal_var, 0.22), 0.52), 0.90)
    metal_f = mixf(rust, 0.70, 0.10)
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


leg_imgs = bake_leg_textures()
pbr_material(leg_mat, leg_imgs["basecolor"], leg_imgs["rm"], leg_imgs["normal"])
leg_mat.use_backface_culling = True    # legs are closed and outward-facing; body stays double-sided as delivered

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
