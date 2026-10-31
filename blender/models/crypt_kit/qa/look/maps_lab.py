"""Run build.py's texture generator without Blender and write maps plus map stats. No geometry, no atlas.json.

  maps_lab.py <tag> [params.json]     .captures/t039/<tag>/tex/*.png and <tag>/maps.json

The PNGs are named like the kit's, so render_pass.py --tex can try them on the exported GLB."""
from common import *
import json
import os
import types
from unittest import mock
import OpenImageIO as oiio

BUILD = HERE.parents[1] / "build.py"


def wr(p, a):
    a = np.clip(a, 0, 1)
    s = oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8')
    o = oiio.ImageOutput.create(str(p))
    o.open(str(p), s)
    o.write_image((a * 255 + .5).astype(np.uint8))
    o.close()


def lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def plaster(a):
    "band C, as triage plaster.py"
    a = a[1500:1980, 300:1750].astype(np.float64)
    m = metrics.crop_metrics(a)
    l = a @ metrics.LUM
    return dict(mean=round(m['mean'], 3), std_rel=round(float(l.std() / l.mean()), 4), bands=[round(b, 4) for b in m['bands']],
                low32=round(float(metrics.px_bands(l, 6)[5].std() / l.mean()), 4))


def main():
    tag = sys.argv[1]
    params = sys.argv[2] if len(sys.argv) > 2 else None
    banner("maps " + tag)
    out = CAP / tag / "tex"
    out.mkdir(parents=True, exist_ok=True)
    src = BUILD.read_text().rstrip()
    assert src.endswith("main()")
    src = src[:-len("main()")]
    sys.modules.setdefault('bpy', mock.MagicMock())
    sys.modules.setdefault('bmesh', mock.MagicMock())
    saved = sys.argv
    sys.argv = ['x', '--', '--out-dir', str(CAP / tag / "scratch")] + (['--params', params] if params else [])
    ns = {'__name__': 'build', '__file__': str(BUILD)}
    exec(compile(src, str(BUILD), 'exec'), ns)
    sys.argv = saved
    maps, cap = {}, {}
    bf = ns['block_field']

    def to_image(name, arr, srgb):
        maps[name] = arr.astype(np.float32)
        return name

    def block_field(*a, **k):
        r = bf(*a, **k)
        cap[a[4]] = r
        return r
    ns['to_image'] = to_image
    ns['block_field'] = block_field
    ns['build_textures']()
    for n, a in maps.items():
        wr(out / (n + '.png'), a)
    ids, dist = cap[1501][0], cap[1501][1]
    a = maps['stone_ashlar_color'][12:1036].astype(np.float64)
    n = maps['stone_ashlar_normal'][12:1036].astype(np.float64)
    res = metrics.map_metrics(a, n, ids, dist, 512)
    res['plaster'] = plaster(maps['stone_ashlar_color'])
    edges = np.array(ns['COURSE_EDGES'])
    rows = (1024 * (1 - edges / 2.0)).astype(int)
    L = lin(a) @ metrics.LUM
    res['course_linear'] = [round(float(L[rows[c + 1] + 6:rows[c] - 6].mean()), 4) for c in range(len(edges) - 1)]
    json.dump(res, open(CAP / tag / "maps.json", "w"), indent=1)
    np.savez_compressed(CAP / tag / "ids_dist.npz", ids=ids, dist=dist.astype(np.float32))
    print("courses linear", res['course_linear'], "plaster", res['plaster'])


main()
