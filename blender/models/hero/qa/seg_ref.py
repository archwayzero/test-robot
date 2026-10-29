import numpy as np, sys
sys.path.insert(0, "/home/archwayzero/game/blender/models/hero/qa")
from imgtool import load, save
R = "/home/archwayzero/game/"
a = load(R + "reference/hero/full_body.png")
H, W, _ = a.shape
lum = a.mean(2)
# background model: quadratic surface fitted to obvious bg pixels (right strip + left strip + top-right)
yy, xx = np.mgrid[0:H, 0:W]
sel = np.zeros((H, W), bool)
sel[:, 370:] = True; sel[:, :20] = True; sel[700:, 330:] = True; sel[:300, 250:] = True
sel[:380, :40] = True
def feats(x, y):
    x = x / W; y = y / H
    return np.stack([np.ones_like(x), x, y, x*x, x*y, y*y, x**3, y**3, x*x*y, x*y*y], -1)
A = feats(xx[sel].astype(float), yy[sel].astype(float))
bg = np.zeros_like(a)
for c in range(3):
    coef, *_ = np.linalg.lstsq(A, a[..., c][sel], rcond=None)
    bg[..., c] = feats(xx.astype(float), yy.astype(float)) @ coef
d = np.abs(a - bg).max(2)
print("bg residual on sel: p50 %.4f p99 %.4f max %.4f" % (np.percentile(d[sel], 50), np.percentile(d[sel], 99), d[sel].max()))
thr = float(sys.argv[1]) if len(sys.argv) > 1 else 0.06
m = d > thr
np.save(R + ".captures/T011/v6/ref_mask.npy", m)
vis = a.copy(); vis[m] = vis[m] * 0.4 + np.array((1, 0, 0)) * 0.6
save(R + ".captures/T011/v6/ref_mask.png", vis)
rows = np.where(m.any(1))[0]; print("mask rows", rows.min(), rows.max())
for y in range(780, 807):
    xs = np.where(m[y])[0]
    if len(xs): print(y, xs.min(), xs.max(), len(xs))
