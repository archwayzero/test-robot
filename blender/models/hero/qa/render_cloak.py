"""T044 scratch renders of a hero blend (Cycles CPU) -> <outdir>/<tag>_<view>.png
usage: blender -b <blend> -P render_cloak.py -- <outdir> <tag> <views comma list> [samples]
  <outdir>: absolute, or relative to the repository root (e.g. .captures/t044/pass2/r)
views: front, side (from +X, the hero's left), back, threeq (front 3/4), rear3q (rear 3/4), sideR, rear3qR (full, ortho);
       torso_front, torso_back, torso_side, torso_3q, hood, hem (close-ups, ortho);
       neck_front, neck_3qL, neck_3qR, neck_back, shoulder_top, rear3q_pack (close-ups as in the T044 review);
       neck8 (8 neck close-ups every 45 deg); game (one third-person shot); game2 (3 shots behind/above at 2.5 m)"""
import math
import os
import sys

import bpy
from mathutils import Vector

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0] if os.path.isabs(argv[0]) else os.path.join(REPO, argv[0])
os.makedirs(OUT, exist_ok=True)
tag, views = argv[1], argv[2].split(",")
samples = int(argv[3]) if len(argv) > 3 else 24
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type != "MESH" or o.name != "hero":
        bpy.data.objects.remove(o)
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.10, 0.095, 1)
sc.world = w
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def light(name, rot, e):
    lo = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
    lo.data.energy = e
    lo.data.angle = math.radians(8)
    lo.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lo)
    lo.parent = cam


light("key", (-35, 40, 0), 3.2)
light("fill", (-20, -45, 0), 1.0)
light("rim", (-150, 0, 0), 2.0)
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))      # dark floor, to judge the hem clearance
fl = bpy.context.active_object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
fl.data.materials.append(fm)


def aim(pos, tgt):
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()


def render(name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, f"{tag}_{name}.png")
    bpy.ops.render.render(write_still=True)


def ortho(span):
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = span


D = 6.0
full = {"front": 0, "threeq": 35, "side": 90, "rear3q": 145, "back": 180, "sideR": 270, "rear3qR": 215}
for v, a in full.items():
    if v in views:          # angle 0 = camera in front (+Y), 90 = camera at +X
        ortho(1.95)
        r = math.radians(a)
        aim((D * math.sin(r), D * math.cos(r), 0.9), (0, 0, 0.9))
        render(v, (520, 1000))
if "game" in views:
    cam.data.type = "PERSP"
    cam.data.lens = 35
    aim((0.4, -2.5, 2.3), (0, 0.3, 1.0))
    render("game", (960, 540))
close = {"torso_front": (0, 1.25, 0.9), "torso_back": (180, 1.25, 0.9), "torso_side": (90, 1.25, 0.9),
         "torso_3q": (35, 1.25, 0.9), "hood": (25, 1.55, 0.45), "hem": (120, 0.25, 0.7)}
for v, (a, zc, span) in close.items():
    if v in views:
        ortho(span)
        r = math.radians(a)
        aim((D * math.sin(r), D * math.cos(r), zc), (0, 0, zc))
        render(v, (700, 700))
extra = {"neck_front": ((0, 6, 1.42), (0, 0, 1.42), 0.45), "neck_3qL": ((3.5, 4.8, 1.45), (0, 0, 1.42), 0.5),
         "neck_3qR": ((-3.5, 4.8, 1.45), (0, 0, 1.42), 0.5), "neck_back": ((0, -6, 1.45), (0, 0, 1.42), 0.5),
         "shoulder_top": ((1.5, 2.0, 5.0), (0, 0, 1.4), 0.8), "rear3q_pack": ((3.5, -4.8, 1.6), (0, 0, 1.2), 0.75)}
for v, (pos, tgt, span) in extra.items():
    if v in views:
        ortho(span)
        aim(pos, tgt)
        render(v, (700, 700))
if "neck8" in views:
    for k in range(8):
        r = math.radians(45 * k)
        ortho(0.5)
        aim((D * math.sin(r), D * math.cos(r), 2.6), (0, 0, 1.42))
        render(f"neck8_{45 * k:03d}", (500, 500))
if "game2" in views:
    cam.data.type = "PERSP"
    cam.data.lens = 35
    for i, a in enumerate((0, 30, -30)):
        r = math.radians(a)
        aim((2.5 * math.sin(r), -2.5 * math.cos(r), 2.3), (0, 0, 1.0))
        render(f"game2_{i}", (960, 540))
