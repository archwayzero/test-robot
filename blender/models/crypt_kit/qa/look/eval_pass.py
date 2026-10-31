"""Pass metrics against v2, clean stone and the previous pass, on the frozen boxes. Regressions print with the aspect; not a fail.

  eval_pass.py <tag> <previous tag>      renders from .captures/t039/<tag>/{lit,flat}/, map stats from <tag>/maps.json"""
from common import *
import json

KS = [('spec_dist', 'spec', 1), ('crete', 'crete', 1), ('fine_over_coarse', 'f/c', -1), ('ml_mid', 'mid', 0), ('ml_span', 'span', 0),
      ('ml_fine', 'fine', 0), ('hist_emd', 'hist', 1), ('local', 'local', 0)]
MK = [('grad_interior_p99', 'gp99', -1), ('between_over_within', 'bt/wi', 0), ('neighbour_step_rel', 'nbr', 1), ('band2', 'b25-100', 1),
      ('k1', 'kurt1', 0), ('k2', 'kurt2', 0), ('joint_rise_10_90_cm', 'jrise', 1), ('fine13', 'fine1-3', -1)]


def mx(m):
    b = m['band_interior']
    m = dict(m, band2=(b[5] ** 2 + b[6] ** 2) ** .5, k1=m['kurt_interior'][0], k2=m['kurt_interior'][1], fine13=(b[0] ** 2 + b[1] ** 2) ** .5)
    return m


tag, prev = sys.argv[1], sys.argv[2]
banner("eval " + tag)
clean = clean_ref()
res = {}
rows = [("crypt_clean", "stone", clean)]
for t in ("base_v2", "base_v4", prev, tag):
    for rig, name in (("lit", "arcade_crypt_camera"), ("flat", "arcade_flat")):
        f = CAP / t / rig / (name + ".png")
        if f.exists():
            d = compare(measure(crop(R.rd(f), BOX)), clean)
            res["%s/%s" % (t, rig)] = {k: d[k] for k, _, _ in KS}
            rows.append((t, rig, d))
print('%-22s %-5s' % ('stone-only 145 px box', ''), *['%7s' % n for _, n, _ in KS], 'k0')
seen = set()
for t, rig, d in rows:
    if (t, rig) in seen:
        continue
    seen.add((t, rig))
    print('%-22s %-5s' % (t, rig), *['%7.4f' % d[k] for k, _, _ in KS], '%.2f' % d['kurt'][0])
if prev != tag:
    for rig in ("lit", "flat"):
        a, b = res.get("%s/%s" % (prev, rig)), res.get("%s/%s" % (tag, rig))
        if a and b:
            for k, n, sign in KS:
                if sign and sign * (b[k] - a[k]) > 0.15 * abs(a[k]):
                    print("REGRESSION >15%% %s %s: %.4f -> %.4f" % (rig, n, a[k], b[k]))
# map stats, band A
B = json.load(open(TRIAGE / "maps_builds.json"))
A = json.load(open(TRIAGE / "abl_all.json"))
M = {"v2": mx(B["v2"]), "v4": mx(B["v4"]), "v4_R": mx(A["v4.R_stain_tone_rim"])}
for t in (prev, tag):
    f = CAP / t / "maps.json"
    if f.exists():
        M[t] = mx(json.load(open(f)))
print('%-22s' % 'band A map', *['%8s' % n for _, n, _ in MK])
for t, m in M.items():
    print('%-22s' % t, *['%8.4f' % m[k] for k, _, _ in MK])
if prev in M and tag in M and prev != tag:
    for k, n, sign in MK:
        if sign and sign * (M[tag][k] - M[prev][k]) > 0.15 * abs(M[prev][k]):
            print("REGRESSION >15%% map %s: %.4f -> %.4f" % (n, M[prev][k], M[tag][k]))
f = CAP / tag / "maps.json"
if f.exists():
    x = json.load(open(f))
    print("plaster band C:", json.dumps(x.get("plaster")))
    print("courses linear luma:", x.get("course_linear"))
json.dump({"renders": res, "maps": {t: {k: m[k] for k, _, _ in MK} for t, m in M.items()}}, open(CAP / tag / "metrics.json", "w"), indent=1)
