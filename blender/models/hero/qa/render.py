"""Scratch renders of hero_model.blend (Cycles CPU) -> .captures/T011/v5/r/.
usage: blender -b <blend> -P render.py -- <tag> <views> [samples] [pose]
views (comma list): side_ref (reference-aligned ortho 414x807, transparent), full, legs (8 turnaround angles each,
framed like reference/hero/turnaround), game, threeq, seam, foot, knee, front, back
pose: 'stride' rotates the legs at the hips (scratch only) so the knees land on the reference knees."""
import bpy, math, sys, json
import re as _re
CUT_Z = float(_re.search(r"^CUT_Z = ([0-9.]+)", open("/home/archwayzero/game/blender/models/hero/conform.py").read(), _re.M).group(1))
import bmesh
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index("--") + 1:]
tag, views = argv[0], argv[1].split(",")
samples = int(argv[2]) if len(argv) > 2 else 24
pose = argv[3] if len(argv) > 3 else ""
OUT = "/home/archwayzero/game/.captures/T011/v5/r/"
PPM, GROUND = 793 / 1.75, 801.0
HIP_PX = (113.0, 402.0)          # reference near hip disc centre
HIP_Y, HIP_Z = 0.0686, 0.8708    # model hip disc centre (measured by check_legs.py)
sc = bpy.context.scene
obj = bpy.data.objects["hero"]

if pose in ("stride", "stride_joints"):
    # rotate each leg's faces (material 1) about the hip axis (X) so the knee hits the reference knee position
    lm = json.load(open("/home/archwayzero/game/blender/models/hero/qa/reference_landmarks.json"))["landmarks_px"]
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    lp = bm.faces.layers.float["lm_part"]; lt = bm.faces.layers.float["lm_t"]
    for side, leg in ((-1, "near"), (1, "far")):        # camera at -X: the -X leg is the near one
        vs = {v for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * side > 0 for v in f.verts}
        vs = {v for v in vs if v.co.z < CUT_Z - 0.001}          # keep the welded cut loop in place
        knee_ring = [v for f in bm.faces if f.material_index == 1 and int(round(f[lp])) == 4 and abs(f[lt]) < 1e-4
                     and f.calc_center_median().x * side > 0 for v in f.verts]
        K = sum((v.co for v in knee_ring), Vector()) / len(knee_ring)
        kx, ky = lm[leg]["knee_centre"]
        try:      # upper-body alignment of the unposed render (overlay.py): model appears shifted by dx px
            kx -= json.load(open("/home/archwayzero/game/.captures/T011/v5/align.json"))["dx_px"]
        except FileNotFoundError:
            pass
        # image -> model: z = (GROUND - y)/PPM ; y = HIP_Y + (HIP_PX[0] - x)/PPM
        Kt = Vector((K.x, HIP_Y + (HIP_PX[0] - kx) / PPM, (GROUND - ky) / PPM))
        a0 = math.atan2(K.y - HIP_Y, HIP_Z - K.z); a1 = math.atan2(Kt.y - HIP_Y, HIP_Z - Kt.z)
        R = (Matrix.Translation((0, HIP_Y, HIP_Z)) @ Matrix.Rotation((a1 - a0), 4, "X")
             @ Matrix.Translation((0, -HIP_Y, -HIP_Z)))
        def ringc(t0, t1):
            a = {v for f in bm.faces if f.material_index == 1 and int(round(f[lp])) in (4, 5, 6) and abs(f[lt] - t0) < 1e-5
                 and f.calc_center_median().x * side > 0 for v in f.verts}
            b = {v for f in bm.faces if f.material_index == 1 and int(round(f[lp])) in (4, 5, 6) and abs(f[lt] - t1) < 1e-5
                 and f.calc_center_median().x * side > 0 for v in f.verts}
            s_ = a & b
            return sum((v.co for v in s_), Vector()) / len(s_)
        lts = sorted({round(f[lt], 5) for f in bm.faces if f.material_index == 1 and int(round(f[lp])) in (4, 5, 6)
                      and f.calc_center_median().x * side > 0})
        def before(t):
            return max(x for x in lts if x < t - 1e-6)
        Jm, Am = ringc(before(0.4855), 0.4855), ringc(before(1.0), 1.0)
        for v in vs:
            v.co = R @ v.co
        if pose == "stride_joints":   # also bend knee and ankle (pose-dependent joints) onto the reference
            dx_ = json.load(open("/home/archwayzero/game/.captures/T011/v5/align.json"))["dx_px"]
            def to_m(px):
                return Vector((0, HIP_Y + (HIP_PX[0] - (px[0] - dx_)) / PPM, (GROUND - px[1]) / PPM))
            Kp, Ap = R @ K, R @ Am
            At = to_m(lm[leg]["ankle"])
            b0 = math.atan2(Ap.y - Kp.y, Kp.z - Ap.z); b1 = math.atan2(At.y - Kp.y, Kp.z - At.z)
            Rk = (Matrix.Translation((0, Kp.y, Kp.z)) @ Matrix.Rotation(b1 - b0, 4, "X")
                  @ Matrix.Translation((0, -Kp.y, -Kp.z)))
            below = {v for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * side > 0
                     and int(round(f[lp])) in (4, 5, 6, 10, 11, 12) for v in f.verts if v in vs}
            below = {v for v in below if (v.co - Kp).dot(Vector((0, Ap.y - Kp.y, Ap.z - Kp.z)).normalized()) > 0.02}
            for v in below:
                v.co = Rk @ v.co
            # foot pitch about the ankle: the near foot is the far foot rotated (reference foot_pose_check)
            if leg == "near":
                fr = json.load(open("/home/archwayzero/game/blender/models/hero/qa/reference_landmarks.json"))["foot_pose_check"]["near_to_far_rotation_deg"]
                Ap2 = Rk @ Ap
                Ra = (Matrix.Translation((0, Ap2.y, Ap2.z)) @ Matrix.Rotation(math.radians(-fr), 4, "X")
                      @ Matrix.Translation((0, -Ap2.y, -Ap2.z)))
                feet = {v for f in bm.faces if f.material_index == 1 and f.calc_center_median().x * side > 0
                        and int(round(f[lp])) in (10, 11, 12) for v in f.verts}
                for v in feet:
                    if v.co.z < Ap2.z + 0.03:
                        v.co = Ra @ v.co
            print(f"  joints {leg}: knee bend {math.degrees(b1 - b0):+.1f} deg")
        dxp = json.load(open("/home/archwayzero/game/.captures/T011/v5/align.json"))["dx_px"] if __import__("os").path.exists("/home/archwayzero/game/.captures/T011/v5/align.json") else 0
        def img(p):
            p = R @ p
            return (round(HIP_PX[0] + (HIP_Y - p.y) * PPM + dxp, 1), round(GROUND - p.z * PPM, 1))
        print(f"pose {leg}: thigh {math.degrees(a0):.1f} -> {math.degrees(a1):.1f} deg (forward +); image px "
              f"knee {img(K)} vs ref {tuple(lm[leg]['knee_centre'])}, hock {img(Jm)} vs ref {tuple(lm[leg]['hock'])}, "
              f"ankle {img(Am)} vs ref {tuple(lm[leg]['ankle'])}")
    bm.to_mesh(me); bm.free()

for o in list(sc.objects):
    if o.type != "MESH": bpy.data.objects.remove(o)
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("w"); w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.10, 0.10, 0.095, 1); bg.inputs[1].default_value = 1.0
sc.world = w
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
def light(name, rot, e):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN")); l.data.energy = e
    l.data.angle = math.radians(8)
    l.rotation_euler = [math.radians(a) for a in rot]; sc.collection.objects.link(l); l.parent = cam
light("key", (-35, 40, 0), 3.2); light("fill", (-20, -45, 0), 1.0); light("rim", (-150, 0, 0), 2.0)

def aim(pos, tgt):
    cam.location = Vector(pos); cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()

def render(name, res, transparent=False):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = transparent
    sc.render.filepath = OUT + f"{tag}_{name}.png"
    bpy.ops.render.render(write_still=True)

if "side_ref" in views:
    cam.data.type = "ORTHO"; cam.data.ortho_scale = 807 / PPM
    zc = (GROUND - 403.5) / PPM; yc = HIP_Y - (207 - HIP_PX[0]) / PPM
    aim((-6, yc, zc), (0, yc, zc))
    render("side_ref", (414, 807), transparent=True)
FR = {"full": (1.82, 0.885, 1.30, 4.0), "legs": (0.967, 0.466, 0.55, 3.0)}
for s in ("full", "legs"):
    if s not in views: continue
    vspan, zc, camz, dist = FR[s]
    cam.data.type = "ORTHO"; cam.data.ortho_scale = vspan * 864 / 480
    for a in (0, 45, 90, 135, 180, 225, 270, 315):
        r = math.radians(a)
        aim((-dist * math.sin(r), dist * math.cos(r), camz), (0, 0, zc))
        render(f"{s}_{a:03d}", (864, 480))
cam.data.type = "PERSP"
shots = {"game": ((0.4, -2.5, 2.3), (0, 0.3, 1.0), (960, 540), 35),
         "threeq": ((3.2, 3.6, 1.6), (0, 0, 0.8), (700, 900), 55),
         "seam": ((-0.9, 0.9, 0.8), (-0.05, 0.03, 0.6), (700, 700), 50),
         "foot": ((-0.9, 0.6, 0.35), (-0.15, -0.08, 0.12), (700, 700), 60),
         "knee": ((-0.8, 0.8, 0.6), (-0.13, 0.05, 0.47), (700, 700), 70),
         "front": ((0, 4.0, 0.6), (0, 0, 0.5), (700, 700), 50),
         "back": ((0, -4.0, 0.6), (0, 0, 0.5), (700, 700), 50)}
for name, (pos, tgt, res, lens) in shots.items():
    if name in views:
        cam.data.lens = lens; aim(pos, tgt); render(name, res)
