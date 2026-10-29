"""Overlay a reference-aligned side render (RGBA, 414x807) on reference/hero/full_body.png.
usage: python overlay.py <render.png> <out_prefix>  -> <out>_overlay.png (semi-transparent), <out>_sbs.png,
<out>_lower.png (3x crop with silhouettes) and prints the silhouette IoU of the leg region (rows >= ROW0)."""
import sys, numpy as np, OpenImageIO as oiio
sys.path.insert(0, "/home/archwayzero/game/blender/models/hero/qa")
from imgtool import load, save
R = "/home/archwayzero/game/"
ROW0 = 400            # below the pelvis armour (plate tops, hip disc centre is at y 402)
ref = load(R + "reference/hero/full_body.png")
b = oiio.ImageBuf(sys.argv[1]); rgba = b.get_pixels(oiio.FLOAT)
mod, alpha = rgba[..., :3], rgba[..., 3]
out = sys.argv[2]
rm = np.load(R + ".captures/T011/v7/ref_mask.npy").copy()
# close small holes in the reference mask row/col-wise (gaps <= 3 px between foreground pixels)
for axis in (0, 1):
    m = rm if axis == 1 else rm.T
    for r in range(m.shape[0]):
        xs = np.where(m[r])[0]
        if len(xs) > 1:
            gaps = np.where((np.diff(xs) > 1) & (np.diff(xs) <= 4))[0]
            for g in gaps: m[r, xs[g]:xs[g + 1]] = True
rm[792:] = False                       # floor shadow band: keep only the tine contact rows
H, W = rm.shape
gm0 = alpha > 0.5
# align on the upper body (rows 8..380: hood, torso, backpack, arms): best horizontal shift of the model
best = None
for dx in range(-40, 41):
    g = np.roll(gm0, dx, axis=1)
    i_ = (rm[8:380] & g[8:380]).sum() / max(1, (rm[8:380] | g[8:380]).sum())
    if best is None or i_ > best[1]: best = (dx, i_)
DX = int(sys.argv[3]) if len(sys.argv) > 3 else best[0]
gm = np.roll(gm0, DX, axis=1); alpha = np.roll(alpha, DX, axis=1); mod = np.roll(mod, DX, axis=1)
import json
json.dump({"dx_px": DX, "upper_iou": round(float(best[1]), 4)}, open(R + ".captures/T011/v7/align.json", "w"))
print(f"upper-body alignment shift {DX} px (upper IoU {best[1]:.4f})")
reg = np.zeros_like(rm); reg[ROW0:792] = True
inter = (rm & gm & reg).sum(); union = ((rm | gm) & reg).sum()
iou = inter / union
# overlay: model at 50 % over the reference
comp = ref * (1 - 0.5 * alpha[..., None]) + mod * 0.5 * alpha[..., None]
for y in (int(GY) for GY in (801, 8)):
    if y < H: comp[y, ::2] = (0, 1, 0)
comp[ROW0, ::4] = (1, 0.5, 0)
save(out + "_overlay.png", comp)
# silhouette diff: green = both, red = reference only, blue = model only
sil = ref * 0.35
sil[rm & gm] = (0.2, 0.8, 0.2); sil[rm & ~gm] = (0.9, 0.15, 0.15); sil[~rm & gm] = (0.2, 0.4, 1.0)
sil[ROW0, ::4] = (1, 0.5, 0)
bgc = np.array((0.30, 0.30, 0.30))
modc = mod * alpha[..., None] + bgc * (1 - alpha[..., None])
save(out + "_sbs.png", np.concatenate([ref, modc, sil], 1))
crop = lambda a: np.repeat(np.repeat(a[380:807, 30:340], 2, 0), 2, 1)
save(out + "_lower.png", np.concatenate([crop(comp), crop(sil)], 1))
print(f"IoU(leg region rows {ROW0}-791) = {iou:.4f}  ref px {int((rm & reg).sum())} model px {int((gm & reg).sum())}")
