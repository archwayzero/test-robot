"""T044 hero cloak stage (decision D18): white mantle + gray cloak, looser hood, budget paid by hidden body faces.

Called by conform.py at the end (on the finished T011 hero, final coordinates: front +Y, feet at z 0), or standalone
for iteration on a saved hero blend:
  blender -b <hero.blend> -P blender/models/hero/cloak.py -- <out.blend>

Coordinates: cylindrical around the vertical axis (0, YC); theta 0 = +X (the hero's left), 90 deg = front (+Y),
270 deg = back. Cloth columns are functions of (theta, z).

Steps:
  1. Classify body vertices: backpack, hood (head shell + chainmail bib / collar), face, inner neck.
  2. Hood loosened: radial push HOOD_NECK at the neck and shoulder fall, HOOD_FACE around the face opening (the face
     itself never moves). The faces joining the hood's lower edge to the torso are deleted (they would stretch through
     the mantle as dark "teeth") and the open lower edge is smoothed along its loop.
  3. Gray cloak: per column a convex drape profile over the body (cloth hangs from the shoulders, straight where it
     spans), flare / train at the back, open at the front; sinusoidal vertical folds (troughs only as deep as the room
     over the body allows). Hem 3 cm above the floor.
  4. White mantle over it: the neckline is raised under the hood so the shoulder line falls >= SHOULDER_DEG to the
     outer arm (no shelf); sinusoidal vertical folds that start at the shoulder line and deepen to the hem; zigzag hem,
     about knee height at the front centre, long tails at the front / back sides, raised over the forearms.
  5. Hood lifted over the mantle where it rests on it; torso faces that still cut the cloth at the neck are deleted
     (they are inside the cloth).
  6. Backpack straps: ribbons projected onto the mantle / bib, STRAP_LIFT over the surface.
  7. Cloth inside the backpack removed where it can not show.
  8. Budget: body faces always covered by the cloth are deleted; then limited dissolve of the Tripo torso.
  9. One material `hero_cloak` (1024x512 albedo: mantle left half, cloak right half), roughness 0.9, double-sided.
     Vertex groups `cloak_mantle`, `cloak_gray`; face attribute lm_part 20 (mantle) / 21 (cloak) / 22 (straps).
"""
import math
import os
import sys
from collections import defaultdict

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
TRI_MAX = 19990               # whole hero (budget 20,000)
YC = 0.07                     # cloth axis y (torso centre)
YH = 0.075                    # head axis y
DT_DEG, DZ = 2.0, 0.005
NT, NZ = int(360 / DT_DEG), 321       # z 0 .. 1.60
WEDGE_BINS = 2                         # +-4 deg

# hood
HOOD_NECK = 0.036                      # radial push at the neck / shoulder fall (z <= 1.47)
HOOD_FACE = 0.017                      # radial push around the face opening (z >= 1.58)
# cloak (gray)
C_COLS, C_ROWS = 37, 18                # 9 folds x 4 columns + 1; rows denser towards the floor
C_ROW_POW = 0.8
C_OFF = 0.012                          # clearance over the body
C_TUCK = 0.020                         # neckline tucked this far up under the hood's lower edge
C_EDGE_DEG = -18.0                     # cloak front edge (deg from +X; mirrored), behind the arms
C_EDGE_FWD_DEG = 18.0                  # the edges swing this far forward at the floor
C_HEM = 0.030                          # lowest hem point above the floor
C_FOLD = 0.045                         # fold crest height at the hem
C_FLARE, C_TRAIN = 0.05, 0.09          # extra radius at the floor (all round / at the back)
# mantle (white)
M_COLS, M_ROWS = 61, 14                # 15 folds x 4 columns + the closing column; rows denser at the shoulders
M_ROW_POW = 1.2
M_GAP = 0.010                          # over the cloak
M_OFF = 0.016                          # over the body where there is no cloak
M_FOLD_Z = ([0.20, 0.55, 0.90, 1.20, 1.36, 1.47], [0.078, 0.075, 0.062, 0.045, 0.020, 0.0])   # crest height by z
M_FOLD_HEM = 0.068                     # at least this at the hem
M_FOLD_IN = 0.75                       # trough depth / crest height (limited by the room over body / cloak)
M_ZIG = 0.07                           # zigzag hem depth
M_OPEN_HEM_DEG = 10.0                  # half opening at the hem; the front edges part below M_OPEN_Z
M_OPEN_Z = 1.22
SH_Z0, SH_X0 = 1.495, 0.13           # outline point at the hood edge for the pressed shoulders
SHOULDER_DEG = 34.0                    # the neckline is raised until neck -> shoulder corner falls this steeply
START_ZMAX = 1.505                     # ... but not higher than this (inside the loosened hood)
LIFT_MAX = 0.06                        # hood lift over the mantle neckline (cap)
LIFT_CLEAR = 0.008                     # hood clearance over the mantle
FOREARM_X, FOREARM_TOP = 0.185, 1.10   # |x| beyond this and below this: forearm / hand (kept free)
RAY_DOWN = 0.30                        # hidden-face test ignores rays steeper than this downwards (sin)
COVER_DIST = 0.10                      # hidden-face test: cloth within this distance along the face normal
STRAP_X, STRAP_W, STRAP_LIFT, STRAP_STEP = 0.185, 0.034, 0.002, 0.012
STRAP_X_TOP = 0.205                    # over the shoulder top, clear of the hood's shoulder fall
STRAP_X_PACK = 0.155                   # the ribbons end on the backpack's top corners
STRAP_SRC = (0.143, 0.079, 1.30)       # a point on the original strap (its UVs texture the ribbon)
MAT = "hero_cloak"
COL_MANTLE = (215, 210, 198)
COL_CLOAK = (105, 105, 108)
COL_TRIM = (150, 147, 140)


def log(*a):
    print("[cloak]", *a, flush=True)


def sstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ang(x, y):
    return np.mod(np.arctan2(y - YC, x), 2 * np.pi)


def bib_bottom(ax):
    """z of the hood's chainmail bib lower edge at the front, by |x|"""
    return np.interp(ax, [0.0, 0.05, 0.08, 0.10, 0.12, 0.135], [1.255, 1.275, 1.305, 1.335, 1.385, 1.43])


# ----------------------------------------------------------------------------------------------- classification
def classify(V, mat_v):
    x, y, z = V.T
    pack = (mat_v == 0) & (y < -0.05) & (z > 0.99) & (z < 1.46) & (np.abs(x) < 0.17)
    rh = np.hypot(x, y - YH)
    head = (mat_v == 0) & (z > 1.45) & (np.abs(x) < 0.10)
    face = head & (np.abs(x) < 0.062) & (y > 0.095) & (z < 1.73)
    inner = head & (rh < 0.058) & (z < 1.56)              # neck under the hood
    # cowl = the chainmail bib / collar of the hood (measured on ortho renders with height rings): at the front a
    # U-shaped bib, bottom 1.26 at the centre, 1.33 at |x| 0.10, 1.43 at 0.13; at the back the collar ends at 1.435
    r = np.hypot(x, y - YC)
    cb = np.where(y > YC - 0.01, bib_bottom(np.abs(x)), 1.435)
    cowl = (mat_v == 0) & ~pack & (z > cb) & (z <= 1.47) & (np.abs(x) < 0.145) & (r < 0.17)
    hood = (head & ~face & ~inner) | cowl
    return {"pack": pack, "hood": hood, "face": face, "inner": inner, "cowl_bottom": cb}


# ----------------------------------------------------------------------------------------------- hood
def loosen_hood(V0, C, mat_v, polys):
    """Radial push of the hood (neck / shoulder fall HOOD_NECK, face opening HOOD_FACE), the faces joining the hood
    to the torso (to be deleted), and the open lower edge smoothed along its loop. Returns V, mixed faces, stats."""
    V = V0.copy()
    hood = C["hood"]
    idx = np.nonzero(hood)[0]
    hv = V0[idx]
    z = hv[:, 2]
    ax_y = np.where(z > 1.47, YH, YC)
    dv = np.stack([hv[:, 0], hv[:, 1] - ax_y, np.zeros(len(hv))], 1)
    rr = np.linalg.norm(dv, axis=1)
    dv /= np.maximum(rr, 1e-6)[:, None]
    L = HOOD_FACE + (HOOD_NECK - HOOD_FACE) * sstep(1.58, 1.47, z)
    phi = np.degrees(np.arctan2(np.abs(hv[:, 0]), hv[:, 1] - YH))        # 0 = straight ahead from the head axis
    g = np.where((z > 1.49) & (z < 1.745), sstep(38.0, 52.0, phi), 1.0)  # the face (front) stays
    L = L * g * sstep(0.0, 0.05, rr)                                    # no hole at the crown
    V[idx] += dv * L[:, None]
    # face opening rim: hood vertices sharing a face with face vertices
    face_v = C["face"]
    rim = set()
    for p in polys:
        pl = list(p)
        if face_v[pl].any():
            rim.update(i for i in pl if hood[i])
    push = dict(zip(idx.tolist(), L.tolist()))
    rim_push = np.array([push[i] for i in rim]) if rim else np.zeros(1)
    # faces hood + torso -> deleted; their hood edges become the open lower edge
    torso = (mat_v == 0) & ~hood & ~C["face"] & ~C["inner"] & ~C["pack"]
    mixed = [fi for fi, p in enumerate(polys) if hood[list(p)].any() and torso[list(p)].any()]
    mixed_set = set(mixed)
    ef = defaultdict(list)
    for fi, p in enumerate(polys):
        for a, b in zip(p, p[1:] + p[:1]):
            ef[(min(a, b), max(a, b))].append(fi)
    bnb = defaultdict(set)
    for (a, b), fs in ef.items():
        if hood[a] and hood[b] and any(f in mixed_set for f in fs) and \
                any(f not in mixed_set and hood[list(polys[f])].all() for f in fs):
            bnb[a].add(b)
            bnb[b].add(a)
    loop = [v for v, n in bnb.items() if len(n) == 2]
    before = V[loop].copy()
    for _ in range(12):
        new = {}
        for v in loop:
            a, b = tuple(bnb[v])
            new[v] = 0.5 * V[v] + 0.25 * (V[a] + V[b])
        for v, p in new.items():
            V[v] = p
    moved = np.linalg.norm(V[loop] - before, axis=1) if loop else np.zeros(1)
    stats = {"max": float(L.max()), "neck_min": float(L[z < 1.47].min()) if (z < 1.47).any() else 0.0,
             "rim_min": float(rim_push.min()), "rim_median": float(np.median(rim_push)), "rim_n": len(rim),
             "mixed_faces": len(mixed), "edge_loop_verts": len(loop), "edge_smooth_max": float(moved.max())}
    return V, mixed, stats


# ----------------------------------------------------------------------------------------------- envelope
def envelope(P):
    """E[k, i]: max radius of points P (n,3) in theta bin k (+- WEDGE_BINS) and z bin i (+-2)."""
    E = np.zeros((NT, NZ))
    th = ang(P[:, 0], P[:, 1])
    r = np.hypot(P[:, 0], P[:, 1] - YC)
    k0 = np.round(th / math.radians(DT_DEG)).astype(int)
    i0 = np.round(P[:, 2] / DZ).astype(int)
    for dk in range(-WEDGE_BINS, WEDGE_BINS + 1):
        for di in (-2, -1, 0, 1, 2):
            k = (k0 + dk) % NT
            i = np.clip(i0 + di, 0, NZ - 1)
            np.maximum.at(E, (k, i), r)
    return E


def env_at(E, TH, Z):
    k = np.round(np.mod(TH, 2 * np.pi) / math.radians(DT_DEG)).astype(int) % NT
    i = np.clip(np.round(Z / DZ).astype(int), 0, NZ - 1)
    return E[k, i]


def upsample(grid, f=4):
    """denser point sampling of a (cols, rows, 3) grid (bilinear), for envelopes"""
    nc, nr = grid.shape[:2]
    a = np.linspace(0, nc - 1, (nc - 1) * f + 1)
    b = np.linspace(0, nr - 1, (nr - 1) * f + 1)
    j0 = np.minimum(np.floor(a).astype(int), nc - 2)
    i0 = np.minimum(np.floor(b).astype(int), nr - 2)
    ta = (a - j0)[:, None, None]
    tb = (b - i0)[None, :, None]
    g00 = grid[j0][:, i0]
    g10 = grid[j0 + 1][:, i0]
    g01 = grid[j0][:, i0 + 1]
    g11 = grid[j0 + 1][:, i0 + 1]
    return ((1 - ta) * (1 - tb) * g00 + ta * (1 - tb) * g10 + (1 - ta) * tb * g01 + ta * tb * g11).reshape(-1, 3)


# ----------------------------------------------------------------------------------------------- cloth grids
def tri_wave(u):
    return 1.0 - np.abs(2.0 * np.mod(u, 1.0) - 1.0)


def convex_hull(pts):
    """Andrew's monotone chain, CCW, starting at the lowest-leftmost point."""
    P = sorted(set(pts))
    if len(P) < 3:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(P):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


DIL = [(1.0, 0.0), (0.92, 0.38), (0.7, 0.7), (0.38, 0.92), (0.0, 1.0)]


def hull_profile(groups, theta, S, z_hem, wedge=math.radians(4), sweep=0.0):
    """Draped profile (r, z) polyline of one column: from the neckline point S over everything outside it (convex:
    the cloth spans shoulders / pauldrons, then falls vertically from the outermost point) down to z_hem.
    groups: [((th, r, z) arrays, offset)] - every point is dilated by its offset (quarter disc, outwards / up)."""
    rs, zs = [], []
    lo, hi = min(0.0, sweep) - wedge, max(0.0, sweep) + wedge       # the column swings by `sweep` near the floor
    r_at_s = 0.0
    for (th, r, z), off in groups:
        dth = ((th - theta) + np.pi) % (2 * np.pi) - np.pi
        dd = (dth > lo) & (dth < hi)
        near = dd & (np.abs(z - S[1]) < 0.015) & (r < S[0] + 0.02)      # the surface right at the start point
        if near.any():
            r_at_s = max(r_at_s, float(r[near].max()) + off)
        sel = dd & (r + off >= S[0]) & (z >= z_hem - 0.05)
        for cr, sz in DIL:
            rs.append(r[sel] + off * cr)
            zs.append(z[sel] + off * sz)
    rs = np.concatenate(rs)
    zs = np.concatenate(zs)
    S = (max(S[0], r_at_s), S[1])            # never start inside the body
    sel = rs > S[0]
    rs, zs = rs[sel], zs[sel]
    s0 = (S[0] - 0.002, S[1])
    rfall = max(float(rs.max()) if len(rs) else S[0], S[0])
    low = z_hem - 0.06
    pts = list(zip(rs.round(5).tolist(), zs.round(5).tolist())) + [s0, (rfall, low), (s0[0], low)]
    hull = convex_hull(pts)
    i = hull.index(s0)
    path = []
    for k in range(len(hull)):
        p = hull[(i - k) % len(hull)]
        if path and p[1] < z_hem:
            q = path[-1]
            t = (q[1] - z_hem) / (q[1] - p[1])
            path.append((q[0] + (p[0] - q[0]) * t, z_hem))
            break
        path.append(p)
    return np.array(path)


def shoulder_corner(prof, fall_deg=55.0):
    """first profile vertex after which the cloth falls steeper than fall_deg (the shoulder / chest corner)"""
    for k in range(1, len(prof)):
        dr, dz = prof[k] - prof[k - 1]
        if dr <= 1e-4 or math.degrees(math.atan2(-dz, dr)) > fall_deg:
            return prof[k - 1]
    return prof[-1]


def build_layer(thetas, starts, hems, groups, nrows, extra, row_pow=1.0):
    """Base (unfolded) layer: R, TH, Z, S arrays (cols, nrows+1); rows at arclength fractions s = t^row_pow of each
    column profile. extra(j, z) -> (radius added, rotation about the axis)."""
    ncol = len(thetas)
    R, TH, Z, S = (np.zeros((ncol, nrows + 1)) for _ in range(4))
    s_t = np.linspace(0, 1, nrows + 1) ** row_pow
    for j in range(ncol):
        prof = hull_profile(groups, thetas[j], starts[j], hems[j], sweep=float(extra(j, np.zeros(1))[1][0]))
        seg = np.linalg.norm(np.diff(prof, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        r = np.interp(s_t * cum[-1], cum, prof[:, 0])
        z = np.interp(s_t * cum[-1], cum, prof[:, 1])
        dr, dth = extra(j, z)
        R[j], TH[j], Z[j], S[j] = r + dr, thetas[j] + dth, z, s_t
    return R, TH, Z, S


def to_xyz(R, TH, Z):
    return np.stack([R * np.cos(TH), YC + R * np.sin(TH), Z], -1)


def folds(R, u, A, room, k_in):
    """sinusoidal vertical folds: crest +A (outward), trough -k_in*A but never deeper than `room`"""
    c = -np.cos(2 * np.pi * u)[:, None] * np.ones_like(R)
    d = np.where(c > 0, A * c, np.maximum(A * c * k_in, -room))
    return R + d, d, c


# ----------------------------------------------------------------------------------------------- texture / material
def make_texture(path):
    W, H = 1024, 512
    rng = np.random.default_rng(18)
    u = np.arange(W)[None, :] / W
    v = np.arange(H)[:, None] / H
    grain = rng.normal(0, 1, (H, W))
    for _ in range(2):        # soft weave grain
        grain = 0.25 * (np.roll(grain, 1, 0) + np.roll(grain, -1, 0) + np.roll(grain, 1, 1) + np.roll(grain, -1, 1))
    streak = (0.6 * np.sin(2 * np.pi * (u * 9 + 0.13)) + 0.4 * np.sin(2 * np.pi * (u * 17 + 0.4))) * np.ones_like(v)
    mottle = np.sin(2 * np.pi * (u * 3.0 + v * 1.7)) * np.sin(2 * np.pi * (v * 2.3 + 0.2))
    var = 0.012 * grain / max(1e-6, grain.std()) + 0.008 * streak + 0.025 * mottle
    img = np.zeros((H, W, 4))
    left = u < 0.5
    base = np.where(left[..., None], np.array(COL_MANTLE)[None, None, :] / 255.0,
                    np.array(COL_CLOAK)[None, None, :] / 255.0) * np.ones((H, W, 3))
    trim = (~left) & (v < 0.035) & (v > 0.006)       # lighter band at the cloak hem
    base[np.broadcast_to(trim, (H, W))] = np.array(COL_TRIM) / 255.0
    img[..., :3] = np.clip(base * (1.0 + var[..., None]), 0, 1)
    img[..., 3] = 1.0
    im = bpy.data.images.new("hero_cloak_basecolor", W, H, alpha=False)
    im.colorspace_settings.name = "sRGB"
    im.pixels.foreach_set(img.astype(np.float32).ravel())   # row 0 = v 0 (bottom)
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    log("texture", path, W, "x", H, "mean sRGB mantle",
        tuple(int(c) for c in np.round(img[:, :W // 2, :3].reshape(-1, 3).mean(0) * 255)), "cloak",
        tuple(int(c) for c in np.round(img[int(0.05 * H):, W // 2:, :3].reshape(-1, 3).mean(0) * 255)))


def make_material(path):
    mat = bpy.data.materials.get(MAT) or bpy.data.materials.new(MAT)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    nt.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.use_backface_culling = False          # glTF doubleSided
    try:
        mat.surface_render_method = "DITHERED"
    except AttributeError:
        pass
    return mat


# ----------------------------------------------------------------------------------------------- main stage
def apply(obj):
    me = obj.data
    nv0 = len(me.vertices)
    tris0 = sum(len(p.vertices) - 2 for p in me.polygons)
    V0 = np.array([v.co[:] for v in me.vertices])
    mat_v = np.zeros(nv0, int)
    for p in me.polygons:
        if p.material_index == 1:
            mat_v[list(p.vertices)] = 1
    polys = [tuple(p.vertices) for p in me.polygons]
    C = classify(V0, mat_v)
    log("classified: pack", int(C["pack"].sum()), "hood", int(C["hood"].sum()), "face", int(C["face"].sum()),
        "inner neck", int(C["inner"].sum()))

    # ---- hood: loosened, lower edge freed from the torso and smoothed
    V, mixed, hs = loosen_hood(V0, C, mat_v, polys)
    log("hood: loosened max", round(hs["max"], 4), "| neck/shoulder fall (z<1.47) min", round(hs["neck_min"], 4),
        "| face-opening rim min", round(hs["rim_min"], 4), "median", round(hs["rim_median"], 4), "n", hs["rim_n"],
        "| hood-torso faces deleted", hs["mixed_faces"], "lower edge loop", hs["edge_loop_verts"], "verts, smoothed max",
        round(hs["edge_smooth_max"], 4))

    # ---- shoulder tops pressed under the outline z_allow(|x|) (falls SHOULDER_DEG from the neck): they are always
    # under the mantle; without this the cloth would make a horizontal shelf over the square Tripo shoulders
    sh = (mat_v == 0) & ~C["pack"] & ~C["hood"] & ~C["face"] & ~C["inner"] & (V0[:, 2] > 1.25) & \
        (np.abs(V0[:, 0]) > 0.09)
    ax = np.abs(V0[:, 0])
    z_allow = SH_Z0 - math.tan(math.radians(SHOULDER_DEG)) * (ax - SH_X0) - M_OFF - 0.004
    dz = np.where(sh, np.minimum(0.0, z_allow - V0[:, 2]) * sstep(0.09, 0.11, ax), 0.0)
    V0 = V0.copy()
    V0[:, 2] += dz
    V[:, 2] += dz
    n_sh = int((dz < -1e-4).sum())
    log("shoulder tops pressed down:", n_sh, "verts, max", round(float(-dz.min()), 4), "m")
    # ---- drape points: body + legs + arms (backpack, hood, face, inner neck excluded)
    use = ~C["pack"] & ~C["hood"] & ~C["face"] & ~C["inner"] & (V0[:, 2] < 1.52)
    BP = V0[use]
    body_pts = (ang(BP[:, 0], BP[:, 1]), np.hypot(BP[:, 0], BP[:, 1] - YC), BP[:, 2])
    E_body = envelope(BP)
    cowl = C["hood"] & (V0[:, 2] < 1.47)
    cowl_pts = (ang(V[cowl, 0], V[cowl, 1]), np.hypot(V[cowl, 0], V[cowl, 1] - YC), V[cowl, 2])

    def neck_edge(thetas):
        """(r, z) of the (loosened) hood's bib / collar bottom edge per column angle (median r of its lowest 2 cm)."""
        out = np.full((len(thetas), 2), np.nan)
        for j, th in enumerate(thetas):
            dd = np.abs(((cowl_pts[0] - th) + np.pi) % (2 * np.pi) - np.pi) < math.radians(6)
            if dd.sum() >= 3:
                zmin = cowl_pts[2][dd].min()
                band = dd & (cowl_pts[2] < zmin + 0.02)
                out[j] = (np.median(cowl_pts[1][band]), zmin)
        for c in range(2):          # fill gaps from the neighbours (periodic)
            ok = ~np.isnan(out[:, c])
            idx = np.arange(len(thetas))
            out[~ok, c] = np.interp(idx[~ok], idx[ok], out[ok, c], period=len(thetas))
        return out

    # ---- gray cloak: columns behind the arms, around the back; edges come forward a little at the floor
    c_th = np.radians(C_EDGE_DEG) - np.arange(C_COLS) / (C_COLS - 1) * np.radians(180 - 2 * C_EDGE_DEG)
    c_neck = neck_edge(c_th)
    c_start = np.stack([c_neck[:, 0] - HOOD_NECK + 0.008, c_neck[:, 1] + C_TUCK], 1)
    c_u = np.arange(C_COLS) / 4.0
    c_back = np.clip(-np.sin(c_th), 0, 1)
    c_amp = C_FOLD * (1 + 0.5 * c_back)
    c_amp[[0, -1]] *= 0.5
    c_hem = C_HEM + 0.012 * tri_wave(c_u + 0.5)                # lowest under the fold crests
    c_swing = (1 - 2 * np.arange(C_COLS) / (C_COLS - 1)) * np.radians(C_EDGE_FWD_DEG)

    def c_extra(j, z):
        """flare / train radius and the forward swing of the edges near the floor"""
        k = sstep(0.75, 0.0, z)
        return (C_FLARE + C_TRAIN * c_back[j] ** 1.5) * k, c_swing[j] * sstep(0.7, 0.0, z)
    cR, cTH, cZ, cS = build_layer(c_th, c_start, c_hem, [(body_pts, C_OFF)], C_ROWS, c_extra, C_ROW_POW)
    cA = c_amp[:, None] * sstep(0.10, 1.0, cS)
    c_room = np.maximum(0.0, cR - (env_at(E_body, cTH, cZ) + C_OFF))
    cR, cD, _ = folds(cR, c_u, cA, c_room, 0.8)
    cloak = to_xyz(cR, cTH, cZ)
    # the cloak's shoulder tops pressed under the mantle's falling shoulder line as well (it is hidden there)
    cax = np.abs(cloak[..., 0])
    c_allow = SH_Z0 - math.tan(math.radians(SHOULDER_DEG)) * (cax - SH_X0) - M_GAP - 0.004
    cloak[..., 2] += np.minimum(0.0, c_allow - cloak[..., 2]) * sstep(0.09, 0.11, cax)

    # ---- white mantle: all round (front welded above M_OPEN_Z), over the cloak (+ gap)
    m_th = np.pi / 2 - np.arange(M_COLS) / (M_COLS - 1) * 2 * np.pi
    m_neck = neck_edge(m_th)
    m_start = np.stack([m_neck[:, 0] - HOOD_NECK + 0.014, m_neck[:, 1] + C_TUCK + 0.006], 1)
    dfront = np.abs(((np.degrees(m_th) - 90 + 180) % 360) - 180)
    # hem: front centre about knee height, long tails at the front and back sides, the arm span raised (arm_min)
    hem_design = np.interp(dfront, [0, 10, 22, 35, 50, 62, 75, 105, 118, 130, 145, 162, 180],
                           [0.56, 0.54, 0.46, 0.36, 0.31, 0.36, 0.9, 0.9, 0.36, 0.30, 0.32, 0.42, 0.50])
    fa = use & (np.abs(V0[:, 0]) > FOREARM_X) & (V0[:, 2] < FOREARM_TOP)
    fa_th = ang(V0[fa, 0], V0[fa, 1])
    arm_min = np.zeros(M_COLS)
    for j in range(M_COLS):
        dd = np.abs(((fa_th - m_th[j]) + np.pi) % (2 * np.pi) - np.pi) < math.radians(16)
        if dd.any():
            arm_min[j] = V0[fa, 2][dd].max() + 0.035
    m_hem = np.maximum(hem_design, arm_min)
    for _ in range(3):
        m_hem = np.maximum(0.25 * np.roll(m_hem, 1) + 0.5 * m_hem + 0.25 * np.roll(m_hem, -1), arm_min)
    m_hem[-1] = m_hem[0]
    m_u = np.arange(M_COLS) / 4.0
    m_hem = np.maximum(m_hem - M_ZIG * tri_wave(m_u) * sstep(1.0, 0.8, m_hem), arm_min)   # zigzag, lower at crests
    m_swing = (2 * np.arange(M_COLS) / (M_COLS - 1) - 1) * np.radians(M_OPEN_HEM_DEG)
    cl = upsample(cloak)
    cloak_pts = (ang(cl[:, 0], cl[:, 1]), np.hypot(cl[:, 0], cl[:, 1] - YC), cl[:, 2])
    E_cloak = envelope(cl)

    def m_extra(j, z):
        return 0.0, m_swing[j] * sstep(M_OPEN_Z, 0.55, z)
    groups = [(body_pts, M_OFF), (cloak_pts, M_GAP)]
    # shoulders: raise the neckline (tucked inside the loosened hood shell) until neck -> shoulder corner falls
    # >= SHOULDER_DEG; the hood is then lifted onto the mantle (it rests on the gathered cloth)
    hv_ = V[C["hood"]]
    h_th, h_r, h_z = ang(hv_[:, 0], hv_[:, 1]), np.hypot(hv_[:, 0], hv_[:, 1] - YC), hv_[:, 2]

    def hood_r(th, z):
        dd = (np.abs(((h_th - th) + np.pi) % (2 * np.pi) - np.pi) < math.radians(10)) & (np.abs(h_z - z) < 0.012)
        return float(np.median(h_r[dd])) if dd.sum() >= 2 else None
    def min_fall(prof):
        """smallest fall angle of the profile segments from the start down to the shoulder corner"""
        cr = shoulder_corner(prof)
        k_end = next(k for k in range(len(prof)) if prof[k][0] == cr[0] and prof[k][1] == cr[1])
        a = [math.degrees(math.atan2(prof[k][1] - prof[k + 1][1], prof[k + 1][0] - prof[k][0]))
             for k in range(k_end) if prof[k + 1][0] - prof[k][0] > 0.004]
        return (min(a) if a else 90.0), cr
    z0 = m_start[:, 1].copy()
    for j in range(M_COLS):
        sw = float(m_extra(j, np.zeros(1))[1][0])
        prof = hull_profile(groups, m_th[j], m_start[j], m_hem[j], sweep=sw)
        a, cr = min_fall(prof)
        if cr[0] - prof[0][0] <= 0.01 or a >= SHOULDER_DEG or prof[0][1] >= START_ZMAX:
            continue
        s0 = prof[0]
        for zq in np.arange(s0[1] + 0.005, START_ZMAX + 1e-6, 0.005):
            rh = hood_r(m_th[j], zq)
            rq = min(s0[0], rh - 0.012) if rh is not None else s0[0]
            pq = hull_profile(groups, m_th[j], (rq, zq), m_hem[j], sweep=sw)
            if min_fall(pq)[0] >= SHOULDER_DEG:
                break
        m_start[j] = (rq, zq)
    zs = m_start[:, 1].copy()
    zs[-1] = zs[0]
    m_start[:, 1] = zs
    log("mantle neckline raised for the shoulder fall: max", round(float((zs - z0).max()), 3), "m, columns",
        int(((zs - z0) > 0.002).sum()), "| start z", round(float(zs.min()), 3), "..", round(float(zs.max()), 3))
    mR, mTH, mZ, mS = build_layer(m_th, m_start, m_hem, groups, M_ROWS, m_extra, M_ROW_POW)
    if os.environ.get("CLOAK_DEBUG"):
        for j in range(M_COLS):
            if abs(math.degrees(m_th[j]) % 360 - 0) < 7 or abs(math.degrees(m_th[j]) % 360 - 360) < 7:
                pr = hull_profile(groups, m_th[j], m_start[j], m_hem[j], sweep=float(m_extra(j, np.zeros(1))[1][0]))
                log("DEBUG col", j, round(math.degrees(m_th[j]) % 360), "start", m_start[j].round(3), "prof", pr[:6].round(3).tolist(),
                    "rows", np.stack([mR[j], mZ[j]], 1)[:5].round(3).tolist())
    # folds: start at the shoulder line, deepen to the hem; flat under the bib and the strap ribbons
    A = np.interp(mZ, *M_FOLD_Z)
    A = np.maximum(A, M_FOLD_HEM * sstep(0.55, 1.0, mS) * (m_hem[:, None] < 0.95))
    A *= sstep(0.0, 0.10, m_start[:, 1][:, None] - mZ)
    B = to_xyz(mR, mTH, mZ)
    bx, by, bz = B[..., 0], B[..., 1], B[..., 2]
    bib = (by > YC) * sstep(bib_bottom(np.abs(bx)) - 0.05, bib_bottom(np.abs(bx)), bz)
    strap = np.exp(-((np.abs(bx) - STRAP_X) / 0.035) ** 2) * sstep(1.08, 1.16, bz) * (by > -0.08)
    A *= (1 - bib) * (1 - 0.9 * strap)
    m_room = np.maximum(0.0, mR - np.maximum(env_at(E_body, mTH, mZ) + M_OFF, env_at(E_cloak, mTH, mZ) + M_GAP))
    mR2, mD, mc = folds(mR, m_u, A, m_room, M_FOLD_IN)
    mantle = to_xyz(mR2, mTH, mZ)
    top = mZ[0] >= M_OPEN_Z - 1e-6        # the closing column = the first column above the opening
    mantle[-1, top] = mantle[0, top]
    # measured fold relief (crest columns, outward over the unfolded drape) and trough depth
    crest = mc[:, 0] > 0.9
    i12 = np.argmin(np.abs(mZ - 1.2), axis=1)
    d12 = mD[np.arange(M_COLS), i12]
    free12 = crest & (strap[np.arange(M_COLS), i12] < 0.3) & (bib[np.arange(M_COLS), i12] < 0.3)
    hemc = crest & (m_hem < 0.95)
    FOLD = {"crest_z1.2_median": round(float(np.median(d12[free12])), 4), "crest_z1.2_min": round(float(d12[free12].min()), 4),
            "crest_z1.2_cols": int(free12.sum()), "crest_hem_min": round(float(mD[hemc, -1].min()), 4),
            "crest_hem_median": round(float(np.median(mD[hemc, -1])), 4),
            "trough_hem_median": round(float(np.median(mD[mc[:, 0] < -0.9, -1])), 4),
            "trough_z1.2_median": round(float(np.median(d12[mc[:, 0] < -0.9])), 4)}
    hem_z = mantle[:, -1, 2]
    HEM = {"front_centre_min": round(float(hem_z[dfront <= 15].min()), 3),
           "front_side_min": round(float(hem_z[(dfront >= 25) & (dfront <= 70)].min()), 3),
           "back_side_min": round(float(hem_z[(dfront >= 110) & (dfront <= 155)].min()), 3),
           "back_centre_min": round(float(hem_z[dfront >= 165].min()), 3),
           "arm_span_min": round(float(hem_z[(dfront > 75) & (dfront < 105)].min()), 3)}
    log("cloak start z", round(c_start[:, 1].min(), 3), "..", round(c_start[:, 1].max(), 3), "hem", round(c_hem.min(), 3),
        "| mantle hem", HEM, "| folds", FOLD)

    # ---- write the hood back, build the cloth into the same mesh
    hood_idx = np.nonzero(C["hood"])[0]
    for i in np.nonzero(C["hood"] | (dz < -1e-4))[0]:
        me.vertices[i].co = V[i]
    nb = [[] for _ in range(nv0)]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    mat = make_material(texture_path())
    if MAT not in [m.name for m in me.materials]:
        me.materials.append(mat)
    mi = [m.name for m in me.materials].index(MAT)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in mixed], context="FACES_ONLY")
    uvl = bm.loops.layers.uv.active
    lp = bm.faces.layers.float.get("lm_part")
    lt = bm.faces.layers.float.get("lm_t")
    dl = bm.verts.layers.deform.verify()
    g_m = obj.vertex_groups.get("cloak_mantle") or obj.vertex_groups.new(name="cloak_mantle")
    g_c = obj.vertex_groups.get("cloak_gray") or obj.vertex_groups.new(name="cloak_gray")
    layers = []
    for grid, S, part, grp, (u0, u1) in ((cloak, cS, 21, g_c, (0.5, 1.0)), (mantle, mS, 20, g_m, (0.0, 0.5))):
        ncol, nr = grid.shape[0], grid.shape[1]
        vs = [[bm.verts.new(Vector(grid[j, i])) for i in range(nr)] for j in range(ncol)]
        for row in vs:
            for v in row:
                v[dl][grp.index] = 1.0
        faces = []
        for j in range(ncol - 1):
            for i in range(nr - 1):
                f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
                f.material_index = mi
                f.smooth = True
                if lp:
                    f[lp] = part
                if lt:
                    f[lt] = S[j, i]
                for loop in f.loops:
                    jj = j + (1 if loop.vert in (vs[j + 1][i], vs[j + 1][i + 1]) else 0)
                    ii = i + (1 if loop.vert in (vs[j][i + 1], vs[j + 1][i + 1]) else 0)
                    loop[uvl].uv = (u0 + 0.004 + (u1 - u0 - 0.008) * jj / (ncol - 1), 1.0 - S[jj, ii] * 0.99 - 0.005)
                faces.append(f)
        if part == 20:     # close the mantle front above the opening: weld the coinciding edge columns
            pairs = [(vs[0][i], vs[-1][i]) for i in range(nr) if (vs[0][i].co - vs[-1][i].co).length < 1e-5]
            bmesh.ops.weld_verts(bm, targetmap={b: a for a, b in pairs})
            vs[-1] = [vs[0][i] if i < len(pairs) else vs[-1][i] for i in range(nr)]
            faces = [f for f in faces if f.is_valid]
            log("mantle front closed over", len(pairs), "rows")
        layers.append((part, faces, vs))
    for part, faces, vs in layers:          # cloth normals: outward
        for f in faces:
            f.normal_update()
            c = f.calc_center_median()
            if f.normal.x * c.x + f.normal.y * (c.y - YC) + 0.3 * f.normal.z * max(0.0, c.z - 1.38) < 0:
                f.normal_flip()

    # ---- hood lifted over the mantle where it lies on it: push along the mantle normal to LIFT_CLEAR outside,
    # only where the hood vertex projects onto the inside of a mantle face (not beyond the neckline edge)
    bm.verts.ensure_lookup_table()
    mfaces = [f for part, faces, vs in layers if part == 20 for f in faces]
    mtree, _ = tree_of(mfaces)
    need = {}
    for i in hood_idx:
        p = bm.verts[i].co
        q, n, fi, dist = mtree.find_nearest(p, 0.10)
        if q is None:
            continue
        sd = (p - q).dot(n)
        lateral = ((p - q) - n * sd).length
        if sd < LIFT_CLEAR and p.z < 1.56 and sd > -0.08 and lateral < 0.01:
            need[i] = (n.copy(), LIFT_CLEAR - sd)
    disp = {i: (need[i][0] * need[i][1] if i in need else Vector()) for i in hood_idx}
    hood_set = set(hood_idx.tolist())
    for _ in range(24):
        new_d = {}
        for i in hood_idx:
            ns = [disp[n] for n in nb[i] if n in hood_set]
            d = disp[i] * 0.5 + (sum(ns, Vector()) / len(ns)) * 0.42 if ns else disp[i]     # decays away from the mantle
            if i in need:
                n, amt = need[i]
                if d.dot(n) < amt:
                    d = d + n * (amt - d.dot(n))
            new_d[i] = d
        disp = new_d
    big = 0
    for i in hood_idx:
        d = disp[i]
        if d.length > LIFT_MAX:
            d = d * (LIFT_MAX / d.length)
            big += 1
        bm.verts[i].co += d
    log("hood lifted over the mantle", len(need), "verts, max", round(max((d.length for d in disp.values()), default=0), 4),
        "capped", big)

    # ---- mantle neckline rows that still stick out past the hood: tucked back under it (8 mm inside the shell)
    hfaces0 = [f for f in bm.faces if f.material_index == 0 and all(v.index in hood_set for v in f.verts)]
    htree0, _ = tree_of(hfaces0)
    mvs = [vs for part, faces, vs in layers if part == 20][0]
    tucked = 0
    for col in mvs:
        for v in col[:3]:
            p = v.co
            rad = Vector((p.x, p.y - YC, 0.0))
            if rad.length < 1e-6:
                continue
            rad.normalize()
            if htree0.ray_cast(p + rad * 1e-4, rad, 0.06)[0] is not None:
                continue                                    # under the hood already
            h = htree0.ray_cast(p, -rad, 0.05)
            if h[0] is not None and h[0].z > p.z - 0.03:
                v.co = h[0] - rad * 0.008
                tucked += 1
    log("mantle neckline vertices tucked back under the hood", tucked)
    # cloak vertices that poke out of the mantle at the top (z > 1.15): pulled back under it
    mtree3, _ = tree_of(mfaces)
    cvs = [vs for part, faces, vs in layers if part == 21][0]
    pulled = 0
    for col in cvs:
        for v in col:
            p = v.co
            if p.z < 1.15:
                continue
            rad = Vector((p.x, p.y - YC, 0.0)).normalized()
            if mtree3.ray_cast(p + rad * 1e-4, rad, 0.15)[0] is not None:
                continue
            h = mtree3.ray_cast(p, -rad, 0.05)
            if h[0] is not None:
                v.co = h[0] - rad * 0.006
                pulled += 1
    log("cloak vertices pulled back under the mantle", pulled)
    # ---- backpack straps on top of the mantle / bib
    hood_faces = [f for f in bm.faces if f.material_index == 0 and all(v.index in hood_set for v in f.verts)]
    STRAP = add_straps(bm, mfaces + hood_faces, lp, uvl)
    log("strap ribbons", STRAP)

    # ---- torso faces that still cut the cloth at the neck / shoulders: inside the cloth, deleted
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    protect = set(np.nonzero(C["hood"] | C["face"] | C["inner"])[0].tolist())
    pack_set = set(np.nonzero(C["pack"])[0].tolist())
    cloth_faces = [f for f in bm.faces if f.material_index == mi]
    ctree, _ = tree_of(cloth_faces)
    cand = []
    for f in bm.faces:
        if f.material_index != 0 or (lp and int(round(f[lp])) == 22):
            continue
        c = f.calc_center_median()
        ids = [v.index for v in f.verts]
        if c.z < 1.15 or abs(c.x) > 0.27 or any(i in protect for i in ids) or all(i in pack_set for i in ids):
            continue
        cand.append(f)
    btree, bf = tree_of(cand)
    neck_cut = list({bf[b] for a, b in ctree.overlap(btree)})
    bmesh.ops.delete(bm, geom=neck_cut, context="FACES_ONLY")
    log("torso faces cutting the cloth at the neck / shoulders deleted", len(neck_cut))
    # hood faces still cutting the mantle with their centre under it: they are covered by the mantle there
    mtree2, _ = tree_of([f for f in bm.faces if f.material_index == mi and lp and int(round(f[lp])) == 20])
    hf = [f for f in bm.faces if f.material_index == 0 and all(v.index in hood_set for v in f.verts)]
    htree, hfl = tree_of(hf)
    hood_cut = []
    for b in {b for a, b in mtree2.overlap(htree)}:
        f = hfl[b]
        c = f.calc_center_median()
        loc, n, _, d = mtree2.find_nearest(c)
        if loc is not None and (c - loc).dot(n) < 0:
            hood_cut.append(f)
    bmesh.ops.delete(bm, geom=hood_cut, context="FACES_ONLY")
    log("hood faces under the mantle deleted", len(hood_cut))

    # ---- cut the cloth inside the backpack (closed Tripo surface: inside = behind the nearest pack face)
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    body_faces = [f for f in bm.faces if f.material_index != mi]
    pack_faces = [f for f in body_faces if all(v.index in pack_set for v in f.verts)]
    btree, bfaces = tree_of(body_faces)
    inside = {}
    for part, faces, vs in layers:
        for row in vs:
            for v in row:
                if not v.is_valid or not (0.95 < v.co.z < 1.47 and v.co.y < 0.0 and abs(v.co.x) < 0.2):
                    continue
                inside[v] = point_inside(btree, bfaces, v.co, pack_faces)
    cut = [f for part, faces, vs in layers for f in faces if f.is_valid and all(inside.get(v, False) for v in f.verts)]
    bmesh.ops.delete(bm, geom=cut, context="FACES")
    log("cloth faces inside the backpack removed", len(cut))

    # ---- hidden body faces (always under the cloth)
    bm.faces.ensure_lookup_table()
    cloth_faces = [f for f in bm.faces if f.material_index == mi]
    ctree, _ = tree_of(cloth_faces)
    btree, bfaces = tree_of([f for f in bm.faces if f.material_index != mi])
    dirs = fib_dirs(64)
    hidden, why = [], {}
    for f in [f for f in bm.faces if f.material_index == 0]:
        if (lp and int(round(f[lp])) == 22) or any(v.index in protect for v in f.verts if v.index < nv0):
            why["protect"] = why.get("protect", 0) + 1
            continue
        c = f.calc_center_median()
        if c.z < 1.12 and not (c.y < 0.0 and c.z > 0.98):     # upper torso / shoulders / under the backpack only
            why["region"] = why.get("region", 0) + 1
            continue
        if abs(c.x) > 0.2 and c.z < 1.25:                       # upper arms (they move under the mantle sleeve)
            continue
        n = f.normal
        hit = ctree.ray_cast(c + n * 1e-4, n, COVER_DIST)
        if hit[0] is None:
            hb = btree.ray_cast(c + n * 3e-4, n, COVER_DIST)
            if hb[0] is None or (abs(hb[0].x) > 0.19 and hb[0].z < 1.40):     # covered by the backpack / body
                why["normal"] = why.get("normal", 0) + 1
                continue
        ok = True
        for dvc in dirs:
            # rays leaving steeply downwards exit under the open hems: only a camera below the hem sees that
            if dvc.dot(n) < 0.05 or dvc.z < -RAY_DOWN:
                continue
            o = c + n * 1e-4
            hc = ctree.ray_cast(o, dvc, 2.0)
            hb = btree.ray_cast(o + dvc * 2e-4, dvc, 2.0)
            if hc[0] is not None and (hb[0] is None or hc[3] <= hb[3]):
                continue
            # blocked by the body first: covered, unless it is an arm (arms move): then the cloth must be beyond it
            if hb[0] is not None and not (abs(hb[0].x) > 0.19 and hb[0].z < 1.40):
                continue
            if hb[0] is not None and ctree.ray_cast(hb[0] + dvc * 1e-3, dvc, 2.0)[0] is not None:
                continue
            ok = False
            key = ("arm" if hb[0] is not None else "escape", round(dvc.z, 1))
            why[key] = why.get(key, 0) + 1
            break
        if ok:
            hidden.append(f)
    n_hidden = sum(len(f.verts) - 2 for f in hidden)
    bmesh.ops.delete(bm, geom=hidden, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    log("hidden body faces removed", len(hidden), "tris", n_hidden, "| kept because of",
        sorted(why.items(), key=lambda kv: -kv[1])[:12])

    def count():
        return sum(len(f.verts) - 2 for f in bm.faces)

    cloth_tris = sum(len(f.verts) - 2 for f in bm.faces if f.material_index == mi)
    total = count()
    log("tris: before", tris0, "cloth", cloth_tris, "total now", total, "max", TRI_MAX)
    dissolved = 0
    if total > TRI_MAX:      # (vertex indices are still the original ones here: no index_update since the removal)
        dissolved = limited_dissolve(bm, total - TRI_MAX, protect)
        total = count()
        log("after limited dissolve", total)
    # duplicate faces (same vertex set, e.g. a triangulated dissolve n-gon over an existing triangle): keep one
    seen, dup = {}, []
    bm.verts.index_update()
    for f in bm.faces:
        key = frozenset(v.index for v in f.verts)
        if key in seen:
            dup.append(f)
        else:
            seen[key] = f
    if dup:
        log("duplicate faces removed", len(dup))
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
        total = count()
    bm.to_mesh(me)
    bm.free()
    me.update()
    if me.validate(verbose=True, clean_customdata=False):
        log("WARNING: mesh.validate() changed the mesh")
    report = check(obj, mi)
    report.update({"tris": total, "cloth_tris": cloth_tris, "hidden_removed_tris": n_hidden, "dissolved": dissolved,
                   "tris_before": tris0, "hood": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in hs.items()},
                   "hem": HEM, "folds": FOLD, "straps": STRAP, "neck_cut": len(neck_cut)})
    log("REPORT", report)
    return report


def add_straps(bm, top_faces, lp, uvl):
    """Two ribbons (one per side) from z 1.16 on the chest up over the shoulder to the backpack's top edge, resampled
    every STRAP_STEP and projected onto the outermost surface (mantle / bib), STRAP_LIFT above it.
    Returns stats (tris, max / min distance of the ribbon to the surface under it)."""
    bm.verts.ensure_lookup_table()
    tree, faces = tree_of(top_faces)
    src = Vector(STRAP_SRC)
    best = min((f for f in bm.faces if f.material_index == 0 and (f.calc_center_median() - src).length < 0.03),
               key=lambda f: (f.calc_center_median() - src).length)
    uv0 = best.loops[0][uvl].uv.copy()
    n_tris, ribbon_faces = 0, []
    for side in (1, -1):
        x = side * STRAP_X
        pts = []

        def outer(origins, d, key):
            hs = [tree.ray_cast(o, d, 3.0) for o in origins]
            hs = [h for h in hs if h[0] is not None]
            return max(hs, key=key)[0] if hs else None
        for z in np.linspace(1.16, 1.42, 14):                 # chest, front: rays from the front, frontmost hit
            h = outer([Vector((x, 0.8, z))], Vector((0, -1, 0)), lambda h: h[0].y)
            if h is not None:
                pts.append(Vector((x, h.y, h.z)))
        y_front = pts[-1].y if pts else 0.15
        for y in np.linspace(y_front - 0.02, -0.05, 9):       # over the shoulder: rays from above, highest hit
            k_top = float(sstep(y_front - 0.02, y_front - 0.06, y))
            xx = side * (STRAP_X + (STRAP_X_TOP - STRAP_X) * k_top + (STRAP_X_PACK - STRAP_X_TOP) * float(sstep(0.03, -0.05, y)))
            h = outer([Vector((xx, y, 2.2))], Vector((0, 0, -1)), lambda h: h[0].z)
            if h is not None:
                pts.append(Vector((xx, h.y, h.z)))
        z_last = pts[-1].z if pts else 1.44
        for z in np.linspace(z_last - 0.01, 1.395, 4):      # down the back to the backpack's top: rays from behind
            xx = side * STRAP_X_PACK
            h = outer([Vector((xx, -0.8, z))], Vector((0, 1, 0)), lambda h: -h[0].y)
            if h is not None and h.y < pts[-1].y:
                pts.append(Vector((xx, h.y, h.z)))
        if len(pts) < 4:
            log("WARNING: strap path not found", side)
            continue
        P = np.array([p[:] for p in pts])
        for _ in range(3):
            P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
        cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        n = max(4, int(round(cum[-1] / STRAP_STEP)) + 1)
        tt = np.linspace(0, cum[-1], n)
        Q = [Vector(np.array([np.interp(tt, cum, P[:, k]) for k in range(3)])[:, i]) for i in range(n)]
        rows = []
        for k, q in enumerate(Q):
            # the path lies in the plane x = const: its outward normal in that plane, the ribbon width along x
            t = Q[min(k + 1, n - 1)] - Q[max(k - 1, 0)]
            nrm = Vector((0.0, t.z, -t.y)).normalized()
            if nrm.dot(Vector((0.0, q.y - YC, q.z - 1.30))) < 0:
                nrm = -nrm
            hc = tree.ray_cast(q + nrm * 0.08, -nrm, 0.16)
            if hc[0] is not None:
                nrm = hc[1].copy() if hc[1].dot(nrm) > 0 else -hc[1]
            w = t.normalized().cross(nrm).normalized()
            if w.x * side < 0:
                w = -w
            row = []
            for off in (-STRAP_W / 2, 0.0, STRAP_W / 2):
                p = q + w * off
                h = tree.ray_cast(p + nrm * 0.08, -nrm, 0.16)          # first (outermost) surface along -n
                if h[0] is None:
                    h = tree.find_nearest(p)
                hp, hn = h[0], h[1].copy()
                if hn.dot(nrm) < 0:
                    hn = -hn
                row.append(bm.verts.new(hp + hn * STRAP_LIFT))
            rows.append((row, nrm))
        for i in range(len(rows) - 1):
            r0, n0 = rows[i]
            r1, _ = rows[i + 1]
            for m in range(2):
                f = bm.faces.new((r0[m], r0[m + 1], r1[m + 1], r1[m]))
                f.material_index = 0
                f.smooth = True
                if lp:
                    f[lp] = 22
                for k, loop in enumerate(f.loops):
                    loop[uvl].uv = (uv0.x + 0.0015 * (k in (1, 2)), uv0.y + 0.0015 * (k in (2, 3)))
                f.normal_update()
                if f.normal.dot(n0) < 0:
                    f.normal_flip()
                ribbon_faces.append(f)
                n_tris += 2
    # chords of the flat ribbon faces sink into the convex cloth between the samples: push the corners out until
    # every face centre / edge midpoint is >= 1.5 mm above the surface
    for _ in range(6):
        push = {}
        for f in ribbon_faces:
            vs = [v.co for v in f.verts]
            for p in [(vs[i] + vs[(i + 1) % 4]) / 2 for i in range(4)] + [sum(vs, Vector()) / 4]:
                loc, nrm, fi, dist = tree.find_nearest(p)
                nn = nrm if nrm.dot(f.normal) > 0 else -nrm
                sd = (p - loc).dot(nn)
                if sd < 0.0015:
                    for v in f.verts:
                        push[v] = max(push.get(v, 0.0), 0.0015 - sd)
        if not push:
            break
        for v, d in push.items():
            n = sum((g.normal for g in v.link_faces), Vector()).normalized()
            v.co += n * d
        for f in ribbon_faces:
            f.normal_update()
    # distance of the ribbon to the surface under it (vertices, edge midpoints, centres)
    dmax, dmin = 0.0, 1.0
    for f in ribbon_faces:
        vs = [v.co for v in f.verts]
        samples = vs + [(vs[i] + vs[(i + 1) % 4]) / 2 for i in range(4)] + [sum(vs, Vector()) / 4]
        for p in samples:
            loc, nrm, fi, dist = tree.find_nearest(p)
            sd = (p - loc).dot(nrm) if nrm.dot(f.normal) > 0 else -(p - loc).dot(nrm)
            dmax = max(dmax, dist)
            dmin = min(dmin, sd)
    return {"tris": n_tris, "offset_max": round(dmax, 4), "signed_min": round(dmin, 4)}


def texture_path():
    os.makedirs(TEX, exist_ok=True)
    p = os.path.join(TEX, "hero_cloak_basecolor.png")
    make_texture(p)
    return p


def tree_of(faces):
    verts, polys, idx = [], [], {}
    for f in faces:
        ps = []
        for v in f.verts:
            if v not in idx:
                idx[v] = len(verts)
                verts.append(v.co.copy())
            ps.append(idx[v])
        polys.append(ps)
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), faces


def point_inside(tree, faces, p, pack_faces):
    """Inside the closed body near the backpack: the nearest body face is a backpack face and p is behind it."""
    loc, nrm, i, dist = tree.find_nearest(p)
    if i is None or faces[i] not in pack_faces_set(pack_faces):
        return False
    return (p - loc).dot(faces[i].normal) < 0


_PF = {}


def pack_faces_set(pf):
    key = id(pf)
    if key not in _PF:
        _PF.clear()
        _PF[key] = set(pf)
    return _PF[key]


def fib_dirs(n):
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        out.append(Vector((r * math.cos(g * i), r * math.sin(g * i), z)))
    return out


def limited_dissolve(bm, excess, protect):
    """Planar (limited) dissolve of Tripo body faces away from the face, hood and backpack, angle raised until
    `excess` triangles are gone; the resulting n-gons are triangulated (deforming mesh)."""
    # torso and hips under / inside the cloth only (not the arms, hands, face, hood or backpack silhouette)
    cand = [f for f in bm.faces if f.material_index == 0 and not any(v.index in protect for v in f.verts)
            and all(abs(v.co.x) < 0.19 and 0.80 < v.co.z < 1.45 and not (v.co.y < -0.05 and v.co.z > 0.99)
                    for v in f.verts)]
    t0 = sum(len(f.verts) - 2 for f in bm.faces)
    for deg in (2, 4, 6, 8, 10, 12, 15, 18, 22):
        bm2 = bm.copy()
        bm2.faces.ensure_lookup_table()
        idx = {f.index for f in cand}
        fs = [f for f in bm2.faces if f.index in idx]
        es = list({e for f in fs for e in f.edges if all(g.index in idx for g in e.link_faces)})
        vs = list({v for f in fs for v in f.verts})
        bmesh.ops.dissolve_limit(bm2, angle_limit=math.radians(deg), verts=vs, edges=es, use_dissolve_boundaries=False)
        ng = [f for f in bm2.faces if len(f.verts) > 3]
        bmesh.ops.triangulate(bm2, faces=ng, quad_method="BEAUTY", ngon_method="BEAUTY")
        t = sum(len(f.verts) - 2 for f in bm2.faces)
        bm2.free()
        log("limited dissolve", deg, "deg ->", t0 - t, "tris saved")
        if t0 - t >= excess:
            fs = [f for f in bm.faces if f.index in idx]
            es = list({e for f in fs for e in f.edges if all(g.index in idx for g in e.link_faces)})
            vs = list({v for f in fs for v in f.verts})
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(deg), verts=vs, edges=es,
                                     use_dissolve_boundaries=False)
            ng = [f for f in bm.faces if len(f.verts) > 3]
            bmesh.ops.triangulate(bm, faces=ng, quad_method="BEAUTY", ngon_method="BEAUTY")
            return deg
    log("WARNING: limited dissolve up to 22 deg is not enough")
    return -1


def silhouette(P, x0=0.08, x1=0.32, step=0.005):
    """front / back ortho outline (identical): highest z per |x| bin"""
    ax = np.abs(P[:, 0])
    nb = int(round((x1 - x0) / step))
    top = np.full(nb, np.nan)
    b = np.floor((ax - x0) / step).astype(int)
    ok = (b >= 0) & (b < nb)
    for k in range(nb):
        s = ok & (b == k)
        if s.any():
            top[k] = P[s, 2].max()
    return top


def check(obj, mi):
    """Rest-pose checks: cloth vs body intersections (by part), mantle vs cloak, hem clearance, head top, shoulder
    outline."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    lp = bm.faces.layers.float.get("lm_part")
    mant = [f for f in bm.faces if f.material_index == mi and int(round(f[lp])) == 20]
    clo = [f for f in bm.faces if f.material_index == mi and int(round(f[lp])) == 21]
    body = [f for f in bm.faces if f.material_index != mi]
    tb, fb = tree_of(body)
    tm, fm = tree_of(mant)
    tc, fc = tree_of(clo)

    def kinds(pairs, fbx):
        out = {}
        for a, b in pairs:
            g = fbx[b]
            c = g.calc_center_median()
            k = ("legs" if g.material_index == 1 else "pack" if (c.y < -0.04 and 0.98 < c.z < 1.46 and abs(c.x) < 0.17)
                 else "hood/neck" if c.z > 1.34 and abs(c.x) < 0.17 else "body")
            out[k] = out.get(k, 0) + 1
        return out
    for nm, pairs in (("mantle", tm.overlap(tb)), ("cloak", tc.overlap(tb))):
        cl = {}
        for a, b in pairs:
            c = fb[b].calc_center_median()
            key = (round(c.x * 10) / 10, round(c.y * 10) / 10, round(c.z * 10) / 10)
            cl[key] = cl.get(key, 0) + 1
        log("intersections", nm, sorted(cl.items(), key=lambda kv: -kv[1])[:14])
    res = {"mantle_x_body": kinds(tm.overlap(tb), fb), "cloak_x_body": kinds(tc.overlap(tb), fb),
           "mantle_x_cloak": len(tm.overlap(tc))}
    cz = [v.co.z for f in clo for v in f.verts]
    res["cloak_hem_min_z"] = round(min(cz), 4)
    res["head_top"] = round(max(v.co.z for v in bm.verts), 4)
    vs = [v.co for v in bm.verts]
    res["bbox"] = [tuple(round(min(c[i] for c in vs), 3) for i in range(3)),
                   tuple(round(max(c[i] for c in vs), 3) for i in range(3))]
    res["materials"] = [m.name for m in me.materials]
    # shoulder outline in the front / back ortho views: all geometry above z 1.2 vs the mantle alone
    pts_all = np.array([v.co[:] for v in bm.verts] + [f.calc_center_median()[:] for f in bm.faces])
    pts_all = pts_all[pts_all[:, 2] > 1.2]
    pm = np.array([v.co[:] for f in mant for v in f.verts] + [f.calc_center_median()[:] for f in mant])
    top_all, top_m = silhouette(pts_all), silhouette(pm[pm[:, 2] > 1.2])
    xs = 0.08 + 0.005 * (np.arange(len(top_all)) + 0.5)
    outer = xs[np.nonzero(top_m > 1.30)[0].max()] if (top_m > 1.30).any() else 0.25
    angs = []
    for k in range(len(xs) - 6):
        if 0.12 <= xs[k] and xs[k + 6] <= outer - 0.005 and not np.isnan(top_all[k]) and not np.isnan(top_all[k + 6]):
            angs.append(math.degrees(math.atan2(top_all[k] - top_all[k + 6], 0.03)))
    k12 = int(round((0.12 - 0.08) / 0.005))
    ko = int(round((outer - 0.08) / 0.005))
    chord = math.degrees(math.atan2(top_all[k12] - top_all[ko], xs[ko] - xs[k12]))
    res["shoulder_outline"] = {"x_outer_arm": round(float(outer), 3), "chord_deg_x0.12_to_outer": round(chord, 1),
                               "min_drop_deg_3cm_windows": round(min(angs), 1) if angs else None,
                               "z_top_all": [round(float(z), 3) for z in top_all[::2]],
                               "z_top_mantle": [None if np.isnan(z) else round(float(z), 3) for z in top_m[::2]]}
    bm.free()
    return res


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    hero = bpy.data.objects["hero"]
    apply(hero)
    for img in bpy.data.images:
        if img.source == "FILE" and not img.packed_file:
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(argv[0]), compress=True)
    log("saved", argv[0])
