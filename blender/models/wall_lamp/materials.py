"""wall_lamp materials (T016): iron maps from numpy and the flame gradient, plain Principled BSDF. Numbers: material_params.json.

Iron uses a tiling box projection, one material, three 512 px maps (base colour, normal, ORM with AO unused). The flame has an
emissive gradient along its height; emission strength stays 1.0 because anything else exports KHR_materials_emissive_strength
and the asset may use no extensions. Flame brightness at run time is the game's: StandardMaterial3D.emission_energy_multiplier.
"""
import json
from pathlib import Path

import bpy
import numpy as np

PARAMS = json.loads((Path(__file__).resolve().parent / "material_params.json").read_text())


def band(rng, n, lo, hi):
    """Tileable band-pass noise, 0..1 by rank, features between hi and lo cycles per tile."""
    f = np.fft.fftfreq(n) * n
    r = np.hypot(*np.meshgrid(f, f, indexing="ij"))
    spec = np.fft.fft2(rng.standard_normal((n, n))) * ((r >= lo) & (r <= hi)) / np.maximum(r, 1.0)
    a = np.fft.ifft2(spec).real
    return (np.argsort(np.argsort(a.ravel())).reshape(a.shape) + 0.5) / a.size


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def image(name, rgb, data):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb
    img.pixels.foreach_set(px.ravel())
    img.file_format = "PNG"
    img.pack()
    return img


def iron_maps():
    p, n = PARAMS["iron"], PARAMS["iron_px"]
    rng = np.random.default_rng(PARAMS["seed"])
    hammer, pits = band(rng, n, 5, 14), band(rng, n, 40, 110)
    rust = band(rng, n, 2, 9) * 0.7 + band(rng, n, 16, 60) * 0.3
    rust = np.argsort(np.argsort(rust.ravel())).reshape(rust.shape) / rust.size
    worn = band(rng, n, 4, 24)
    r = smooth(rust, 1 - p["rust_cover"] - 0.06, 1 - p["rust_cover"] + 0.06)
    w = smooth(worn, 1 - p["worn_cover"] - 0.1, 1 - p["worn_cover"] + 0.1) * (1 - r)
    color = np.array(p["scale_srgb"])[None, None] * (0.86 + 0.28 * band(rng, n, 8, 50))[..., None]
    color = color * (1 - w[..., None]) + np.array(p["worn_srgb"])[None, None] * w[..., None]
    rust_col = np.array(p["rust_srgb"])[None, None] * (0.7 + 0.6 * pits)[..., None]
    color = color * (1 - r[..., None]) + rust_col * r[..., None]
    rough = p["roughness_iron"] * (1 - r) + p["roughness_rust"] * r + (pits - 0.5) * 0.1
    metal = p["metallic_iron"] * (1 - r) + p["metallic_rust"] * r
    orm = np.dstack([np.ones_like(r), np.clip(rough, 0.04, 1), metal])
    height = hammer * p["hammer_depth"] + (pits + r * 1.5) * p["pit_depth"]
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5
    nm = np.dstack([-dx, -dy, np.ones_like(dx)])
    nm /= np.linalg.norm(nm, axis=2, keepdims=True)
    return (image("wall_lamp_iron_color", color, False), image("wall_lamp_iron_normal", nm * 0.5 + 0.5, True),
            image("wall_lamp_iron_orm", orm, True))


def flame_map():
    f = PARAMS["flame"]
    w, h = f["size_px"]
    v = (np.arange(h) + 0.5) / h
    stops = [s[0] for s in f["stops_srgb"]]
    rgb = np.dstack([np.tile(np.interp(v, stops, [s[1][k] for s in f["stops_srgb"]])[:, None], (1, w)) for k in range(3)])
    return image("wall_lamp_flame_emissive", rgb, False)


def box_uv(ob, tile):
    me = ob.data
    uv = me.uv_layers.new(name="UVMap").data
    for poly in me.polygons:
        axis = max(range(3), key=lambda k: abs(poly.normal[k]))
        a, b = [k for k in range(3) if k != axis]
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = (co[a] / tile + 0.37 * axis, co[b] / tile + 0.61 * axis)


def height_uv(ob, top):
    me = ob.data
    uv = me.uv_layers.new(name="UVMap").data
    for li, loop in enumerate(me.loops):
        uv[li].uv = (0.5, me.vertices[loop.vertex_index].co.z / top)


def new_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def tex(nt, img):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    return t


def iron_material():
    m, nt, b = new_material("wall_lamp_iron")
    color, normal, orm = iron_maps()
    nt.links.new(tex(nt, color).outputs[0], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex(nt, orm).outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], b.inputs["Roughness"])
    nt.links.new(sep.outputs[2], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex(nt, normal).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m


def flame_material():
    m, nt, b = new_material("wall_lamp_flame")
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Roughness"].default_value = 1.0
    nt.links.new(tex(nt, flame_map()).outputs[0], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 1.0
    return m


def apply(iron_ob, flame_ob, flame_top):
    box_uv(iron_ob, PARAMS["tile_m"])
    height_uv(flame_ob, flame_top)
    iron_ob.data.materials[0] = iron_material()
    flame_ob.data.materials[0] = flame_material()
