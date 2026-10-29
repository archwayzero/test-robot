"""Small image helpers (Blender's python: numpy + OpenImageIO)."""
import numpy as np, OpenImageIO as oiio, sys
def load(p):
    b = oiio.ImageBuf(p); a = b.get_pixels(oiio.FLOAT); return a[..., :3].copy()
def save(p, a):
    a = np.clip(a, 0, 1); h, w = a.shape[:2]
    spec = oiio.ImageSpec(w, h, a.shape[2], oiio.UINT8); o = oiio.ImageOutput.create(p); o.open(p, spec)
    o.write_image((a * 255 + 0.5).astype(np.uint8)); o.close()
def grid_crop(src, out, x0, y0, x1, y1, k, step=10, major=50):
    a = load(src)[y0:y1, x0:x1]
    a = np.repeat(np.repeat(a, k, 0), k, 1).copy()
    h, w = a.shape[:2]
    for yy in range(y0 - y0 % step, y1, step):
        if yy < y0: continue
        r = (yy - y0) * k
        a[r, :, :] = (0, 1, 1) if yy % major == 0 else a[r, :, :] * 0.5 + np.array((0, 0.4, 0.4))
    for xx in range(x0 - x0 % step, x1, step):
        if xx < x0: continue
        c = (xx - x0) * k
        a[:, c, :] = (1, 1, 0) if xx % major == 0 else a[:, c, :] * 0.5 + np.array((0.4, 0.4, 0))
    save(out, a)
if __name__ == "__main__":
    a = load(sys.argv[1]); print(a.shape)
    if len(sys.argv) > 2:
        grid_crop(sys.argv[1], sys.argv[2], *[int(v) for v in sys.argv[3:8]])
