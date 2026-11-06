"""T044: horizontal cross-sections of hero_model.blend as one PNG grid (top view, front = +Y up in the image).
usage: blender -b <blend> -P slices.py -- <out.png> z1,z2,... [cx cy halfrange]  colours: body grey, legs orange, cloak cyan/white"""
import bpy, bmesh, sys, numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]
out, zs = argv[0], [float(z) for z in argv[1].split(",")]
CX, CY, R = (float(argv[2]), float(argv[3]), float(argv[4])) if len(argv) > 4 else (0.0, 0.0, 0.40)
o = bpy.data.objects["hero"]; me = o.data
bm = bmesh.new(); bm.from_mesh(me)
S = 320                   # px per tile; R = half range (m), CX/CY = tile centre
cols = int(np.ceil(len(zs) / 2)) if len(zs) > 4 else len(zs)
rows = int(np.ceil(len(zs) / cols))
img = np.zeros((rows * S, cols * S, 4), np.float32); img[..., 3] = 1
mg = o.vertex_groups.get("cloak_mantle"); cg = o.vertex_groups.get("cloak_gray")
def vcol(v):
    for g in me.vertices[v.index].groups:
        if mg and g.group == mg.index: return (1, 1, 1)
        if cg and g.group == cg.index: return (0.2, 0.9, 1)
    return None
DIG = {"0": ["111","101","101","101","111"], "1": ["010","110","010","010","111"], "2": ["111","001","111","100","111"],
       "3": ["111","001","111","001","111"], "4": ["101","101","111","001","001"], "5": ["111","100","111","001","111"],
       "6": ["111","100","111","101","111"], "7": ["111","001","001","001","001"], "8": ["111","101","111","101","111"],
       "9": ["111","101","111","001","111"], ".": ["000","000","000","000","010"]}
for k, z in enumerate(zs):
    oy, ox = (k // cols) * S, (k % cols) * S
    # grid lines every 10 cm
    for g in np.arange(-R, R + 1e-6, 0.1 if R > 0.2 else 0.02):
        p = int((g + R) / (2 * R) * (S - 1))
        img[oy + p, ox:ox + S, :3] = 0.15; img[oy:oy + S, ox + p, :3] = 0.15
    img[oy:oy + S, ox, :3] = 0.6; img[oy, ox:ox + S, :3] = 0.6
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - z) * (b.z - z) >= 0: continue
        for f in e.link_faces:
            pts = []
            for e2 in f.edges:
                c, d = e2.verts[0].co, e2.verts[1].co
                if (c.z - z) * (d.z - z) < 0:
                    pts.append(c.lerp(d, (z - c.z) / (d.z - c.z)))
            if len(pts) != 2: continue
            col = vcol(e.verts[0]) or ((0.9, 0.5, 0.1) if f.material_index == 1 else (0.6, 0.6, 0.6))
            for t in np.linspace(0, 1, 12):
                p = pts[0].lerp(pts[1], t)
                x = int((p.x - CX + R) / (2 * R) * (S - 1)); y = int((R - p.y + CY) / (2 * R) * (S - 1))
                if 0 <= x < S and 0 <= y < S:
                    img[oy + y, ox + x, :3] = col
    s = f"{z:.2f}"
    for i, ch in enumerate(s):
        for r_, row in enumerate(DIG[ch]):
            for c_, bit in enumerate(row):
                if bit == "1":
                    img[oy + 4 + r_ * 3:oy + 7 + r_ * 3, ox + 4 + (i * 4 + c_) * 3:ox + 7 + (i * 4 + c_) * 3, :3] = 1
im = bpy.data.images.new("sl", cols * S, rows * S, alpha=True)
im.pixels.foreach_set(np.flipud(img).ravel())
im.filepath_raw = out; im.file_format = "PNG"; im.save()
print("saved", out)
