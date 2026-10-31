"""crypt_kit generator (T015). Contract: docs/contracts/crypt-kit.md.

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b --factory-startup -P blender/models/crypt_kit/build.py

Re-runnable: wipes the scene, regenerates textures/*.png (seeded) and writes crypt_kit_model.blend + atlas.json.

Blender axes: X along the piece, Y across, Z up. glTF/Godot: (x, y, z) -> (x, z, -y). `wall` and `arch` run along
local X (Godot `_wall_h`); rotate 90 deg about up for edges along Z. All root nodes sit at the origin of the file; each
piece's origin is the contract's logical pivot.

Texture layout. stone_ashlar is a 2048 atlas, stone_floor a 1024 full tile:
  band A  ashlar, 4 m x 2 m at 512 px/m, periodic in U and V: walls, piers, capitals and ceilings. Bed joints line up
          between wall and pier; head joints do not, because the assembler alternates `wall` by 180 degrees and the two
          faces differ by half a tile. The pier stands PIER_PROUD in front of the wall, so that butt joint is covered by
          the pier below the capital, and by the transverse arch above it. Above z=2 the wall restarts at the bottom of the
          band (bed joint) with a U offset, to hide the 2 m repeat. The top course holds two plain 0.85 m stones that the
          capitals map onto (no joint crosses a capital). The low ceilings map each rubble block inside ONE stone of this
          band, magnified, so that no joint crosses a block.
  band B  voussoir strip, not tiled: arch soffit + the arch face ring folded over the arris.
  band C  plaster, not tiled: vault webs.

Height-varying soiling is a COLOR_0 multiplier on stone_ashlar pieces (standard glTF: base colour x vertex colour). It only
varies with height. A piece is one mesh, so anything that varies along a wall repeats per instance; see the task report.
The rubble ceilings use COLOR_0 too: a per-block shade, darkened towards the recesses (painted occlusion).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

FLOOR_MAX_RUN = 1.5  # m, longest straight floor joint
FLOOR_RUN_M = 0.0    # as built, set by rect_field
MORTAR_CM = 0.0      # as built, set by stone_maps
HERE = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(HERE, "textures")
BLEND = os.path.join(HERE, "crypt_kit_model.blend")

# ---------------------------------------------------------------- contract numbers
CELL = 4.0
WALL_T = 0.6
SHAFT_TOP = 1.9
SPRING = 2.2
ARCH_CROWN = 3.9     # soffit crown
TOP = 4.15           # wall top, arch block top, ceiling insert top, vault crown
PIER = 0.6
CAPITAL = 0.75
FLOOR_T = 0.2
R_ARCH = 1.7
CROUCH_Y = 1.3
CRAWL_Y = 0.75

# Tiny offsets inside the +-5 mm tolerance, so that coplanar faces never z-fight.
PIER_PROUD = 0.002    # shaft faces sit 2 mm IN FRONT of the wall faces in their line: alternated walls butt behind the pier
WEB_RISE = TOP - 0.002 - SPRING    # web crown 4.148, under the 4.15 tops it dies into, so no pinhole at the crown
# Vault web section: a true semi-ellipse, half-span WEB_W, rise WEB_RISE. WEB_W is wider than the 1.7 clear span: the web
# springs at 2.2 behind the arch and wall faces (hidden), and enters the room at z = 2.2 + web_h(1.7). That is what keeps
# the arch ring proud all the way down instead of tapering to nothing at the springing.
WEB_W = 1.84

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

CAP_JOINTS = [0.35, 1.20, 1.55, 2.40, 2.90, 3.35]   # top course: 0.35-1.20 and 1.55-2.40 are the capital stones
STONE_LEN = (0.35, 1.10)
CAP_U = (0.775 / 4, 1.975 / 4)
ASHLAR_COURSES = [0.32, 0.24, 0.30, 0.22, 0.33, 0.25, 0.34]  # bottom to top, sum 2.0 (last one: capital course)
STONES = []     # band A stones as (u0, u1, z0, z1) in metres, filled by block_field; the rubble blocks map into these
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


def longest_straight(grid, n):
    """Longest joint on the torus that runs straight along one grid line, in grid cells."""
    best = 0
    for flip in (False, True):
        g = grid.T if flip else grid
        for i in range(n):
            joint = g[:, i] != g[:, (i + 1) % n]
            if joint.all():
                return n
            d = np.concatenate([joint, joint]).astype(int)
            run = 0
            for v in d:
                run = run + 1 if v else 0
                best = max(best, run)
    return best


def pack_flags(n, rng, max_run, big=4, small=2):
    """Flags from a Pythagorean tiling on an n x n torus (n = big^2 + small^2 divides out, here 20): it has no long joints by
    construction, unlike any random packing tried. Random splits of the big flags hide the regular lattice; a split is
    kept only if the longest straight joint stays within max_run cells."""
    grid = -np.ones((n, n), dtype=np.int32)
    rects = []
    for m in range(n):
        for k in range(n):
            ox, oy = (m * big - k * small) % n, (m * small + k * big) % n
            if grid[oy, ox] >= 0:
                continue
            for sz, (dx, dy) in ((big, (0, 0)), (small, (big, 0))):
                for x in range(sz):
                    for y in range(sz):
                        grid[(oy + dy + y) % n, (ox + dx + x) % n] = len(rects)
                rects.append([(ox + dx) % n, (oy + dy) % n, sz, sz])
    if (grid < 0).any():
        raise RuntimeError("flag lattice does not fit the torus")
    for ri in rng.permutation(len(rects)):
        i, j, sw, sh = rects[ri]
        if sw != big or sh != big or rng.uniform() > 0.72:
            continue
        cut = int(rng.choice([1, 2, 2, 3]))
        keep = grid.copy()
        along_x = rng.uniform() < 0.5
        new = len(rects)
        for x in range(sw):
            for y in range(sh):
                if (x if along_x else y) >= cut:
                    grid[(j + y) % n, (i + x) % n] = new
        if longest_straight(grid, n) > max_run:
            grid = keep
            continue
        if along_x:
            rects[ri] = [i, j, cut, sh]
            rects.append([(i + cut) % n, j, sw - cut, sh])
        else:
            rects[ri] = [i, j, sw, cut]
            rects.append([i, (j + cut) % n, sw, sh - cut])
    return grid, [tuple(r) for r in rects]


def rect_field(h, w, ppm, seed, n_cells, warp):
    """Random flagging on a torus, packed so that no joint runs straight for more than FLOOR_MAX_RUN metres."""
    rng = np.random.RandomState(seed)
    pu, pv = w / ppm, h / ppm
    global FLOOR_RUN_M
    grid, cells = pack_flags(n_cells, rng, int(FLOOR_MAX_RUN / (pu / n_cells)))
    FLOOR_RUN_M = longest_straight(grid, n_cells) * pu / n_cells

    def lines(period):
        d = rng.uniform(0.92, 1.08, n_cells)
        return np.concatenate([[0.0], np.cumsum(d / d.sum() * period)])

    cx, cy = lines(pu), lines(pv)
    rects = []
    for i, j, sw, sh in cells:
        x1 = cx[i + sw] if i + sw <= n_cells else cx[i + sw - n_cells] + pu
        y1 = cy[j + sh] if j + sh <= n_cells else cy[j + sh - n_cells] + pv
        rects.append((cx[i], cy[j], x1 - cx[i], y1 - cy[j]))
    rects = np.array(rects)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    # phase shift: no grid line may lie on the tile edge, or every wrap would be a joint
    x = np.mod((xx + 0.5) / ppm + 0.17 + noise(h, w, 3.0, seed + 1) * warp, pu)
    y = np.mod((h - 1 - yy + 0.5) / ppm + 0.23 + noise(h, w, 3.0, seed + 2) * warp, pv)
    ci = np.clip(np.searchsorted(cx, x, side="right") - 1, 0, n_cells - 1)
    cj = np.clip(np.searchsorted(cy, y, side="right") - 1, 0, n_cells - 1)
    ids = grid[cj, ci]
    dx = np.mod(x - rects[ids, 0], pu)
    dy = np.mod(y - rects[ids, 1], pv)
    k = 0.004
    dist = -k * np.log(np.exp(-dx / k) + np.exp(-(rects[ids, 2] - dx) / k) + np.exp(-dy / k)
                       + np.exp(-(rects[ids, 3] - dy) / k))
    return ids, np.maximum(dist, 0.0), len(rects)


def block_field(h, w, ppm, courses, seed, len_range, warp=0.012, force=None):
    """Irregular coursed blocks on a torus. Returns stone id, distance to the nearest joint (m), stone count."""
    rng = np.random.RandomState(seed)
    pu, pv = w / ppm, h / ppm
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    yy = (h - 1 - yy + 0.5) / ppm     # metres up from the bottom of the region
    xx = (xx + 0.5) / ppm
    wx = noise(h, w, 3.0, seed + 1) * warp
    wy = noise(h, w, 3.0, seed + 2) * warp
    if force:
        # the wall restarts this band at z=2 with a U offset: the wrap's bed joint must be straight so it meets any U
        wy = wy * sstep(0.0, 0.05, np.minimum(yy, pv - yy))
    x = np.mod(xx + wx, pu)
    y = np.mod(yy + wy, pv)
    edges = np.concatenate([[0.0], np.cumsum(courses)])
    edges[-1] = pv
    ids = np.zeros((h, w), dtype=np.int32)
    dist = np.zeros((h, w))
    next_id = 0
    prev = None
    for c in range(len(courses)):
        m = (y >= edges[c]) & (y < edges[c + 1])
        for attempt in range(4000):
            n_st = rng.randint(int(np.ceil(pu / len_range[1])), int(pu / len_range[0]) + 1)
            ln = rng.uniform(len_range[0], len_range[1], n_st)
            ln *= pu / ln.sum()
            joints = rng.uniform(0, 0.5) + np.concatenate([[0.0], np.cumsum(ln[:-1])])
            if ln.min() < len_range[0] or ln.max() > len_range[1]:
                continue
            if prev is None or len(courses) < 2:
                break
            # broken bond: no head joint sits over the one below
            gap = np.abs(joints[:, None] - prev[None, :])
            if np.minimum(gap, pu - gap).min() >= 0.11:
                break
        if force and c in force:
            joints = force[c]
        joints = np.array(joints)
        prev = joints
        if seed == 1501:
            for a_, b_ in zip(joints, np.concatenate([joints[1:], [joints[0] + pu]])):
                STONES.append((float(a_), float(b_), float(edges[c]), float(edges[c + 1])))
        ext = np.concatenate([joints - pu, joints, joints + pu])
        i = np.searchsorted(ext, x[m]) - 1
        d_head = np.minimum(x[m] - ext[i], ext[i + 1] - x[m])
        d_bed = np.minimum(y[m] - edges[c], edges[c + 1] - y[m])
        k = 0.004
        dist[m] = -k * np.log(np.exp(-d_head / k) + np.exp(-d_bed / k))
        ids[m] = next_id + np.mod(i, len(joints))
        next_id += len(joints)
    return ids, dist, next_id


def stone_maps(h, w, ppm, courses, seed, len_range, palette, joint=0.0045, wear=0.022, relief=0.011, warp=0.012, force=None,
               rect_cells=0):
    """Shared block material. Returns albedo (sRGB 0..1), height (m), roughness, all periodic."""
    if rect_cells:
        ids, d, n = rect_field(h, w, ppm, seed, rect_cells, warp)
    else:
        ids, d, n = block_field(h, w, ppm, courses, seed, len_range, warp, force)
    rng = np.random.RandomState(seed + 7)
    pu, pv = w / ppm, h / ppm

    n_lo = noise(h, w, 3.2, seed + 3)
    n_mid = noise(h, w, 2.2, seed + 4, low=6)
    n_hi = noise(h, w, 1.2, seed + 5, low=40)
    n_edge = noise(h, w, 3.2, seed + 6, low=3)

    jw = joint * (1.0 + 0.5 * n_edge).clip(0.4, 1.8)
    ww = wear * (1.0 + 0.7 * n_lo).clip(0.3, 2.4)
    profile = sstep(0, 1, (d - jw) / ww)
    profile = np.where(d < jw, 0.0, profile)

    tone = rng.uniform(-1, 1, n)
    warm_s = rng.uniform(-1, 1, n)
    if force:                                            # the capital stones are plain: neither pale nor dark, nor orange
        tone[n - len(force[max(force)]):] = 0.2
        warm_s[n - len(force[max(force)]):] = 0.0
    tone = (np.sign(tone) * np.abs(tone) ** 0.8)[ids]    # more stones far from the mean
    # High-pass over about a metre: stones differ from their neighbours, but no dark or pale cluster forms, because a cluster
    # is a landmark that repeats every tile.
    tone = tone - blur(tone, palette.get("tone_hp", 0.0) * ppm) if palette.get("tone_hp") else tone
    # no bright outliers: a lone pale stone is what the eye tracks from tile to tile (the chevron along a wall)
    tone = np.clip(tone / max(tone.std() / 0.60, 1e-6), -1.5, palette.get("tone_top", 0.62))
    warm = warm_s[ids]
    inset = rng.uniform(-1, 1, n)[ids]
    rough_s = rng.uniform(-1, 1, n)[ids]

    # tool marks: integer wave numbers keep them periodic
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    nx = rng.randint(30, 110, n)[ids]
    ny = rng.randint(-70, 70, n)[ids]
    tool = np.sin(2 * np.pi * (nx * xx / w + ny * (yy / h) * max(1, round(pv / pu * 2))) + 2.0 * n_mid)
    tool_on = sstep(-0.3, 0.8, rng.uniform(-1, 1, n)[ids] + 0.5 * n_lo)

    pits = sstep(1.6, 2.8, noise(h, w, 1.4, seed + 8, low=30) + 0.5 * n_mid)
    height = profile * (relief + 0.005 * inset) + 0.004 * sstep(0.0, 0.09, d) + 0.0014 * n_lo * profile + 0.0008 * n_mid * profile + 0.00011 * n_hi * profile \
        + 0.00010 * tool * tool_on * profile - 0.0009 * pits * profile + 0.0002 * n_hi * (1 - profile)

    base = np.array(palette["stone"])
    alb = np.ones((h, w, 3)) * base
    v = 1.0 + palette["tone"] * tone + 0.015 * n_lo + 0.05 * n_mid + 0.02 * n_hi
    # a darker stone is browner, not greyer: the blue channel falls faster with tone
    alb = alb * v[..., None]
    alb[..., 2] *= 1.0 + 0.45 * palette["tone"] * tone
    # weathering inside the stone, and across joints: this carries the mid-scale contrast without a stone-by-stone checker
    patch = blur(noise(h, w, 2.2, seed + 11, low=7), 0.012 * ppm)
    patch = patch / (patch.std() + 1e-9)
    alb *= (1.0 + palette.get("patch", 0.0) * patch)[..., None]
    alb *= (1.0 - palette.get("rim", 0.0) * (1 - sstep(0.0, 0.11, d)))[..., None]
    alb[..., 0] *= 1.0 + palette["warm"] * warm
    alb[..., 2] *= 1.0 - palette["warm"] * 1.8 * warm
    # soiling is soft: blurred noise through a wide ramp, so it has no edge. Variation between stones comes from `tone`.
    n_soft = blur(n_mid, 0.055 * ppm)
    n_soft = n_soft / (n_soft.std() + 1e-9)
    stain = sstep(-1.0, 2.6, n_lo * 0.25 + n_soft * 0.9)
    alb *= (1.0 - palette["stain"] * stain[..., None] * np.array([0.85, 0.95, 1.1]))
    pale = sstep(-0.4, 2.8, -n_lo * 0.25 - n_soft * 0.9) * palette.get("pale_amt", 0.14)
    alb = alb * (1 - pale[..., None]) + np.array(palette["pale"]) * pale[..., None]
    arris = sstep(0.0, 0.6, profile) * (1 - sstep(0.6, 1.0, profile))
    alb *= 1.0 + 0.02 * arris[..., None]
    alb *= 1.0 - 0.13 * pits[..., None]
    alb *= (1.0 + 0.035 * tool * tool_on)[..., None]
    run = streaks(h, w, seed + 9)
    dark_run = sstep(0.7, 2.4, run) * palette.get("runs", 0.0)
    pale_run = sstep(0.7, 2.4, -run) * palette.get("runs", 0.0)
    alb *= 1.0 - 0.34 * dark_run[..., None] * np.array([0.85, 1.0, 1.2])
    alb = alb * (1 - 0.40 * pale_run[..., None]) + np.array(palette["pale"]) * 0.40 * pale_run[..., None]
    fleck = sstep(0.9, 2.2, noise(h, w, 1.7, seed + 10, low=24))
    alb *= 1.0 - 0.06 * fleck[..., None] * np.array([0.8, 1.0, 1.25])
    # mortar follows the local stone value, so a joint reads by its recess and not as a drawn outline
    blur_alb = np.dstack([blur(alb[..., c], 0.05 * ppm) for c in range(3)])
    mort = blur_alb * palette.get("mortar_value", 0.84) * (1.0 + 0.06 * n_mid + 0.05 * n_hi)[..., None]
    if force:
        # ... and its mortar one neutral tone, not the local stone's, so the pair at z=2 looks like any bed joint
        zz = (h - 1 - yy + 0.5) / ppm
        band_edge = (1 - sstep(0.0, 0.03, np.minimum(zz, pv - zz)))[..., None]
        mort = mort * (1 - band_edge) + mort.mean((0, 1)) * band_edge
    mix = sstep(0.0, 0.35, profile)[..., None]
    alb = mort * (1 - mix) + alb * mix
    if seed == 1501:
        # as-built mortar width: area where any mortar shows, over total joint length (beds + heads)
        length = pu * len(courses) + sum(st[3] - st[2] for st in STONES)
        global MORTAR_CM
        MORTAR_CM = float((mix < 0.99).sum()) / ppm ** 2 / length * 100

    worn = profile ** 2 * sstep(-1.0, 1.0, n_lo + 0.5 * n_mid)
    rough = palette["rough"] + 0.05 * rough_s + 0.03 * n_mid - palette["polish"] * worn
    rough = np.where(profile < 0.35, 0.92, rough)
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
    vv = 1.0 - (yy + 0.5) / h                                # 0 hidden edge of the web, WEB_FACE_V at the arch/wall face
    edge_v = 1.0 - sstep(WEB_FACE_V, WEB_FACE_V + 0.28, vv)
    centre_u = np.abs((xx + 0.5) / w - 0.5) * 2              # 0 crown, 1 springing
    low = sstep(0.55, 1.0, centre_u)
    grime = np.clip(0.55 * low + 0.45 * edge_v * low + 0.25 * edge_v, 0, 1)
    blotch = sstep(-0.4, 2.2, n_lo + 0.25 * n_mid)
    crack = 1 - sstep(0.0, 0.035, np.abs(noise(h, w, 3.0, seed + 3)))
    crack = crack * sstep(0.7, 1.6, noise(h, w, 3.2, seed + 4))
    height = 0.0045 * n_lo + 0.0010 * n_mid + 0.00012 * n_hi - 0.0010 * crack
    pal = np.array([0.860, 0.825, 0.745])
    # the blotch is mapped to all four webs of every bay, so at low frequency it is what shows bays repeating: keep it faint
    v = 1.0 + 0.012 * n_lo + 0.024 * n_mid + 0.010 * n_hi
    alb = pal * v[..., None]
    alb *= 1 - 0.07 * blotch[..., None] * np.array([0.9, 1.0, 1.15])
    alb *= 1 - 0.20 * grime[..., None] * np.array([0.8, 1.0, 1.3])
    alb *= 1 - 0.35 * crack[..., None]
    # contact shade where the web dies into the back of the ring: the shadowed step. The lightmap pass may be skipped on
    # mobile, so a little of it is painted
    contact = 1.0 - sstep(WEB_FACE_V, WEB_FACE_V + 0.09, vv)
    alb *= 1 - 0.15 * contact[..., None] * np.array([0.8, 1.0, 1.25])
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
    STONES.clear()
    pal_a = dict(stone=[0.760, 0.640, 0.430], pale=[0.86, 0.79, 0.64], tone=0.225, warm=0.022, patch=0.055, rim=0.13,
                 stain=0.22, rough=0.86, polish=0.04, runs=0.26, tone_hp=0.32)
    # band A
    ppm = 512
    a_alb, a_h, a_r = stone_maps(1024, 2048, ppm, ASHLAR_COURSES, 1501, STONE_LEN, pal_a, warp=0.005, relief=0.009, joint=0.003,
                                 wear=0.008, force={len(ASHLAR_COURSES) - 1: CAP_JOINTS})
    a_n = normal_from_height(a_h, ppm)
    a_ao = ao_from_height(a_h, ppm, 0.012)
    # band B: voussoirs. One course across, irregular joints along the arc. Generated on a square-ish torus in metres.
    bh, bw = B_ROWS[1] - B_ROWS[0], ATLAS
    bppm = ATLAS / B_LEN
    pal_b = dict(pal_a, tone=0.11, warm=0.02, stain=0.20, stone=[0.905, 0.825, 0.645], tone_hp=0, patch=0.04)
    b_alb, b_h, b_r = stone_maps(bh, bw, bppm, [bh / bppm], 1604, (0.17, 0.27), pal_b, joint=0.003, wear=0.008,
                                 relief=0.008, warp=0.005)
    # the soffit carries the limewash of the crypt.jpg arches: paler and lower contrast than the ring on the arch face.
    # Its edge is brushed: it wanders over 0.20-0.35 m from the arch mid-plane, per side, along the arc.
    fold = np.abs(((np.arange(bh) + 0.5) / bh - 0.5) * B_DEPTH)[:, None]
    edge = 0.275 + 0.075 * np.clip(noise(bh, bw, 2.8, 1650, low=2) / 1.5, -1, 1)
    edge = edge + 0.010 * noise(bh, bw, 1.6, 1651, low=20)
    wash = 0.20 * (1 - sstep(-0.025, 0.025, fold - edge))[..., None]
    b_alb = b_alb * (1 - wash) + np.array([0.86, 0.785, 0.625]) * (0.93 + 0.07 * b_alb / b_alb.mean()) * wash
    b_n = normal_from_height(b_h, bppm)
    b_ao = ao_from_height(b_h, bppm, 0.012)
    # band C: plaster
    ch, cw = C_ROWS[1] - C_ROWS[0], ATLAS
    cppm = ATLAS / (2 * WEB_L)
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
    alb = alb * (0.90 + 0.10 * aoc)[..., None]
    imgs = {}
    imgs["ashlar_color"] = to_image("stone_ashlar_color", alb, True)
    imgs["ashlar_normal"] = to_image("stone_ashlar_normal", nrm, False)
    orm = np.dstack([half(aoc), half(rgh), np.zeros((ATLAS // 2, ATLAS // 2))])
    imgs["ashlar_orm"] = to_image("stone_ashlar_orm", orm, False)

    # stone_floor: 4 x 4 m full tile at 256 px/m. Flags on a 20 x 20 grid, no straight joint over FLOOR_MAX_RUN.
    # `tone` stays low and high-passed: the eye reads strong per-flag tone on a regular floor as a checkerboard
    pal_f = dict(stone=[0.70, 0.655, 0.575], pale=[0.76, 0.72, 0.64], tone=0.045, warm=0.02,
                 stain=0.24, rough=0.70, polish=0.20, tone_hp=0.6)
    fppm = 256
    f_alb, f_h, f_r = stone_maps(1024, 1024, fppm, None, 1801, None, pal_f, joint=0.0028, wear=0.024, relief=0.0045,
                                 warp=0.008, rect_cells=20)
    f_ao = ao_from_height(f_h, fppm, 0.010)
    f_alb = f_alb * (0.93 + 0.07 * f_ao)[..., None]
    imgs["floor_color"] = to_image("stone_floor_color", f_alb, True)
    imgs["floor_normal"] = to_image("stone_floor_normal", normal_from_height(f_h, fppm, 0.45), False)
    imgs["floor_orm"] = to_image("stone_floor_orm", np.dstack([f_ao, f_r, np.zeros_like(f_r)]), False)
    return imgs


# ---------------------------------------------------------------- materials
def occlusion_group():
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def make_material(name, color, normal, orm, vcol=False):
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
    if vcol:
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        nt.links.new(tc.outputs["Color"], mx.inputs["A"])
        nt.links.new(ca.outputs["Color"], mx.inputs["B"])
        nt.links.new(mx.outputs["Result"], bsdf.inputs["Base Color"])
    else:
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


def add_box(b, lo, hi):
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


WALL_ROWS = [0.0, 0.35, 0.8, 1.4, 2.0, 2.7, 3.4, 4.0, TOP]     # vertex rows, for the height soiling


def grime(z):
    """stone_ashlar vertex colour: rising damp near the floor, soot under the springing and above. Linear RGB multiplier."""
    t = np.clip(z / 1.1, 0.0, 1.0)
    damp = 1.0 - t * t * (3 - 2 * t)
    u = np.clip((z - 2.2) / 1.6, 0.0, 1.0)
    soot = u * u * (3 - 2 * u)
    return (1.0 - 0.34 * damp - 0.14 * soot, 1.0 - 0.38 * damp - 0.16 * soot, 1.0 - 0.46 * damp - 0.20 * soot)


def add_grime(ob, height=True):
    me = ob.data
    att = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    data = []
    for v in me.vertices:
        c = grime(v.co.z) if height else VCOL.get(ob.name, {}).get(v.index, (1.0, 1.0, 1.0))
        data.extend((c[0], c[1], c[2], 1.0))
    att.data.foreach_set("color", data)
    me.color_attributes.active_color = att
    me.color_attributes.render_color_index = 0


def build_wall(mat):
    b = Builder()
    h, t = CELL / 2, WALL_T / 2
    front = lambda s, z: (s, -t, z)     # faces -Y: s runs +X
    back = lambda s, z: (-s, t, z)      # faces +Y: s runs -X
    end_r = lambda s, z: (h, s, z)
    end_l = lambda s, z: (-h, -s, z)
    spans = [(0.0, 2.0, 0.0), (2.0, 4.0, 0.37), (4.0, TOP, 0.71)]

    def tiled(tag, s0, s1, place, off):
        for k, (z0, z1, o) in enumerate(spans):
            rows = [z for z in WALL_ROWS if z0 <= z <= z1]
            for z_a, z_b in zip(rows[:-1], rows[1:]):
                pts = [place(s0, z_a), place(s1, z_a), place(s1, z_b), place(s0, z_b)]
                za, zb = z_a - z0, z_b - z0
                u0, u1 = s0 / 4 + off + o, s1 / 4 + off + o
                b.face("%s%d" % (tag, k), pts, [band_a(u0, za), band_a(u1, za), band_a(u1, zb), band_a(u0, zb)], False)

    tiled("f", -h, h, front, 0.5)
    tiled("b", -h, h, back, 0.0)        # the two sides of a wall differ, so a corridor does not mirror itself
    tiled("e", -t, t, end_r, 0.0)
    tiled("g", -t, t, end_l, 0.0)
    b.face("top", [(-h, -t, TOP), (h, -t, TOP), (h, t, TOP), (-h, t, TOP)],
           [band_a(0, 0), band_a(1, 0), band_a(1, 0.6), band_a(0, 0.6)], False)
    ob = b.to_object("wall", mat)
    collision(ob, [((-h, -t, 0), (h, t, TOP))])
    return ob


def build_pier(mat):
    b = Builder()
    rng = np.random.RandomState(31)
    half = PIER / 2 + PIER_PROUD
    # shaft: square with a worn, slightly irregular chamfer. Rings at these heights:
    levels = [0.0, 0.35, 0.8, 1.4, SHAFT_TOP]
    ch = [[0.012 + 0.016 * rng.uniform() for _ in levels] for _ in range(4)]
    for k in range(4):              # k = which side; rotate +90 deg each side
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        rot = lambda x, y: (ca * x - sa * y, sa * x + ca * y)
        uo = 0.31 * k + 0.1         # the four faces show different stones
        for j in range(len(levels) - 1):
            z0, z1 = levels[j], levels[j + 1]
            c0r, c1r = ch[k][j], ch[k][j + 1]                  # chamfer at this side's +s end
            c0l, c1l = ch[(k + 3) % 4][j], ch[(k + 3) % 4][j + 1]
            # flat face, seen from outside at y=-half: s runs +x
            s0l, s1l = -half + c0l, -half + c1l
            s0r, s1r = half - c0r, half - c1r
            P = lambda s, z: (*rot(s, -half), z)
            b.face("f%d" % k, [P(s0l, z0), P(s0r, z0), P(s1r, z1), P(s1l, z1)],
                   [band_a(s0l / 4 + uo, z0), band_a(s0r / 4 + uo, z0), band_a(s1r / 4 + uo, z1), band_a(s1l / 4 + uo, z1)],
                   False)
            # chamfer towards the next side
            Q = (P(s0r, z0), (*rot(half, -half + c0r), z0), (*rot(half, -half + c1r), z1), P(s1r, z1))
            b.face("c%d" % k, list(Q), [band_a(s0r / 4 + uo, z0), band_a((s0r + c0r * 1.4) / 4 + uo, z0),
                                        band_a((s1r + c1r * 1.4) / 4 + uo, z1), band_a(s1r / 4 + uo, z1)], True)
    # capital: a square impost in two steps with crisp, flat undersides. Half widths from the axis:
    cap = CAPITAL / 2
    low = 0.345
    prof = [(half - 0.01, SHAFT_TOP), (low - 0.006, SHAFT_TOP), (low, SHAFT_TOP + 0.006), (low, 2.045),
            (cap - 0.008, 2.045), (cap, 2.053), (cap, SPRING - 0.006), (cap - 0.006, SPRING)]
    total = sum(math.hypot(prof[i + 1][0] - prof[i][0], prof[i + 1][1] - prof[i][1]) for i in range(len(prof) - 1))
    fit = min(1.0, (CAP_COURSE[1] - CAP_COURSE[0] - 0.05) / total)
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        rot = lambda x, y: (ca * x - sa * y, sa * x + ca * y)
        rows, uvs = [], []
        dist = 0.0
        for j, (w, z) in enumerate(prof):
            if j:
                dist += math.hypot(w - prof[j - 1][0], z - prof[j - 1][1])
            v = CAP_COURSE[0] + 0.025 + dist * fit
            um = CAP_U[k % 2]
            rows.append([(*rot(-w, -w), z), (*rot(w, -w), z)])
            uvs.append([band_a(um - w / 4, v), band_a(um + w / 4, v)])
        b.grid("cap%d" % k, rows, uvs, smooth=False)
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
    mid = 0.5 * (B_V0 + B_V1)
    dv = 1.0 / B_DEPTH * (B_V1 - B_V0)

    def uv(th, d_fold):
        u = 0.5 + (th - math.pi / 2) * R_ARCH / B_LEN
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
                # flat-topped outer outline, reaches the piece box: x +-2.0, z 4.15. Always above the web section.
                x = 2.0 * c
                z = min(SPRING + 2.1 * s, TOP)
                fold = 0.5 * (1 if y > 0 else -1)
                row.append((x, y, z))
                urow.append(uv(th, fold))
            else:
                y, dr = item[1]
                foot = min(1.0, s / 0.1)        # the worn arris dies out at the springing: no hollow at the pier corner
                r = R_ARCH + dr * foot
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
              R_ARCH * math.cos(math.pi * i / seg), TOP if i not in (0, seg) else SPRING) for i in range(seg + 1)]
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
    """Semi-elliptical web section: rise above springing at plan offset a from the barrel axis."""
    a = min(abs(a), WEB_W)
    return WEB_RISE * math.sqrt(max(0.0, 1.0 - (a / WEB_W) ** 2))


def web_arc_table(steps=400):
    # sample densely near the springing, where the profile is steep
    xs = [WEB_W * (1 - (1 - i / steps) ** 3) for i in range(steps + 1)]
    s = [0.0]
    for i in range(steps):
        s.append(s[-1] + math.hypot(xs[i + 1] - xs[i], web_h(xs[i + 1]) - web_h(xs[i])))
    return xs, s


WEB_XS, WEB_S = web_arc_table()
WEB_L = WEB_S[-1]
WEB_FACE_V = 0.012 + 0.976 * (1 - R_ARCH / WEB_W)      # fraction of band C where a web enters the room


def web_s(x):
    x = min(abs(x), WEB_W)
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


def vault_z(x, y, soft=0.10):
    """Ceiling of the union of two barrels, with a soft groin that fades to nothing at springing and crown."""
    a, b = web_h(x), web_h(y)
    hi, lo = max(a, b), min(a, b)
    t = hi / WEB_RISE
    k = soft * 4 * t * (1 - t)
    g = max(k - (hi - lo), 0.0)
    extra = g * g / (4 * k) if k > 1e-6 else 0.0
    return SPRING + hi + extra


def build_vault(mat):
    b = Builder()
    half_cols = 8
    rows_n = 7
    cs = [web_x_at_s(WEB_L * i / half_cols) / WEB_W for i in range(half_cols + 1)]
    cs = [-c for c in cs[::-1]] + cs[1:]        # -1 .. 1, densest towards the groins
    # first row: hidden flare down to the springing, behind the arch/wall face. Second row: exactly on the face.
    ys = [WEB_W] + [R_ARCH * (1 - j / rows_n) for j in range(rows_n + 1)]
    edge = WEB_W
    du = 0.5 / WEB_L * 0.985

    def lump(x, y):
        # hand-laid plaster: a few mm of low frequency unevenness, none at the springing or the crown
        t = (vault_z(x, y) - SPRING) / WEB_RISE
        return 0.009 * 4 * t * (1 - t) * (math.sin(1.7 * x + 0.8 * y + 0.4) * math.cos(2.3 * y - 0.5 * x))

    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        sign = 1 if k in (0, 3) else -1     # alternate so texture mirrors across each groin (see report notes)
        rows, uvs = [], []
        for y in ys:
            row, urow = [], []
            for c in cs:
                xl = c * y
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
    yy = [WEB_W, R_ARCH * 0.55, 0.0]
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


# ---------------------------------------------------------------- rubble ceilings
def clip_poly(poly, a, b, c):
    """Keep the part of a convex polygon where a*x + b*y <= c."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if fp * fq < 0:
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def voronoi(sites, box, period, stretch):
    """Convex cells of `sites` inside box (x0, y0, x1, y1). period=(px, py), 0 for none. stretch > 1: cells wide in x.
    Periodic images of a site give several pieces of one block. Returns [(block index, offset of the image, polygon)]."""
    x0, y0, x1, y1 = box
    images = [(i * period[0], j * period[1]) for i in ((-1, 0, 1) if period[0] else (0,)) for j in ((-1, 0, 1) if period[1] else (0,))]
    every = [(s[0] + o[0], s[1] + o[1]) for s in sites for o in images]
    out = []
    for bi, s in enumerate(sites):
        for o in images:
            a = (s[0] + o[0], s[1] + o[1])
            poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for q in every:
                if q == a:
                    continue
                # bisector under the metric (dx / stretch, dy): nearer to a than to q
                nx, ny = (q[0] - a[0]) / stretch ** 2, q[1] - a[1]
                mx, my = 0.5 * (a[0] + q[0]), 0.5 * (a[1] + q[1])
                poly = clip_poly(poly, nx, ny, nx * mx + ny * my)
                if len(poly) < 3:
                    break
            if len(poly) >= 3:
                area = 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                                     for i in range(len(poly))))
                if area > 1e-4:
                    out.append((bi, o, poly))
    return out


def jitter_sites(nx, ny, box, rng, amount=0.32):
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    return [(x0 + dx * (i + 0.5 + 0.5 * (j % 2) + rng.uniform(-amount, amount)), y0 + dy * (j + 0.5 + rng.uniform(-amount, amount)))
            for j in range(ny) for i in range(nx)]


def stone_map(poly, rng):
    """Map a polygon inside one band A stone, rotated a little, magnified as little as possible. Returns p -> (u, v)."""
    cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    best = None
    ang = rng.uniform(-0.3, 0.3) + (math.pi if rng.uniform() < 0.5 else 0.0)
    ca, sa = math.cos(ang), math.sin(ang)
    loc = [((p[0] - cx) * ca - (p[1] - cy) * sa, (p[0] - cx) * sa + (p[1] - cy) * ca) for p in poly]
    w, h = 2 * max(abs(q[0]) for q in loc), 2 * max(abs(q[1]) for q in loc)
    rim = 0.035
    for si in rng.permutation(len(STONES))[:14]:
        s = STONES[si]
        sw, sh = s[1] - s[0] - 2 * rim, s[3] - s[2] - 2 * rim
        f = max(w / sw, h / sh, 1.0)
        if best is None or f < best[0]:
            best = (f, s)
    f, s = best
    mu, mv = 0.5 * (s[0] + s[1]), 0.5 * (s[2] + s[3])

    def uv(p):
        lx = (p[0] - cx) * ca - (p[1] - cy) * sa
        ly = (p[0] - cx) * sa + (p[1] - cy) * ca
        return band_a((mu + lx / f) / 4, mv + ly / f)
    return uv, (cx, cy), f


def planar_uv(pts, rng):
    """UVs of a flat-ish 3D polygon, mapped undistorted inside one stone."""
    o = pts[0]
    e1 = [pts[1][i] - o[i] for i in range(3)]
    ln = math.sqrt(sum(a * a for a in e1)) or 1.0
    e1 = [a / ln for a in e1]
    far = max(pts[1:], key=lambda r: sum((r[i] - o[i]) ** 2 for i in range(3)))
    t = sum((far[i] - o[i]) * e1[i] for i in range(3))
    e2 = [far[i] - o[i] - t * e1[i] for i in range(3)]
    ln = math.sqrt(sum(a * a for a in e2)) or 1.0
    e2 = [a / ln for a in e2]
    flat = [(sum((r[i] - o[i]) * e1[i] for i in range(3)), sum((r[i] - o[i]) * e2[i] for i in range(3))) for r in pts]
    uv = stone_map(flat, rng)[0]
    return [uv(f) for f in flat]


def relief_patch(b, name, pieces, n_blocks, depth, place, rng, shade, boundary=None):
    """A broken surface: convex blocks at different depths. `pieces` from voronoi(); depth(bi, o, p) >= 0 is the depth of a
    point of block bi, place(x, y, d) its 3D position. Blocks are fans around a slightly deeper centre (a tumbled, faceted
    face). A shared edge makes one skirt, owned by the nearer block, which is the visible depth step. boundary(...) closes
    edges that have no neighbour. Each block is its own vertex group, so it can carry its own COLOR_0 and stay flat shaded."""
    VCOL.setdefault(name, {})
    edges = {}
    mags = []
    blocks = []
    tone = [rng.uniform(0.72, 1.0) for _ in range(n_blocks)]
    for pi, (bi, o, poly) in enumerate(pieces):
        uv, c, f = stone_map(poly, rng)
        mags.append(f)
        blocks.append((bi, o, poly, uv, c))
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            ka, kb = (round(p[0], 4), round(p[1], 4)), (round(q[0], 4), round(q[1], 4))
            if ka == kb:
                continue
            edges.setdefault(tuple(sorted((ka, kb))), []).append((pi, p, q))
    for pi, (bi, o, poly, uv, c) in enumerate(blocks):
        g = "%s_b%d" % (name, pi)
        n = len(poly)
        cen = place(c[0], c[1], depth(bi, o, c) + 0.022)
        cen_uv = uv(c)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            pts = [cen, place(p[0], p[1], depth(bi, o, p)), place(q[0], q[1], depth(bi, o, q))]
            nrm = _normal(pts)
            test = _normal([place(0, 0, 0), place(1, 0, 0), place(0, 1, 0)])
            if sum(a * t for a, t in zip(nrm, test)) * shade["wind"] < 0:
                b.face(g, [pts[0], pts[2], pts[1]], [cen_uv, uv(q), uv(p)], False)
            else:
                b.face(g, pts, [cen_uv, uv(p), uv(q)], False)
        for k in list(b.index):
            if k[0] == g:
                c_v = tone[bi]
                VCOL[name][b.index[k]] = (c_v, c_v * 0.985, c_v * 0.95)

    for ed in edges.values():
        if len(ed) == 1:
            if boundary:
                pi, p, q = ed[0]
                boundary(blocks[pi], p, q)
            continue
        (pa, p, q), (pb, _, _) = ed[0], ed[1]
        ba, bb = blocks[pa], blocks[pb]
        mid = (0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1]))
        da, db = depth(ba[0], ba[1], mid), depth(bb[0], bb[1], mid)
        if da > db:
            ba, bb = bb, ba
            da, db = db, da
        if db - da < 0.004:
            continue
        pts = [place(p[0], p[1], depth(ba[0], ba[1], p)), place(q[0], q[1], depth(ba[0], ba[1], q)),
               place(q[0], q[1], depth(bb[0], bb[1], q)), place(p[0], p[1], depth(bb[0], bb[1], p))]
        cx, cy = ba[4]
        uvs = planar_uv(pts, rng)
        out = (mid[0] - cx, mid[1] - cy)     # from the block outwards: the skirt must face its lower neighbour
        o0 = place(mid[0], mid[1], da)
        o1 = place(mid[0] + out[0], mid[1] + out[1], da)
        w = (o1[0] - o0[0], o1[1] - o0[1], o1[2] - o0[2])
        nrm = _normal(pts[:3])
        if sum(a * c for a, c in zip(nrm, w)) < 0:
            pts, uvs = pts[::-1], uvs[::-1]
        g = "%s_s%d" % (name, len(b.index))
        b.face(g, pts, uvs, False)
        t = tone[ba[0]]
        # painted occlusion: the skirt darkens into the recess
        near = {tuple(place(p[0], p[1], depth(ba[0], ba[1], p))), tuple(place(q[0], q[1], depth(ba[0], ba[1], q)))}
        for pt in pts:
            c_v = 0.84 * t if tuple(pt) in near else 0.40 * t
            VCOL[name][b.index[(g, round(pt[0], 5), round(pt[1], 5), round(pt[2], 5))]] = (c_v, c_v * 0.97, c_v * 0.90)
    return mags


def _normal(p):
    a = [p[1][i] - p[0][i] for i in range(3)]
    c = [p[-1][i] - p[0][i] for i in range(3)]
    return (a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0])


VCOL = {}


def build_ceiling(name, underside, seed, mat, n_under=(5, 6), n_side=(3, 5)):
    b = Builder()
    h = CELL / 2
    rng = np.random.RandomState(seed)
    # underside: periodic in 4 m, so that neighbouring low cells of one kind join without a step
    box = (-h, -h, h, h)
    sites = jitter_sites(n_under[0], n_under[1], box, rng, 0.44)
    pieces = voronoi(sites, box, (CELL, CELL), 1.3)
    # neighbour table, to keep a visible step between adjacent blocks
    near = {i: set() for i in range(len(sites))}
    seen = {}
    for bi, o, poly in pieces:
        for p in poly:
            key = (round(p[0], 3) % CELL, round(p[1], 3) % CELL)
            for other in seen.setdefault(key, []):
                if other != bi:
                    near[bi].add(other)
                    near[other].add(bi)
            seen[key].append(bi)
    drop = {}
    for i in rng.permutation(len(sites)):
        i = int(i)
        for attempt in range(60):
            d = rng.uniform(0.0, 0.34)
            if all(abs(d - drop[o]) >= 0.075 for o in near[i] if o in drop):
                break
        drop[i] = d
    slope = {i: rng.uniform(-0.05, 0.05, 2) for i in range(len(sites))}

    def under_depth(bi, o, p):
        sx, sy = sites[bi][0] + o[0], sites[bi][1] + o[1]
        return drop[bi] + float(np.clip(slope[bi][0] * (p[0] - sx) + slope[bi][1] * (p[1] - sy), -0.03, 0.03))

    lo = min(under_depth(bi, o, p) for bi, o, poly in pieces for p in poly)
    hi = max(under_depth(bi, o, p) for bi, o, poly in pieces for p in poly) - lo
    z0 = underside + hi + 0.03          # the side walls start here, behind the plates

    def place_u(x, y, d):
        return (x, y, underside + d - lo)

    def plate(blk, p, q):
        """Outer edge of an underside block: a plate on the cell boundary, rising above z0 by a per-block amount. The tops
        of the plates step, so the side wall does not start on one straight line."""
        bi, o, poly, uv, c = blk
        rise = z0 + 0.03 + 0.30 * ((bi * 7919 + seed) % 13) / 12.0
        pts = [place_u(p[0], p[1], under_depth(bi, o, p)), place_u(q[0], q[1], under_depth(bi, o, q)),
               (q[0], q[1], rise), (p[0], p[1], rise)]
        m = (0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1]))
        out = (1.0 if m[0] > h - 1e-6 else -1.0 if m[0] < -h + 1e-6 else 0.0, 1.0 if m[1] > h - 1e-6 else -1.0 if m[1] < -h + 1e-6 else 0.0)
        uvs = planar_uv(pts, rng)
        nrm = _normal(pts[:3])
        if nrm[0] * out[0] + nrm[1] * out[1] < 0:
            pts, uvs = pts[::-1], uvs[::-1]
        g = "%s_p%d" % (name, len(b.index))
        b.face(g, pts, uvs, False)
        t = 0.62 + 0.3 * ((bi * 31 + seed) % 7) / 6.0
        for pt in pts:
            c_v = t * (0.55 if pt[2] >= z0 else 1.0)
            VCOL[name][b.index[(g, round(pt[0], 5), round(pt[1], 5), round(pt[2], 5))]] = (c_v, c_v * 0.97, c_v * 0.91)

    relief_patch(b, name, pieces, len(sites), under_depth, place_u, rng, dict(wind=-1), plate)

    # the four sides: tumbled blocks, wide rather than tall, set back up to 0.27 m. Depth fades to 0 at the cell corners so
    # that neighbouring sides meet
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        box_s = (-h, z0, h, TOP)
        ss = jitter_sites(n_side[0], n_side[1], box_s, rng, 0.46)
        ps = voronoi(ss, box_s, (0, 0), 2.2)
        dr = {i: rng.uniform(0.014, 0.25) for i in range(len(ss))}
        sl = {i: rng.uniform(-0.05, 0.05, 2) for i in range(len(ss))}

        def side_depth(bi, o, p, ss=ss, dr=dr, sl=sl):
            fade = 1.0 - (abs(p[0]) / h) ** 8
            return max(0.0, dr[bi] + float(np.clip(sl[bi][0] * (p[0] - ss[bi][0]) + sl[bi][1] * (p[1] - ss[bi][1]), -0.02, 0.02))) * fade

        def place_s(s, z, d, ca=ca, sa=sa):
            x, y = s, -h + d
            return (ca * x - sa * y, sa * x + ca * y, z)

        relief_patch(b, name, ps, len(ss), side_depth, place_s, rng, dict(wind=1))
    ob = b.to_object(name, mat)
    collision(ob, [((-h, -h, underside), (h, h, TOP))])
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
    ashlar = make_material("stone_ashlar", imgs["ashlar_color"], imgs["ashlar_normal"], imgs["ashlar_orm"], vcol=True)
    flr = make_material("stone_floor", imgs["floor_color"], imgs["floor_normal"], imgs["floor_orm"])
    pieces = [build_floor(flr), build_wall(ashlar), build_pier(ashlar), build_arch(ashlar), build_vault(ashlar),
              build_ceiling("ceiling_crouch", CROUCH_Y, 77, ashlar), build_ceiling("ceiling_crawl", CRAWL_Y, 91, ashlar)]
    for ob in pieces:
        add_uv2(ob)
        if ob.name != "floor":
            add_grime(ob, height=ob.name in ("wall", "pier"))
    json.dump({
        "note": "written by build.py; rows count from the top of the image",
        "atlas_size": ATLAS, "band_a_rows": list(A_ROWS), "band_b_rows": list(B_ROWS), "band_c_rows": list(C_ROWS),
        "band_a_courses_m": ASHLAR_COURSES, "band_a_stone_len_m": [round(min(s[1] - s[0] for s in STONES), 3),
                                                                   round(max(s[1] - s[0] for s in STONES), 3)],
        "floor_longest_straight_joint_m": round(FLOOR_RUN_M, 3), "band_a_mortar_width_cm": round(MORTAR_CM, 2),
    }, open(os.path.join(HERE, "atlas.json"), "w"), indent=1)
    for ob in pieces:
        me = ob.data
        print("piece %-16s tris %5d" % (ob.name, sum(len(p.vertices) - 2 for p in me.polygons)))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved", BLEND)


main()
