"""T015 look metrics, the independent review's definitions, printed against crypt.jpg.

  python3 tools/qa/memguard.py -- blender -b --factory-startup -P blender/models/crypt_kit/qa/measure_look.py -- \
      [--dir .captures/t015] [--png arcade_crypt_camera.png] [--flat arcade_flat.png]

From the render: luminance statistics per region, ring/soffit ratio, wall autocorrelation (reviewer's formula on the upper span
of wall_3_tiles). From atlas.json: as-built mortar width. From the exported GLB images: the longest straight floor joint.
"""
import json
import os
import struct
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


DIR = os.path.join(ROOT, arg("--dir", ".captures/t015"))
PNG = os.path.join(DIR, arg("--png", "arcade_crypt_camera.png"))
LUM = np.array([.2126, .7152, .0722])


def load(p):
    i = bpy.data.images.load(p)
    i.colorspace_settings.name = "Non-Color"
    w, h = i.size
    c = i.channels
    px = np.empty(w * h * c, "f4")
    i.pixels.foreach_get(px)
    bpy.data.images.remove(i)
    return np.flipud(px.reshape(h, w, c))[..., :3]


def blur(L, s):
    h, w = L.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    return np.fft.irfft2(np.fft.rfft2(L) * np.exp(-2 * (np.pi * s) ** 2 * (fx ** 2 + fy ** 2)), s=(h, w))


def st(a, box, sc):
    x0, y0, x1, y1 = [int(v * sc) for v in box]
    r = a[y0:y1, x0:x1]
    L = r @ LUM
    m = r.reshape(-1, 3).mean(0)
    hp2 = blur(L, 6 * sc) - blur(L, 30 * sc)
    p = np.percentile(L, [5, 50, 95])
    return dict(rgb=m, p5=p[0], p50=p[1], p95=p[2], span=p[2] - p[0], br=m[2] / m[0], fine=(L - blur(L, 6 * sc)).std(), mid=hp2.std())


def show(tag, name, d):
    print("%-4s %-10s rgb %.3f %.3f %.3f  L p5 %.3f p50 %.3f p95 %.3f span %.3f  B/R %.3f  fine %.4f  mid %.4f" % (
        tag, name, *d["rgb"], d["p5"], d["p50"], d["p95"], d["span"], d["br"], d["fine"], d["mid"]))


ref = load(os.path.join(ROOT, "reference/map/crypt.jpg"))
k = ref.shape[1] / 2000
for n, b in {"back wall": (1130, 620, 1450, 900), "web": (760, 110, 1100, 200), "ring": (990, 235, 1160, 285),
             "soffit": (870, 330, 1050, 350), "pier": (560, 880, 690, 1190)}.items():
    show("REF", n, st(ref, b, k))
Q = {"back wall": (810, 400, 1080, 700), "web": (650, 110, 880, 160), "ring": (850, 150, 1000, 190),
     "soffit*": (740, 235, 880, 255), "true sof": (880, 191, 960, 204), "pier": (310, 600, 480, 950), "floor": (560, 760, 1000, 900)}
for path in [PNG] + ([os.path.join(DIR, arg("--flat"))] if arg("--flat") else []):
    if os.path.exists(path):
        r = load(path)
        kk = r.shape[1] / 1500
        res = {n: st(r, b, kk) for n, b in Q.items()}
        print(path)
        for n, d in res.items():
            show("KIT", n, d)
        print("TARGET1 back wall mid %.4f (>=0.06), span %.3f (>=0.40)" % (res["back wall"]["mid"], res["back wall"]["span"]))
        # soffit*: the review's box. Projected through the camera it lies on the plaster web of the bay between the arches at
        # x=20 and 24. "true sof" is the soffit crown of the arch at x=20, whose face the ring box measures.
        print("TARGET3 ring/soffit luminance: review box (web) %.3f, true soffit %.3f (>=0.85)" % (
            res["ring"]["p50"] / res["soffit*"]["p50"], res["ring"]["p50"] / res["true sof"]["p50"]))

for name in ("wall_3_tiles.png", "wall_3_tiles_unalternated.png"):
    f = os.path.join(DIR, name)
    if os.path.exists(f):
        w = load(f)
        q = w.shape[1] / 900                    # the review's numbers are for a 900 px wide render; px below scale with it
        L = (w @ LUM)[int(75 * q):int(205 * q)]
        L = L - blur(L, 12 * q)
        L = L - L.mean(1, keepdims=True)
        out = []
        x0, n_x = int(20 * q), int(230 * q)
        for lag_m in (1.34, 2.0, 2.76, 4.0, 8.0):
            lag = int(round(lag_m * 72.5 * q))
            a = L[:, x0:x0 + n_x].ravel()
            b = L[:, x0 + lag:x0 + lag + n_x].ravel()
            if a.size == b.size:
                out.append("%.2f m %.3f" % (lag_m, np.corrcoef(a, b)[0, 1]))
        print("TARGET4", name, "autocorr:", ", ".join(out))

# from the exported GLB
d = open(os.path.join(ROOT, "godot/assets/crypt_kit/model/crypt_kit.glb"), "rb").read()
jl = struct.unpack_from("<I", d, 12)[0]
g = json.loads(d[20:20 + jl])
o = 20 + jl
b = d[o + 8:o + 8 + struct.unpack_from("<I", d, o)[0]]
tmp = os.path.join(DIR, "_x.png")
imgs = {}
for im in g["images"]:
    v = g["bufferViews"][im["bufferView"]]
    open(tmp, "wb").write(b[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]])
    imgs[im["name"]] = load(tmp)
os.remove(tmp)
A = json.load(open(os.path.join(HERE, "..", "atlas.json")))
print("TARGET2 mortar width %.2f cm (1.0-1.5; a6d7e65: 2.56 by the same definition, area of mortar / joint length)" % A["band_a_mortar_width_cm"])
print("TARGET2 courses per 2 m %d, stone length %s m" % (len(A["band_a_courses_m"]), A["band_a_stone_len_m"]))
# floor: longest run of a joint along a row or column, from the normal map (the joint is the steepest part of it)
nm = imgs["stone_floor_normal"]
s = np.hypot(nm[..., 0] - 0.5, nm[..., 1] - 0.5)
mask = s > np.percentile(s, 88)
best = 0
for m_ in (mask, mask.T):
    # a joint is allowed to wander 4 px: warp is not a turn
    wide = np.zeros_like(m_)
    for off in range(-4, 5):
        wide |= np.roll(m_, off, 0)
    for row in wide[::4]:
        z = np.concatenate([[0], row.astype(int), row.astype(int), [0]])
        ed = np.flatnonzero(np.diff(z))
        if len(ed):
            best = max(best, int((ed[1::2] - ed[::2]).max()))
print("TARGET7 floor longest straight joint: image %.2f m (normal map, +-4 px wander), built %.2f m (<=1.5)" % (
    min(best, 2048) / 256, A["floor_longest_straight_joint_m"]))
