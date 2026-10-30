"""crypt_kit generator (T015). Contract: docs/contracts/crypt-kit.md.

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b --factory-startup -P blender/models/crypt_kit/build.py

Re-runnable: wipes the scene, regenerates textures/*.png (seeded) and writes crypt_kit_model.blend + atlas.json.

Blender axes: X along the piece, Y across, Z up. glTF/Godot: (x, y, z) -> (x, z, -y). `wall` and `arch` run along
local X (Godot `_wall_h`); rotate 90 deg about up for edges along Z. All root nodes sit at the origin of the file; each
piece's origin is the contract's logical pivot.

Texture layout. stone_ashlar is a 2048 atlas, stone_floor a 1024 full tile:
  band A  ashlar, 4 m x 2 m at 512 px/m, periodic in U and V: walls, piers, capitals and ceilings. Wall/pier share
          world-aligned U (U wraps at every cell corner) so their courses run through the join. Above z=2 the wall
          restarts at the bottom of the band (bed joint) with a U offset, to hide the 2 m repeat.
  band B  voussoir strip, not tiled: arch soffit + the arch face ring folded over the arris.
  band C  plaster, not tiled: vault webs.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(HERE, "textures")
BLEND = os.path.join(HERE, "crypt_kit_model.blend")

# ---------------------------------------------------------------- contract numbers
CELL = 4.0
WALL_T = 0.6
SHAFT_TOP = 1.9
SPRING = 2.2
CROWN = 3.9
PIER = 0.6
CAPITAL = 0.75
FLOOR_T = 0.2
R_ARCH = 1.7
CROUCH_Y = 1.3
CRAWL_Y = 0.75

# Tiny offsets inside the +-5 mm tolerance, so that coplanar faces never z-fight.
PIER_PROUD = 0.002   # pier faces stand 2 mm proud of the wall faces they sit in line with
ARCH_R = R_ARCH - 0.002   # arch soffit crown 3.898, web crown 3.902: tangent surfaces stay 4 mm apart
WEB_CROWN = 1.702
# Vault web section: superellipse with the same springing (+-1.7 at z=2.2) and crown as the arch but fuller haunches,
# which is the only way an arch of crown 3.9 can show a face below a vault of crown 3.9. See report (deviation D1).
WEB_N = 2.6
WEB_TUCK = 0.02      # web runs this far behind the arch/wall face

# ---------------------------------------------------------------- texture atlas
ATLAS = 2048
PAD = 12
A_ROWS = (PAD, PAD + 1024)      # rows counted from the top of the image
B_ROWS = (1048, 1428)
C_ROWS = (1428, 2048)
A_M = (4.0, 2.0)
B_LEN = 5.46                    # metres of arc mapped to the width of band B
B_DEPTH = B_LEN * (B_ROWS[1] - B_ROWS[0]) / ATLAS


def v_of_row(row):
    return 1.0 - row / ATLAS


A_V0, A_V1 = v_of_row(A_ROWS[1]), v_of_row(A_ROWS[0])
B_V0, B_V1 = v_of_row(B_ROWS[1]), v_of_row(B_ROWS[0])
C_V0, C_V1 = v_of_row(C_ROWS[1]), v_of_row(C_ROWS[0])

ASHLAR_COURSES = [0.22, 0.17, 0.28, 0.15, 0.25, 0.19, 0.21, 0.19, 0.34]  # bottom to top, sum 2.0 (last one: capital course)
CAP_COURSE = (1.66, 2.0)


def band_a(u, z):
    """Band A UV for u in tile widths (may leave 0..1, wraps) and z in metres 0..2."""
    return u, A_V0 + (A_V1 - A_V0) * (z / A_M[1])


# ---------------------------------------------------------------- periodic noise
def noise(h, w, beta, seed, low=0.0):
    """Periodic gaussian noise with a 1/f^beta spectrum, zero mean, unit std."""
    rng = np.random.RandomState(seed)
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.rfftfreq(w)[None, :] * w
    f = np.sqrt((fx * (h / w)) ** 2 + fy ** 2)
    amp = np.where(f > 0, np.maximum(f, 1e-6) ** (-beta / 2.0), 0.0)
    if low > 0:
        amp *= 1.0 - np.exp(-(f / low) ** 2)
    n = np.fft.irfft2(np.fft.rfft2(rng.standard_normal((h, w))) * amp, s=(h, w))
    return (n - n.mean()) / (n.std() + 1e-9)


def streaks(h, w, seed):
    """Periodic vertical weathering runs: noise that is long in V, short in U."""
    rng = np.random.RandomState(seed)
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.rfftfreq(w)[None, :] * w
    f = np.sqrt((fx * 0.25) ** 2 + (fy * 2.5) ** 2)
    amp = np.where(f > 0, np.maximum(f, 1e-6) ** -1.35, 0.0)
    n = np.fft.irfft2(np.fft.rfft2(rng.standard_normal((h, w))) * amp, s=(h, w))
    return (n - n.mean()) / n.std()


def blur(a, sigma):
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * g, s=(h, w))


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def normal_from_height(h, ppm, strength=1.0):
    """Tangent-space normal, +Y up in texture space (glTF). Row 0 is the top of the image."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * ppm * 0.5 * strength
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * ppm * 0.5 * strength   # d/dv: v grows towards row 0
    nz = np.ones_like(h)
    ln = np.sqrt(dx * dx + dy * dy + nz * nz)
    return np.dstack([(-dx / ln + 1) * 0.5, (-dy / ln + 1) * 0.5, (nz / ln + 1) * 0.5])


def block_field(h, w, ppm, courses, seed, len_range, warp=0.012):
    """Irregular coursed blocks on a torus. Returns stone id, distance to the nearest joint (m), stone count."""
    rng = np.random.RandomState(seed)
    pu, pv = w / ppm, h / ppm
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    yy = (h - 1 - yy + 0.5) / ppm     # metres up from the bottom of the region
    xx = (xx + 0.5) / ppm
    wx = noise(h, w, 3.0, seed + 1) * warp
    wy = noise(h, w, 3.0, seed + 2) * warp
    x = np.mod(xx + wx, pu)
    y = np.mod(yy + wy, pv)
    edges = np.concatenate([[0.0], np.cumsum(courses)])
    edges[-1] = pv
    ids = np.zeros((h, w), dtype=np.int32)
    dist = np.zeros((h, w))
    next_id = 0
    for c in range(len(courses)):
        m = (y >= edges[c]) & (y < edges[c + 1])
        joints = [rng.uniform(0, 0.5)]
        while True:
            step = rng.uniform(*len_range)
            if joints[-1] + step > pu + joints[0] - len_range[0] * 0.7:
                break
            joints.append(joints[-1] + step)
        joints = np.array(joints)
        ext = np.concatenate([joints - pu, joints, joints + pu])
        i = np.searchsorted(ext, x[m]) - 1
        d_head = np.minimum(x[m] - ext[i], ext[i + 1] - x[m])
        d_bed = np.minimum(y[m] - edges[c], edges[c + 1] - y[m])
        k = 0.012
        dist[m] = -k * np.log(np.exp(-d_head / k) + np.exp(-d_bed / k))
        ids[m] = next_id + np.mod(i, len(joints))
        next_id += len(joints)
    return ids, dist, next_id


def stone_maps(h, w, ppm, courses, seed, len_range, palette, joint=0.0045, wear=0.022, relief=0.016, warp=0.012):
    """Shared block material. Returns albedo (sRGB 0..1), height (m), roughness, all periodic."""
    ids, d, n = block_field(h, w, ppm, courses, seed, len_range, warp)
    rng = np.random.RandomState(seed + 7)
    pu, pv = w / ppm, h / ppm

    n_lo = noise(h, w, 3.2, seed + 3)
    n_mid = noise(h, w, 2.2, seed + 4, low=6)
    n_hi = noise(h, w, 1.2, seed + 5, low=40)
    n_edge = noise(h, w, 2.0, seed + 6, low=10)

    jw = joint * (1.0 + 0.8 * n_edge).clip(0.25, 2.8)
    ww = wear * (1.0 + 0.8 * n_mid).clip(0.25, 2.6)
    profile = sstep(0, 1, (d - jw) / ww)
    profile = np.where(d < jw, 0.0, profile)

    tone = rng.uniform(-1, 1, n)[ids]
    warm = rng.uniform(-1, 1, n)[ids]
    inset = rng.uniform(-1, 1, n)[ids]
    rough_s = rng.uniform(-1, 1, n)[ids]

    # tool marks: integer wave numbers keep them periodic
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    nx = rng.randint(30, 110, n)[ids]
    ny = rng.randint(-70, 70, n)[ids]
    tool = np.sin(2 * np.pi * (nx * xx / w + ny * (yy / h) * max(1, round(pv / pu * 2))) + 2.0 * n_mid)
    tool_on = sstep(-0.3, 0.8, rng.uniform(-1, 1, n)[ids] + 0.5 * n_lo)

    pits = sstep(1.6, 2.8, noise(h, w, 1.4, seed + 8, low=30) + 0.5 * n_mid)
    height = profile * (relief + 0.005 * inset) + 0.006 * sstep(0.0, 0.09, d) + 0.0014 * n_lo * profile + 0.0013 * n_mid * profile + 0.00030 * n_hi * profile \
        + 0.00022 * tool * tool_on * profile - 0.0018 * pits * profile + 0.0005 * n_hi * (1 - profile)

    base = np.array(palette["stone"])
    alb = np.ones((h, w, 3)) * base
    v = 1.0 + palette["tone"] * tone + 0.07 * n_lo + 0.035 * n_mid + 0.02 * n_hi
    alb = alb * v[..., None]
    alb[..., 0] *= 1.0 + palette["warm"] * warm
    alb[..., 2] *= 1.0 - palette["warm"] * 1.8 * warm
    stain = sstep(0.0, 2.6, n_lo * 0.8 + n_mid * 0.35)
    alb *= (1.0 - palette["stain"] * stain[..., None] * np.array([0.85, 0.95, 1.1]))
    pale = sstep(0.3, 2.6, -n_lo * 0.7 + n_mid * 0.35)
    alb = alb * (1 - 0.35 * pale[..., None]) + np.array(palette["pale"]) * 0.35 * pale[..., None]
    arris = sstep(0.0, 0.6, profile) * (1 - sstep(0.6, 1.0, profile))
    alb *= 1.0 + 0.08 * arris[..., None]
    alb *= 1.0 - 0.28 * pits[..., None]
    alb *= (1.0 + 0.035 * tool * tool_on)[..., None]
    run = streaks(h, w, seed + 9)
    dark_run = sstep(0.7, 2.4, run) * palette.get("runs", 0.0)
    pale_run = sstep(0.7, 2.4, -run) * palette.get("runs", 0.0)
    alb *= 1.0 - 0.34 * dark_run[..., None] * np.array([0.85, 1.0, 1.2])
    alb = alb * (1 - 0.40 * pale_run[..., None]) + np.array(palette["pale"]) * 0.40 * pale_run[..., None]
    fleck = sstep(0.9, 2.2, noise(h, w, 1.7, seed + 10, low=24))
    alb *= 1.0 - 0.15 * fleck[..., None] * np.array([0.8, 1.0, 1.25])
    mort = np.array(palette["mortar"])[None, None, :] * (1.0 + 0.06 * n_mid + 0.05 * n_hi)[..., None]
    mix = sstep(0.0, 0.35, profile)[..., None]
    alb = mort * (1 - mix) + alb * mix

    rough = palette["rough"] + 0.05 * rough_s + 0.03 * n_mid - palette["polish"] * profile * sstep(-0.5, 1.5, n_lo)
    rough = np.where(profile < 0.35, 0.95, rough)
    return np.clip(alb, 0, 1), height, np.clip(rough, 0.25, 1)


def ao_from_height(h, ppm, scale):
    small = (blur(h, 0.012 * ppm) - h) / scale
    large = (blur(h, 0.05 * ppm) - h) / scale
    return np.clip(1.0 - 0.75 * np.clip(small, 0, 1) - 0.35 * np.clip(large, 0, 1), 0.25, 1.0)


def plaster_maps(h, w, ppm, seed):
    n_lo = noise(h, w, 3.4, seed)
    n_mid = noise(h, w, 2.4, seed + 1, low=5)
    n_hi = noise(h, w, 1.3, seed + 2, low=50)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    edge_v = 1.0 - sstep(0.0, 0.32, 1.0 - (yy + 0.5) / h)    # bottom of band: edge of web at the arch/wall
    centre_u = np.abs((xx + 0.5) / w - 0.5) * 2              # 0 crown, 1 springing
    low = sstep(0.55, 1.0, centre_u)
    grime = np.clip(0.55 * low + 0.45 * edge_v * low + 0.25 * edge_v, 0, 1)
    blotch = sstep(0.1, 1.6, n_lo + 0.5 * n_mid)
    crack = 1 - sstep(0.0, 0.035, np.abs(noise(h, w, 3.0, seed + 3)))
    crack = crack * sstep(0.7, 1.6, noise(h, w, 3.2, seed + 4))
    height = 0.0045 * n_lo + 0.0010 * n_mid + 0.00012 * n_hi - 0.0010 * crack
    pal = np.array([0.905, 0.855, 0.735])
    v = 1.0 + 0.030 * n_lo + 0.022 * n_mid + 0.012 * n_hi
    alb = pal * v[..., None]
    alb *= 1 - 0.14 * blotch[..., None] * np.array([0.9, 1.0, 1.15])
    alb *= 1 - 0.20 * grime[..., None] * np.array([0.8, 1.0, 1.3])
    alb *= 1 - 0.35 * crack[..., None]
    rough = 0.9 + 0.03 * n_mid
    return np.clip(alb, 0, 1), height, np.clip(rough, 0.5, 1)


def to_image(name, arr, srgb):
    """arr: h x w x 3, row 0 = top. Saves textures/<name>.png, returns the loaded, packed image."""
    h, w = arr.shape[:2]
    path = os.path.join(TEX_DIR, name + ".png")
    img = bpy.data.images.new(name + "_tmp", w, h, alpha=False)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(np.flipud(arr), 0, 1).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    out = bpy.data.images.load(path)
    out.name = name
    out.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    out.pack()
    return out


def half(a):
    return 0.25 * (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2])


def build_textures():
    os.makedirs(TEX_DIR, exist_ok=True)
    pal_a = dict(stone=[0.770, 0.665, 0.495], mortar=[0.72, 0.66, 0.54], pale=[0.88, 0.83, 0.72], tone=0.085, warm=0.03,
                 stain=0.46, rough=0.86, polish=0.04, runs=1.0)
    # band A
    ppm = 512
    a_alb, a_h, a_r = stone_maps(1024, 2048, ppm, ASHLAR_COURSES, 1501, (0.30, 0.78), pal_a, warp=0.007)
    a_n = normal_from_height(a_h, ppm)
    a_ao = ao_from_height(a_h, ppm, 0.012)
    # band B: voussoirs. One course across, irregular joints along the arc. Generated on a square-ish torus in metres.
    bh, bw = B_ROWS[1] - B_ROWS[0], ATLAS
    bppm = ATLAS / B_LEN
    pal_b = dict(pal_a, tone=0.085, warm=0.03, stain=0.30, stone=[0.785, 0.675, 0.495])
    b_alb, b_h, b_r = stone_maps(bh, bw, bppm, [bh / bppm], 1601, (0.17, 0.27), pal_b, joint=0.006, wear=0.018,
                                 relief=0.014, warp=0.005)
    b_n = normal_from_height(b_h, bppm)
    b_ao = ao_from_height(b_h, bppm, 0.012)
    # band C: plaster
    ch, cw = C_ROWS[1] - C_ROWS[0], ATLAS
    cppm = ATLAS / 5.6
    c_alb, c_h, c_r = plaster_maps(ch, cw, cppm, 1701)
    c_n = normal_from_height(c_h, cppm)
    c_ao = np.ones((ch, cw))

    alb = np.zeros((ATLAS, ATLAS, 3))
    nrm = np.zeros((ATLAS, ATLAS, 3))
    rgh = np.zeros((ATLAS, ATLAS))
    aoc = np.zeros((ATLAS, ATLAS))
    r0, r1 = A_ROWS
    rows = np.mod(np.arange(0, B_ROWS[0]) - r0, 1024)   # wrapped padding above and below band A
    alb[0:B_ROWS[0]] = a_alb[rows]
    nrm[0:B_ROWS[0]] = a_n[rows]
    rgh[0:B_ROWS[0]] = a_r[rows]
    aoc[0:B_ROWS[0]] = a_ao[rows]
    for rr, (al, nn, ro, ao) in ((B_ROWS, (b_alb, b_n, b_r, b_ao)), (C_ROWS, (c_alb, c_n, c_r, c_ao))):
        alb[rr[0]:rr[1]] = al
        nrm[rr[0]:rr[1]] = nn
        rgh[rr[0]:rr[1]] = ro
        aoc[rr[0]:rr[1]] = ao
    # cavity also goes into the base colour a little: Cycles and glTF viewers ignore the occlusion input differently
    alb = alb * (0.84 + 0.16 * aoc)[..., None]
    imgs = {}
    imgs["ashlar_color"] = to_image("stone_ashlar_color", alb, True)
    imgs["ashlar_normal"] = to_image("stone_ashlar_normal", nrm, False)
    orm = np.dstack([half(aoc), half(rgh), np.zeros((ATLAS // 2, ATLAS // 2))])
    imgs["ashlar_orm"] = to_image("stone_ashlar_orm", orm, False)

    # stone_floor: 4 x 4 m full tile at 256 px/m (texture memory budget: see report)
    pal_f = dict(stone=[0.66, 0.60, 0.50], mortar=[0.50, 0.45, 0.37], pale=[0.76, 0.72, 0.64], tone=0.09, warm=0.02,
                 stain=0.38, rough=0.66, polish=0.22)
    fppm = 256
    courses = [0.66, 0.84, 0.54, 0.72, 0.60, 0.64]
    f_alb, f_h, f_r = stone_maps(1024, 1024, fppm, courses, 1801, (0.48, 1.15), pal_f, joint=0.005, wear=0.05,
                                 relief=0.007, warp=0.012)
    f_ao = ao_from_height(f_h, fppm, 0.010)
    f_alb = f_alb * (0.84 + 0.16 * f_ao)[..., None]
    imgs["floor_color"] = to_image("stone_floor_color", f_alb, True)
    imgs["floor_normal"] = to_image("stone_floor_normal", normal_from_height(f_h, fppm, 0.6), False)
    imgs["floor_orm"] = to_image("stone_floor_orm", np.dstack([f_ao, f_r, np.zeros_like(f_r)]), False)
    return imgs


# ---------------------------------------------------------------- materials
def occlusion_group():
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def make_material(name, color, normal, orm):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexImage")
    tc.image = color
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = normal
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = orm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = occlusion_group()
    nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    nt.links.new(sep.outputs[0], grp.inputs["Occlusion"])
    return m


# ---------------------------------------------------------------- mesh builder
class Builder:
    """Faces with per-corner UVs. Vertices merge only inside a named group, so group borders are hard edges."""

    def __init__(self):
        self.verts, self.index, self.faces = [], {}, []

    def vid(self, group, p):
        key = (group, round(p[0], 5), round(p[1], 5), round(p[2], 5))
        i = self.index.get(key)
        if i is None:
            i = len(self.verts)
            self.index[key] = i
            self.verts.append(tuple(p))
        return i

    def face(self, group, pts, uvs, smooth=True):
        ids = [self.vid(group, p) for p in pts]
        keep = [i for i in range(len(ids)) if ids[i] != ids[i - 1]]
        if len(keep) < 3:
            return
        self.faces.append(([ids[i] for i in keep], [uvs[i] for i in keep], smooth))

    def grid(self, group, rows, uv_rows, flip=False, smooth=True):
        """rows[j][i] are points, uv_rows[j][i] their UVs."""
        for j in range(len(rows) - 1):
            for i in range(len(rows[0]) - 1):
                pts = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
                uvs = [uv_rows[j][i], uv_rows[j][i + 1], uv_rows[j + 1][i + 1], uv_rows[j + 1][i]]
                if flip:
                    pts, uvs = pts[::-1], uvs[::-1]
                self.face(group, pts, uvs, smooth)

    def to_object(self, name, mat, parent=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], [f[0] for f in self.faces])
        me.update()
        uv = me.uv_layers.new(name="UVMap") if mat else None
        for pi, (ids, uvs, smooth) in enumerate(self.faces):
            poly = me.polygons[pi]
            poly.use_smooth = smooth
            if uv:
                for k in range(len(ids)):
                    uv.uv[poly.loop_start + k].vector = uvs[k]
        if mat:
            me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        if parent:
            ob.parent = parent
        return ob


def add_box(b, lo, hi, u_scale=None):
    """Closed box, outward normals, no UV (collision)."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    for f in ((3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        b.face(id(b), [p[i] for i in f], [(0, 0)] * 4, False)


def collision(parent, boxes=None, tris=None):
    b = Builder()
    for lo, hi in boxes or []:
        add_box(b, lo, hi)
    for pts in tris or []:
        b.face("c", pts, [(0, 0)] * len(pts), False)
    ob = b.to_object(parent.name + "-colonly", None, parent)
    return ob


def wall_face(b, group, s0, s1, z0, z1, place, u_off=0.0):
    """Vertical rectangle in band A. s: metres rightwards as seen from outside; U = s/4 + u_off."""
    pts = [place(s0, z0), place(s1, z0), place(s1, z1), place(s0, z1)]
    z_lo = z0 % A_M[1]
    z_hi = z_lo + (z1 - z0)
    uvs = [band_a(s0 / 4 + u_off, z_lo), band_a(s1 / 4 + u_off, z_lo), band_a(s1 / 4 + u_off, z_hi),
           band_a(s0 / 4 + u_off, z_hi)]
    b.face(group, pts, uvs, False)


# ---------------------------------------------------------------- pieces
def build_floor(mat):
    b = Builder()
    h = CELL / 2
    b.face("top", [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [(0, 0), (1, 0), (1, 1), (0, 1)], False)
    for i, (ax, ay) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
        px, py = -ay, ax
        p0 = (ax * h - px * h, ay * h - py * h)
        p1 = (ax * h + px * h, ay * h + py * h)
        b.face("s%d" % i, [(p0[0], p0[1], -FLOOR_T), (p1[0], p1[1], -FLOOR_T), (p1[0], p1[1], 0), (p0[0], p0[1], 0)],
               [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], False)
    ob = b.to_object("floor", mat)
    collision(ob, [((-h, -h, -FLOOR_T), (h, h, 0))])
    return ob


def build_wall(mat):
    b = Builder()
    h, t = CELL / 2, WALL_T / 2
    front = lambda s, z: (s, -t, z)     # faces -Y: s runs +X
    back = lambda s, z: (-s, t, z)      # faces +Y: s runs -X
    end_r = lambda s, z: (h, s, z)
    end_l = lambda s, z: (-h, -s, z)
    for tag, place, off in (("f", front, 0.5), ("b", back, 0.5)):
        wall_face(b, tag + "0", -h, h, 0, 2.0, place, off)
        wall_face(b, tag + "1", -h, h, 2.0, CROWN, place, off + 0.37)
    wall_face(b, "e0", -t, t, 0, CROWN if False else 2.0, end_r, 0.0)
    wall_face(b, "e1", -t, t, 2.0, CROWN, end_r, 0.37)
    wall_face(b, "e2", -t, t, 0, 2.0, end_l, 0.0)
    wall_face(b, "e3", -t, t, 2.0, CROWN, end_l, 0.37)
    b.face("top", [(-h, -t, CROWN), (h, -t, CROWN), (h, t, CROWN), (-h, t, CROWN)],
           [band_a(0, 0), band_a(1, 0), band_a(1, 0.6), band_a(0, 0.6)], False)
    ob = b.to_object("wall", mat)
    collision(ob, [((-h, -t, 0), (h, t, CROWN))])
    return ob


def build_pier(mat):
    b = Builder()
    rng = np.random.RandomState(31)
    half = PIER / 2 + PIER_PROUD
    # shaft: square with a worn, slightly irregular chamfer. Rings at these heights:
    levels = [0.0, 0.55, 1.2, SHAFT_TOP]
    ch = [[0.012 + 0.016 * rng.uniform() for _ in levels] for _ in range(4)]
    for k in range(4):              # k = which side; rotate +90 deg each side
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        rot = lambda x, y: (ca * x - sa * y, sa * x + ca * y)
        for j in range(len(levels) - 1):
            z0, z1 = levels[j], levels[j + 1]
            c0r, c1r = ch[k][j], ch[k][j + 1]                  # chamfer at this side's +s end
            c0l, c1l = ch[(k + 3) % 4][j], ch[(k + 3) % 4][j + 1]
            # flat face, seen from outside at y=-half: s runs +x
            s0l, s1l = -half + c0l, -half + c1l
            s0r, s1r = half - c0r, half - c1r
            P = lambda s, z: (*rot(s, -half), z)
            b.face("f%d" % k, [P(s0l, z0), P(s0r, z0), P(s1r, z1), P(s1l, z1)],
                   [band_a(s0l / 4, z0), band_a(s0r / 4, z0), band_a(s1r / 4, z1), band_a(s1l / 4, z1)], False)
            # chamfer towards the next side
            Q0 = lambda c, z: (*rot(half, -c), z)
            Q = (P(s0r, z0), (*rot(half, -half + c0r), z0), (*rot(half, -half + c1r), z1), P(s1r, z1))
            b.face("c%d" % k, list(Q), [band_a(s0r / 4, z0), band_a((s0r + c0r * 1.4) / 4, z0),
                                        band_a((s1r + c1r * 1.4) / 4, z1), band_a(s1r / 4, z1)], True)
    # capital: chamfered bed, then block up to 2.2, slightly rounded lower arris
    cap = CAPITAL / 2
    prof = [(0.0, SHAFT_TOP), (0.012, SHAFT_TOP + 0.006), (cap - PIER / 2 - 0.018, SHAFT_TOP + 0.075),
            (cap - PIER / 2 - 0.004, SHAFT_TOP + 0.095), (cap - PIER / 2, SHAFT_TOP + 0.115),
            (cap - PIER / 2, SPRING - 0.012), (cap - PIER / 2 - 0.008, SPRING)]
    cz0 = CAP_COURSE[0] + 0.015
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        rot = lambda x, y: (ca * x - sa * y, sa * x + ca * y)
        rows, uvs = [], []
        dist = 0.0
        for j, (o, z) in enumerate(prof):
            if j:
                dist += math.hypot(o - prof[j - 1][0], z - prof[j - 1][1])
            w = half + o
            rows.append([(*rot(-w, -w), z), (*rot(w, -w), z)])
            uvs.append([band_a(-w / 4 + 0.27 * k, cz0 + dist), band_a(w / 4 + 0.27 * k, cz0 + dist)])
        b.grid("cap%d" % k, rows, uvs, smooth=True)
    ob = b.to_object("pier", mat)
    h = PIER / 2
    collision(ob, [((-h, -h, 0), (h, h, SHAFT_TOP)), ((-cap, -cap, SHAFT_TOP), (cap, cap, SPRING))])
    return ob


def build_arch(mat):
    b = Builder()
    n = 40
    # cross-section across the depth: (d, dr). d = signed distance from the arch mid-plane, folded onto band B. dr >= 0.
    t = WALL_T / 2
    sect = [(0.28, 0.008), (0.262, 0.0), (-0.262, 0.0), (-0.28, 0.008)]
    rim = [(0.30, 0.038), (0.293, 0.022)]  # outer arris, front (+Y); mirrored for the back
    s_total = math.pi * ARCH_R
    mid = 0.5 * (B_V0 + B_V1)
    dv = 1.0 / B_DEPTH * (B_V1 - B_V0)

    def uv(th, d_fold):
        u = 0.5 + (th - math.pi / 2) * ARCH_R / B_LEN
        return (u, mid + d_fold * dv)

    rows, uvs = [], []
    # rows across: face ring (front), arris, soffit, arris, face ring (back)
    across = [("front_out", None)] + [(None, x) for x in rim] + [(None, x) for x in sect] + \
        [(None, (-x[0], x[1])) for x in rim[::-1]] + [("back_out", None)]
    for item in across:
        row, urow = [], []
        for i in range(n + 1):
            th = math.pi * i / n
            c, s = math.cos(th), math.sin(th)
            if item[0]:
                y = t if item[0] == "front_out" else -t
                # flat-topped outer outline, reaches the piece box: x +-2.0, z 3.9
                x = 2.0 * c
                z = min(SPRING + 1.95 * s, CROWN)
                fold = 0.5 * (1 if y > 0 else -1)
                row.append((x, y, z))
                urow.append(uv(th, fold))
            else:
                y, dr = item[1]
                # the worn arris dies out at the crown, staying under the 3.9 top of the piece
                fade = s ** 6
                r = ARCH_R + dr * (1 - fade) + 0.0018 * (dr / 0.038) * fade
                x = r * c
                z = SPRING + r * s
                fold = (y + (dr if abs(y) >= 0.29 else 0.0) * (1 if y > 0 else -1))
                row.append((x, y, z))
                urow.append(uv(th, fold))
        rows.append(row)
        uvs.append(urow)
    # visible part: arris + soffit are smooth together, the flat faces are separate groups
    b.grid("face_f", rows[0:2], uvs[0:2], flip=True, smooth=False)
    b.grid("soffit", rows[1:-1], uvs[1:-1], flip=True, smooth=True)
    b.grid("face_b", rows[-2:], uvs[-2:], flip=True, smooth=False)
    # hidden extrados: closes the shell
    top_f, top_b = rows[0], rows[-1]
    uvf, uvb = uvs[0], uvs[-1]
    b.grid("extrados", [top_b, top_f], [uvb, uvf], flip=True, smooth=False)
    ob = b.to_object("arch", mat)

    # collision: extruded 12-segment intrados up to the flat top, simple trimesh, r = 1.7 exact at the nodes
    seg = 12
    tris = []
    ring = [(R_ARCH * math.cos(math.pi * i / seg), SPRING + R_ARCH * math.sin(math.pi * i / seg)) for i in range(seg + 1)]
    outer = [(2.0 * math.cos(math.pi * i / seg) if abs(math.cos(math.pi * i / seg)) > 0.71 else
              R_ARCH * math.cos(math.pi * i / seg), CROWN if i not in (0, seg) else SPRING) for i in range(seg + 1)]
    outer[0], outer[seg] = (2.0, SPRING), (-2.0, SPRING)
    # outline (counter-clockwise seen from +Y is not required for a trimesh, but keep normals outward)
    for i in range(seg):
        a, c = ring[i], ring[i + 1]
        d, e = outer[i], outer[i + 1]
        tris.append([(a[0], -t, a[1]), (a[0], t, a[1]), (c[0], t, c[1]), (c[0], -t, c[1])])    # soffit
        tris.append([(a[0], -t, a[1]), (c[0], -t, c[1]), (e[0], -t, e[1]), (d[0], -t, d[1])])  # face -Y
        tris.append([(a[0], t, a[1]), (d[0], t, d[1]), (e[0], t, e[1]), (c[0], t, c[1])])      # face +Y
        tris.append([(d[0], -t, d[1]), (e[0], -t, e[1]), (e[0], t, e[1]), (d[0], t, d[1])])    # top
    collision(ob, tris=tris)
    return ob


def web_h(a):
    """Superellipse web section: rise above springing at plan offset a from the barrel axis."""
    a = min(abs(a), R_ARCH)
    return WEB_CROWN * max(0.0, 1.0 - (a / R_ARCH) ** WEB_N) ** (1.0 / WEB_N)


def web_arc_table(steps=400):
    xs = [R_ARCH * i / steps for i in range(steps + 1)]
    # sample densely near the springing, where the profile is steep
    xs = [R_ARCH * (1 - (1 - i / steps) ** 3) for i in range(steps + 1)]
    s = [0.0]
    for i in range(steps):
        s.append(s[-1] + math.hypot(xs[i + 1] - xs[i], web_h(xs[i + 1]) - web_h(xs[i])))
    return xs, s


WEB_XS, WEB_S = web_arc_table()
WEB_L = WEB_S[-1]


def web_s(x):
    x = min(abs(x), R_ARCH)
    i = np.searchsorted(WEB_XS, x)
    if i == 0:
        return 0.0
    if i >= len(WEB_XS):
        return WEB_L
    t = (x - WEB_XS[i - 1]) / (WEB_XS[i] - WEB_XS[i - 1] + 1e-12)
    return WEB_S[i - 1] + t * (WEB_S[i] - WEB_S[i - 1])


def web_x_at_s(s):
    i = int(np.searchsorted(WEB_S, s))
    i = min(max(i, 1), len(WEB_S) - 1)
    t = (s - WEB_S[i - 1]) / (WEB_S[i] - WEB_S[i - 1] + 1e-12)
    return WEB_XS[i - 1] + t * (WEB_XS[i] - WEB_XS[i - 1])


def vault_z(x, y, soft=0.17):
    """Ceiling of the union of two barrels, with a soft groin that fades to nothing at springing and crown."""
    a, b = web_h(x), web_h(y)
    hi, lo = max(a, b), min(a, b)
    t = hi / WEB_CROWN
    k = soft * 4 * t * (1 - t)
    g = max(k - (hi - lo), 0.0)
    extra = g * g / (4 * k) if k > 1e-6 else 0.0
    return SPRING + hi + extra


def build_vault(mat):
    b = Builder()
    half_cols = 8
    rows_n = 7
    cs = [web_x_at_s(WEB_L * i / half_cols) / R_ARCH for i in range(half_cols + 1)]
    cs = [-c for c in cs[::-1]] + cs[1:]        # -1 .. 1, densest towards the groins
    ys = [R_ARCH + WEB_TUCK] + [R_ARCH * (1 - j / rows_n) for j in range(rows_n + 1)]
    edge = R_ARCH + WEB_TUCK
    du = 0.5 / WEB_L * 0.985

    def lump(x, y):
        # hand-laid plaster: a few mm of low frequency unevenness, none at the springing or the crown
        t = (vault_z(x, y) - SPRING) / WEB_CROWN
        return 0.009 * 4 * t * (1 - t) * (math.sin(1.7 * x + 0.8 * y + 0.4) * math.cos(2.3 * y - 0.5 * x))

    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        sign = 1 if k in (0, 3) else -1     # alternate so texture mirrors across each groin (see report notes)
        rows, uvs = [], []
        for y in ys:
            row, urow = [], []
            for c in cs:
                xl = c * min(y, R_ARCH)
                px, py = ca * xl - sa * y, sa * xl + ca * y
                z = vault_z(xl, y) + lump(px, py)
                row.append((px, py, z))
                s = web_s(xl) * (1 if xl >= 0 else -1) * sign
                u = 0.5 + s * du
                v = C_V0 + 0.012 + (C_V1 - C_V0 - 0.024) * (1 - y / edge)
                urow.append((u, v))
            rows.append(row)
            uvs.append(urow)
        b.grid("web", rows, uvs, smooth=True)
    ob = b.to_object("vault_bay", mat)
    # coarse collision: same surface at low resolution
    cb = []
    cc = [-1.0, -0.8, -0.45, 0.0, 0.45, 0.8, 1.0]
    yy = [R_ARCH, R_ARCH * 0.55, 0.0]
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        for j in range(len(yy) - 1):
            for i in range(len(cc) - 1):
                q = []
                for y, c in ((yy[j], cc[i]), (yy[j], cc[i + 1]), (yy[j + 1], cc[i + 1]), (yy[j + 1], cc[i])):
                    xl = c * y
                    q.append((ca * xl - sa * y, sa * xl + ca * y, vault_z(xl, y)))
                cb.append(q)
    collision(ob, tris=cb)
    return ob


def rubble_field(x, y, seed):
    """Periodic in 4 m so neighbouring low cells join. >= 0 is guaranteed by the caller's normalisation."""
    tau = 2 * math.pi / CELL
    r = np.random.RandomState(seed)
    v = 0.0
    for f in ((1, 2), (2, 1), (3, 2), (2, 3), (4, 3), (5, 2), (3, 5), (6, 5)):
        ph = r.uniform(0, 6.28, 2)
        amp = 0.11 / (f[0] + f[1]) ** 0.7
        v += amp * math.sin(tau * f[0] * x + ph[0]) * math.sin(tau * f[1] * y + ph[1])
    return v


def build_ceiling(name, underside, seed, mat):
    b = Builder()
    h = CELL / 2
    n = 12
    grid = [[-h + CELL * i / n for i in range(n + 1)] for _ in range(1)][0]
    lows = [[rubble_field(x, y, seed) for x in grid] for y in grid]
    lo = min(min(r) for r in lows)
    d = [[v - lo for v in r] for r in lows]
    rng = np.random.RandomState(seed)
    # underside, split at y=0 because band A is 2 m tall
    for part, (j0, j1) in enumerate(((0, n // 2), (n // 2, n))):
        rows, uvs = [], []
        for j in range(j0, j1 + 1):
            row, urow = [], []
            for i in range(n + 1):
                row.append((grid[i], grid[j], underside + d[j][i]))
                urow.append(band_a(grid[i] / 4 + 0.5 + 0.13 * part, grid[j] + h if part == 0 else grid[j]))
            rows.append(row)
            uvs.append(urow)
        b.grid("under%d" % part, rows, uvs, flip=True, smooth=False)
    # four sides: rough tumbled face, set back from the edge line, up to 3.9
    cols = n
    nz = 5
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        rot = lambda x, y: (ca * x - sa * y, sa * x + ca * y)
        zs = [underside + (CROWN - underside) * (j / nz) for j in range(nz + 1)]
        # keep a row boundary at z = 2 (band A restarts there)
        zc = min(range(1, nz), key=lambda j: abs(zs[j] - 2.0))
        zs[zc] = 2.0
        for part, (j0, j1) in enumerate(((0, zc), (zc, nz))):
            rows, uvs = [], []
            for j in range(j0, j1 + 1):
                row, urow = [], []
                for i in range(cols + 1):
                    s = -h + CELL * i / cols
                    z = zs[j]
                    in_set = 0.0
                    # edge row: follows the underside exactly, so the two surfaces close
                    bottom = 0.0
                    if j == 0:
                        ii = int(round((s + h) / CELL * n))
                        # side k=0 sits at y=-h: take the matching underside edge
                        e = {0: d[0][ii], 1: d[ii][n], 2: d[n][n - ii], 3: d[n - ii][0]}[k]
                        bottom = e
                    else:
                        in_set = 0.05 + 0.07 * abs(math.sin(2.1 * s + 1.3 * z + k)) + 0.03 * math.sin(4.3 * z + 3 * s)
                        in_set *= 1.0 - (abs(s) / h) ** 6     # corners close: neighbouring sides meet at the cell corner
                    px, py = rot(s, -h + in_set)
                    zz = z + bottom if j == 0 else z
                    row.append((px, py, zz))
                    zv = z - 2.0 if part == 1 else z
                    urow.append(band_a(s / 4 + 0.5 + 0.21 * k, zv % 2.0 if part == 0 else zv))
                rows.append(row)
                uvs.append(urow)
            b.grid("side%d_%d" % (k, part), rows, uvs, smooth=False)
    ob = b.to_object(name, mat)
    collision(ob, [((-h, -h, underside), (h, h, CROWN))])
    return ob


# ---------------------------------------------------------------- UV2
def add_uv2(ob):
    me = ob.data
    uv2 = me.uv_layers.new(name="UV2")
    me.uv_layers.active = uv2
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.012, area_weight=1.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.012)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.uv_layers["UVMap"].active_render = True


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imgs = build_textures()
    ashlar = make_material("stone_ashlar", imgs["ashlar_color"], imgs["ashlar_normal"], imgs["ashlar_orm"])
    flr = make_material("stone_floor", imgs["floor_color"], imgs["floor_normal"], imgs["floor_orm"])
    pieces = [build_floor(flr), build_wall(ashlar), build_pier(ashlar), build_arch(ashlar), build_vault(ashlar),
              build_ceiling("ceiling_crouch", CROUCH_Y, 77, ashlar), build_ceiling("ceiling_crawl", CRAWL_Y, 91, ashlar)]
    for ob in pieces:
        add_uv2(ob)
    json.dump({
        "note": "written by build.py; rows count from the top of the image",
        "atlas_size": ATLAS, "band_a_rows": list(A_ROWS), "band_b_rows": list(B_ROWS), "band_c_rows": list(C_ROWS),
    }, open(os.path.join(HERE, "atlas.json"), "w"), indent=1)
    for ob in pieces:
        me = ob.data
        print("piece %-16s tris %5d" % (ob.name, sum(len(p.vertices) - 2 for p in me.polygons)))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved", BLEND)


main()
