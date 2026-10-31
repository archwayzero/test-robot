"""Blender side of test_replacement_maps.py: numpy and an image codec.

  make <folder>        trivial test maps + stones.json
  small <folder>       one map of the wrong size
  verify <folder> <glb>  the GLB carries the test maps, and the generated plaster band
"""
import json
import os
import struct
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = json.load(open(os.path.join(HERE, "..", "atlas.json")))
argv = sys.argv[sys.argv.index("--") + 1:]


def save(path, a):
    h, w = a.shape[:2]
    im = bpy.data.images.new("o", w, h, alpha=False)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.flipud(a)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw, im.file_format = path, "PNG"
    im.save()
    bpy.data.images.remove(im)


def load(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return np.flipud(px.reshape(h, w, 4))[..., :3]


def make(out):
    rng = np.random.RandomState(4)
    ppm = ATLAS["band_a_px_per_m"]
    edges = ATLAS["band_a_course_edges_m"]
    h, w = 1024, 2048
    alb, nrm, orm = np.zeros((h, w, 3)), np.zeros((h, w, 3)), np.zeros((h, w, 3))
    nrm[...] = (0.5, 0.5, 1.0)
    orm[...] = (1.0, 0.85, 0.0)
    stones = []
    cap = sorted(v for s in ATLAS["capital_stones_m"] for v in s[:2])
    for c in range(len(edges) - 1):
        joints = np.array(cap + [2.9, 3.35]) if c == len(edges) - 2 else \
            np.sort(np.mod(rng.uniform(0, 4) + np.cumsum(rng.uniform(0.55, 0.95, 5)), 4.0))
        r0, r1 = int(h - edges[c + 1] * ppm), int(h - edges[c] * ppm)
        px = (np.arange(w) + 0.5) / ppm
        idx = np.searchsorted(joints, px) % len(joints)
        tone = 1.0 + rng.uniform(-0.12, 0.12, len(joints))
        tone -= tone.mean() - 1.0
        d_head = np.abs(px[:, None] - joints[None, :]).min(1)
        d_head = np.minimum(d_head, 4.0 - np.abs(px[:, None] - joints[None, :]).max(1))
        for r in range(r0, r1):
            d_bed = min(r - r0 + 0.5, r1 - r - 0.5) / ppm
            joint = np.minimum(d_head, d_bed) < 0.006
            alb[r] = np.array([0.72, 0.60, 0.42])[None, :] * tone[idx][:, None] * np.where(joint, 0.6, 1.0)[:, None]
            nrm[r, :, 0] = np.where(joint, 0.45, 0.5)
            orm[r, :, 0] = np.where(joint, 0.5, 1.0)
        for a, b in zip(joints, np.append(joints[1:], joints[0] + 4.0)):
            stones.append([float(a), float(b), float(edges[c]), float(edges[c + 1])])
    save(os.path.join(out, "ashlar_band_a_color.png"), alb)
    save(os.path.join(out, "ashlar_band_a_normal.png"), nrm)
    save(os.path.join(out, "ashlar_band_a_orm.png"), orm)
    yy, xx = np.mgrid[0:1024, 0:1024] * 2 * np.pi / 1024
    v = 0.55 + 0.06 * np.sin(5 * xx) * np.sin(3 * yy) + 0.03 * np.sin(17 * xx + 11 * yy)
    save(os.path.join(out, "stone_floor_color.png"), np.dstack([v, 0.92 * v, 0.8 * v]))
    json.dump(stones, open(os.path.join(out, "stones.json"), "w"))


def glb_images(path):
    d = open(path, "rb").read()
    jl = struct.unpack_from("<I", d, 12)[0]
    g = json.loads(d[20:20 + jl])
    o = 20 + jl
    b = d[o + 8:o + 8 + struct.unpack_from("<I", d, o)[0]]
    out = {}
    tmp = path + ".png"
    for im in g["images"]:
        v = g["bufferViews"][im["bufferView"]]
        open(tmp, "wb").write(b[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]])
        out[im["name"]] = load(tmp)
    os.remove(tmp)
    return out


def verify(folder, glb):
    imgs = glb_images(glb)
    r0, r1 = ATLAS["band_a_rows"]
    a = np.abs(imgs["stone_ashlar_color"][r0:r1] - load(os.path.join(folder, "ashlar_band_a_color.png"))).max()
    f = np.abs(imgs["stone_floor_color"] - load(os.path.join(folder, "stone_floor_color.png"))).max()
    root = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
    live = load(os.path.join(root, "blender/models/crypt_kit/textures/stone_ashlar_color.png"))
    c0 = ATLAS["band_c_rows"][0]
    p = np.abs(imgs["stone_ashlar_color"][c0:] - live[c0:]).max()
    print("MAPS band A differs by %.4f, floor %.4f, plaster band from the generated one %.4f" % (a, f, p))
    if max(a, f, p) > 2.5 / 255:
        sys.exit(1)


if argv[0] == "make":
    make(argv[1])
elif argv[0] == "small":
    save(os.path.join(argv[1], "stone_floor_color.png"), np.ones((64, 64, 3)) * 0.5)
else:
    verify(argv[1], argv[2])
