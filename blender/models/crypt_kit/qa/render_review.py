"""Assemble the kit from the exported GLB and render review images (T015).

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b --factory-startup --python-exit-code 1 \
      -P blender/models/crypt_kit/qa/render_review.py -- [--only arcade,flat,joins,pieces,low,tiles] [--samples N] [--scale 1.0]

Layout: a 9-cell aisle (A, along +X) with a walled side at -Y (right of frame looking +X). The open side at +Y (left of
frame) gives onto a second aisle (B) through arches on the piers, and B is walled beyond. End of the aisle: wall. Only
-colonly children are dropped; pieces are the exported meshes, placed like the maze would.

What this scene adds beyond the kit (the same things the game must add; see "Rules for the assembler" in the contract):
  1. `wall` alternated by 180 degrees by cell parity.
  2. A world-space tint: base colour x (0.90-1.08, noise of about 7 m). In Godot: a shader or per-instance colour.
  3. Soiling on: base colour x COLOR_0, as Godot does with vertex_color_use_as_albedo.
  4. An arch on every open edge, a pier on every corner.
  5. Light. `arcade_crypt_camera`: neutral floods on the floor, both sides of each arch, plus fills at the game's lamp height
     (y = 2.0 in Godot). `arcade_flat`: no cast shadows, even light from six directions, Standard view, so the kit can be
     judged apart from lighting. Neither is the game's Mobile renderer: Cycles has bounces, the game has lamps and a
     possible lightmap, so these renders only judge the kit's shapes and maps.

Camera for crypt.jpg, level, verticals parallel (lens shift, as in the photo). Fit from the photo: vanishing point at
(0.645, 0.56) of the frame; arch feet left/right of the VP in ratio 1.35 (camera off the aisle axis); feet spans of the
first arches give f = 62 mm on 36 mm at 4 m bay spacing. Eye height is the compromise: the photo's eye is above its short
capitals, which on this kit (2.2 m capitals) would be 2.75 m; the crown/eye ratio of the photo gives 1.9 m, used here.
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


ONLY = arg("--only", "arcade,flat,joins,pieces,low,tiles").split(",")
SAMPLES = int(arg("--samples", "96"))
SCALE = float(arg("--scale", "1.0"))
S = 4.0
LEN = 9
NAMES = [n for n in arg("--names", "").split(",") if n]
ALT = "--no-alt" not in argv


def game_material(m):
    """Base colour x COLOR_0 (when the mesh has it) x world-space tint: what the game applies, see the module docstring."""
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    link = bsdf.inputs["Base Color"].links[0]
    src = link.from_socket
    while src.node.type == "MIX":                       # the importer may have wired COLOR_0 already; rebuild from the image
        src = src.node.inputs["A"].links[0].from_socket
    if src.node.type != "TEX_IMAGE":
        src = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and "color" in n.image.name).outputs["Color"]
    nt.links.remove(link)
    if m.name == "stone_ashlar":
        col = nt.nodes.new("ShaderNodeVertexColor")
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type, mx.blend_type = "RGBA", "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        nt.links.new(src, mx.inputs["A"])
        nt.links.new(col.outputs["Color"], mx.inputs["B"])
        src = mx.outputs["Result"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.42
    nz.inputs["Detail"].default_value = 1.0
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs[1].default_value, ramp.inputs[2].default_value = 0.35, 0.65
    ramp.inputs[3].default_value, ramp.inputs[4].default_value = 0.90, 1.08
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    nt.links.new(nz.outputs[0], ramp.inputs[0])
    mx2 = nt.nodes.new("ShaderNodeMix")
    mx2.data_type, mx2.blend_type = "RGBA", "MULTIPLY"
    mx2.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mx2.inputs["A"])
    nt.links.new(ramp.outputs[0], mx2.inputs["B"])
    nt.links.new(mx2.outputs["Result"], bsdf.inputs["Base Color"])


def load():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    for m in bpy.data.materials:
        if m.use_nodes and m.node_tree:
            game_material(m)
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

    def wall(self, x, y, rot=0.0, flip=False):
        """Assembler rule: alternate `wall` by 180 degrees."""
        return self.put("wall", x, y, rot + (math.pi if flip else 0.0))

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
        s.wall((i + 0.5) * S, 0, flip=i % 2 == 1)          # walled side
        s.wall((i + 0.5) * S, rows * S, flip=i % 2 == 0)   # far side of aisle B
        for j in range(1, rows):
            s.put("arch", (i + 0.5) * S, j * S)            # open bays between the aisles
    for j in range(rows):
        s.wall(0, (j + 0.5) * S, math.pi / 2, j % 2 == 1)   # ends
        s.wall(LEN * S, (j + 0.5) * S, math.pi / 2, j % 2 == 0)
        for i in range(1, LEN):
            s.put("arch", i * S, (j + 0.5) * S, math.pi / 2)  # transverse arches
    for i in range(LEN + 1):
        for j in range(rows + 1):
            s.put("pier", i * S, j * S)


def lights(strength=1.0):
    col = (1.0, 0.96, 0.91)     # neutral: the warmth must come from the kit's albedo

    def up(x, y, z, e, r=0.12, angle=3.14, tilt=(0.0, 0.0)):
        l = bpy.data.lights.new("l", "SPOT")
        l.energy, l.color, l.shadow_soft_size = e * strength, col, r
        l.spot_size, l.spot_blend = angle, 0.03
        ob = bpy.data.objects.new("l", l)
        ob.location = (x, y, z)
        ob.rotation_euler = (math.pi + tilt[0], tilt[1], 0)
        bpy.context.scene.collection.objects.link(ob)

    def fill(x, y, z, e):
        l = bpy.data.lights.new("f", "POINT")
        l.energy, l.color, l.shadow_soft_size = e * strength, col, 0.8
        ob = bpy.data.objects.new("f", l)
        ob.location = (x, y, z)
        bpy.context.scene.collection.objects.link(ob)

    # The photo is lit by small floods on the floor, aimed up: bright webs and walls, a dim floor, and hard pointed
    # shadows thrown up the walls by the piers. Same thing here: one per bay and aisle, tucked against the piers.
    for i in range(LEN):
        for y, e in ((1.5, 3.5), (2.7, 6), (5.0, 2), (6.5, 3)):     # either side of each transverse arch
            up((i + 0.27) * S, y, 0.06, e)
            if i < LEN - 1:
                up((i + 0.73) * S, y, 0.06, e)
        fill((i + 0.5) * S, 0.7, 2.0, 13)         # wall lamps at the game's lamp height, y = 2.0
        fill((i + 0.5) * S, 3.3, 2.0, 13)
        fill((i + 0.5) * S, 6.0, 2.0, 12)
    fill(LEN * S - 1.2, 1.2, 0.5, 26)                     # far end wall: a flood in the corner, as in the photo


def flat_lights():
    """Even light with no cast shadows: six soft suns, so only the kit's maps and shapes show."""
    for ob in [o for o in bpy.context.scene.collection.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(ob)
    for rot in ((0, 0, 0), (math.pi, 0, 0), (math.pi / 2, 0, 0), (-math.pi / 2, 0, 0), (0, math.pi / 2, 0), (0, -math.pi / 2, 0)):
        l = bpy.data.lights.new("flat", "SUN")
        l.energy, l.color, l.use_shadow = 0.95, (1, 1, 1), False
        ob = bpy.data.objects.new("flat", l)
        ob.rotation_euler = rot
        bpy.context.scene.collection.objects.link(ob)
    sc = bpy.context.scene
    sc.view_settings.view_transform, sc.view_settings.look = "Standard", "None"
    sc.view_settings.exposure = 0.0


def setup(w=1500, h=1000):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 3
    sc.render.resolution_x, sc.render.resolution_y = int(w * SCALE), int(h * SCALE)
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Filmic"
    for look in ("Filmic - Very High Contrast", "Very High Contrast"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            pass
    sc.view_settings.exposure = 0.55
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
    eye = float(arg("--eye", "1.9"))
    x0 = float(arg("--cam-x", "6.2"))
    cy = float(arg("--cam-y", "1.75"))
    lens = float(arg("--lens", "60"))
    cam = camera((x0, cy, eye), (x0 + 10, cy, eye), lens=lens, shift=(-0.145, 0.04))
    if "flat" in ONLY:
        flat_lights()
        shot("arcade_flat")
        return
    if not NAMES or "crypt" in NAMES:
        shot("arcade_crypt_camera")
    if NAMES and "along" not in NAMES:
        return
    camera((10.0, 2.2, 1.7), (30.0, 2.2, 1.9), lens=24)
    shot("arcade_along_aisle")


JOINS = {
    # name: camera, target, lens
    "join_wall_pier": ((3.0, 1.2, 1.3), (4.05, 0.3, 1.35), 30),
    "join_wall_capital": ((3.1, 1.1, 1.7), (4.0, 0.3, 2.25), 32),
    "join_arch_pier": ((3.1, 2.8, 1.5), (4.0, 3.65, 2.5), 26),
    "capital_close": ((2.6, 2.6, 1.55), (3.65, 3.65, 2.02), 40),
    "join_arch_vault": ((5.2, 2.0, 1.7), (4.32, 2.1, 3.85), 24),
    "join_arch_vault_side": ((6.0, 2.9, 1.6), (7.3, 3.7, 3.2), 26),
    "join_vault_vault": ((2.0, 2.0, 1.6), (6.0, 2.0, 4.0), 24),
    "join_groin_capital": ((2.2, 2.2, 1.0), (3.65, 3.65, 2.5), 26),
    "join_floor_wall": ((2.0, 1.5, 0.7), (3.4, 0.3, 0.0), 28),
    "join_floor_floor": ((3.0, 2.0, 1.7), (4.0, 2.0, 0.0), 26),
}


def joins():
    for name, (loc, tgt, lens) in JOINS.items():
        if NAMES and name not in NAMES:
            continue
        camera(loc, tgt, lens)
        shot(name)


def piece_lights(ob_center, r=6.0):
    for (dx, dy, dz, e) in ((-3, -4, 3, 500), (4, -2, 1, 260), (0, 4, 5, 250), (0, 0, -3, 200)):
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
    "ceiling_crouch": ((3, -6.0, 0.2), (0, 0, 2.2)),
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


def wall_tiles(src):
    """Three wall tiles under flat light and an orthographic camera: the honest view of how the soiling repeats."""
    sc = bpy.context.scene
    for ob in list(sc.collection.objects):
        bpy.data.objects.remove(ob)
    s = Scene(src)
    for i in range(3):
        s.wall((i + 0.5) * S, 0, flip=ALT and i % 2 == 1)
        s.put("floor", (i + 0.5) * S, -2.0)
    for i in range(4):
        s.put("pier", i * S, 0)
    bg = sc.world.node_tree.nodes["Background"].inputs
    keep = bg[0].default_value[:], bg[1].default_value
    bg[0].default_value = (1.0, 0.86, 0.66, 1)
    bg[1].default_value = 0.42
    cam = camera((6.0, -12.0, 2.3), (6.0, 0.0, 2.3), 50)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 12.4
    sc.render.resolution_y = int(sc.render.resolution_x * 0.45)
    shot("wall_3_tiles" if ALT else "wall_3_tiles_unalternated")
    sc.render.resolution_y = int(1000 * SCALE)
    bg[0].default_value, bg[1].default_value = keep


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
    if "arcade" in ONLY or "joins" in ONLY or "flat" in ONLY:
        assemble(Scene(src))
        lights()
        if "arcade" in ONLY or "flat" in ONLY:
            arcade()
        if "joins" in ONLY:
            if "flat" in ONLY:
                raise SystemExit("flat removes the lights: render joins in a separate run")
            joins()
    if "tiles" in ONLY:
        wall_tiles(src)
    if "low" in ONLY:
        low_view(src)
    if "pieces" in ONLY:
        pieces(src)


main()
