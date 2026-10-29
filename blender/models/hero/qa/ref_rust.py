"""Sample the near thigh plate of full_body.png: rust fraction (same classifier as conform.py) and tones (linear)."""
import sys, numpy as np
sys.path.insert(0, "/home/archwayzero/game/blender/models/hero/qa")
from imgtool import load
a = load("/home/archwayzero/game/reference/hero/full_body.png")   # sRGB values 0..1
reg = a[470:568, 118:178].reshape(-1, 3)
rust = (reg[:, 0] > 0.16) & (reg[:, 0] > 1.7 * reg[:, 2])
lin = np.where(reg <= 0.04045, reg / 12.92, ((reg + 0.055) / 1.055) ** 2.4)
lum = lin @ np.array([0.2126, 0.7152, 0.0722])
r = lin[rust]; rl = lum[rust]; o = np.argsort(rl)
print("rust fraction", round(rust.mean(), 3), "n", len(reg))
print("rust lo (median lower half)", np.median(r[o[:len(o)//2]], 0).round(4), "rust hi (median top 30%)", np.median(r[o[int(len(o)*.7):]], 0).round(4))
print("metal median", np.median(lin[~rust], 0).round(4))
# patch size: mean run length of rust along rows (px) -> m at 453 px/m
m = rust.reshape(98, 60); runs = []
for row in m:
    c = 0
    for v in row:
        if v: c += 1
        elif c: runs.append(c); c = 0
    if c: runs.append(c)
print("mean rust run length px", round(np.mean(runs), 1), "->", round(np.mean(runs) / 453 * 100, 1), "cm")
