"""Per-clip QA table for the hero rig (T013).

  python3 tools/qa/memguard.py -- blender -b blender/rigs/hero/hero_rig.blend -P blender/rigs/hero/qa/check_rig.py \
      [-- --out .captures/T013/check_table.md] [--clips a,b]

Metrics (evaluated deformed mesh, every frame):
- seam: max vertex distance between frame 0 and the last frame (loops must be ~0).
- top / min z: highest and lowest vertex over the clip (m). Ground rule: min z >= -0.01.
- contact: (not jump/jog, which have flight phases) the lowest blade vertex is within 0.01 m of the floor.
- slip: planted-blade slip vs. game speed. Per frame, blade vertices touching the floor (z < 0.01) in both frames
  must move by exactly (0, -v/30, 0); the error is summed over each contiguous stance phase; reported = worst phase
  (cm). Crawl also tracks the hands (z < 0.01).
- joints: bones in the armature (all exported as skin joints).
- max edge stretch: largest length ratio (stretch or compression) of any edge >= 5 mm vs. rest, and the bone that
  dominates it. Informational (weight-painting weak spots), not a pass/fail criterion.
- arm-torso / leg-leg / thigh-torso: penetration estimate = 3rd-deepest vertex of one part found inside the other's
  surface (nearest-surface normal test, ignoring the shoulder seam), max over frames (cm) and frames with > 1 cm.
"""
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else ".captures/T013/check_table.md"
ONLY = argv[argv.index("--clips") + 1].split(",") if "--clips" in argv else None
SPEED = {"walk_loop": 1.6, "jog_loop": 4.0, "crouch_walk_loop": 1.0, "crawl_loop": 0.5}
LIMITS = {"crouch": 1.25, "crawl": 0.70}
FPS = 30

sc = bpy.context.scene
arm = bpy.data.objects["Armature"]
hero = bpy.data.objects["hero"]
me = hero.data
nv = len(me.vertices)
groups = {g.index: g.name for g in hero.vertex_groups}
Wn = {}
for v in me.vertices:
    for g in v.groups:
        Wn.setdefault(groups[g.group], np.zeros(nv))[v.index] = g.weight
z0 = np.zeros(nv)
def W(*names):
    return sum((Wn.get(n, z0) for n in names), z0.copy())

rest = np.array([v.co[:] for v in me.vertices])
arm_w = {s: W(f"upper_arm_{s}", f"lower_arm_{s}", f"hand_{s}") for s in "lr"}
clav_w = W("shoulder_l", "shoulder_r")
leg_w = {s: W(f"upper_leg_{s}", f"lower_leg_{s}", f"metatarsal_{s}", f"foot_{s}") for s in "lr"}
foot_ids = {s: np.where(W(f"foot_{s}") > 0.5)[0] for s in "lr"}
hand_ids = {s: np.where(W(f"hand_{s}") > 0.5)[0] for s in "lr"}
arm_ids = {s: np.where((arm_w[s] > 0.5) & (W(f"shoulder_{s}") < 0.05))[0] for s in "lr"}
torso_mask = (arm_w["l"] + arm_w["r"] < 0.01) & (leg_w["l"] + leg_w["r"] < 0.01)
torso_mask &= ~((rest[:, 2] > 1.30) & (np.abs(rest[:, 0]) > 0.12))      # shoulder seam excluded
leg_ids = {s: np.where(leg_w[s] > 0.5)[0] for s in "lr"}
thigh_ids = np.where((W("upper_leg_l", "upper_leg_r") > 0.9) & (rest[:, 2] < 0.78))[0]
torso_hi_mask = torso_mask & (rest[:, 2] > 0.95)

polys = [tuple(p.vertices) for p in me.polygons]
EDGES = np.array([e.vertices[:] for e in me.edges])
REST_LEN = np.linalg.norm(rest[EDGES[:, 0]] - rest[EDGES[:, 1]], axis=1)
EDGE_OK = REST_LEN > 0.005   # ignore sub-5 mm edges (ratios are noise there)
def faces_of(mask):
    return [p for p in polys if all(mask[i] for i in p)]
torso_faces = faces_of(torso_mask)
torso_hi_faces = faces_of(torso_hi_mask)
leg_faces = {s: faces_of(leg_w[s] > 0.5) for s in "lr"}


def eval_co():
    dg = bpy.context.evaluated_depsgraph_get()
    ob = hero.evaluated_get(dg)
    m = ob.to_mesh()
    co = np.empty(nv * 3)
    m.vertices.foreach_get("co", co)
    ob.to_mesh_clear()
    co = co.reshape(nv, 3)
    M = np.array(hero.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def penetration(co, ids, faces):
    if not len(ids) or not faces:
        return 0.0
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], faces, all_triangles=False)
    depths = [0.0, 0.0, 0.0]
    for i in ids:
        p = Vector(co[i])
        hit = bvh.find_nearest(p, 0.04)
        if hit[0] is None:
            continue
        loc, nrm, _, dist = hit
        if (p - loc).dot(nrm) < 0:
            depths.append(dist)
    return sorted(depths)[-3]   # 3rd deepest: single flipped-normal vertices are ignored


def pose_snapshot():
    return {pb.name: (pb.matrix.copy()) for pb in arm.pose.bones}


rows = []
for act in bpy.data.actions:
    name = act.name
    if ONLY and name not in ONLY:
        continue
    arm.animation_data.action = act
    arm.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    v = SPEED.get(name, 0.0)
    loop = name.endswith("loop")
    frames = list(range(f0, f1 + 1))
    top, low = -9.0, 9.0
    prev = None
    phase_err = {s: 0.0 for s in "lr"}
    worst_slip = {s: 0.0 for s in "lr"}
    hand_err = {s: 0.0 for s in "lr"}
    worst_hand = {s: 0.0 for s in "lr"}
    contact_bad = 0
    pen = {"arm": [0.0, 0], "leg": [0.0, 0], "thigh": [0.0, 0]}
    first = last = None
    stretch = [0.0, None]
    for f in frames:
        sc.frame_set(f)
        co = eval_co()
        if f == f0:
            first = co.copy()
        L = np.linalg.norm(co[EDGES[:, 0]] - co[EDGES[:, 1]], axis=1)
        r = (L / np.maximum(REST_LEN, 1e-9))[EDGE_OK]
        r = np.maximum(r, 1 / np.maximum(r, 1e-9))     # stretch or compression
        if r.max() > stretch[0]:
            e = EDGES[EDGE_OK][int(r.argmax())]
            stretch = [float(r.max()), (f, max(((n, w[e[0]]) for n, w in Wn.items()), key=lambda kv: kv[1])[0])]
        last = co
        top = max(top, co[:, 2].max())
        if co[:, 2].min() < low:
            low = co[:, 2].min()
            iv = int(co[:, 2].argmin())
            low_who = (f, max(((n, w[iv]) for n, w in Wn.items()), key=lambda kv: kv[1])[0])
        if co[:, 2].max() >= top:
            iv = int(co[:, 2].argmax())
            top_who = (f, max(((n, w[iv]) for n, w in Wn.items()), key=lambda kv: kv[1])[0])
        for s in "lr":
            fz = co[foot_ids[s], 2]
            if prev is not None:
                pz = prev[foot_ids[s], 2]
                both = (fz < 0.01) & (pz < 0.01)
                if both.any():
                    d = co[foot_ids[s]][both, :2] - prev[foot_ids[s]][both, :2]
                    err = np.linalg.norm(d - np.array([0.0, -v / FPS]), axis=1).mean()
                    phase_err[s] += err
                    worst_slip[s] = max(worst_slip[s], phase_err[s])
                else:
                    phase_err[s] = 0.0
                if name.startswith("crawl"):
                    hz, phz = co[hand_ids[s], 2], prev[hand_ids[s], 2]
                    hb = (hz < 0.01) & (phz < 0.01)
                    if hb.any():
                        d = co[hand_ids[s]][hb, :2] - prev[hand_ids[s]][hb, :2]
                        hand_err[s] += np.linalg.norm(d - np.array([0.0, -v / FPS]), axis=1).mean()
                        worst_hand[s] = max(worst_hand[s], hand_err[s])
                    else:
                        hand_err[s] = 0.0
        # contact: at least one blade on the floor (except jump air frames / crawl handled by tips)
        mins = [co[foot_ids[s], 2].min() for s in "lr"]
        if name not in ("jump", "jog_loop") and min(mins) > 0.01:
            contact_bad += 1
        # penetration (every 2nd frame for speed)
        if (f - f0) % 2 == 0 or f == f1:
            a = max(penetration(co, arm_ids[s], torso_faces) for s in "lr")
            l = max(penetration(co, leg_ids["l"], leg_faces["r"]), penetration(co, leg_ids["r"], leg_faces["l"]))
            t = penetration(co, thigh_ids, torso_hi_faces)
            for k, val in (("arm", a), ("leg", l), ("thigh", t)):
                pen[k][0] = max(pen[k][0], val)
                pen[k][1] += val > 0.01
        prev = co
    seam = float(np.linalg.norm(first - last, axis=1).max()) if loop else float("nan")
    lim = 1.85
    if name.startswith("crouch"):
        lim = LIMITS["crouch"]
    if name.startswith("crawl"):
        lim = LIMITS["crawl"]
    slip = max(worst_slip.values()) * 100
    hslip = max(worst_hand.values()) * 100 if name.startswith("crawl") else float("nan")
    ok = (top <= lim and low >= -0.01 and (not loop or seam < 0.001) and slip <= 2.0
          and (np.isnan(hslip) or hslip <= 2.0) and contact_bad == 0 and pen["arm"][0] <= 0.02)
    rows.append((name, f"{f0}-{f1}", f"{(f1 - f0) / FPS:.2f}", "-" if not loop else f"{seam * 100:.2f}",
                 f"{top:.3f} (<= {lim})", f"{low:+.4f}", f"{v:.1f}", f"{slip:.2f}",
                 "-" if np.isnan(hslip) else f"{hslip:.2f}", str(contact_bad), str(len(arm.data.bones)),
                 f"{stretch[0]:.1f} ({stretch[1][1]})",
                 f"{pen['arm'][0] * 100:.1f} / {pen['arm'][1]}", f"{pen['leg'][0] * 100:.1f} / {pen['leg'][1]}",
                 f"{pen['thigh'][0] * 100:.1f} / {pen['thigh'][1]}", "PASS" if ok else "FAIL"))
    print("row", rows[-1], "lowest", low_who, "highest", top_who)

hdr = ("clip", "frames", "len s", "seam cm", "top m", "min z m", "speed", "blade slip cm", "hand slip cm",
       "no-contact frames", "joints", "max edge stretch (where)", "arm-torso cm / frames>1cm", "leg-leg cm / n", "thigh-torso cm / n", "result")
lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
lines += ["| " + " | ".join(r) + " |" for r in rows]
txt = "\n".join(lines)
print(txt)
with open(OUT, "w") as fh:
    fh.write(txt + "\n")
