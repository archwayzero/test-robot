"""T044 hero cloak stage (decision D18): white mantle + gray cloak, looser hood, budget paid by hidden body faces.

Called by conform.py at the end (on the finished T011 hero, final coordinates: front +Y, feet at z 0), or standalone
for iteration on a saved hero blend:
  blender -b <hero.blend> -P blender/models/hero/cloak.py -- <out.blend>

Coordinates: cylindrical around the vertical axis (0, YC); theta 0 = +X (the hero's left), 90 deg = front (+Y),
270 deg = back. Everything is a function of (theta, z), sampled on a 2 deg x 5 mm grid.

Steps:
  1. Classify body vertices: backpack (behind the back, excluded from the cloth envelope; cloth inside it is cut away),
     hood (head shell + cowl; pushed out over the mantle and loosened), face / inner neck (never moved).
  2. Envelope E(theta, z): max body radius per bin (wedge +-4 deg), legs and arms included, backpack excluded.
  3. Gray cloak: per theta the draped profile = concave majorant of the cumulative envelope (cloth hangs from the
     shoulders, straight lines where it spans), + offset, + a flare / slight train at the back, + vertical folds that
     only go outward. Open at the front: its two edges run from the neck front (top) back over the shoulders to
     behind the arms (elbow height) and come forward again a little at the floor. Hem 3 cm above the floor.
  4. White mantle over it (encloses the cloak + gap), open at the front centre, folds + zigzag hem: about knee height at
     the front, longer at the back-sides, raised above the forearms/hands at the arms (arms free from the elbow).
  5. Hood: loosened (radial push growing towards the neck) and lifted over the mantle neckline.
  6. Cloth faces inside the backpack are removed (the cloth runs under the backpack).
  7. Budget: body faces that are always covered by the cloth (rays from the face hit cloth in every direction, cloth
     within COVER_DIST) are deleted; if still over, limited dissolve of the Tripo body away from face / hood / backpack;
     then the cloth would have to shrink (reported, not automatic).
  8. One material `hero_cloak` (1024x512 albedo: mantle left half, cloak right half), roughness 0.9, double-sided.
     Vertex groups `cloak_mantle`, `cloak_gray`; face attribute lm_part 20 (mantle) / 21 (cloak).
"""
import math
import os
import sys

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
NT, NZ = int(360 / DT_DEG), 301       # z 0 .. 1.50
WEDGE_BINS = 2                         # +-4 deg

# cloak (gray)
C_COLS, C_ROWS = 37, 22                # 9 folds x 4 columns + 1
C_OFF = 0.012                          # clearance over the body
C_TUCK = 0.020                         # neckline tucked this far under the hood's bib / collar edge
C_EDGE_DEG = -18.0                     # cloak front edge (deg from +X; mirrored), behind the arms
C_EDGE_FWD_DEG = 18.0                  # the edges swing this far forward at the floor
C_HEM = 0.030                          # lowest hem point above the floor
C_FOLD = 0.040                         # fold depth at the hem (outward only)
C_FLARE, C_TRAIN = 0.05, 0.09          # extra radius at the floor (all round / at the back)
# mantle (white)
M_COLS, M_ROWS = 61, 13                # 15 folds x 4 columns + the closing column (welded above the opening)
M_GAP = 0.010                          # over the cloak
M_OFF = 0.016                          # over the body where there is no cloak
M_FOLD = 0.065
M_ZIG = 0.07                           # zigzag hem depth
M_OPEN_DEG = 0.0                       # half opening at the front centre (neck): closed, edges welded
M_OPEN_HEM_DEG = 10.0                  # half opening at the hem; the front edges part below M_OPEN_Z
M_OPEN_Z = 1.22
Z_NECK = 1.47                          # neckline height (under the hood)
LIFT_MAX = 0.05                       # hood lift over the mantle neckline (cap)
LIFT_CLEAR = 0.008                     # hood clearance over the mantle
FOREARM_X, FOREARM_TOP = 0.185, 1.10   # |x| beyond this and below this: forearm / hand (kept free)
RAY_DOWN = 0.30                        # hidden-face test ignores rays steeper than this downwards (sin)
COVER_DIST = 0.10                      # hidden-face test: cloth within this distance along the face normal
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


# ----------------------------------------------------------------------------------------------- classification
def classify(V, mat_v):
    x, y, z = V.T
    pack = (mat_v == 0) & (y < -0.05) & (z > 0.99) & (z < 1.46) & (np.abs(x) < 0.17)
    rh = np.hypot(x, y - YH)
    head = (mat_v == 0) & (z > 1.45) & (np.abs(x) < 0.10)
    face = head & (np.abs(x) < 0.062) & (y > 0.095) & (z < 1.73)
    inner = head & (rh < 0.058) & (z < 1.56)              # neck under the hood
    th = np.degrees(ang(x, y))
    # cowl = the chainmail bib / collar of the hood (measured on ortho renders with height rings): at the front a
    # U-shaped bib, bottom 1.26 at the centre, 1.33 at |x| 0.10, 1.43 at 0.13; at the back the collar ends at 1.435
    r = np.hypot(x, y - YC)
    cb_front = np.interp(np.abs(x), [0.0, 0.05, 0.08, 0.10, 0.12, 0.135], [1.255, 1.275, 1.305, 1.335, 1.385, 1.43])
    cb = np.where(y > YC - 0.01, cb_front, 1.435)
    cowl = (mat_v == 0) & ~pack & (z > cb) & (z <= 1.47) & (np.abs(x) < 0.145) & (r < 0.17)
    hood = (head & ~face & ~inner) | cowl
    return {"pack": pack, "hood": hood, "face": face, "inner": inner, "cowl_bottom": cb}


# ----------------------------------------------------------------------------------------------- envelope
def envelope(P):
    """E[k, i]: max radius of points P (n,3) in theta bin k (+- WEDGE_BINS) and z bin i (+-1)."""
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


def concave_majorant(zs, rs):
    """Smallest concave function r(z) >= rs over zs (ascending)."""
    hull = []
    for p in zip(zs, rs):
        while len(hull) >= 2:
            (z1, r1), (z2, r2) = hull[-2], hull[-1]
            if (r2 - r1) * (p[0] - z1) <= (p[1] - r1) * (z2 - z1):   # hull[-1] below the chord -> drop
                hull.pop()
            else:
                break
        hull.append(p)
    hz, hr = zip(*hull)
    return np.interp(zs, hz, hr)


# ----------------------------------------------------------------------------------------------- cloth grids
def tri_wave(u):
    return 1.0 - np.abs(2.0 * np.mod(u, 1.0) - 1.0)


def fold_wave(u):
    return 0.5 - 0.5 * np.cos(2 * np.pi * u)


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


def build_layer(thetas, starts, hems, groups, nrows, fold_amp, fold_u, fold_start, extra):
    """Vertices (cols, nrows+1, 3) of a draped layer, rows at equal arclength fractions s of each column profile.
    extra(j, z) -> (radius added, rotation about the axis); folds: radial, outward only, growing with s."""
    ncol = len(thetas)
    out = np.zeros((ncol, nrows + 1, 3))
    S = np.zeros((ncol, nrows + 1))
    s_t = np.linspace(0, 1, nrows + 1)
    for j in range(ncol):
        prof = hull_profile(groups, thetas[j], starts[j], hems[j], sweep=float(extra(j, np.zeros(1))[1][0]))
        seg = np.linalg.norm(np.diff(prof, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        r = np.interp(s_t * cum[-1], cum, prof[:, 0])
        z = np.interp(s_t * cum[-1], cum, prof[:, 1])
        dr, dth = extra(j, z)
        r = r + dr + fold_amp[j] * fold_wave(fold_u[j]) * sstep(fold_start, 1.0, s_t)
        th = thetas[j] + dth
        out[j] = np.stack([r * np.cos(th), YC + r * np.sin(th), z], 1)
        S[j] = s_t
    return out, S


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
        tuple(np.round(img[:, :W // 2, :3].reshape(-1, 3).mean(0) * 255).astype(int)), "cloak",
        tuple(np.round(img[int(0.05 * H):, W // 2:, :3].reshape(-1, 3).mean(0) * 255).astype(int)))


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
    V = np.array([v.co[:] for v in me.vertices])
    mat_v = np.zeros(nv0, int)
    for p in me.polygons:
        if p.material_index == 1:
            mat_v[list(p.vertices)] = 1
    C = classify(V, mat_v)
    log("classified: pack", int(C["pack"].sum()), "hood", int(C["hood"].sum()), "face", int(C["face"].sum()),
        "inner neck", int(C["inner"].sum()))

    # ---- drape points: body + legs + arms (backpack, hood, face, inner neck excluded), (theta, r, z)
    use = ~C["pack"] & ~C["hood"] & ~C["face"] & ~C["inner"] & (V[:, 2] < 1.52)
    body_pts = (ang(V[use, 0], V[use, 1]), np.hypot(V[use, 0], V[use, 1] - YC), V[use, 2])
    cowl = C["hood"] & (V[:, 2] < 1.47)
    cowl_pts = (ang(V[cowl, 0], V[cowl, 1]), np.hypot(V[cowl, 0], V[cowl, 1] - YC), V[cowl, 2])

    def neck_edge(thetas):
        """(r, z) of the hood's bib / collar bottom edge per column angle (median radius of its lowest 2 cm)."""
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
    c_start = np.stack([c_neck[:, 0] + C_OFF * 0.5, c_neck[:, 1] + C_TUCK], 1)
    c_u = np.arange(C_COLS) / 4.0
    c_back = np.clip(-np.sin(c_th), 0, 1)
    c_amp = C_FOLD * (1 + 0.6 * c_back)
    c_amp[[0, -1]] *= 0.5
    c_hem = C_HEM + 0.012 * tri_wave(c_u + 0.5)                # lowest at the fold troughs
    c_swing = (1 - 2 * np.arange(C_COLS) / (C_COLS - 1)) * np.radians(C_EDGE_FWD_DEG)

    def c_extra(j, z):
        """flare / train radius and the forward swing of the edges near the floor"""
        k = sstep(0.75, 0.0, z)
        return (C_FLARE + C_TRAIN * c_back[j] ** 1.5) * k, c_swing[j] * sstep(0.7, 0.0, z)
    cloak, cS = build_layer(c_th, c_start, c_hem, [(body_pts, C_OFF)], C_ROWS, c_amp, c_u, 0.15, c_extra)

    # ---- white mantle: all round (front welded above M_OPEN_Z), over the cloak (+ gap)
    m_th = np.pi / 2 - np.arange(M_COLS) / (M_COLS - 1) * 2 * np.pi
    m_neck = neck_edge(m_th)
    m_start = np.stack([m_neck[:, 0] + C_OFF * 0.5 + M_GAP * 0.6, m_neck[:, 1] + C_TUCK + M_GAP * 0.6], 1)
    dfront = np.abs(((np.degrees(m_th) - 90 + 180) % 360) - 180)
    hem_design = np.interp(dfront, [0, 8, 25, 50, 75, 105, 130, 155, 180],
                           [0.80, 0.62, 0.48, 0.56, 0.9, 0.9, 0.40, 0.48, 0.55])
    # raised over the forearms / hands (arms free from the elbow down), with soft sides
    fa = use & (np.abs(V[:, 0]) > FOREARM_X) & (V[:, 2] < FOREARM_TOP)
    fa_th = ang(V[fa, 0], V[fa, 1])
    arm_min = np.zeros(M_COLS)
    for j in range(M_COLS):
        dd = np.abs(((fa_th - m_th[j]) + np.pi) % (2 * np.pi) - np.pi) < math.radians(16)
        if dd.any():
            arm_min[j] = V[fa, 2][dd].max() + 0.035
    m_hem = np.maximum(hem_design, arm_min)
    for _ in range(4):
        m_hem = np.maximum(0.25 * np.roll(m_hem, 1) + 0.5 * m_hem + 0.25 * np.roll(m_hem, -1), arm_min)
    m_hem[-1] = m_hem[0]
    m_u = np.arange(M_COLS) / 4.0
    m_hem = np.maximum(m_hem - M_ZIG * tri_wave(m_u) * sstep(1.0, 0.8, m_hem), arm_min)   # zigzag, lower at crests
    m_amp = M_FOLD * (1 - 0.6 * sstep(0.8, 1.0, m_hem))
    m_swing = (2 * np.arange(M_COLS) / (M_COLS - 1) - 1) * np.radians(M_OPEN_HEM_DEG)
    cl = cloak.reshape(-1, 3)
    cloak_pts = (ang(cl[:, 0], cl[:, 1]), np.hypot(cl[:, 0], cl[:, 1] - YC), cl[:, 2])

    def m_extra(j, z):
        return 0.0, m_swing[j] * sstep(M_OPEN_Z, 0.55, z)
    mantle, mS = build_layer(m_th, m_start, m_hem, [(body_pts, M_OFF), (cloak_pts, M_GAP)], M_ROWS, m_amp, m_u,
                             0.12, m_extra)
    log("cloak start z", round(c_start[:, 1].min(), 3), "..", round(c_start[:, 1].max(), 3), "hem", round(c_hem.min(), 3),
        "| mantle start z", round(m_start[:, 1].min(), 3), "..", round(m_start[:, 1].max(), 3), "hem min",
        round(m_hem.min(), 3), "max", round(m_hem.max(), 3), "front-lowest", round(m_hem[dfront < 40].min(), 3))

    # ---- hood: loosen (radial push growing towards the neck, faded next to the face)
    hood = C["hood"]
    hv = V[hood]
    loosen = 0.010 * sstep(1.68, 1.50, hv[:, 2])
    near_face = sstep(0.10, 0.06, np.hypot(hv[:, 0] / 1.3, np.maximum(0, 0.17 - hv[:, 1])))
    loosen *= (1 - 0.6 * near_face)
    ax_y = np.where(hv[:, 2] > 1.47, YH, YC)
    dvec = np.stack([hv[:, 0], hv[:, 1] - ax_y, np.zeros(len(hv))], 1)
    dvec /= np.maximum(np.linalg.norm(dvec, axis=1, keepdims=True), 1e-6)
    hood_idx = np.nonzero(hood)[0]
    V[hood_idx] += dvec * loosen[:, None]
    nb = [[] for _ in range(nv0)]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)

    # ---- write body positions back, build the cloth into the same mesh
    for i in hood_idx:
        me.vertices[i].co = V[i]
    log("hood: loosened max", round(float(loosen.max()), 4))
    mat = make_material(texture_path())
    if MAT not in [m.name for m in me.materials]:
        me.materials.append(mat)
    mi = [m.name for m in me.materials].index(MAT)
    bm = bmesh.new()
    bm.from_mesh(me)
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
    # cloth normals: outward
    for part, faces, vs in layers:
        for f in faces:
            f.normal_update()
            c = f.calc_center_median()
            if f.normal.x * c.x + f.normal.y * (c.y - YC) < 0:
                f.normal_flip()

    # ---- hood lifted over the mantle where it lies on it: push along the mantle normal to LIFT_CLEAR outside,
    # only where the hood vertex projects onto the inside of a mantle face (not beyond the neckline edge)
    bm.verts.ensure_lookup_table()
    mfaces = [f for part, faces, vs in layers if part == 20 for f in faces]
    mtree, _ = tree_of(mfaces)
    need = {}
    for i in hood_idx:
        p = bm.verts[i].co
        q, n, fi, dist = mtree.find_nearest(p, 0.08)
        if q is None:
            continue
        sd = (p - q).dot(n)
        lateral = ((p - q) - n * sd).length
        if sd < LIFT_CLEAR and p.z < 1.50 and sd > -0.07 and lateral < 0.01:
            need[i] = (n.copy(), LIFT_CLEAR - sd)
    disp = {i: (need[i][0] * need[i][1] if i in need else Vector()) for i in hood_idx}
    hood_set = set(hood_idx.tolist())
    for _ in range(20):
        new_d = {}
        for i in hood_idx:
            ns = [disp[n] for n in nb[i] if n in hood_set]
            d = disp[i] * 0.5 + (sum(ns, Vector()) / len(ns)) * 0.5 if ns else disp[i]
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
    log("hood: loosened max", round(float(loosen.max()), 4), "lifted over the mantle", len(need), "verts, max",
        round(max((d.length for d in disp.values()), default=0), 4), "capped", big)

    # ---- backpack straps on top: the Tripo straps run under the mantle now, so a strap ribbon (body material,
    # textured from the original strap's UVs) is laid over the mantle / bib from the chest over the shoulder to the
    # top of the backpack, on each side
    n_strap = add_straps(bm, [f for part, faces, vs in layers if part == 20 for f in faces], hood_idx, lp, uvl)
    log("strap ribbons on top of the mantle: tris", n_strap)

    # ---- cut the cloth inside the backpack (closed Tripo surface: inside = behind the nearest pack face)
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    body_faces = [f for f in bm.faces if f.material_index != mi]
    pack_set = set(np.nonzero(C["pack"])[0].tolist())
    pack_faces = [f for f in body_faces if all(v.index in pack_set for v in f.verts)]
    btree, bfaces = tree_of(body_faces)
    inside = {}
    for part, faces, vs in layers:
        for row in vs:
            for v in row:
                if not (0.95 < v.co.z < 1.47 and v.co.y < 0.0 and abs(v.co.x) < 0.2):
                    continue
                inside[v] = point_inside(btree, bfaces, v.co, pack_faces)
    cut = [f for part, faces, vs in layers for f in faces if all(inside.get(v, False) for v in f.verts)]
    bmesh.ops.delete(bm, geom=cut, context="FACES")
    log("cloth faces inside the backpack removed", len(cut))

    # ---- hidden body faces (always under the cloth)
    bm.faces.ensure_lookup_table()
    cloth_faces = [f for f in bm.faces if f.material_index == mi]
    ctree, _ = tree_of(cloth_faces)
    btree, bfaces = tree_of([f for f in bm.faces if f.material_index != mi])
    dirs = fib_dirs(64)
    protect = set(np.nonzero(C["hood"] | C["face"] | C["inner"])[0].tolist())
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
            why[("arm" if hb[0] is not None else "escape", round(dvc.z, 1))] = why.get(("arm" if hb[0] is not None else "escape", round(dvc.z, 1)), 0) + 1
            break
        if ok:
            hidden.append(f)
    n_hidden = sum(len(f.verts) - 2 for f in hidden)
    bmesh.ops.delete(bm, geom=hidden, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    log("hidden body faces removed", len(hidden), "tris", n_hidden, "| kept because of", sorted(why.items(), key=lambda kv: -kv[1])[:12])

    def count():
        return sum(len(f.verts) - 2 for f in bm.faces)

    cloth_tris = sum(len(f.verts) - 2 for f in bm.faces if f.material_index == mi)
    total = count()
    log("tris: before", tris0, "cloth", cloth_tris, "total now", total, "max", TRI_MAX)
    dissolved = 0
    if total > TRI_MAX:
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
        log("duplicate faces removed", len(dup), [(round(f.calc_center_median().x, 3), round(f.calc_center_median().y, 3),
                                                    round(f.calc_center_median().z, 3), f.material_index) for f in dup])
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
        total = count()
    bm.to_mesh(me)
    bm.free()
    me.update()
    if me.validate(verbose=True, clean_customdata=False):
        log("WARNING: mesh.validate() changed the mesh")
    report = check(obj, mi)
    report.update({"tris": total, "cloth_tris": cloth_tris, "hidden_removed_tris": n_hidden, "dissolved": dissolved,
                   "tris_before": tris0})
    log("REPORT", report)
    return report


STRAP_X, STRAP_W, STRAP_LIFT = 0.155, 0.034, 0.007
STRAP_SRC = (0.143, 0.079, 1.30)        # a point on the original strap (its UVs texture the ribbon)


def add_straps(bm, mantle_faces, hood_idx, lp, uvl):
    """Two ribbons (one per side), lying STRAP_LIFT over whatever is on top (mantle, hood bib), from z 1.16 on the
    chest up over the shoulder and down to the backpack's top edge. Returns the triangle count."""
    bm.verts.ensure_lookup_table()
    hood_set = set(int(i) for i in hood_idx)
    top_faces = list(mantle_faces) + [f for f in bm.faces if f.material_index == 0
                                      and all(v.index in hood_set for v in f.verts)]
    tree, faces = tree_of(top_faces)
    # strap texture: UV of the original strap surface nearest to STRAP_SRC
    src = Vector(STRAP_SRC)
    best = min((f for f in bm.faces if f.material_index == 0 and (f.calc_center_median() - src).length < 0.03),
               key=lambda f: (f.calc_center_median() - src).length)
    uv0 = best.loops[0][uvl].uv.copy()
    n_tris = 0
    for side in (1, -1):
        x = side * STRAP_X
        pts = []
        def best(origins, d, key):
            hs = [tree.ray_cast(o, d, 3.0) for o in origins]
            hs = [h for h in hs if h[0] is not None]
            if not hs:
                return None
            h = max(hs, key=key)
            return (Vector((x, h[0].y, h[0].z)) if d.y else Vector((x, h[0].y, h[0].z)), h[1])
        dx = [-STRAP_W * 0.6, 0.0, STRAP_W * 0.6]
        for z in np.linspace(1.16, 1.42, 12):                 # chest, front: rays from the front, frontmost hit
            r = best([Vector((x + d, 0.8, z)) for d in dx], Vector((0, -1, 0)), lambda h: h[0].y)
            if r:
                pts.append(r)
        y_front = pts[-1][0].y if pts else 0.15
        for y in np.linspace(y_front - 0.03, -0.05, 6):       # over the shoulder: rays from above, highest hit
            r = best([Vector((x + d, y, 2.2)) for d in dx], Vector((0, 0, -1)), lambda h: h[0].z)
            if r:
                pts.append(r)
        if len(pts) < 4:
            log("WARNING: strap path not found", side)
            continue
        # smooth the path (keep ends), then build the ribbon
        P = [p for p, n in pts]
        N = [n.normalized() for p, n in pts]
        for _ in range(2):
            Q = [P[0]] + [(P[i - 1] + 2 * P[i] + P[i + 1]) / 4 for i in range(1, len(P) - 1)] + [P[-1]]
            P = [q if (q - p).dot(n) > 0 else q + n * (p - q).dot(n) for q, p, n in zip(Q, P, N)]
        rows = []
        for i, (p, n) in enumerate(zip(P, N)):
            t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
            w = t.cross(n).normalized()
            if w.x * side < 0:
                w = -w
            c = p + n * STRAP_LIFT
            rows.append((bm.verts.new(c - w * STRAP_W / 2), bm.verts.new(c + w * STRAP_W / 2)))
        for i in range(len(rows) - 1):
            a, b = rows[i]
            c, d = rows[i + 1]
            f = bm.faces.new((a, b, d, c) if side > 0 else (b, a, c, d))
            f.material_index = 0
            f.smooth = False
            if lp:
                f[lp] = 22
            for k, loop in enumerate(f.loops):
                loop[uvl].uv = (uv0.x + 0.0015 * (k in (1, 2)), uv0.y + 0.0015 * (k in (2, 3)))
            f.normal_update()
            if f.normal.dot(N[i]) < 0:
                f.normal_flip()
            n_tris += 2
    return n_tris


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


def check(obj, mi):
    """Rest-pose checks: cloth vs body intersections (by part), mantle vs cloak, hem clearance, head top."""
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

    def kinds(pairs, fa, fbx):
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
    res = {"mantle_x_body": kinds(tm.overlap(tb), fm, fb), "cloak_x_body": kinds(tc.overlap(tb), fc, fb),
           "mantle_x_cloak": len(tm.overlap(tc))}
    cz = [v.co.z for f in clo for v in f.verts]
    res["cloak_hem_min_z"] = round(min(cz), 4)
    res["head_top"] = round(max(v.co.z for v in bm.verts), 4)
    vs = [v.co for v in bm.verts]
    res["bbox"] = [tuple(round(min(c[i] for c in vs), 3) for i in range(3)),
                   tuple(round(max(c[i] for c in vs), 3) for i in range(3))]
    res["materials"] = [m.name for m in me.materials]
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
