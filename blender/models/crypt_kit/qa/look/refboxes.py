"""Reference audit: measure stone-only boxes on crypt.jpg (refboxes_triage.py boxes) and store each crop, 1:1 and x4, under
.captures/t039/refboxes/. Every target must cite one of these crops."""
from common import *
import json
import OpenImageIO as oiio


def wr(p, a):
    a = np.clip(a, 0, 1)
    s = oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8')
    o = oiio.ImageOutput.create(str(p))
    o.open(str(p), s)
    o.write_image((a * 255 + .5).astype(np.uint8))
    o.close()


banner("refboxes")
ref = R.rd(REF)
k = ref.shape[1] / 2000
out = CAP / "refboxes"
out.mkdir(parents=True, exist_ok=True)
B = {'void_old_target_with_statue': (1130, 620, 1450, 900), 'clean_R': (1305, 700, 1445, 840), 'clean_R2': (1345, 720, 1445, 820),
     'void_clean_L_cast_shadow': (1135, 650, 1205, 720), 'void_pier_crosses_arris': (560, 880, 690, 1190),
     'void_web_crosses_groin': (760, 110, 1100, 200), 'pier_lit_face': (565, 884, 599, 1082), 'web_one_surface': (1005, 169, 1097, 197)}
res = {}
print('%-30s %5s %4s %5s %4s | p50 span mid fine | f/c crete k0 blue%%' % ('box', 'x0', 'y0', 'x1', 'y1'))
for n, b in B.items():
    x0, y0, x1, y1 = [int(v * k) for v in b]
    c = ref[y0:y1, x0:x1]
    m = R.one(ref, b, k)
    blue = float((c[..., 2] > c[..., 0]).mean() * 100)
    res[n] = dict(px=[x0, y0, x1, y1], p50=m['ml_p50'], span=m['ml_span'], mid=m['ml_mid'], fine=m['ml_fine'], fc=m['fine_over_coarse'],
                  crete=m['crete'], k0=m['kurt'][0], blue=blue)
    print('%-30s %5d %4d %5d %4d | %.3f %.3f %.4f %.4f | %.2f %.3f %.2f %.1f' % (n, x0, y0, x1, y1, m['ml_p50'], m['ml_span'], m['ml_mid'],
                                                                              m['ml_fine'], m['fine_over_coarse'], m['crete'], m['kurt'][0], blue))
    wr(out / (n + '.png'), c)
    wr(out / (n + '_x4.png'), np.repeat(np.repeat(c, 4, 0), 4, 1))
json.dump(res, open(out / 'refboxes.json', 'w'), indent=1)
