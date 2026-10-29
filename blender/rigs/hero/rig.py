"""hero rig + 8 animation clips (T013). Reproducible from the model; never modifies it.

Build (reads blender/models/hero/hero_model.blend, writes the rig .blend):
  python3 tools/qa/memguard.py -- blender -b --factory-startup -P blender/rigs/hero/rig.py -- \
      --out blender/rigs/hero/hero_rig.blend
Export (GLB with skin + animations):
  python3 tools/qa/memguard.py -- blender -b blender/rigs/hero/hero_rig.blend -P tools/blender/export_gltf.py -- \
      --out godot/assets/hero/rig/hero.glb
Checks (table) and review renders:
  python3 tools/qa/memguard.py -- blender -b blender/rigs/hero/hero_rig.blend -P blender/rigs/hero/qa/check_rig.py
  python3 tools/qa/memguard.py -- blender -b blender/rigs/hero/hero_rig.blend -P blender/rigs/hero/qa/render_strips.py

Conventions: Blender Z up, character faces +Y (= -Z in Godot), left side is x < 0. Rest pose = delivered I-pose
(no re-rest). Clips are in place (no root motion), 30 fps, keyed on every frame (frame 0..N; loops have
pose(N) == pose(0), so the clip length N/30 s loops without a duplicated frame).
Design notes:
- Legs are digitigrade: upper_leg (hip->knee), lower_leg (knee->hock), metatarsal (hock->tine root),
  foot (tine root->blade tip). The blades + the tube below the hock move as one rigid "foot unit"
  (metatarsal and foot never bend against each other in the clips), so the thin tines never bend or shear.
- Feet are solved analytically per frame (2-bone IK hip->hock with the foot unit placed on the ground,
  rolled about the blade's rear end at strike and about the blade tip at push-off), so planted blades move
  backward at exactly the game speed during stance.
- Weights are computed geometrically (not bone heat): arms are a topological region (they only touch the torso
  at the top of the shoulder), so arm bones never influence torso/backpack vertices.
"""
import math
import sys

import bpy
import numpy as np
from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

MODEL_BLEND = "blender/models/hero/hero_model.blend"
FPS = 30
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else "blender/rigs/hero/hero_rig.blend"
ONLY = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None

# ----------------------------------------------------------------------------------------------------------
# Skeleton (left side given; right side mirrored x -> -x). Joint positions measured on the final model.
# ----------------------------------------------------------------------------------------------------------
HIP = Vector((-0.11, 0.0686, 0.8708))
KNEE = Vector((-0.1303, 0.0834, 0.4471))
HOCK = Vector((-0.1413, 0.0238, 0.336))
SCREW = Vector((-0.1531, -0.048, 0.2233))           # end of the metatarsal tube (screw tip)
TINE_ROOT = HOCK.lerp(SCREW, 0.72)                   # where the tines leave the tube (measured t = 0.6..1.0)
BLADE_TIP = Vector((-0.154, 0.034, 0.0))             # front end of the outer tine's ground segment
BLADE_REAR = Vector((-0.154, -0.096, 0.0))           # rear end of the ground segment
BLADE_MID = Vector((-0.154, -0.031, 0.0))
SHOULDER = Vector((-0.195, 0.025, 1.385))
ELBOW = Vector((-0.208, 0.022, 1.115))
WRIST = Vector((-0.238, 0.062, 0.930))
HAND_TIP = Vector((-0.250, 0.085, 0.780))

SPINE_Z = [0.90, 1.00, 1.12, 1.26, 1.43, 1.53, 1.75]  # hips, spine, chest, upper_chest, neck, head (head..tail)
SPINE_Y = [0.055, 0.050, 0.045, 0.040, 0.035, 0.045, 0.060]
SPINE_NAMES = ["hips", "spine", "chest", "upper_chest", "neck", "head"]

SIDES = {"l": -1.0, "r": 1.0}


def mir(v, s):
    """v is given for the left side (x<0); return it for side sign s (-1 left, +1 right)."""
    return Vector((v.x * -s, v.y, v.z))


def bone_defs():
    d = [("root", Vector((0, 0, 0)), Vector((0, 0.15, 0)), None)]
    parent = "root"
    for i, n in enumerate(SPINE_NAMES):
        d.append((n, Vector((0, SPINE_Y[i], SPINE_Z[i])), Vector((0, SPINE_Y[i + 1], SPINE_Z[i + 1])), parent))
        parent = n
    for sd, s in SIDES.items():
        clav_head = Vector((-0.03, 0.035, 1.41))
        d += [
            (f"shoulder_{sd}", mir(clav_head, s), mir(SHOULDER, s), "upper_chest"),
            (f"upper_arm_{sd}", mir(SHOULDER, s), mir(ELBOW, s), f"shoulder_{sd}"),
            (f"lower_arm_{sd}", mir(ELBOW, s), mir(WRIST, s), f"upper_arm_{sd}"),
            (f"hand_{sd}", mir(WRIST, s), mir(HAND_TIP, s), f"lower_arm_{sd}"),
            (f"upper_leg_{sd}", mir(HIP, s), mir(KNEE, s), "hips"),
            (f"lower_leg_{sd}", mir(KNEE, s), mir(HOCK, s), f"upper_leg_{sd}"),
            (f"metatarsal_{sd}", mir(HOCK, s), mir(TINE_ROOT, s), f"lower_leg_{sd}"),
            (f"foot_{sd}", mir(TINE_ROOT, s), mir(BLADE_TIP, s), f"metatarsal_{sd}"),
        ]
    return d


# ----------------------------------------------------------------------------------------------------------
# Scene setup
# ----------------------------------------------------------------------------------------------------------
def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(MODEL_BLEND, link=False) as (src, dst):
        dst.objects = ["hero"]
    hero = dst.objects[0]
    bpy.context.scene.collection.objects.link(hero)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    arm_data = bpy.data.armatures.new("Armature")
    arm = bpy.data.objects.new("Armature", arm_data)
    sc.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in bone_defs():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = False
        eb.use_deform = name != "root"
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    hero.parent = arm
    mod = hero.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return hero, arm


# ----------------------------------------------------------------------------------------------------------
# Weights
# ----------------------------------------------------------------------------------------------------------
def sstep(e0, e1, x):
    t = (x - e0) / (e1 - e0)
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def arm_regions(me):
    """Vertices reachable from the hand while staying at |x| > 0.16 (the arms touch the torso only there)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    res = {}
    for sd, s in SIDES.items():
        seed = min((v for v in bm.verts if v.co.x * s > 0),
                   key=lambda v: (v.co - Vector((0.245 * s, 0.08, 0.80))).length)
        seen = {seed.index}
        st = [seed]
        while st:
            a = st.pop()
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen and abs(b.co.x) > 0.16 and b.co.z < 1.50:
                    seen.add(b.index)
                    st.append(b)
        res[sd] = seen
    bm.free()
    return res


def seg_param(p, a, b):
    ab = b - a
    t = (p - a).dot(ab) / ab.length_squared
    return t, (p - (a + ab * min(max(t, 0), 1))).length


def chain_u(p, pts):
    """Arc-length coordinate of p projected onto polyline pts (closest segment)."""
    best = None
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        t, d = seg_param(p, a, b)
        L = (b - a).length
        tc = min(max(t, 0 if i else -1e9), 1 if i < len(pts) - 2 else 1e9)
        u = acc + tc * L
        if best is None or d < best[0] - 1e-9:
            best = (d, u)
        acc += L
    joints = []
    acc = 0.0
    for i in range(len(pts) - 1):
        joints.append(acc)
        acc += (pts[i + 1] - pts[i]).length
    return best[1], joints[1:]


POD_CENTER = Vector((-0.130, 0.150, 0.455))   # replaced by the measured centroid in compute_weights()


def leg_local(c):
    """Weights inside one leg for a vertex c given in LEFT-side coordinates. All blends are continuous
    (the knee pod is welded to the thigh plate and the shin, so a hard boundary would tear under bending)."""
    t, d = seg_param(c, HOCK, SCREW)
    tine = c.z < 0.20 or (c.z < 0.345 and (d > 0.024 or t > 1.05))
    if tine:
        return {"foot": 1.0}
    below = sstep(0.47, 0.405, c.z)                     # 0 on the thigh plate, 1 on the shin tube
    pod = sstep(0.06, 0.02, (c - POD_CENTER).length)    # smooth blob around the knee pod
    below = max(below, 0.40 * pod) if c.z > 0.40 else below
    wt = 1.0 - below
    w_sh = sstep(0.352, 0.405, c.z)   # tine roots reach z 0.345: keep the tube below them rigid with the foot unit
    w_me = sstep(0.235, 0.275, c.z)
    rem = (1 - wt) * (1 - w_sh)
    return {"upper_leg": wt, "lower_leg": (1 - wt) * w_sh, "metatarsal": rem * w_me, "foot": rem * (1 - w_me)}


GROIN_TO_HIPS = 0.30     # share of the thigh weight moved onto hips on the front-groin ring
FOLD_SMOOTH_ITERS = 8


def smooth_folds(me, W, arm_of):
    """Soften the deep-flexion folds (crouch/crawl): (1) on the front-groin ring (vertices shared by hips and a
    thigh) 30% of the thigh weight goes to hips; (2) Laplacian smoothing of the weights in the groin band and in
    the back-of-knee band, so the compression spreads over several face rows instead of collapsing one."""
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    co = [v.co for v in me.vertices]
    for i, c in enumerate(co):
        if i in arm_of or not (0.72 < c.z < 0.93 and c.y > -0.03 and abs(c.x) < 0.20):
            continue
        h = W[i].get("hips", 0.0)
        if 0.02 < h < 0.98:
            for sd in SIDES:
                k = f"upper_leg_{sd}"
                if k in W[i]:
                    m = W[i][k] * (GROIN_TO_HIPS + 0.40 * sstep(0.06, 0.0, abs(c.x)))   # crotch centre: 70%
                    W[i][k] -= m
                    W[i]["hips"] = W[i].get("hips", 0.0) + m

    def region(c):
        groin = 0.70 < c.z < 0.95 and abs(c.x) < 0.22 and c.y > -0.065
        knee = 0.38 < c.z < 0.54 and c.y < 0.10 and abs(c.x) > 0.05
        return groin or knee

    R_ = [i for i, c in enumerate(co) if i not in arm_of and region(c)]
    for _ in range(FOLD_SMOOTH_ITERS):
        new = {}
        for i in R_:
            acc = {}
            ns = [j for j in nb[i] if j not in arm_of]
            if not ns:
                continue
            for j in ns:
                for bn, x in W[j].items():
                    acc[bn] = acc.get(bn, 0.0) + x / len(ns)
            w = {bn: 0.5 * W[i].get(bn, 0.0) + 0.5 * acc.get(bn, 0.0) for bn in set(acc) | set(W[i])}
            new[i] = w
        for i, w in new.items():
            W[i] = w
    print("fold smoothing: verts", len(R_))


def compute_weights(hero):
    global POD_CENTER
    me = hero.data
    pod = [v.co for v in me.vertices if v.co.x < -0.05 and v.co.y > 0.145 and 0.40 < v.co.z < 0.53]
    POD_CENTER = sum(pod, Vector()) / len(pod)
    print("knee pod centre", tuple(round(x, 3) for x in POD_CENTER), len(pod))
    arms = arm_regions(me)
    arm_of = {}
    for sd, ids in arms.items():
        for i in ids:
            arm_of[i] = sd
    spine_j = SPINE_Z[1:6]
    spine_h = [0.04, 0.04, 0.04, 0.03, 0.03]
    W = []
    for v in me.vertices:
        c = v.co
        w = {}
        if v.index in arm_of:
            sd = arm_of[v.index]
            s = SIDES[sd]
            cl = Vector((-abs(c.x), c.y, c.z))
            u, (ue, uw) = chain_u(cl, [SHOULDER, ELBOW, WRIST, HAND_TIP])
            c_el = sstep(ue - 0.035, ue + 0.035, u)
            c_wr = sstep(uw - 0.02, uw + 0.02, u)
            clav = sstep(0.215, 0.165, abs(c.x)) * sstep(1.34, 1.40, c.z)
            w[f"upper_arm_{sd}"] = (1 - c_el) * (1 - clav)
            w[f"lower_arm_{sd}"] = (c_el - c_wr) * (1 - clav)
            w[f"hand_{sd}"] = c_wr * (1 - clav)
            w[f"shoulder_{sd}"] = clav
        else:
            backpack = c.y < -0.065 and 0.98 < c.z < 1.46 and abs(c.x) < 0.165
            if backpack:
                w["upper_chest"] = 1.0
            else:
                cs = [sstep(j - h, j + h, c.z) for j, h in zip(spine_j, spine_h)]
                tw = {"hips": 1 - cs[0], "spine": cs[0] - cs[1], "chest": cs[1] - cs[2],
                      "upper_chest": cs[2] - cs[3], "neck": cs[3] - cs[4], "head": cs[4]}
                # clavicle influence on the shoulder top of the torso (not the arm: arms are separate)
                if c.z > 1.33 and abs(c.x) > 0.10:
                    sd = "l" if c.x < 0 else "r"
                    k = sstep(0.10, 0.16, abs(c.x)) * sstep(1.33, 1.38, c.z) * 0.8
                    tw = {b: x * (1 - k) for b, x in tw.items()}
                    tw[f"shoulder_{sd}"] = k
                # legs (blend out of the hips between z 0.90 and 0.78)
                wl = sstep(0.90, 0.78, c.z) if c.z < 0.90 else 0.0
                if wl > 0:
                    tw = {b: x * (1 - wl) for b, x in tw.items()}
                    share_l = min(max(0.5 - c.x / 0.10, 0.0), 1.0)
                    for sd, share in (("l", share_l), ("r", 1 - share_l)):
                        if share <= 0:
                            continue
                        s = SIDES[sd]
                        cl = Vector((c.x * -s, c.y, c.z))  # into left-side coords
                        for b, x in leg_local(cl).items():
                            tw[f"{b}_{sd}"] = tw.get(f"{b}_{sd}", 0) + x * wl * share
                w = tw
        W.append(w)
    # armpit seam: arm vertices near the torso blend toward the weights of the adjacent torso vertex, so the
    # connecting faces stretch over a 5 cm band instead of one face row. Torso vertices get no arm weight.
    seam = set()
    for e in me.edges:
        a, b = e.vertices
        if (a in arm_of) != (b in arm_of):
            seam.add(b if a in arm_of else a)
    seam_co = [(i, me.vertices[i].co.copy()) for i in seam]
    if seam_co:
        for i, sd in arm_of.items():
            c = me.vertices[i].co
            j, cj = min(seam_co, key=lambda ic: (ic[1] - c).length_squared)
            k = 0.85 * sstep(0.05, 0.0, (cj - c).length) * sstep(1.12, 1.18, c.z)
            if k > 0:
                w = {b: x * (1 - k) for b, x in W[i].items()}
                for b, x in W[j].items():
                    w[b] = w.get(b, 0) + x * k
                W[i] = w
    smooth_folds(me, W, arm_of)
    for i, w in enumerate(W):
        w = {b: x for b, x in w.items() if x > 1e-4}
        top = sorted(w.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(x for _, x in top)
        W[i] = {b: x / tot for b, x in top}
    groups = {}
    for i, w in enumerate(W):
        for b, x in w.items():
            if b not in groups:
                groups[b] = hero.vertex_groups.new(name=b)
            groups[b].add([i], x, "REPLACE")
    print("weights: groups", sorted(groups))
    return W, arms


# ----------------------------------------------------------------------------------------------------------
# Math helpers
# ----------------------------------------------------------------------------------------------------------
def Rx(deg):
    return Quaternion((1, 0, 0), math.radians(deg))


def Ry(deg):
    return Quaternion((0, 1, 0), math.radians(deg))


def Rz(deg):
    return Quaternion((0, 0, 1), math.radians(deg))


def frame_rot(d0, n0, d1, n1):
    def basis(d, n):
        d = d.normalized()
        n = (n - d * n.dot(d))
        if n.length < 1e-8:
            n = d.orthogonal()
        n.normalize()
        return Matrix((d, n, d.cross(n))).transposed()
    return (basis(d1, n1) @ basis(d0, n0).transposed()).to_quaternion()


def TR(t, q=None):
    m = Matrix.Translation(t)
    if q is not None:
        m = m @ q.to_matrix().to_4x4()
    return m


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 2


def ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x * x


def hermite(p0, p1, m0, m1, s):
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def bump(s):
    s = min(max(s, 0.0), 1.0)
    return 16 * s * s * (1 - s) * (1 - s)


def keyed(keys, f, cyclic_len=None):
    """Catmull-Rom through (frame, value) keys; clamped ends (or cyclic if cyclic_len)."""
    ks = list(keys)
    if cyclic_len:
        f = f % cyclic_len
        ks = [(ks[-2][0] - cyclic_len, ks[-2][1])] + ks + [(ks[1][0] + cyclic_len, ks[1][1])]
    else:
        ks = [ks[0]] + ks + [ks[-1]]
    for i in range(1, len(ks) - 2):
        f0, f1 = ks[i][0], ks[i + 1][0]
        if f0 <= f <= f1 or (i == len(ks) - 3):
            s = 0 if f1 == f0 else min(max((f - f0) / (f1 - f0), 0), 1)
            p0, p1 = ks[i][1], ks[i + 1][1]
            dtp = (ks[i + 1][0] - ks[i - 1][0]) or 1
            dtn = (ks[i + 2][0] - ks[i][0]) or 1
            m0 = (ks[i + 1][1] - ks[i - 1][1]) / dtp * (f1 - f0)
            m1 = (ks[i + 2][1] - ks[i][1]) / dtn * (f1 - f0)
            if ks[i - 1][0] == f0:
                m0 = 0
            if ks[i + 2][0] == f1:
                m1 = 0
            return hermite(p0, p1, m0, m1, s)
    return ks[-1][1]


# ----------------------------------------------------------------------------------------------------------
# Pose solver
# ----------------------------------------------------------------------------------------------------------
class Pose:
    def __init__(self):
        self.hips_pos = Vector((0, SPINE_Y[0], SPINE_Z[0]))
        self.hips_rot = Quaternion()
        self.fk = {}          # bone -> Quaternion, rotation relative to parent expressed in rest (armature) axes
        self.feet = {}        # side -> ("foot", Matrix foot-unit transform) | ("crawl", knee_target, tip_target)
        self.hands = {}       # side -> (wrist_target, pole_dir, hand_dir, palm_normal)


class Solver:
    def __init__(self, arm, hero, W):
        self.arm = arm
        self.B = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
        self.order = [b.name for b in arm.data.bones]  # parents come first
        co = np.array([v.co[:] for v in hero.data.vertices])
        self.foot_pts = {}
        for sd, s in SIDES.items():
            idx = [i for i, w in enumerate(W)
                   if w.get(f"foot_{sd}", 0) + w.get(f"metatarsal_{sd}", 0) > 0.5]
            self.foot_pts[sd] = co[idx]
        # knee region (thigh plate, knee pod, shin: same vertex set as qa/check_rig.py) for linear-blend skinning
        # inside the solver, so crawl knee contact can be fitted on the deformed mesh, not on the joint
        self.knee_skin = {}
        for sd in SIDES:
            idx = [i for i, w in enumerate(W) if w.get(f"upper_leg_{sd}", 0) + w.get(f"lower_leg_{sd}", 0) > 0.5]
            bones = sorted({b for i in idx for b in W[i]})
            wm = np.array([[W[i].get(b, 0.0) for b in bones] for i in idx])
            self.knee_skin[sd] = (np.c_[co[idx], np.ones(len(idx))], bones, wm)
        self.warn = []
        self.L_thigh = (KNEE - HIP).length
        self.L_shin = (HOCK - KNEE).length
        self.L_fu = (BLADE_TIP - HOCK).length   # hock -> blade tip (rigid foot unit)

    def head(self, b):
        return self.B[b].translation

    def rest_rot(self, b):
        return self.B[b].to_quaternion()

    # foot-unit helpers ------------------------------------------------------------------------------
    def foot_min_z(self, sd, F):
        R = np.array(F.to_3x3())
        t = np.array(F.translation)
        return float((self.foot_pts[sd] @ R.T + t)[:, 2].min())

    def foot_matrix(self, sd, pivot_rest_left, pivot_world, theta, ground=0.0):
        """Foot unit rotated by theta (deg, + = toe up) about the pivot; lifted so no point is below `ground`."""
        s = SIDES[sd]
        pr = mir(pivot_rest_left, s)
        F = TR(pivot_world, Rx(theta)) @ Matrix.Translation(-pr)
        mz = self.foot_min_z(sd, F)
        if mz < ground:
            F = Matrix.Translation((0, 0, ground - mz)) @ F
        return F

    def knee_points(self, sd, P):
        """Deformed knee-region vertices (world) for pose P (same linear blend skinning as the armature modifier)."""
        Q = Pose()   # solve a copy: solve() caches leg/arm results on the pose object
        Q.hips_pos, Q.hips_rot, Q.fk, Q.feet, Q.hands = P.hips_pos, P.hips_rot, P.fk, P.feet, P.hands
        _, Wm = self.solve(Q)
        v4, bones, wm = self.knee_skin[sd]
        out = np.zeros((len(v4), 3))
        for k, b in enumerate(bones):
            M = np.array(Wm[b] @ self.B[b].inverted())
            out += wm[:, k:k + 1] * (v4 @ M.T)[:, :3]
        return out

    # main -------------------------------------------------------------------------------------------
    def solve(self, P):
        Wm = {}
        L = {}
        B = self.B
        for b in self.order:
            p = self.parent[b]
            if p is None:
                Wm[b] = B[b].copy()
                L[b] = Matrix.Identity(4)
                continue
            rest_in_parent = Wm[p] @ B[p].inverted() @ B[b]   # bone pose if its local basis were identity
            target = None
            if b == "hips":
                target = TR(P.hips_pos, P.hips_rot @ self.rest_rot(b))
            elif b.startswith(("upper_leg", "lower_leg", "metatarsal", "foot")):
                target = self.leg_bone(b, P, Wm)
            elif b.startswith(("upper_arm", "lower_arm", "hand")) and b[-1] in P.hands and P.hands[b[-1]]:
                target = self.arm_bone(b, P, Wm)
            if target is None:
                D = P.fk.get(b, Quaternion())
                rr = self.rest_rot(b)
                Lb = (rr.inverted() @ D @ rr).to_matrix().to_4x4()
                Wm[b] = rest_in_parent @ Lb
                L[b] = Lb
            else:
                Wm[b] = target
                L[b] = rest_in_parent.inverted() @ target
        return L, Wm

    # legs ---------------------------------------------------------------------------------------------
    def leg_bone(self, b, P, Wm):
        sd = b[-1]
        s = SIDES[sd]
        if not hasattr(P, "_leg_cache"):
            P._leg_cache = {}
        if sd not in P._leg_cache:
            P._leg_cache[sd] = self.solve_leg(sd, P, Wm)
        return P._leg_cache[sd][b[:-2]]

    def solve_leg(self, sd, P, Wm):
        s = SIDES[sd]
        hip_r, knee_r, hock_r = mir(HIP, s), mir(KNEE, s), mir(HOCK, s)
        tip_r = mir(BLADE_TIP, s)
        Hw = (Wm["hips"] @ self.B["hips"].inverted() @ Matrix.Translation(hip_r)).translation
        u0 = (hock_r - hip_r).normalized()
        w0 = (knee_r - hip_r) - u0 * (knee_r - hip_r).dot(u0)
        n0 = u0.cross(w0.normalized())
        a, bL = self.L_thigh, self.L_shin
        mode = P.feet[sd]
        if mode[0] == "foot":
            F = mode[1]
            T = F @ hock_r
            d = (T - Hw).length
            dmax = (a + bL) * 0.999
            if d > dmax:
                self.warn.append(f"{sd} reach {d:.3f}>{dmax:.3f}")
                shift = (T - Hw).normalized() * (d - dmax)
                F = Matrix.Translation(-shift) @ F
                T = F @ hock_r
                d = dmax
            if d < abs(a - bL) * 1.02:
                self.warn.append(f"{sd} fold {d:.3f}")
            u = (T - Hw).normalized()
            pole = P.hips_rot @ Vector((0.12 * s, 1.0, 0.0))
            w = pole - u * pole.dot(u)
            w.normalize()
            ca = max(-1, min(1, (a * a + d * d - bL * bL) / (2 * a * d)))
            al = math.acos(ca)
            K = Hw + (u * math.cos(al) + w * math.sin(al)) * a
            n1 = u.cross(w)
        else:  # crawl: thigh aims at the knee target; shin + rigid foot unit = 2-bone IK knee -> blade tip
            _, Kt, Tip = mode
            K = Hw + (Kt - Hw).normalized() * a
            dv = Tip - K
            d = dv.length
            c_ = self.L_fu
            dmax = (bL + c_) * 0.999
            if d > dmax:
                self.warn.append(f"{sd} crawl reach {d:.3f}>{dmax:.3f}")
                d = dmax
            u = dv.normalized()
            up = Vector((0, 0, 1))
            w = up - u * up.dot(u)
            w.normalize()
            ca = max(-1, min(1, (bL * bL + d * d - c_ * c_) / (2 * bL * d)))
            al = math.acos(ca)
            T = K + (u * math.cos(al) + w * math.sin(al)) * bL
            n1 = (P.hips_rot @ n0)
            # foot unit: rotation about X mapping rest (tip - hock) onto (Tip - T), pitch only
            v0 = tip_r - hock_r
            v1 = (K + u * d) - T
            ang0 = math.atan2(v0.z, v0.y)
            ang1 = math.atan2(v1.z, v1.y)
            F = TR(T, Rx(math.degrees(ang1 - ang0))) @ Matrix.Translation(-hock_r)
        q_th = frame_rot(knee_r - hip_r, n0, K - Hw, n1)
        q_sh = frame_rot(hock_r - knee_r, n0, T - K, n1)
        out = {
            "upper_leg": TR(Hw, q_th @ self.rest_rot(f"upper_leg_{sd}")),
            "lower_leg": TR(K, q_sh @ self.rest_rot(f"lower_leg_{sd}")),
            "metatarsal": F @ self.B[f"metatarsal_{sd}"],
            "foot": F @ self.B[f"foot_{sd}"],
        }
        P.__dict__.setdefault("_dbg", {})[sd] = (Hw, K, T, F)
        return out

    # arms (IK only where a clip asks for it) -------------------------------------------------------------
    def arm_bone(self, b, P, Wm):
        sd = b[-1]
        if not hasattr(P, "_arm_cache"):
            P._arm_cache = {}
        if sd not in P._arm_cache:
            P._arm_cache[sd] = self.solve_arm(sd, P, Wm)
        return P._arm_cache[sd][b[:-2]]

    def solve_arm(self, sd, P, Wm):
        s = SIDES[sd]
        sh_r, el_r, wr_r, ht_r = mir(SHOULDER, s), mir(ELBOW, s), mir(WRIST, s), mir(HAND_TIP, s)
        pn = f"shoulder_{sd}"
        S = (Wm[pn] @ self.B[pn].inverted() @ Matrix.Translation(sh_r)).translation
        Wt, pole, hdir, palm = P.hands[sd]
        a, bL = (el_r - sh_r).length, (wr_r - el_r).length
        dv = Wt - S
        d = min(dv.length, (a + bL) * 0.999)
        if dv.length > (a + bL) * 0.999:
            self.warn.append(f"{sd} arm reach {dv.length:.3f}")
        u = dv.normalized()
        w = pole - u * pole.dot(u)
        w.normalize()
        ca = max(-1, min(1, (a * a + d * d - bL * bL) / (2 * a * d)))
        al = math.acos(ca)
        E = S + (u * math.cos(al) + w * math.sin(al)) * a
        Wr = S + u * d
        hinge = (E - S).cross(Wr - E)
        if hinge.length < 1e-6:
            hinge = Vector((1, 0, 0))
        X = Vector((1, 0, 0))
        q_u = frame_rot(el_r - sh_r, X, E - S, hinge)
        q_l = frame_rot(wr_r - el_r, X, Wr - E, hinge)
        palm0 = Vector((s * 1.0, 0, 0))   # rest palms face outward on this model (-x on the left hand)
        q_h = frame_rot(ht_r - wr_r, palm0, hdir, palm)
        return {
            "upper_arm": TR(S, q_u @ self.rest_rot(f"upper_arm_{sd}")),
            "lower_arm": TR(E, q_l @ self.rest_rot(f"lower_arm_{sd}")),
            "hand": TR(Wr, q_h @ self.rest_rot(f"hand_{sd}")),
        }


# ----------------------------------------------------------------------------------------------------------
# Pose building blocks
# ----------------------------------------------------------------------------------------------------------
def torso(P, lean=0.0, twist=0.0, roll=0.0, head_pitch=0.0, breathe=0.0, hips_share=0.6, head_yaw=0.0):
    """Forward lean (deg, + = forward) distributed hips->upper_chest; head_pitch = world pitch of the head."""
    hl = lean * hips_share
    rest = lean - hl
    P.hips_rot = Rz(twist * 0.5) @ Ry(roll) @ Rx(-hl)
    P.fk["spine"] = Rz(-twist * 0.4) @ Rx(-rest * 0.50)
    P.fk["chest"] = Rz(-twist * 0.3) @ Rx(-rest * 0.30 + breathe)
    P.fk["upper_chest"] = Rz(-twist * 0.3) @ Rx(-rest * 0.20 - breathe)
    comp = head_pitch - lean      # remaining pitch the neck+head must add (world)
    P.fk["neck"] = Rx(-comp * 0.45) @ Rz(head_yaw * 0.4)
    P.fk["head"] = Rx(-comp * 0.55) @ Rz(head_yaw * 0.6) @ Ry(-roll * 0.5)


def arm_fk(P, sd, swing=0.0, abd=4.0, bend=8.0, wrist=0.0, clav=0.0, twist=0.0):
    """swing + = forward (relative to the chest), abd + = away from the body, bend + = elbow flexion."""
    s = SIDES[sd]
    P.fk[f"shoulder_{sd}"] = Rx(clav)
    P.fk[f"upper_arm_{sd}"] = Rx(swing) @ Ry(-s * abd) @ Rz(s * twist)
    P.fk[f"lower_arm_{sd}"] = Rx(bend)
    P.fk[f"hand_{sd}"] = Rx(wrist)


STAND_HIPS_Z = 0.90


# ----------------------------------------------------------------------------------------------------------
# Locomotion gait (bipeds): foot-unit trajectories with exact planted stance
# ----------------------------------------------------------------------------------------------------------
class Gait:
    def __init__(self, solver, v, T, duty, y_off=0.0, strike_pitch=10.0, strike_frac=0.12, off_frac=0.35,
                 off_pitch=-30.0, lift=0.10, swing_pitch=-15.0, stance_pitch=None, width=0.0,
                 pivot_flat=True, tangent_k=1.0, kick=0.0, stance_bump=0.0, pitch_ease_in=False):
        self.S, self.v, self.T, self.duty = solver, v, T, duty
        self.y_off, self.a0, self.f1, self.f2 = y_off, strike_pitch, strike_frac, off_frac
        self.phi, self.lift, self.swp, self.width = off_pitch, lift, swing_pitch, width
        self.stance_pitch = stance_pitch   # (theta_strike, theta_end) for tip-pivot gaits (crouch)
        self.Lst = v * T * duty
        self.tk = tangent_k
        self.kick = kick     # extra backward/upward heel kick early in the swing (m)
        self.sbump = stance_bump   # extra tip-pivot pitch at mid-stance (deg; crouch: hock low under the hip)
        # tip-pivot pitch blend over the stance: ease_out (default) or, for the crouch walk, held low (hock low and
        # forward) until mid-stance, then rising quickly so the trailing leg extends back (heel up) before toe-off
        self.pease = (lambda u: ease((u - 0.6) / 0.4)) if pitch_ease_in else ease_out

    def stance_F(self, sd, tau):
        """tau = time since strike (s). Planted pivots move back at exactly v."""
        s = SIDES[sd]
        Tst = self.T * self.duty
        x = mir(BLADE_MID, s).x + s * self.width
        yc = self.y_off + self.Lst / 2 - self.v * tau      # contact-centre y if the blade were flat
        if self.stance_pitch is not None:   # tip pivot all the time (rolled forward crouch gait)
            th0, th1 = self.stance_pitch
            th = th0 + (th1 - th0) * self.pease(tau / Tst) + self.sbump * math.sin(math.pi * tau / Tst)
            piv = BLADE_TIP
        else:
            u = tau / Tst
            if u < self.f1:
                th = self.a0 * (1 - ease_out(u / self.f1))
                piv = BLADE_REAR
            elif u > 1 - self.f2:
                th = self.phi * ease_in((u - (1 - self.f2)) / self.f2)
                piv = BLADE_TIP
            else:
                th, piv = 0.0, BLADE_MID
        pw = Vector((x, yc + (piv.y - BLADE_MID.y), 0.0))
        F = TR(pw, Rx(th)) @ Matrix.Translation(-mir(piv, s))
        return F, th

    def foot(self, sd, t, phase0):
        T, Tst = self.T, self.T * self.duty
        p = ((t / T) + phase0) % 1.0
        tau = p * T
        if tau <= Tst:
            return self.stance_F(sd, tau)[0]
        s_ = (tau - Tst) / (T - Tst)
        F0, th0 = self.stance_F(sd, Tst)
        F1, th1 = self.stance_F(sd, 0.0)
        c_rest = mir(BLADE_MID, SIDES[sd])
        c0, c1 = F0 @ c_rest, F1 @ c_rest
        Tsw = T - Tst
        y = hermite(c0.y, c1.y, -self.v * Tsw * self.tk, -self.v * Tsw * self.tk, s_)
        y -= self.kick * math.sin(math.pi * s_) * (1 - s_) * 1.5
        z = c0.z + (c1.z - c0.z) * ease(s_) + self.lift * bump(s_)
        # pitch: off pitch -> swing pitch -> strike pitch
        if s_ < 0.5:
            th = th0 + (self.swp - th0) * ease(s_ / 0.5)
        else:
            th = self.swp + (th1 - self.swp) * ease((s_ - 0.5) / 0.5)
        F = TR(Vector((c0.x, y, z)), Rx(th)) @ Matrix.Translation(-c_rest)
        mz = self.S.foot_min_z(sd, F)
        clear = min(0.03, 0.6 * s_, 0.6 * (1 - s_))   # swinging blades clear the floor by > 1 cm at once
        if mz < clear:
            F = Matrix.Translation((0, 0, clear - mz)) @ F
        return F


def hips_z_limits(S, P, sd, dmin=0.34, dmax=0.540):
    """Interval of hips z (hips head) for which hip->hock distance stays in [dmin, dmax]."""
    s = SIDES[sd]
    F = P.feet[sd][1]
    T = F @ mir(HOCK, s)
    off = P.hips_rot @ (mir(HIP, s) - Vector((0, SPINE_Y[0], SPINE_Z[0])))
    hx, hy = P.hips_pos.x + off.x, P.hips_pos.y + off.y
    h2 = (hx - T.x) ** 2 + (hy - T.y) ** 2
    lo = T.z - off.z + (math.sqrt(dmin * dmin - h2) if dmin * dmin > h2 else -9)
    hi = T.z - off.z + (math.sqrt(dmax * dmax - h2) if dmax * dmax > h2 else -9)
    return lo, hi


def fit_hips_z(S, poses, base, cyclic=True, smooth_iter=3, dmin=0.34, dmax=0.540, swing_free=False):
    """swing_free: only planted legs constrain the hips (swinging feet are moved instead, see unfold_swing)."""
    n = len(poses) - 1 if cyclic else len(poses)   # cyclic: last pose duplicates the first
    lo = np.zeros(n)
    hi = np.zeros(n)
    for i, P in enumerate(poses[:n]):
        lims = [hips_z_limits(S, P, sd, dmin, dmax) for sd in SIDES
                if not swing_free or getattr(P, "stance", {}).get(sd, True)]
        lo[i], hi[i] = max(l for l, _ in lims), min(h for _, h in lims)
    z = np.clip(np.array(base[:n], float), lo, hi)
    for _ in range(smooth_iter):
        if cyclic:
            z = 0.25 * np.roll(z, 1) + 0.5 * z + 0.25 * np.roll(z, -1)
        else:
            z[1:-1] = 0.25 * z[:-2] + 0.5 * z[1:-1] + 0.25 * z[2:]
        z = np.clip(z, lo, hi)
    bad = int(np.sum(lo > hi + 1e-4))
    if "--debug-hips" in argv:
        print("hips lo", np.round(lo, 3).tolist())
        print("hips hi", np.round(hi, 3).tolist())
        print("hips z ", np.round(z, 3).tolist())
    for i, P in enumerate(poses):
        P.hips_pos.z = float(z[i % n])
    return bad, float(z.min()), float(z.max())


def unfold_swing(S, poses, dmin):
    """Move a swinging foot unit away from the hip (along hip->hock) where the leg would fold past dmin."""
    n = 0
    for P in poses:
        for sd in SIDES:
            if getattr(P, "stance", {}).get(sd, True):
                continue
            s = SIDES[sd]
            F = P.feet[sd][1]
            T = F @ mir(HOCK, s)
            Hj = P.hips_pos + P.hips_rot @ (mir(HIP, s) - Vector((0, SPINE_Y[0], SPINE_Z[0])))
            d = (T - Hj).length
            if d < dmin:   # continuous fix: lower the swinging foot toward the floor, then pitch it toe-down
                def dist(G):
                    return (G @ mir(HOCK, s) - Hj).length
                G = F
                for _ in range(40):
                    mz = S.foot_min_z(sd, G)
                    if dist(G) >= dmin or mz <= 0.016:
                        break
                    G = Matrix.Translation((0, 0, -min(0.004, mz - 0.015))) @ G
                tip = G @ mir(BLADE_TIP, s)
                for _ in range(40):
                    if dist(G) >= dmin:
                        break
                    G = TR(tip, Rx(-2.0)) @ Matrix.Translation(-tip) @ G
                    mz = S.foot_min_z(sd, G)
                    if mz < 0.015:
                        G = Matrix.Translation((0, 0, 0.015 - mz)) @ G
                        tip = G @ mir(BLADE_TIP, s)
                P.feet[sd] = ("foot", G)
                n += 1
    return n


def knee_heights(S, P, stance_only=False):
    Wm = {"hips": TR(P.hips_pos, P.hips_rot @ S.rest_rot("hips"))}
    out = []
    for sd in SIDES:
        if stance_only and not getattr(P, "stance", {}).get(sd, True):
            continue
        Q = Pose()
        Q.hips_pos, Q.hips_rot, Q.feet = P.hips_pos, P.hips_rot, P.feet
        S.solve_leg(sd, Q, Wm)
        out.append(Q._dbg[sd][1].z)
    return min(out)


def raise_for_knees(S, poses, kmin, cyclic=True, stance_only=False):
    """Raise the hips where a knee joint would sink below kmin (knee pod into the floor); keeps loops closed."""
    n = len(poses) - 1 if cyclic else len(poses)
    add = np.zeros(n)
    for i in range(n):
        P = poses[i]
        z0 = P.hips_pos.z
        for _ in range(12):
            k = knee_heights(S, P, stance_only)
            if k >= kmin - 1e-4:
                break
            P.hips_pos.z += (kmin - k) * 0.8 + 0.001
        add[i] = P.hips_pos.z - z0
        P.hips_pos.z = z0
    if "--debug-hips" in argv:
        print("knee raise add", np.round(add, 3).tolist())
    sm = add.copy()
    for _ in range(3):   # spread the correction so it does not pop
        sm = np.maximum(add, (np.roll(sm, 1) + sm + np.roll(sm, -1)) / 3 if cyclic else sm)
    for i, P in enumerate(poses):
        P.hips_pos.z += float(sm[i % n])
    return float(add.max())


# ----------------------------------------------------------------------------------------------------------
# Clips
# ----------------------------------------------------------------------------------------------------------
def standing_feet(S, P, y=0.0, lift=(0.0, 0.0), theta=(0.0, 0.0)):
    for k, sd in enumerate(("l", "r")):
        s = SIDES[sd]
        piv = BLADE_TIP if theta[k] < 0 else BLADE_MID
        pw = mir(piv, s) + Vector((0, y, lift[k]))
        P.feet[sd] = ("foot", S.foot_matrix(sd, piv, pw, theta[k], ground=lift[k] if lift[k] > 0 else 0.0))


def clip_idle(S):
    N = 120
    poses = []
    for f in range(N + 1):
        t = f / N
        P = Pose()
        dip = 0.012 * (math.exp(-((t - 0.16) / 0.07) ** 2) + math.exp(-((t - 0.67) / 0.08) ** 2)
                       + math.exp(-((t - 1.16) / 0.07) ** 2) + math.exp(-((t + 0.33) / 0.08) ** 2))
        br = math.sin(2 * math.pi * 3 * t)          # 3 breaths per loop
        sway = math.sin(2 * math.pi * t)
        P.hips_pos = Vector((0.018 * sway, SPINE_Y[0] + 0.006 * br, STAND_HIPS_Z - 0.006 - dip))
        torso(P, lean=2.0 + 2.0 * dip / 0.012 + 0.8 * br, roll=-2.0 * sway, head_pitch=1.0 * br,
              breathe=1.6 * br, head_yaw=7.0 * math.sin(2 * math.pi * t + 1.0))
        for sd, ph in (("l", 0.0), ("r", math.pi)):
            arm_fk(P, sd, swing=2.5 * math.sin(2 * math.pi * t + ph) - 2.0 * dip / 0.012 + 1.0 * br,
                   abd=4.0 + 1.5 * br, bend=10.0 + 5 * math.sin(2 * math.pi * 2 * t + ph), clav=0.0)
        standing_feet(S, P)
        poses.append(P)
    return poses, N, True, {}


def locomotion(S, name, v, T_frames, duty, base_z, bob, lean, arm_amp, elbow, arm_fwd=0.0, gait_kw=None,
               head_pitch=0.0, twist=6.0, roll=2.0, sway=0.012, elbow_amp=0.0, hips_y=0.0, z_phase=0.0,
               dmin=0.34, dmax=0.540, arm_abd=6.0, clav=0.0, knee_min=None, hips_share=0.6, lean_amp=0.0,
               head_bob=0.0, swing_free=False):
    N = T_frames
    T = N / FPS
    g = Gait(S, v, T, duty, **(gait_kw or {}))
    poses, base = [], []
    for f in range(N + 1):
        t = f / FPS
        P = Pose()
        ph = 2 * math.pi * (f / N)
        P.hips_pos = Vector((sway * math.sin(ph), SPINE_Y[0] + hips_y, base_z))
        base.append(base_z + bob * math.cos(2 * ph + z_phase))
        torso(P, lean=lean + lean_amp * math.cos(2 * ph + z_phase), twist=twist * math.sin(ph),
              roll=roll * math.sin(ph), head_pitch=head_pitch + head_bob * math.cos(2 * ph + z_phase), breathe=0.0,
              hips_share=hips_share)
        P.feet["l"] = ("foot", g.foot("l", t, 0.0))
        P.feet["r"] = ("foot", g.foot("r", t, 0.5))
        P.stance = {sd: (((t / T) + ph0) % 1.0) * T <= T * duty + 1e-9 for sd, ph0 in (("l", 0.0), ("r", 0.5))}
        # arms opposite to the legs (left leg strikes at phase 0 = forward-most -> left arm back)
        for sd, off in (("l", 0.0), ("r", math.pi)):
            c = math.cos(ph + off - 0.35)
            arm_fk(P, sd, swing=arm_fwd - arm_amp * c, abd=arm_abd, bend=elbow + elbow_amp * (-c),
                   clav=clav)
        poses.append(P)
    bad, zmin, zmax = fit_hips_z(S, poses, base, cyclic=True, dmin=dmin, dmax=dmax, swing_free=swing_free)
    if knee_min:
        r = raise_for_knees(S, poses, knee_min, stance_only=swing_free)
        zs = [P.hips_pos.z for P in poses]
        zmin, zmax = min(zs), max(zs)
        print(f"{name}: knee raise max {r:.3f}")
    if swing_free:
        print(f"{name}: unfolded swing frames {unfold_swing(S, poses, dmin + 0.005)}")
    return poses, N, True, {"cycle_s": T, "stride_m": v * T, "stance_travel_m": g.Lst, "duty": duty,
                            "hips_z": (round(zmin, 3), round(zmax, 3)), "infeasible_frames": bad, "speed": v}


def clip_walk(S):
    # 0.8 s cycle (stride 1.28 m at 1.6 m/s; the reference cadence, 44 src frames = 1.8 s, would need a 2.9 m stride
    # at game speed, so only its poses are used). Reach: contacts shifted forward (y_off), flatter swing.
    return locomotion(S, "walk_loop", v=1.6, T_frames=24, duty=0.56, base_z=0.885, bob=0.012, lean=10.0,
                      arm_amp=22.0, elbow=14.0, elbow_amp=8.0, head_pitch=1.0, twist=10.0, roll=2.5,
                      sway=0.014, hips_share=0.5,
                      gait_kw=dict(strike_pitch=16.0, strike_frac=0.15, off_frac=0.40, off_pitch=-36.0,
                                   lift=0.055, swing_pitch=-14.0, y_off=0.05, tangent_k=1.1))


def clip_jog(S):
    return locomotion(S, "jog_loop", v=4.0, T_frames=18, duty=0.32, base_z=0.85, bob=0.024, lean=25.0,
                      arm_amp=46.0, elbow=84.0, elbow_amp=14.0, arm_fwd=10.0, head_pitch=6.0, twist=13.0,
                      z_phase=math.pi, sway=0.008, hips_share=0.7, lean_amp=1.5,
                      gait_kw=dict(strike_pitch=6.0, strike_frac=0.15, off_frac=0.50, off_pitch=-50.0,
                                   lift=0.34, swing_pitch=-70.0, y_off=0.0, tangent_k=0.3, kick=0.10))


CROUCH_HIPS = (-0.04, 0.47)   # hips head (y, z) in the crouch
CROUCH_LEAN = 38.0            # reference 20-30 deg; 38 keeps the head under the 1.25 m crouch height
CROUCH_FOOT_Y, CROUCH_FOOT_TH = -0.17, -62.0
CROUCH_HEAD = 16.0            # world head pitch (deg, + = face down): eyes forward, slightly down


def crouch_base(P, S, t=0.0, f_amp=1.0):
    """Alert crouch hold: torso fairly upright, thighs ~40 deg below horizontal, hands loose in front of the
    knees. Life: 3 breaths, one slow side-to-side weight shift with a small settle, head scanning."""
    br = math.sin(2 * math.pi * 3 * t)
    sh = math.sin(2 * math.pi * t)
    settle = 0.5 - 0.5 * math.cos(4 * math.pi * t)
    P.hips_pos = Vector((0.018 * sh * f_amp, CROUCH_HIPS[0],
                         CROUCH_HIPS[1] + (0.004 * br - 0.010 * settle) * f_amp))
    torso(P, lean=CROUCH_LEAN + (0.8 * br + 2.0 * settle) * f_amp, roll=-2.5 * sh * f_amp,
          head_pitch=CROUCH_HEAD + 3.0 * math.sin(2 * math.pi * 2 * t + 0.5) * f_amp, breathe=1.0 * br * f_amp,
          hips_share=0.8, head_yaw=9.0 * math.sin(2 * math.pi * t + 0.9) * f_amp)
    for sd, ph, sw0, bd0 in (("l", 0.0, 34.0, 44.0), ("r", 1.9, 28.0, 54.0)):
        drift = math.sin(2 * math.pi * t + ph)
        arm_fk(P, sd, swing=sw0 + 4.0 * drift * f_amp + 2.0 * br * f_amp, abd=10.0 + 2.0 * drift * f_amp,
               bend=bd0 + 6.0 * math.sin(2 * math.pi * 2 * t + ph) * f_amp, wrist=18.0, twist=10.0)
    for sd in ("l", "r"):
        s = SIDES[sd]
        P.feet[sd] = ("foot", S.foot_matrix(sd, BLADE_TIP, mir(BLADE_TIP, s) + Vector((0, CROUCH_FOOT_Y, 0)),
                                             CROUCH_FOOT_TH))


def clip_crouch_idle(S):
    N = 120
    poses = []
    for f in range(N + 1):
        P = Pose()
        crouch_base(P, S, f / N)
        poses.append(P)
    return poses, N, True, {}


CW_KNEE_MIN, CW_PITCH, CW_YOFF, CW_BUMP, CW_LEAN = 0.08, (-60.0, -50.0), -0.36, 0.0, 38.0
CW_LIFT, CW_SWP = 0.10, -40.0
CW_BASE, CW_HS, CW_HEAD = 0.45, 0.85, 40.0
CW_FRAMES = 30


def clip_crouch_walk(S):
    poses, N, loop, info = locomotion(
        S, "crouch_walk_loop", v=1.0, T_frames=CW_FRAMES, duty=0.66, base_z=CW_BASE, bob=0.008,
        lean=CW_LEAN, arm_amp=14.0, elbow=40.0, arm_fwd=46.0, head_pitch=CW_HEAD, twist=6.0,
        roll=1.5, sway=0.010, hips_y=CROUCH_HIPS[0] - SPINE_Y[0], dmin=0.31, dmax=0.535, arm_abd=9.0,
        knee_min=CW_KNEE_MIN, hips_share=CW_HS, swing_free=True,
        gait_kw=dict(stance_pitch=CW_PITCH, lift=CW_LIFT, swing_pitch=CW_SWP, y_off=CW_YOFF, stance_bump=CW_BUMP, pitch_ease_in=True))
    return poses, N, loop, info


# ---- crawl -----------------------------------------------------------------------------------------------
# Posture trade-off (top <= 0.70 incl. the backpack): with the lean put almost entirely into the pelvis
# (CRAWL_HIPS_SHARE 0.95, straight spine) the backpack's highest point is its lumbar end, so the shoulders can sit
# ~6 cm higher than with a curled spine at the same top height. That buys nearly straight arms.
CRAWL_LEAN = 99.0        # torso pitch (deg from vertical): shoulders a little below the hips
CRAWL_HIPS_SHARE = 0.95
CRAWL_HIPS_Y = -0.10
CRAWL_KNEE_Z = 0.0440    # knee joint height: the knee pod's lowest vertex rests at ~0.005 m
CRAWL_KNEE_DX = 0.17     # knees slightly abducted (outside the hip joints)
CRAWL_TIP_BACK = 0.42    # blade tips this far behind the knee (shin nearly flat, hook arching up)
CRAWL_HAND_X = 0.21
CRAWL_HAND_FWD = 0.15    # neutral wrists this far ahead of the shoulder joints (arms angled slightly forward)
CRAWL_HEAD = 18.0        # world pitch of the head (deg, + = face down): looks forward-down
_CRAWL_REF = {}


def crawl_ref(S):
    """Reference hip-joint y and shoulder y for the neutral crawl pose (targets are fixed in world from these)."""
    if not _CRAWL_REF:
        P = Pose()
        _CRAWL_REF["hipj_y"] = 0.0
        _CRAWL_REF["sh_y"] = 0.0
        crawl_pose(S, P, {sd: (0.0, 0.0, 0.0, 0.0, True) for sd in SIDES}, {}, CRAWL_LEAN)
        hj = P.hips_pos + P.hips_rot @ (mir(HIP, -1) - Vector((0, SPINE_Y[0], SPINE_Z[0])))
        _, Wm = S.solve(P)
        _CRAWL_REF["hipj_y"] = hj.y
        _CRAWL_REF["sh_y"] = Wm["upper_arm_l"].translation.y
        _CRAWL_REF["sh_z"] = Wm["upper_arm_l"].translation.z
        print("crawl ref", {k: round(v, 3) for k, v in _CRAWL_REF.items()})
    return _CRAWL_REF


def crawl_needs(S, P, legs, knee_out=None, knee_off=None):
    """Hips-head z at which each leg's thigh exactly reaches its knee target (current hips xy/rotation).
    knee_off: side -> world (dx, dy, dz) added to the knee target (contact fit, see knee_contact_fit)."""
    ref = _CRAWL_REF or {"hipj_y": 0.0, "sh_y": 0.0}
    a = S.L_thigh
    need, targets = {}, {}
    for sd, leg in legs.items():
        kdy, kl, tdy, tl = leg[:4]
        s = SIDES[sd]
        dx = CRAWL_KNEE_DX + (knee_out or {}).get(sd, 0.0)
        off = P.hips_rot @ (mir(HIP, s) - Vector((0, SPINE_Y[0], SPINE_Z[0])))
        hjx, hjy = P.hips_pos.x + off.x, P.hips_pos.y + off.y
        K = Vector((s * (abs(HIP.x) + dx), ref["hipj_y"] + kdy, CRAWL_KNEE_Z + kl))
        if knee_off and sd in knee_off:
            K += Vector(knee_off[sd])
        h2 = (K.x - hjx) ** 2 + (K.y - hjy) ** 2
        need[sd] = K.z + math.sqrt(max(a * a - h2, 0.0)) - off.z
        tip = Vector((s * (abs(BLADE_TIP.x) + dx), ref["hipj_y"] + tdy, tl))
        targets[sd] = (K, tip)
    return need, targets


def crawl_pose(S, P, legs, hands, lean, roll=0.0, yaw=0.0, head_pitch=None, breathe=0.0, knee_out=None,
               hips_dy=0.0, hips_dz=0.0, shoulder_push=0.0, knee_off=None, level_knees=False):
    """legs: side -> (knee_dy, knee_lift, tip_dy, tip_lift, in_stance) relative to the reference hip-joint y;
    hands: side -> (wrist_dy, lift) relative to the reference shoulder y. The hips height is set so every stance
    knee exactly touches (callers equalise two stance knees with hips_dy)."""
    ref = _CRAWL_REF or {"hipj_y": 0.0, "sh_y": 0.0}
    P.hips_pos = Vector((0.0, CRAWL_HIPS_Y + hips_dy, 0.45))
    torso(P, lean=lean, head_pitch=CRAWL_HEAD if head_pitch is None else head_pitch, hips_share=CRAWL_HIPS_SHARE,
          breathe=breathe)
    base_rot = P.hips_rot
    P.hips_rot = Rz(yaw) @ Ry(roll) @ base_rot
    need, targets = crawl_needs(S, P, legs, knee_out, knee_off)
    if level_knees and all(leg[4] for leg in legs.values()):
        # both knees planted: add a small pelvis roll so both thighs reach their knee targets at the same hips
        # height (otherwise the hips sit at the higher need and the other knee hovers a few mm)
        def diff(r):
            P.hips_rot = Rz(yaw) @ Ry(roll + r) @ base_rot
            nd = crawl_needs(S, P, legs, knee_out, knee_off)[0]
            return nd["l"] - nd["r"]
        lo, hi = -4.0, 4.0
        dlo = diff(lo)
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            dm = diff(mid)
            if dlo * dm <= 0:
                hi = mid
            else:
                lo, dlo = mid, dm
        P.hips_rot = Rz(yaw) @ Ry(roll + 0.5 * (lo + hi)) @ base_rot
        need, targets = crawl_needs(S, P, legs, knee_out, knee_off)
    st = [need[sd] for sd, leg in legs.items() if leg[4]] or list(need.values())
    if st:
        P.hips_pos.z = max(st) + hips_dz
    for sd, (K, tip) in targets.items():
        P.feet[sd] = ("crawl", K, tip)
    for sd, (wdy, wl) in hands.items():
        s = SIDES[sd]
        Wt = Vector((CRAWL_HAND_X * s, ref["sh_y"] + CRAWL_HAND_FWD + wdy, 0.027 + wl))
        P.hands[sd] = (Wt, Vector((0.45 * s, -1.0, -0.1)), Vector((0.10 * s, 1.0, -0.03 - 0.3 * wl)),
                       Vector((0, 0, -1)))
        push = shoulder_push.get(sd, 0.0) if isinstance(shoulder_push, dict) else shoulder_push
        P.fk[f"shoulder_{sd}"] = Rz(-s * CRAWL_PHI0) @ Rx(32.0 + push) @ Ry(-s * 6.0)
    return need


CRAWL_PHI0 = 10.0       # shoulder elevation (deg, raises the shoulder joint dorsally ~2.8 cm; no effect on the top)
CRAWL_ARM_D = 0.448     # shoulder->wrist distance kept in hand stance (elbow ~25 deg: arms nearly straight)


def crawl_arm_phi(S, P, lo=0.0, hi=24.0):
    """Per-side shoulder elevation so the arm keeps length CRAWL_ARM_D (the shoulder rises over a planted hand)."""
    out = {}
    for sd in P.hands:
        s = SIDES[sd]
        base = P.fk[f"shoulder_{sd}"]
        Wt = P.hands[sd][0]

        def dist(phi):
            P.fk[f"shoulder_{sd}"] = Rz(-s * (phi - CRAWL_PHI0)) @ base
            Q = Pose()
            Q.hips_pos, Q.hips_rot, Q.fk, Q.feet = P.hips_pos, P.hips_rot, P.fk, P.feet
            _, Wm = S.solve(Q)
            return (Wm[f"upper_arm_{sd}"].translation - Wt).length

        a, b = lo, hi
        if dist(a) >= CRAWL_ARM_D:
            phi = a
        elif dist(b) <= CRAWL_ARM_D:
            phi = b
        else:
            for _ in range(14):
                m = 0.5 * (a + b)
                if dist(m) < CRAWL_ARM_D:
                    a = m
                else:
                    b = m
            phi = 0.5 * (a + b)
        P.fk[f"shoulder_{sd}"] = Rz(-s * (phi - CRAWL_PHI0)) @ base
        out[sd] = phi
    return out


def smooth_phi(poses, phis, cyclic=True, it=2):
    """Smooth the solved shoulder elevations over time (only changes elbow bend, never the hand contact)."""
    n = len(poses) - 1 if cyclic else len(poses)
    for sd in ("l", "r"):
        x = np.array([phis[i][sd] for i in range(n)])
        for _ in range(it):
            x = 0.25 * np.roll(x, 1) + 0.5 * x + 0.25 * np.roll(x, -1)
        for i, P in enumerate(poses):
            s = SIDES[sd]
            P.fk[f"shoulder_{sd}"] = Rz(-s * (x[i % n] - phis[i % n][sd])) @ P.fk[f"shoulder_{sd}"]


KNEE_FLOOR = 0.0015     # lowest knee-pod vertex of a planted knee (m)
KNEE_CONTACT = 0.01     # vertices below this count as touching (same rule as qa/check_rig.py)


def knee_contact_fit(S, build, N, v, iters=4, label="crawl"):
    """Fit per-frame knee-target offsets so a planted knee behaves like a real contact on the deformed mesh.
    The knee pod is a rounded part blended between thigh and shin, so with a fixed joint height its lowest vertex
    drifts by ~1 cm over a stance and the touching vertices roll/slide as the thigh swings. Per planted frame:
    dz puts the lowest knee vertex at KNEE_FLOOR; dx/dy (integrated over each stance run) make the vertices that
    touched in the previous frame move by exactly (0, -v/30) on average (the slip rule of the QA table). Swing
    frames blend the offset from the end of one stance to the start of the next (smoothstep), so loops stay closed.
    build(off) -> (poses[0..N], stance[f][sd]) with off = side -> (N, 3) array of world knee-target offsets."""
    off = {sd: np.zeros((N, 3)) for sd in SIDES}
    for it in range(iters + 1):
        poses, stance = build(off, final=(it == iters))
        if it == iters:
            break
        worst = 0.0
        for sd in SIDES:
            st = np.array([stance[f][sd] for f in range(N)])
            pts = [S.knee_points(sd, poses[f]) if st[f] else None for f in range(N)]
            corr = np.zeros((N, 3))
            for f in range(N):
                if st[f]:
                    corr[f, 2] = KNEE_FLOOR - pts[f][:, 2].min()
            # contiguous stance runs in cyclic order
            if st.all():
                runs = [list(range(N)) + [0]]
            else:
                start = [f for f in range(N) if st[f] and not st[f - 1]]
                runs = []
                for f0 in start:
                    run, f = [], f0
                    while st[f % N] and len(run) < N:
                        run.append(f % N)
                        f += 1
                    runs.append(run)
            for run in runs:
                acc = np.zeros(2)
                cum = [np.zeros(2)]
                for a, b in zip(run[:-1], run[1:]):
                    za = pts[a][:, 2] + corr[a, 2]
                    C = za < KNEE_CONTACT
                    if C.any():
                        d = (pts[b][C, :2] - pts[a][C, :2]).mean(0)
                        acc = acc + (np.array([0.0, -v / FPS]) - d)
                    cum.append(acc.copy())
                if st.all():            # closed loop of stance (idle): spread the residual drift linearly
                    drift = cum[-1]
                    cum = [c - drift * k / (len(cum) - 1) for k, c in enumerate(cum)]
                    cum = cum[:-1]
                    run = run[:-1]
                cum = np.array(cum)
                cum -= cum.mean(0)      # centre the xy correction on the stance (no net shift of the stride)
                for k, f in enumerate(run):
                    corr[f, :2] = cum[k]
            worst = max(worst, float(np.abs(corr[st]).max()))
            off[sd][st] += corr[st]
            # swing frames: smooth blend between the neighbouring stance offsets
            if not st.all():
                for f in range(N):
                    if st[f]:
                        continue
                    b0 = f
                    while not st[b0 % N]:
                        b0 -= 1
                    b1 = f
                    while not st[b1 % N]:
                        b1 += 1
                    u = (f - b0) / (b1 - b0)
                    off[sd][f] = off[sd][b0 % N] + (off[sd][b1 % N] - off[sd][b0 % N]) * ease(u)
        print(f"{label}: knee contact fit iter {it} max correction {worst * 1000:.1f} mm")
    return poses, off


def clip_crawl_idle(S):
    crawl_ref(S)
    N = 90

    def build(off, final=False):
        poses, phis = [], []
        for f in range(N + 1):
            t = f / N
            br = math.sin(2 * math.pi * 2 * t)            # 2 breaths per loop
            sw = math.sin(2 * math.pi * t)                # one slow fore-aft weight shift per loop
            P = Pose()
            legs = {sd: (0.0, 0.0, -CRAWL_TIP_BACK, 0.0, True) for sd in SIDES}
            hands = {sd: (0.0, 0.0) for sd in SIDES}
            crawl_pose(S, P, legs, hands, CRAWL_LEAN + 1.5 * br - 2.0 * sw, breathe=1.2 * br,
                       head_pitch=CRAWL_HEAD - 4.0 * sw + 3.0 * math.sin(2 * math.pi * 3 * t + 0.7),
                       hips_dy=0.025 * sw, roll=1.2 * math.sin(2 * math.pi * t + 1.2),
                       knee_off={sd: off[sd][f % N] for sd in SIDES}, level_knees=True)
            P.fk["neck"] = P.fk["neck"] @ Rz(4.0 * math.sin(2 * math.pi * t + 0.4))
            if final:
                phis.append(crawl_arm_phi(S, P))
            poses.append(P)
        if final:
            smooth_phi(poses, phis)
        return poses, [{sd: True for sd in SIDES}] * N

    poses, _ = knee_contact_fit(S, build, N, 0.0, label="crawl_idle_loop")
    return poses, N, True, {}


CRAWL_V, CRAWL_N, CRAWL_DUTY, CRAWL_HAND_DUTY = 0.5, 36, 0.57, 0.45
CRAWL_KNEE_LIFT = 0.055   # swing knee-target lift
CRAWL_REACH_CLAV = 15.0   # extra clavicle swing (deg) while a hand reaches forward (eases the shoulder-top pinch)
CRAWL_SWING_OUT, CRAWL_SWING_ROLL = 0.06, 8.0   # swing knee abduction (m) and swing-side hip hike (deg): knee clearance


def clip_crawl(S):
    """Contralateral crawl (left knee with the right hand). Cycle 1.2 s, stride 0.6 m at 0.5 m/s. Each knee is
    planted 62% of the cycle (forward of the hip at the plant = knee under, hips high; behind the hip before the
    lift = leg extended back, hips low). Double-stance frames shift the hips fore-aft so both planted knees touch."""
    crawl_ref(S)
    v, N, duty, hduty = CRAWL_V, CRAWL_N, CRAWL_DUTY, CRAWL_HAND_DUTY
    T = N / FPS
    Lst, Lh = v * T * duty, v * T * hduty

    def limb(t, phase0, center, lift_h, d, L):
        p = ((t / T) + phase0) % 1.0
        if p < d:
            return center + L / 2 - v * p * T, 0.0, 0.0, True
        s_ = (p - d) / (1 - d)
        y = hermite(center - L / 2, center + L / 2, -v * T * (1 - d), -v * T * (1 - d), s_)
        ramp = min(1.0, 7.0 * s_, 7.0 * (1 - s_))
        return y, lift_h * (0.5 * ramp + 0.5 * bump(s_)), bump(s_), False

    OFF = {}

    def frame_setup(f):
        t = f / FPS
        legs, hands, out, swing, push = {}, {}, {}, {}, {}
        for sd, ph_leg, ph_arm in (("l", 0.0, 0.5), ("r", 0.5, 0.0)):   # left knee moves with the right hand
            ky, kl, sw, st = limb(t, ph_leg, 0.03, CRAWL_KNEE_LIFT, duty, Lst)
            ty, tl, _, _ = limb(t, ph_leg, 0.03 - CRAWL_TIP_BACK, 0.05, duty, Lst)
            wy, wl, wsw, _ = limb(t, ph_arm + 0.06, 0.0, 0.06, hduty, Lh)
            legs[sd] = (ky, kl, ty, tl, st)
            hands[sd] = (wy, wl)
            push[sd] = CRAWL_REACH_CLAV * wsw
            out[sd] = CRAWL_SWING_OUT * sw
            swing[sd] = sw
        roll = CRAWL_SWING_ROLL * (swing["l"] - swing["r"])     # hike the swing-side hip (0 in double stance)
        return legs, hands, out, roll, push

    def pose_at(f, hy):
        legs, hands, out, roll, push = frame_setup(f)
        P = Pose()
        ph = 2 * math.pi * f / N
        need = crawl_pose(S, P, legs, hands, CRAWL_LEAN + 2.0 * math.cos(2 * ph), roll=roll,
                          yaw=2.5 * math.sin(ph), knee_out=out, hips_dy=hy,
                          head_pitch=CRAWL_HEAD + 3.0 * math.cos(2 * ph), shoulder_push=push,
                          knee_off={sd: OFF[sd][f % N] for sd in SIDES} if OFF else None)
        return P, need, legs

    # pass 1: hips fore-aft offset that equalises the two planted knees (double stance frames)
    def gap(f, h):
        need = pose_at(f, h)[1]
        return need["l"] - need["r"]

    def build(off, final=False):
        OFF.clear()
        OFF.update(off)
        hy_keys = []
        for f in range(N):
            legs = frame_setup(f)[0]
            if legs["l"][4] and legs["r"][4]:
                lo, hi = -0.15, 0.15
                glo = gap(f, lo)
                for _ in range(30):
                    mid = 0.5 * (lo + hi)
                    gm = gap(f, mid)
                    if glo * gm <= 0:
                        hi = mid
                    else:
                        lo, glo = mid, gm
                hy_keys.append((f, 0.5 * (lo + hi)))
        # pass 2: smooth periodic Catmull-Rom through the double-stance values
        ext = [(k - N, x) for k, x in hy_keys] + hy_keys + [(k + N, x) for k, x in hy_keys]
        hy = []
        for f in range(N + 1):
            i = max(j for j in range(len(ext)) if ext[j][0] <= f)
            (f0, p0), (f1, p1) = ext[i], ext[i + 1]
            m0 = (p1 - ext[i - 1][1]) / (f1 - ext[i - 1][0]) * (f1 - f0)
            m1 = (ext[i + 2][1] - p0) / (ext[i + 2][0] - f0) * (f1 - f0)
            hy.append(hermite(p0, p1, m0, m1, (f - f0) / (f1 - f0)))
        poses, phis, stance = [], [], []
        for f in range(N + 1):
            P, need, legs = pose_at(f % N, hy[f])
            if final:
                phis.append(crawl_arm_phi(S, P))
            poses.append(P)
            stance.append({sd: legs[sd][4] for sd in SIDES})
        if final:
            smooth_phi(poses, phis)
            print("crawl hips_dy keys", [(k, round(x, 3)) for k, x in hy_keys])
        return poses, stance[:N]

    poses, _ = knee_contact_fit(S, build, N, v, label="crawl_loop")
    return poses, N, True, {"cycle_s": T, "stride_m": v * T, "stance_travel_m": Lst, "duty": duty,
                            "hand_duty": hduty, "speed": v}


JUMP_TAKEOFF, JUMP_TOUCHDOWN = 1, 25   # first airborne frame, first frame with the blades back on the floor
JUMP_SIDE = {"l": (0.0, 1.00, -3.0, 0.0), "r": (0.8, 0.93, 4.0, 2.0)}   # tuck lead (frames), tuck scale, arm, abd


def clip_jump(S):
    """Game-timed jump. The game starts the clip at frame 0 the moment jumped() fires (instant launch at 4.0 m/s,
    g 9.8 -> 0.816 s airborne = 24.5 frames), so frame 0 is already the push-off extension (blade tips on the floor,
    heels up, arms swinging up; the AnimationTree crossfade covers the transition from idle/walk). The blades leave
    the floor at frame 1, tuck (knees up, blades hanging behind) peaks ~frame 11, the legs reach down from ~frame 15,
    tips touch at frame 25, compression to frame 29, recovered by frame 36 (clip end 38).
    Left and right are slightly out of step (the right leg tucks later and less, arms not mirrored).
    In place: the game moves the body, so the airborne feet are lifted relative to the hips (tuck), not the hips."""
    N = 38
    K = {
        "hz": [(0, 0.0), (2, 0.03), (6, 0.02), (13, 0.01), (22, 0.0), (25, -0.01), (27, -0.12), (29, -0.15),
               (32, -0.07), (36, -0.005), (38, 0.0)],
        "hy": [(0, 0.0), (25, 0.0), (29, -0.05), (34, -0.01), (38, 0.0)],
        "lean": [(0, 4.0), (6, 9.0), (12, 12.0), (20, 6.0), (25, 6.0), (29, 24.0), (33, 9.0), (38, 2.0)],
        "th": [(0, -14.0), (3, -40.0), (9, -54.0), (15, -42.0), (20, -20.0), (23, -10.0), (25, -6.0), (27, 0.0),
               (38, 0.0)],
        "lift": [(0, 0.0), (1, 0.02), (3, 0.10), (7, 0.26), (11, 0.32), (15, 0.26), (19, 0.12), (22, 0.04),
                 (24, 0.008), (25, 0.0), (38, 0.0)],
        "back": [(0, 0.0), (5, 0.12), (10, 0.19), (16, 0.10), (21, 0.02), (25, 0.0), (38, 0.0)],
        "arm": [(0, 15.0), (2, 40.0), (5, 62.0), (11, 55.0), (18, 30.0), (23, 12.0), (25, 5.0), (28, -22.0),
                (32, -8.0), (38, 0.0)],
        "elbow": [(0, 22.0), (3, 32.0), (10, 42.0), (20, 25.0), (25, 20.0), (29, 32.0), (38, 10.0)],
        "abd": [(0, 6.0), (6, 14.0), (14, 18.0), (22, 12.0), (28, 8.0), (38, 4.0)],
        "head": [(0, -2.0), (4, -6.0), (12, -3.0), (20, 6.0), (25, 8.0), (29, 12.0), (38, 0.0)],
    }
    poses = []
    for f in range(N + 1):
        P = Pose()
        g = {k: keyed(v, f) for k, v in K.items()}
        P.hips_pos = Vector((0.0, SPINE_Y[0] + g["hy"], STAND_HIPS_Z - 0.006 + g["hz"]))
        torso(P, lean=g["lean"], head_pitch=g["head"] + g["lean"] * 0.2, twist=1.5 * math.sin(math.pi * f / 25))
        air = JUMP_TAKEOFF <= f < JUMP_TOUCHDOWN
        for sd in ("l", "r"):
            lag, sc_, darm, dabd = JUMP_SIDE[sd]
            arm_fk(P, sd, swing=g["arm"] + darm * math.sin(math.pi * min(f, 30) / 30), abd=g["abd"] + dabd,
                   bend=g["elbow"])
            s = SIDES[sd]
            if air:   # the side's tuck runs `lag` frames late (clamped inside the airborne window)
                fl = min(max(f - lag, JUMP_TAKEOFF), JUMP_TOUCHDOWN - 0.5)
                k = 1.0 - (1.0 - sc_) * math.sin(math.pi * (f - JUMP_TAKEOFF) / (JUMP_TOUCHDOWN - JUMP_TAKEOFF))
                lift = max(0.0, keyed(K["lift"], fl)) * k
                back = keyed(K["back"], fl) * k
                th = min(0.0, keyed(K["th"], fl))
            else:
                lift, back, th = 0.0, 0.0, min(0.0, g["th"])
            pw = mir(BLADE_TIP, s) + Vector((0, back, lift))
            gr = max(lift, 0.012) if air else 0.0     # airborne blades stay clearly off the floor
            P.feet[sd] = ("foot", S.foot_matrix(sd, BLADE_TIP, pw, th, ground=gr))
        poses.append(P)
    # keep the hips reachable (legs never over-extend) and the tucked legs from folding completely
    base = [P.hips_pos.z for P in poses]
    bad, zmin, zmax = fit_hips_z(S, poses, base, cyclic=False, smooth_iter=1, dmin=0.30, dmax=0.542)
    return poses, N, False, {"hips_z": (round(zmin, 3), round(zmax, 3)), "infeasible_frames": bad,
                             "takeoff_frame": JUMP_TAKEOFF, "touchdown_frame": JUMP_TOUCHDOWN}


CLIPS = [
    ("idle_loop", clip_idle),
    ("walk_loop", clip_walk),
    ("jog_loop", clip_jog),
    ("crouch_idle_loop", clip_crouch_idle),
    ("crouch_walk_loop", clip_crouch_walk),
    ("crawl_idle_loop", clip_crawl_idle),
    ("crawl_loop", clip_crawl),
    ("jump", clip_jump),
]


# ----------------------------------------------------------------------------------------------------------
# Baking
# ----------------------------------------------------------------------------------------------------------
def bake(arm, S, name, poses, N):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    slot = act.slots.new(id_type="OBJECT", name=arm.name)
    arm.animation_data.action = act
    arm.animation_data.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    S.warn = []
    data = {b: {"loc": [], "rot": []} for b in S.order}
    prev = {}
    for f, P in enumerate(poses):
        L, _ = S.solve(P)
        for b in S.order:
            loc, q, _ = L[b].decompose()
            if b in prev and prev[b].dot(q) < 0:
                q = -q
            prev[b] = q
            data[b]["loc"].append(loc)
            data[b]["rot"].append(q)
    for b in S.order:
        if b == "root":
            continue
        for path, key, n in (("location", "loc", 3), ("rotation_quaternion", "rot", 4)):
            vals = data[b][key]
            if key == "loc" and all(v.length < 1e-6 for v in vals):
                continue
            for i in range(n):
                fc = cb.fcurves.new(f'pose.bones["{b}"].{path}', index=i, group_name=b)
                fc.keyframe_points.add(len(vals))
                co = []
                for f, v in enumerate(vals):
                    co += [float(f), float(v[i])]
                fc.keyframe_points.foreach_set("co", co)
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
                fc.update()
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, N
    w = sorted(set(S.warn))
    print(f"clip {name}: frames 0-{N}, warnings {len(S.warn)} {w[:6]}")
    return act


def main():
    hero, arm = setup_scene()
    W, arms = compute_weights(hero)
    S = Solver(arm, hero, W)
    infos = {}
    first = None
    for name, fn in CLIPS:
        if ONLY and name not in ONLY:
            continue
        poses, N, loop, info = fn(S)
        act = bake(arm, S, name, poses, N)
        info.update({"frames": N, "loop": loop})
        infos[name] = info
        print("info", name, info)
        first = first or act
    arm.animation_data.action = first
    arm.animation_data.action_slot = first.slots[0]
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 120
    arm["clip_info"] = str(infos)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print("saved", OUT)


if __name__ == "__main__":
    main()
