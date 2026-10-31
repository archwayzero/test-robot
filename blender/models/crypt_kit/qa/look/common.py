"""T039 frozen evaluation: paths, the rig + metric hash, the frozen boxes and metric definitions.

Frozen on first commit (exposure 0.85, Filmic Very High Contrast, 96 samples, the crypt.jpg camera, the triage boxes). Never
change camera, lights, exposure, view transform, boxes or metric definitions without reporting it and taking a new baseline: the
hash printed on every run covers these files.
Run with Blender's Python (it has numpy and OpenImageIO), through the guard.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np                 # noqa: E402
import metrics                     # noqa: E402
import rmetrics_lib as R           # noqa: E402

ROOT = HERE.parents[4]
CAP = ROOT / ".captures/t039"
TRIAGE = ROOT / ".captures/t015_triage"
REF = ROOT / "reference/map/crypt.jpg"
FROZEN = ("rig.py", "metrics.py", "rmetrics_lib.py", "common.py")
CLEAN = (1350, 724, 1495, 869)     # px in crypt.jpg, 145 px, stone only: no statue, no cast shadow (eval_triage.py)
BOX = (873, 478, 1018, 623)        # 145 px, back wall centre, render px (eval_triage.py)
SHOTS = {"lit": ["arcade_crypt_camera", "close_wall", "close_pier", "close_web"],
         "flat": ["arcade_flat", "close_wall", "close_pier", "close_web"]}


def rig_hash():
    h = hashlib.sha256()
    for f in FROZEN:
        h.update((HERE / f).read_bytes())
    return h.hexdigest()[:12]


def L(c):
    return c @ metrics.LUM


def localc(l, w=9):
    k = np.ones(w) / w
    bl = lambda a: np.apply_along_axis(lambda r: np.convolve(r, k, 'same'), 0, np.apply_along_axis(lambda r: np.convolve(r, k, 'same'), 1, a))
    m = bl(l)
    s = np.sqrt(np.maximum(bl(l * l) - m * m, 0))
    e = w
    return float(np.median((s / (m + 1e-6))[e:-e, e:-e]))


def shape(b):
    e = np.log2(np.array(b))
    return e - e.mean()


def measure(c):
    """eval_triage.py m(): every metric of one stone-only crop."""
    d = metrics.crop_metrics(c)
    l = L(c)
    d.update({('ml_' + k): float(v) for k, v in R.ml(c).items()})
    d['crete'] = float(R.crete(l))
    d['local'] = localc(l)
    d['q'] = np.percentile(l / np.median(l), np.arange(1, 100)).tolist()
    return d


def compare(d, clean):
    d['spec_dist'] = float(np.linalg.norm(shape(d['bands']) - shape(clean['bands'])))
    d['hist_emd'] = float(np.abs(np.array(d['q']) - np.array(clean['q'])).mean())
    return d


def crop(a, box):
    x0, y0, x1, y1 = box
    return a[y0:y1, x0:x1]


def clean_ref():
    return compare(measure(crop(R.rd(REF), CLEAN)), measure(crop(R.rd(REF), CLEAN)))


def banner(what):
    print("T039 %s  rig+metrics %s  exposure 0.85 (lit), Standard 0 (flat)" % (what, rig_hash()), flush=True)
