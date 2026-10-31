"""Cycles review of the built lamp at wall scale: mounted at y = 2.0 on a plain stone-coloured wall, one point light at the emitter.

  blender -b blender/models/wall_lamp/wall_lamp_model.blend -P blender/models/wall_lamp/qa/render_review.py -- --out .captures/t016/passN/cycles

Views: 1 m and 4 m from a standing eye (1.6 m), and two close-ups. Nothing is saved back to the .blend.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = Path(argv[argv.index("--out") + 1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
MOUNT_Y = 2.0
scn = bpy.context.scene
root = bpy.data.objects["wall_lamp"]
root.location = (0, 0, MOUNT_Y)
EM = Vector((0, -0.35, MOUNT_Y + 0.25))

wall_m = bpy.data.materials.new("wall")
wall_m.use_nodes = True
wall_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.36, 0.28, 1)
wall_m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
bpy.ops.mesh.primitive_plane_add(size=1)
w = bpy.context.object
w.scale = (8, 6, 1)
w.rotation_euler = (math.pi / 2, 0, 0)
w.location = (0, 0, 2.5)
w.data.materials.append(wall_m)
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, -3, 0))
bpy.context.object.data.materials.append(wall_m)

light = bpy.data.lights.new("lamp", "POINT")
light.energy = 14
light.color = (1.0, 0.86, 0.68)
light.shadow_soft_size = 0.02
lo = bpy.data.objects.new("lamp", light)
scn.collection.objects.link(lo)
lo.location = EM + Vector((0, -0.01, 0.0))
scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.03, 0.03, 0.035, 1)

cam = bpy.data.cameras.new("c")
co = bpy.data.objects.new("c", cam)
scn.collection.objects.link(co)
scn.camera = co
scn.render.engine = "CYCLES"
scn.cycles.device = "CPU"
scn.cycles.samples = 48
scn.cycles.use_denoising = False
scn.cycles.max_bounces = 4
scn.render.resolution_x, scn.render.resolution_y = 640, 360
scn.view_settings.view_transform = "Standard"
scn.render.threads = 8
scn.render.image_settings.file_format = "PNG"


def shot(name, pos, target, lens):
    co.location = pos
    d = (Vector(target) - Vector(pos))
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.lens = lens
    scn.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)


T = (0, -0.2, MOUNT_Y + 0.05)
T2 = (0, -0.2, MOUNT_Y + 0.07)
a = math.radians(35)
shot("a_1m", (1.0 * math.sin(a), -0.35 - 1.0 * math.cos(a), 1.6), T, 22)
shot("b_4m", (4.0 * math.sin(a), -0.35 - 3.0 * math.cos(a), 1.6), T, 22)
shot("c_close_quarter", (0.45, -0.85, MOUNT_Y + 0.1), T2, 35)
shot("d_close_side", (1.0, -0.2, MOUNT_Y + 0.05), T2, 42)
