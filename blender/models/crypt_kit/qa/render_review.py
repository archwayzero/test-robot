"""Assemble the kit from the exported GLB and render review images (T015).

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b --factory-startup --python-exit-code 1 \
      -P blender/models/crypt_kit/qa/render_review.py -- [--only arcade,joins,pieces,low] [--samples N] [--scale 1.0]

Layout: a 5-cell aisle (A, along +X) with a walled side at -Y. The open side at +Y gives onto a second 5-cell aisle (B)
through arches on the piers, and B is walled beyond. End of the aisle: wall. Only -colonly children are dropped; pieces
are the exported meshes, placed like the maze would.
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
GLB = os.path.join(ROOT, "godot/assets/crypt_kit/model/crypt_kit.glb")
OUT = os.path.join(ROOT, ".captures/t015")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


ONLY = arg("--only", "arcade,joins,pieces,low").split(",")
SAMPLES = int(arg("--samples", "96"))
SCALE = float(arg("--scale", "1.0"))
S = 4.0
LEN = 5


def load():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    src = {}
    for ob in list(bpy.data.objects):
        if ob.name.endswith("-colonly"):
            bpy.data.objects.remove(ob)
    for ob in bpy.data.objects:
        src[ob.name] = ob.data
        ob.hide_render = True
        ob.hide_viewport = True
    return src


class Scene:
    def __init__(self, src):
        self.src, self.n = src, 0

    def put(self, name, x, y, rot=0.0):
        self.n += 1
        ob = bpy.data.objects.new("%s.%d" % (name, self.n), self.src[name])
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, "Z")
        return ob


def assemble(s, low=None):
    """Cells (i, j): i along the aisle, j=0 aisle A, j=1 aisle B. Cell (i,j) spans x i*S..(i+1)*S, y j*S..(j+1)*S."""
    low = low or {}
    rows = 2
    for i in range(LEN):
        for j in range(rows):
            cx, cy = (i + 0.5) * S, (j + 0.5) * S
            s.put("floor", cx, cy)
            s.put(low.get((i, j), "vault_bay"), cx, cy)
    for i in range(LEN):
        s.put("wall", (i + 0.5) * S, 0)                    # walled side
        s.put("wall", (i + 0.5) * S, rows * S)             # far side of aisle B
        for j in range(1, rows):
            s.put("arch", (i + 0.5) * S, j * S)            # open bays between the aisles
    for j in range(rows):
        s.put("wall", 0, (j + 0.5) * S, math.pi / 2)        # ends
        s.put("wall", LEN * S, (j + 0.5) * S, math.pi / 2)
        for i in range(1, LEN):
            s.put("arch", i * S, (j + 0.5) * S, math.pi / 2)  # transverse arches
    for i in range(LEN + 1):
        for j in range(rows + 1):
            s.put("pier", i * S, j * S)


def lights(strength=1.0):
    col = (1.0, 0.70, 0.36)
    def pt(x, y, z, e, r=0.12, c=col):
        l = bpy.data.lights.new("l", "POINT")
        l.energy, l.color, l.shadow_soft_size = e * strength, c, r
        ob = bpy.data.objects.new("l", l)
        ob.location = (x, y, z)
        bpy.context.scene.collection.objects.link(ob)
    # the photo is lit by low floods washing up the piers and vaults, one pool per bay
    for i in range(LEN + 1):
        pt(i * S + 0.0, 0.62, 0.35, 16)                  # wall side, wash up the wall and into the webs
        pt(i * S + 0.0, S - 0.62, 0.35, 14)              # arcade piers, aisle side
        pt(i * S + 0.0, S + 0.62, 0.35, 10)              # arcade piers, far side
        pt(i * S + 2.0, 2 * S - 0.6, 0.45, 8)
    for i in range(LEN):
        pt((i + 0.5) * S, 2.0, 0.4, 14, 0.4)            # aisle centre, soft fill towards the vault
    pt(LEN * S - 0.6, 2.0, 1.2, 26)                     # end wall glow
    pt(LEN * S - 0.6, 6.0, 1.2, 18)


def setup(w=1500, h=1000):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = int(w * SCALE), int(h * SCALE)
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Filmic"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.009, 0.006, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0


def camera(loc, target, lens=18.0, shift=(0, 0)):
    cam = bpy.data.cameras.new("c")
    cam.lens, cam.sensor_width, cam.clip_start = lens, 36, 0.02
    cam.shift_x, cam.shift_y = shift
    ob = bpy.data.objects.new("c", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def shot(name):
    bpy.context.scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


def arcade():
    # Camera approximates crypt.jpg: low, in the aisle, near the walled side, looking down the aisle and slightly
    # towards the open arcade so the vanishing point sits right of centre.
    camera((0.75, 1.15, 1.25), (12.0, 2.5, 1.95), lens=15.5)
    shot("arcade_crypt_camera")
    camera((0.8, 3.1, 1.5), (14.0, 1.5, 2.4), lens=17)
    shot("arcade_towards_wall")


JOINS = {
    # name: camera, target, lens
    "join_wall_pier": ((3.0, 1.2, 1.3), (4.05, 0.3, 1.35), 30),
    "join_wall_capital": ((3.1, 1.1, 1.7), (4.0, 0.3, 2.25), 32),
    "join_arch_pier": ((3.1, 2.8, 1.5), (4.0, 3.65, 2.5), 26),
    "join_arch_vault": ((5.2, 2.0, 1.7), (4.32, 2.1, 3.65), 24),
    "join_arch_vault_side": ((6.0, 2.9, 1.6), (7.3, 3.7, 3.2), 26),
    "join_vault_vault": ((2.0, 2.0, 1.6), (6.0, 2.0, 3.8), 24),
    "join_groin_capital": ((2.2, 2.2, 1.0), (3.65, 3.65, 2.5), 26),
    "join_floor_wall": ((2.0, 1.5, 0.7), (3.4, 0.3, 0.0), 28),
    "join_floor_floor": ((3.0, 2.0, 1.7), (4.0, 2.0, 0.0), 26),
}


def joins():
    for name, (loc, tgt, lens) in JOINS.items():
        camera(loc, tgt, lens)
        shot(name)


def piece_lights(ob_center, r=6.0):
    for (dx, dy, dz, e) in ((-3, -4, 3, 120), (4, -2, 1, 60), (0, 4, 5, 60), (0, 0, -3, 40)):
        l = bpy.data.lights.new("p", "POINT")
        l.energy, l.color, l.shadow_soft_size = e, (1.0, 0.85, 0.66), 0.6
        o = bpy.data.objects.new("p", l)
        o.location = (ob_center[0] + dx, ob_center[1] + dy, ob_center[2] + dz)
        bpy.context.scene.collection.objects.link(o)


PIECE_VIEWS = {
    "floor": ((3, -3, 3), (0, 0, 0)),
    "wall": ((-2.6, -6, 2.2), (0, 0, 1.95)),
    "pier": ((1.6, -2.6, 1.6), (0, 0, 1.15)),
    "arch": ((2.2, -5.5, 2.0), (0, 0, 3.0)),
    "vault_bay": ((1.2, -1.3, 0.6), (0, 0.2, 3.3)),
    "ceiling_crouch": ((3, -6.0, 0.4), (0, 0, 2.2)),
    "ceiling_crawl": ((3, -6.0, 0.4), (0, 0, 2.0)),
}


def pieces(src):
    sc = bpy.context.scene
    for name, (loc, tgt) in PIECE_VIEWS.items():
        for ob in list(sc.collection.objects):
            bpy.data.objects.remove(ob)
        Scene(src).put(name, 0, 0)
        piece_lights((0, 0, 2))
        camera(loc, tgt, 26)
        shot("piece_" + name)


def low_view(src):
    sc = bpy.context.scene
    for ob in list(sc.collection.objects):
        bpy.data.objects.remove(ob)
    s = Scene(src)
    assemble(s, {(2, 0): "ceiling_crouch", (3, 0): "ceiling_crawl"})
    lights()
    camera((1.0, 2.0, 1.3), (12.0, 2.0, 1.2), 20)
    shot("low_ceilings_aisle")
    camera((3.2, 2.0, 0.7), (6.5, 2.0, 1.9), 18)
    shot("low_ceilings_close")


def main():
    os.makedirs(OUT, exist_ok=True)
    src = load()
    setup()
    if "arcade" in ONLY or "joins" in ONLY:
        assemble(Scene(src))
        lights()
        if "arcade" in ONLY:
            arcade()
        if "joins" in ONLY:
            joins()
    if "low" in ONLY:
        low_view(src)
    if "pieces" in ONLY:
        pieces(src)


main()
