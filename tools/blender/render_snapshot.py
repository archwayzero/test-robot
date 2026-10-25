"""Render a still of an exported asset for reference-video generation (headless, CPU).

  blender -b -P tools/blender/render_snapshot.py -- --glb godot/assets/<a>/model/<a>.glb \
      --out reference/<a>/snapshot_front.png [--azimuth 0] [--elevation 10] [--size 1024] [--bg 1,1,1]

Azimuth 0 looks at the model's front as exported (verify on the first asset and note the right value
in docs/contracts/blender-godot-assets.md). Uses Cycles on the GPU when one is visible (never inside Claude Code's sandbox), otherwise CPU. --cpu forces CPU.
"""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


glb, out = arg("--glb"), arg("--out")
if not glb or not out:
    sys.exit("usage: -- --glb in.glb --out snapshot.png")
az, el = math.radians(float(arg("--azimuth", 0))), math.radians(float(arg("--elevation", 10)))
size = int(arg("--size", 1024))
bg = [float(x) for x in arg("--bg", "1,1,1").split(",")]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not objs:
    sys.exit("no mesh in file")
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center, radius = (lo + hi) / 2, max((hi - lo).length / 2, 0.01)

scene = bpy.context.scene
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
dist = radius / math.tan(cam_data.angle / 2) * 1.15
# Front of a glTF asset faces +Z in glTF, which the importer maps to -Y in Blender.
direction = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
cam.location = center + direction * dist
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (*bg, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
device_used = "CPU"
if "--cpu" not in argv:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
            except Exception:
                continue
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = "GPU"
                device_used = f"{backend}: {gpus[0].name}"
                break
    except Exception as e:  # never fail a snapshot because of GPU setup
        print(f"GPU setup failed, using CPU: {e}")
print(f"Cycles device: {device_used}")
scene.cycles.samples = 32
scene.render.resolution_x = scene.render.resolution_y = size
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print(f"rendered {out}")
