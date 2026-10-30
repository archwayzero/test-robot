"""Tile images into a grid with Blender's image API (no PIL in this environment).
blender -b --factory-startup -P compose.py -- --out sheet.png --cols 6 --cell 400x400 img1.png img2.png ... ("-" = blank)
"""
import sys
import bpy
import numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]
def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d
out = arg("--out"); cols = int(arg("--cols", 6)); cw, ch = [int(x) for x in arg("--cell", "400x400").split("x")]
skip = {argv.index(k) for k in ("--out", "--cols", "--cell") if k in argv}
files = [a for i, a in enumerate(argv) if i not in skip and (i - 1) not in skip]
rows = (len(files) + cols - 1) // cols
canvas = np.ones((rows * ch, cols * cw, 4), np.float32)
for k, f in enumerate(files):
    if f == "-":
        continue
    im = bpy.data.images.load(f)
    im.scale(cw, ch)
    px = np.array(im.pixels[:], np.float32).reshape(ch, cw, 4)
    r, c = k // cols, k % cols
    canvas[(rows - 1 - r) * ch:(rows - r) * ch, c * cw:(c + 1) * cw] = px
    bpy.data.images.remove(im)
img = bpy.data.images.new("sheet", cols * cw, rows * ch, alpha=False)
img.pixels.foreach_set(canvas.ravel())
img.filepath_raw = out; img.file_format = "PNG"; img.save()
print("wrote", out)
