"""wall_lamp generator (T016): wrought-iron wall bracket holding a small iron oil font with one flame.

  blender -b --factory-startup -P blender/models/wall_lamp/build.py

Writes blender/models/wall_lamp/wall_lamp_model.blend. Re-runnable.

Axes. All dimensions here are written in the contract's Godot local space: x right, y up, z out of the wall, metres, origin on
the wall face at the middle of the back plate, nothing behind z = 0. G() converts to Blender (x, -z, y), which the glTF export
converts back, so the emitter arrives in the GLB at exactly (0, 0.25, 0.35).

Nodes: wall_lamp (empty, root) > wall_lamp_iron, wall_lamp_flame (pivot at the flame base, so the game can scale it from the
wick), light_emitter (empty, the point the maze puts its light at).
"""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
EMITTER = (0.0, 0.25, 0.35)
FLAME_BASE_Y = 0.205


def G(x, y, z):
    return Vector((x, -z, y))


def catmull(pts, per_span):
    """Catmull-Rom through (z, y) points, per_span segments between each pair."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        for s in range(per_span):
            t = s / per_span
            out.append(tuple(0.5 * (2 * p[i][k] + (p[i + 1][k] - p[i - 1][k]) * t
                                    + (2 * p[i - 1][k] - 5 * p[i][k] + 4 * p[i + 1][k] - p[i + 2][k]) * t * t
                                    + (3 * p[i][k] - p[i - 1][k] - 3 * p[i + 1][k] + p[i + 2][k]) * t ** 3) for k in (0, 1)))
    out.append(tuple(pts[-1]))
    return out


def bar(bm, path, wide, deep, x=0.0, end_scale=1.0):
    """Rectangular forged bar along a (z, y) path in the plane x = const; wide along x, deep in the plane."""
    rings = []
    n = len(path)
    for i, (z, y) in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        tz, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tz, ty) or 1.0
        nz, ny = -ty / ln, tz / ln
        s = 1.0 + (end_scale - 1.0) * (i / (n - 1)) ** 2
        w, d = wide * s / 2, deep * s / 2
        ring = [(x + sx * w, y + sd * d * ny, z + sd * d * nz) for sx, sd in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        rings.append([bm.verts.new(G(*c)) for c in ring])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1][::-1])


def lathe(bm, profile, x, z, sides):
    """Surface of revolution about the vertical through (x, z). profile: (radius, y); radius 0 makes a pole at either end."""
    rings = []
    for r, y in profile:
        if r == 0.0:
            rings.append([bm.verts.new(G(x, y, z))])
        else:
            rings.append([bm.verts.new(G(x + r * math.cos(2 * math.pi * k / sides), y,
                                         z + r * math.sin(2 * math.pi * k / sides))) for k in range(sides)])
    for r0, r1 in zip(rings, rings[1:]):
        if len(r0) == 1:
            for k in range(sides):
                bm.faces.new((r0[0], r1[k], r1[(k + 1) % sides]))
        elif len(r1) == 1:
            for k in range(sides):
                bm.faces.new((r0[k], r0[(k + 1) % sides], r1[0]))
        else:
            for k in range(sides):
                bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))


def prism(bm, outline, z0, z1):
    """Flat plate: (x, y) outline extruded from z0 to z1."""
    back = [bm.verts.new(G(x, y, z0)) for x, y in outline]
    front = [bm.verts.new(G(x, y, z1)) for x, y in outline]
    n = len(outline)
    for k in range(n):
        bm.faces.new((back[k], back[(k + 1) % n], front[(k + 1) % n], front[k]))
    bm.faces.new(back[::-1])
    bm.faces.new(front)


def scroll(cz, cy, r0, r1, a0, turns, segs):
    """Spiral in the (z, y) plane about (cz, cy), radius r0 -> r1, starting at angle a0 (radians), turning positive."""
    out = []
    for i in range(segs + 1):
        t = i / segs
        r = r0 * (r1 / r0) ** t
        a = a0 + turns * 2 * math.pi * t
        out.append((cz + r * math.cos(a), cy + r * math.sin(a)))
    return out


def build_iron():
    bm = bmesh.new()
    # Back plate: a forged strap with spear ends, on the wall face.
    prism(bm, [(0.0, 0.175), (0.024, 0.135), (0.016, 0.105), (0.033, 0.0), (0.016, -0.105), (0.024, -0.135), (0.0, -0.175),
               (-0.024, -0.135), (-0.016, -0.105), (-0.033, 0.0), (-0.016, 0.105), (-0.024, 0.135)], 0.0, 0.008)
    # Rivets at the spear ends.
    for y in (0.125, -0.125):
        rivet = [bm.verts.new(G(0.009 * math.cos(k * math.pi / 3), y + 0.009 * math.sin(k * math.pi / 3), 0.007)) for k in range(6)]
        tip = bm.verts.new(G(0, y, 0.016))
        for k in range(6):
            bm.faces.new((rivet[k], rivet[(k + 1) % 6], tip))
        bm.faces.new(rivet[::-1])
    # Main arm: leaves the plate level, sweeps up in a swan neck, ends as the stem under the pan.
    arm = catmull([(0.004, 0.035), (0.09, 0.035), (0.20, 0.042), (0.285, 0.070), (0.340, 0.105), (0.350, 0.150)], 4)
    bar(bm, arm, 0.016, 0.016)
    # Lower scroll: leaves the plate low, rises to the arm and curls back under it. The classic bracket infill.
    tail = catmull([(0.004, -0.105), (0.055, -0.095), (0.125, -0.070), (0.176, -0.0348)], 3)
    sc = scroll(0.135, 0.0, 0.054, 0.012, -0.70, 1.45, 26)
    join = tail[:-1] + sc
    bar(bm, join, 0.012, 0.009)
    # Forge collars where the arm meets the plate and where the scroll touches the arm.
    bar(bm, [(0.008, 0.035), (0.026, 0.035)], 0.026, 0.026)
    bar(bm, [(0.008, -0.105), (0.020, -0.103)], 0.020, 0.018)
    bar(bm, [(0.135, 0.018), (0.135, 0.046)], 0.024, 0.016)
    # Drip pan, turned rim.
    lathe(bm, [(0.0, 0.142), (0.024, 0.144), (0.060, 0.152), (0.073, 0.166), (0.070, 0.169), (0.056, 0.160), (0.0, 0.156)],
          0, 0.35, 12)
    # Oil font sitting in the pan, with a shallow well round the wick.
    lathe(bm, [(0.0, 0.156), (0.030, 0.157), (0.046, 0.168), (0.050, 0.181), (0.041, 0.195), (0.024, 0.202), (0.018, 0.198),
               (0.0, 0.196)], 0, 0.35, 10)
    # Wick stub (the flame starts on it).
    lathe(bm, [(0.005, 0.195), (0.0035, 0.212), (0.0, 0.214)], 0, 0.35, 4)
    return bm


def build_flame():
    """Teardrop, pivot at its base so scaling it dims or flickers from the wick."""
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.009, 0.006), (0.0155, 0.022), (0.016, 0.038), (0.0115, 0.056), (0.0055, 0.073), (0.0, 0.09)]
    lathe(bm, prof, 0.0, 0.0, 8)
    return bm


def to_object(bm, name, material, parent, location=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(38))
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    ob.location = location
    return ob


def plain_material(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    return m


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.objects.new("wall_lamp", None)
    bpy.context.collection.objects.link(root)
    iron = to_object(build_iron(), "wall_lamp_iron", plain_material("wall_lamp_iron", (0.05, 0.05, 0.05)), root)
    flame = to_object(build_flame(), "wall_lamp_flame", plain_material("wall_lamp_flame", (1, 0.6, 0.2)), root,
                      G(EMITTER[0], FLAME_BASE_Y, EMITTER[2]))
    emitter = bpy.data.objects.new("light_emitter", None)
    emitter.empty_display_size = 0.02
    bpy.context.collection.objects.link(emitter)
    emitter.parent = root
    emitter.location = G(*EMITTER)
    tris = sum(len(p.vertices) - 2 for o in (iron, flame) for p in o.data.polygons)
    print("wall_lamp tris", tris)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "wall_lamp_model.blend"))


main()
