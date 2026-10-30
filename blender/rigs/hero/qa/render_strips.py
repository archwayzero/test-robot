"""Side-view review strips: reference frames (top row) vs. our clip at the same phase (bottom row).

  python3 tools/qa/memguard.py --expect-peak-mb 2000 -- blender -b blender/rigs/hero/hero_rig.blend \
      -P blender/rigs/hero/qa/render_strips.py [-- --out .captures/T013/strips] [--clips a,b]

Camera = the reference camera: orthographic, character's left side, facing image-left (snapshot azimuth 270).
Phase mapping (reference 24 fps source frame -> our 30 fps frame) is listed in PAIRS; reference frame files are
frames/frame_NNNN.png with NNNN = src/2 + 1. Left/right legs cannot be told apart in the references.
"""
import os
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else ".captures/T013/strips"
ONLY = argv[argv.index("--clips") + 1].split(",") if "--clips" in argv else None
REF = "reference/hero"
CELL = 360

# clip: [(ref_src_frame_24fps, our_frame), ...]; event names in comments follow each NOTES.md
PAIRS = {
    # contact A 31 -> our 0 (left strike); stride 44 src frames = our 24 frames
    "walk_loop": [(30, 23), (34, 2), (38, 4), (44, 7), (52, 11), (66, 19)],
    # contact A 2 -> our 0; stride 16 src = our 18
    "jog_loop": [(2, 0), (4, 2), (6, 4), (10, 9), (12, 11), (14, 13)],
    # contact A 14 -> our 0 (left strike, wide stance); step 23 src = our 12 (0.8 s cycle): rear lift 18 -> 2,
    # passing 24 -> 6, contact B 38 -> 12, rear lift 42 -> 14, passing 48 -> 18
    "crouch_walk_loop": [(14, 0), (18, 2), (24, 6), (38, 12), (42, 14), (48, 18)],
    # leg extended back (src 0) -> our 19 (left knee at the back end of stance); 104 src = our 36
    "crawl_loop": [(0, 19), (10, 22), (20, 26), (36, 31), (52, 1), (70, 7)],
    # game-timed jump (clip starts at launch): push-off extension 26 -> 0, blades off 28 -> 1, apex 34 -> 11,
    # descent 42 -> 19, contact 46 -> 25, compression 54 -> 29, settled 80 -> 38
    "jump": [(26, 0), (28, 1), (34, 11), (42, 19), (46, 25), (54, 29), (80, 38)],
    "idle_loop": [(0, 0), (20, 20), (48, 48), (82, 80)],
    "crouch_idle_loop": [(60, 0), (80, 40), (100, 80), (122, 120)],
    "crawl_idle_loop": [(0, 0), (40, 30), (80, 60), (122, 90)],
}
CENTER = {"crawl_loop": (0.15, 0.40, 1.6), "crawl_idle_loop": (0.15, 0.40, 1.6)}

sc = bpy.context.scene
arm = bpy.data.objects["Armature"]
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light, sh.color_type = "STUDIO", "MATERIAL"
sc.render.resolution_x = sc.render.resolution_y = CELL
cam_d = bpy.data.cameras.new("strip_cam")
cam_d.type = "ORTHO"
cam = bpy.data.objects.new("strip_cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam.rotation_euler = (1.5707963, 0, -1.5707963)   # looking +X (from the character's left side)
# floor strip so contact is visible
bpy.ops.mesh.primitive_plane_add(size=1)
floor = bpy.context.active_object
floor.scale = (0.4, 6.0, 1.0)
floor.location = (0.6, 0, -0.002)


def load_px(path):
    im = bpy.data.images.load(os.path.abspath(path))
    w, h = im.size
    px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return px


def fit(px, cw, ch):
    h, w = px.shape[:2]
    s = min(cw / w, ch / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    yi = (np.arange(nh) / s).astype(int).clip(0, h - 1)
    xi = (np.arange(nw) / s).astype(int).clip(0, w - 1)
    small = px[yi][:, xi]
    out = np.ones((ch, cw, 4), np.float32) * np.array([0.15, 0.15, 0.15, 1.0], np.float32)
    oy, ox = (ch - nh) // 2, (cw - nw) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out


os.makedirs(OUT, exist_ok=True)
for clip, pairs in PAIRS.items():
    if ONLY and clip not in ONLY:
        continue
    act = bpy.data.actions[clip]
    arm.animation_data.action = act
    arm.animation_data.action_slot = act.slots[0]
    cy, cz, scale = CENTER.get(clip, (0.0, 0.88, 2.0))
    cam_d.ortho_scale = scale
    cam.location = (-5.0, cy, cz)
    ref_row, our_row = [], []
    for src, ours in pairs:
        ref_png = f"{REF}/{clip}/frames/frame_{src // 2 + 1:04d}.png"
        ref_row.append(fit(load_px(ref_png), CELL, int(CELL * 0.75)) if os.path.exists(ref_png)
                       else np.zeros((int(CELL * 0.75), CELL, 4), np.float32))
        sc.frame_set(ours)
        p = os.path.join(OUT, f"_{clip}_{ours:03d}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        our_row.append(load_px(p))
        os.remove(p)
    # rows are stored bottom-up in Blender pixel order: ours at the bottom, reference on top
    canvas = np.concatenate([np.concatenate(our_row, axis=1), np.concatenate(ref_row, axis=1)], axis=0)
    h, w = canvas.shape[:2]
    img = bpy.data.images.new(f"strip_{clip}", w, h, alpha=False)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = os.path.join(OUT, f"{clip}_strip.png")
    img.file_format = "PNG"
    img.save()
    print("strip", img.filepath_raw, "pairs", pairs)
