"""Pass sheet: previous pass, current pass, v2, crypt.jpg, on identical pixels (renders) and stone-only crops (photo). Never overwrites.

  before_after.py pass<N> <previous tag>   writes .captures/t039/pass<N>/before_after.png and mag_{wall,pier,web}_{lit,flat}.png"""
from common import *
import OpenImageIO as oiio

G5 = {'0': '3E5149453E', '1': '00427F4000', '2': '4261514946', '3': '2141454B31', '4': '1814127F10', '5': '2745454539', '6': '3C4A494930', '7': '0171090503', '8': '3649494936', '9': '064949291E',
      'A': '7E1111117E', 'B': '7F49494936', 'C': '3E41414122', 'D': '7F4141221C', 'E': '7F49494941', 'F': '7F09090901', 'G': '3E4149497A', 'H': '7F0808087F', 'I': '00417F4100', 'J': '2040413F01', 'K': '7F08142241', 'L': '7F40404040', 'M': '7F020C027F', 'N': '7F0408107F', 'O': '3E4141413E', 'P': '7F09090906', 'Q': '3E4151215E', 'R': '7F09192946', 'S': '4649494931', 'T': '01017F0101', 'U': '3F4040403F', 'V': '1F2040201F', 'W': '3F4038403F', 'X': '6314081463', 'Y': '0708700807', 'Z': '6151494543',
      '.': '0060600000', '+': '08083E0808', '-': '0808080808', ',': '0050300000', '_': '4040404040', ' ': '0000000000', ':': '0036360000', 'x': '2214081422'}


def wr(p, a):
    a = np.clip(a, 0, 1)
    s = oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8')
    o = oiio.ImageOutput.create(str(p))
    o.open(str(p), s)
    o.write_image((a * 255 + .5).astype(np.uint8))
    o.close()


def label(a, t):
    k = 3
    H = 7 * k + 12
    o = np.vstack([np.zeros((H, a.shape[1], 3)), a])
    x = 8
    for ch in t.upper():
        g = bytes.fromhex(G5.get(ch, G5[' ']))
        for i, col in enumerate(g):
            for j in range(7):
                if col >> j & 1:
                    o[6 + j * k:6 + (j + 1) * k, x + i * k:x + (i + 1) * k] = (1, 1, .6)
        x += 6 * k
    return o


def rs(a, w, h):
    b = oiio.ImageBuf(oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'float'))
    b.set_pixels(oiio.ROI(0, a.shape[1], 0, a.shape[0], 0, 1, 0, 3), a.astype(np.float32))
    r = oiio.ImageBufAlgo.resize(b, roi=oiio.ROI(0, w, 0, h, 0, 1, 0, 3))
    return r.get_pixels(oiio.FLOAT).reshape(h, w, 3).astype(np.float64)


def nn(a, k):
    return np.repeat(np.repeat(a, k, 0), k, 1)


def fit(a, w, h):
    o = np.zeros((h, w, 3))
    a = a[:h, :w]
    o[:a.shape[0], :a.shape[1]] = a
    return o


tag, prev = sys.argv[1], sys.argv[2]
banner("before_after " + tag)
d = CAP / tag
if (d / "before_after.png").exists():
    raise SystemExit("before_after.png exists: passes are never overwritten")
ref = R.rd(REF)
k = ref.shape[1] / 2000
COL = [(prev, prev), (tag, tag), ("base_v2", "v2")]
PW, PH = 750, 500
refp = fit(rs(ref, PW, ref.shape[0] * PW // ref.shape[1]), PW, PH)
rows = []
for rig, name in (("lit", "arcade_crypt_camera"), ("flat", "arcade_flat"), ("lit", "close_wall"), ("lit", "close_pier"), ("lit", "close_web"),
                  ("flat", "close_wall"), ("flat", "close_pier"), ("flat", "close_web")):
    r = [label(rs(R.rd(CAP / t / rig / (name + ".png")), PW, PH), "%s %s %s" % (lab, rig, name)) for t, lab in COL]
    r.append(label(refp, "crypt.jpg"))
    rows.append(np.hstack(r))
# magnified: identical render pixels, x3 nearest; photo: stone-only crop, x3 nearest
RB = {'wall': (850, 450, 1050, 650), 'pier': (500, 590, 620, 790), 'web': (620, 90, 900, 180)}
PB = {'wall': (1350, 724, 1495, 869), 'pier': (int(565 * k), int(884 * k), int(599 * k), int(1082 * k)), 'web': (int(1005 * k), int(169 * k), int(1097 * k), int(197 * k))}
CB = {'wall': (450, 300, 1050, 700), 'pier': (450, 300, 1050, 700), 'web': (450, 300, 1050, 700)}
for n in RB:
    x0, y0, x1, y1 = RB[n]
    z = 2 if n == 'web' else 3
    W, H = (x1 - x0) * z, (y1 - y0) * z
    for rig, far in (("lit", "arcade_crypt_camera"), ("flat", "arcade_flat")):
        T = [label(nn(R.rd(CAP / t / rig / (far + ".png"))[y0:y1, x0:x1], z), "%s far %s %s x%d" % (lab, n, rig, z)) for t, lab in COL]
        a, b, c, e = PB[n]
        T.append(label(fit(nn(ref[b:e, a:c], z), W, H), "crypt stone only x%d" % z))
        cx0, cy0, cx1, cy1 = CB[n]
        C = [label(nn(R.rd(CAP / t / rig / ("close_%s.png" % n))[cy0:cy1, cx0:cx1], 1), "%s close %s %s 1:1" % (lab, n, rig)) for t, lab in COL]
        S = np.hstack(T)
        Z = np.hstack(C)
        w = max(S.shape[1], Z.shape[1])
        M = np.vstack([fit(S, w, S.shape[0]), fit(Z, w, Z.shape[0])])
        wr(d / ("mag_%s_%s.png" % (n, rig)), M)
        rows.append(fit(M, 3000, M.shape[0]) if M.shape[1] <= 3000 else M[:, :3000])
wr(d / "before_after.png", np.vstack([fit(r, 3000, r.shape[0]) for r in rows]))
print("wrote", d / "before_after.png")
