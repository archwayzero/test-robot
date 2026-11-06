"""T044 scratch renders of hero_model.blend (Cycles CPU) -> .captures/t044/r/<tag>_<view>.png
usage: blender -b <blend> -P render_cloak.py -- <tag> <views comma list> [samples]
views: front, side (from +X... left side), back, threeq (front 3/4), rear3q (rear 3/4), sideR,
       torso_front, torso_back, torso_side, hood (close-ups), game (TEST camera-ish)"""
import bpy, math, sys
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
tag, views = argv[0], argv[1].split(",")
samples = int(argv[2]) if len(argv) > 2 else 24
OUT = "/home/archwayzero/game/.captures/t044/r/"
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type != "MESH" or o.name != "hero":
        bpy.data.objects.remove(o)
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("w"); w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.10, 0.10, 0.095, 1)
sc.world = w
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
def light(name, rot, e):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN")); l.data.energy = e
    l.data.angle = math.radians(8)
    l.rotation_euler = [math.radians(a) for a in rot]; sc.collection.objects.link(l); l.parent = cam
light("key", (-35, 40, 0), 3.2); light("fill", (-20, -45, 0), 1.0); light("rim", (-150, 0, 0), 2.0)
# floor (shadow catcher look: dark plane) to judge hem clearance
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
fl = bpy.context.active_object
fm = bpy.data.materials.new("floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
fl.data.materials.append(fm)
def aim(pos, tgt):
    cam.location = Vector(pos); cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()
def render(name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = OUT + f"{tag}_{name}.png"
    bpy.ops.render.render(write_still=True)
D = 6.0
full = {"front": 0, "threeq": 35, "side": 90, "rear3q": 145, "back": 180, "sideR": 270, "rear3qR": 215}
for v, a in full.items():
    if v in views:
        cam.data.type = "ORTHO"; cam.data.ortho_scale = 1.95
        r = math.radians(a)
        # angle 0 = camera in front (+Y), 90 = camera at +X
        aim((D * math.sin(r), D * math.cos(r), 0.9), (0, 0, 0.9))
        render(v, (520, 1000))
if "game" in views:          # third-person game camera (as in qa/render.py)
    cam.data.type = "PERSP"; cam.data.lens = 35
    aim((0.4, -2.5, 2.3), (0, 0.3, 1.0)); render("game", (960, 540))
close = {"torso_front": (0, 1.25, 0.9), "torso_back": (180, 1.25, 0.9), "torso_side": (90, 1.25, 0.9),
         "torso_3q": (35, 1.25, 0.9), "hood": (25, 1.55, 0.45), "hem": (120, 0.25, 0.7)}
for v, (a, zc, span) in close.items():
    if v in views:
        cam.data.type = "ORTHO"; cam.data.ortho_scale = span
        r = math.radians(a)
        aim((D * math.sin(r), D * math.cos(r), zc), (0, 0, zc))
        render(v, (700, 700))
