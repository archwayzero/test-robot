"""Orthographic workbench/cycles renders of the current scene for review.
blender -b <file.blend> -P render_views.py -- --out DIR [--action NAME] [--frames 1,5,9] [--views side,front,back,top]
   [--engine WORKBENCH|CYCLES] [--size 512] [--center 0,0,0.9] [--scale 2.0] [--xray]
"""
import bpy, sys, math, os
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
def arg(n, d=None): return argv[argv.index(n)+1] if n in argv else d
out = arg("--out"); os.makedirs(out, exist_ok=True)
views = arg("--views", "side,front").split(",")
size = int(arg("--size", 512)); engine = arg("--engine", "WORKBENCH")
center = Vector([float(x) for x in arg("--center", "0,0,0.88").split(",")])
oscale = float(arg("--scale", 1.95))
sc = bpy.context.scene
act = arg("--action")
arm = next((o for o in sc.objects if o.type == 'ARMATURE'), None)
if act and arm:
    a = bpy.data.actions[act]
    arm.animation_data_create(); arm.animation_data.action = a
    try:
        arm.animation_data.action_slot = a.slots[0]
    except Exception: pass
frames = [int(f) for f in arg("--frames", str(sc.frame_current)).split(",")]
sc.render.engine = 'BLENDER_WORKBENCH' if engine == "WORKBENCH" else 'CYCLES'
if engine != "WORKBENCH":
    sc.cycles.samples = 8; sc.cycles.device = 'CPU'
else:
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'VERTEX' if "--vcol" in argv else ('MATERIAL' if "--mat" in argv else 'SINGLE')
    sh.single_color = (0.7, 0.62, 0.5)
    sh.show_xray = "--xray" in argv
    sh.show_cavity = False
sc.render.resolution_x = size; sc.render.resolution_y = size
sc.render.film_transparent = False
cam_d = bpy.data.cameras.new("qa_cam"); cam_d.type = 'ORTHO'; cam_d.ortho_scale = oscale
cam = bpy.data.objects.new("qa_cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
# floor line
import bmesh
dirs = {"side": Vector((-1, 0, 0)), "right": Vector((1, 0, 0)), "front": Vector((0, 1, 0)), "back": Vector((0, -1, 0)),
        "top": Vector((0, 0, 1)), "tq": Vector((-1, 1, 0.3)).normalized()}
for f in frames:
    sc.frame_set(f)
    for v in views:
        d = dirs[v]
        cam.location = center + d * 5
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y' if v != "top" else 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f"{act or 'rest'}_{v}_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
print("done")
