"""Step A: reference landmark sheet for reference/hero/full_body.png (hand-picked on 5-8x pixel-grid crops g_*.png,
plus mask-based thickness). Writes reference_landmarks.json + reference_landmarks.png.
Image coords: x right (= character's BACK), y down. Scale: hood top y=8.0, ground (bottom of the planted flat tine)
y=801.0 -> 793 px = 1.75 m. Run with Blender's python (numpy + OpenImageIO)."""
import json, math, sys
import numpy as np
sys.path.insert(0, "/home/archwayzero/game/blender/models/hero/qa")
from imgtool import load, save
R = "/home/archwayzero/game/"
OUT = R + ".captures/T011/v4/"
TOP, GROUND = 8.0, 801.0
PPM = (GROUND - TOP) / 1.75

# ------------------------------------------------------------------ hand-picked landmarks (px)
L = {
 "near": {   # drawn in front: plate R (x 100-185, the near hand lies over it), knee pod B, rear (lifted) foot
  "hip_disc_centre": (113, 402),          # hip joint estimate (disc on the outer hip, also on the Tripo mesh)
  "plate_front_edge": [(102, 470), (107, 510), (112, 550)],
  "plate_back_edge": [(160, 442), (170, 510), (184, 575)],
  "plate_top_y": 395,                     # under the hand/pelvis belt (estimated)
  "plate_bottom_edge": [(147, 583), (184, 576)],   # front part hidden behind the knee pod
  "plate_segment_lines": [[(120, 468), (160, 466)], [(130, 520), (170, 510)]],
  "knee_pod_outline": [(115, 551), (113, 558), (116, 575), (118, 590), (125, 602), (140, 596), (136, 575), (128, 556)],
  "knee_centre": (143, 592),
  "shin_front_edge": [(118, 590), (129, 607), (140, 614), (155, 622), (170, 640), (180, 650), (190, 660), (205, 668)],
  "shin_back_edge": [(169, 590), (174, 600), (179, 611), (182, 626), (186, 633), (194, 640), (206, 660), (214, 666)],
  "hock": (180, 637),                     # shin -> metatarsal (outer tine strand starts on the back here)
  "spring": [(212, 666), (228, 685)],     # bbox of the coil
  "ankle": (222, 681),                    # spring bottom, inner tine root
  "tines": {
   "outer": [(190, 635), (204, 650), (215, 658), (225, 662), (240, 666), (255, 667), (270, 667), (280, 668), (290, 672),
             (300, 679), (308, 688), (313, 697), (315, 703), (313, 712), (309, 722), (303, 732), (296, 742), (288, 752),
             (280, 761), (270, 770), (258, 777), (244, 782), (230, 786), (214, 789)],
   "middle": [(214, 668), (225, 664), (240, 668), (255, 669), (270, 669), (282, 671), (292, 676), (301, 683), (307, 692),
              (311, 700), (311, 707), (306, 717), (300, 730), (293, 742), (286, 752), (278, 762), (268, 771), (262, 775)],
   "inner": [(226, 679), (240, 675.5), (250, 675), (260, 676), (270, 681), (281, 691), (290, 701), (294, 711),
             (295, 720), (294, 733), (290, 743), (287, 751)],
  },
 },
 "far": {    # behind: plate F (front x 62-110, rear part hidden), knee pod A, front (planted) foot
  "plate_front_edge": [(62, 435), (67, 500), (71, 550)],
  "knee_pod_outline": [(58, 545), (57, 550), (62, 570), (70, 590), (78, 600), (80, 580), (72, 556)],
  "knee_centre": (85, 596),
  "shin_front_edge": [(70, 600), (84, 620), (98, 636), (108, 654), (118, 670), (134, 688)],
  "shin_back_edge": [(108, 600), (110, 620), (116, 640), (126, 656), (136, 674), (142, 690)],
  "hock": (113, 645),
  "spring": [(134, 686), (146, 701)],
  "ankle": (141, 699),
  "tines": {
   "outer": [(118, 643), (127, 658), (131, 664), (139, 673), (150, 681), (160, 686), (170, 689), (181, 691), (191, 694),
             (201, 699), (210, 704), (219, 716), (223, 726), (225, 734), (222, 746), (216, 758), (208, 768), (196, 778),
             (186, 786), (176, 793), (166, 798), (158, 800), (140, 800), (120, 800), (104, 800)],
   "middle": [(132, 683), (140, 684), (150, 685), (160, 689), (170, 692), (181, 694), (191, 697), (200, 702), (208, 708),
              (215, 718), (219, 728), (219, 740), (213, 756), (205, 768), (195, 778), (186, 786), (180, 790)],
   "inner": [(143, 697), (150, 696), (160, 696), (170, 698), (180, 703), (190, 710), (197, 720), (200, 730), (201, 742),
             (200, 754), (196, 766), (190, 776), (184, 781)],
  },
 },
}

def z_m(y): return (GROUND - y) / PPM
def dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
def ang_v(a, b):   # angle of a->b from vertical (deg), + = going back (image right) while going down
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
def plen(p): return sum(dist(p[i], p[i - 1]) for i in range(1, len(p)))

mask = np.load(OUT + "ref_mask.npy")

def perp_thickness(a, b, t, maxr=40):
    """mask run length (px) perpendicular to a->b at fraction t, through the axis point (side view)"""
    ax, ay = a; bx, by = b
    px, py = ax + (bx - ax) * t, ay + (by - ay) * t
    L_ = math.hypot(bx - ax, by - ay); nx, ny = -(by - ay) / L_, (bx - ax) / L_
    def inside(s):
        x, y = int(round(px + nx * s)), int(round(py + ny * s))
        return mask[y, x]
    lo = 0
    while lo > -maxr and inside(lo - 0.5): lo -= 0.5
    hi = 0
    while hi < maxr and inside(hi + 0.5): hi += 0.5
    return hi - lo + 1.0

LUM = img_l = load(R + "reference/hero/full_body.png").mean(2)

def tine_thickness(path, i):
    """FWHM (px) of the dark dip across the tine at path[i] (bilinear luminance profile, 0.25 px steps)"""
    a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
    p = path[i]
    L_ = dist(a, b); nx, ny = -(b[1] - a[1]) / L_, (b[0] - a[0]) / L_
    def lum(x, y):
        x0_, y0_ = int(math.floor(x)), int(math.floor(y)); fx, fy = x - x0_, y - y0_
        q = LUM[y0_:y0_ + 2, x0_:x0_ + 2]
        return (q[0, 0] * (1 - fx) * (1 - fy) + q[0, 1] * fx * (1 - fy) + q[1, 0] * (1 - fx) * fy + q[1, 1] * fx * fy)
    ss = np.arange(-7, 7.01, 0.25)
    prof = np.array([lum(p[0] + nx * s_ + 0.5, p[1] + ny * s_ + 0.5) for s_ in ss])
    bg = np.median(np.r_[prof[:6], prof[-6:]])
    dark = bg - prof
    ic = int(np.argmax(dark[12:-12])) + 12              # darkest sample near the picked point
    half = dark[ic] / 2
    lo = ic
    while lo > 0 and dark[lo - 1] > half: lo -= 1
    hi = ic
    while hi < len(ss) - 1 and dark[hi + 1] > half: hi += 1
    return (hi - lo + 1) * 0.25

out = {"scale": {"image": "reference/hero/full_body.png", "hood_top_y": TOP, "ground_y": GROUND, "px_per_m": round(PPM, 2),
                 "note": "x right = character's back; f = forward of the ankle (towards the face), dz = above the ankle"},
       "which_is_near": "near = the leg drawn in front: thigh plate R (x 100-185) with the near hand over it, knee pod B "
                        "over plate R, shin to the spring at (222,681), rear foot slightly lifted (tip y 789). far = plate F "
                        "(x 62-110, partly hidden), pod A, planted front foot with the flat ground run (y 800). "
                        "(full_body.md / turnaround NOTES call the planted foot the near one; the occlusion says otherwise.)",
       "landmarks_px": L}

for leg in ("near", "far"):
    d = L[leg]; K, J, A = d["knee_centre"], d["hock"], d["ankle"]
    m = {}
    m["shin_len_m"] = dist(K, J) / PPM
    m["meta_len_m"] = dist(J, A) / PPM
    m["knee_to_ankle_m"] = dist(K, A) / PPM
    m["shin_angle_from_vertical_deg"] = ang_v(K, J)
    m["meta_angle_from_vertical_deg"] = ang_v(J, A)
    m["hock_angle_deg"] = ang_v(J, A) - ang_v(K, J)   # + = metatarsal more slanted back than the shin
    m["knee_z_m"] = z_m(K[1]); m["hock_z_m"] = z_m(J[1]); m["ankle_z_m"] = z_m(A[1])
    if "hip_disc_centre" in d:
        Hp = d["hip_disc_centre"]
        m["hip_z_m"] = z_m(Hp[1])
        m["thigh_len_m"] = dist(Hp, K) / PPM
        m["thigh_angle_from_vertical_deg"] = ang_v(Hp, K)
        m["knee_angle_deg"] = ang_v(K, J) - ang_v(Hp, K)  # shin slant relative to the thigh (0 = straight)
    else:   # far hip hidden: thigh direction from the plate front edge
        e = d["plate_front_edge"]
        m["thigh_angle_from_vertical_deg (plate edge)"] = ang_v(e[0], e[-1])
        m["knee_angle_deg (vs plate edge)"] = ang_v(K, J) - ang_v(e[0], e[-1])
    m["shin_thickness_m"] = {f"{int(t*100)}%": perp_thickness(K, A, t) / PPM for t in (0.25, 0.5, 0.85)}
    # foot, relative to the ankle, in H = ankle height above the foot's lowest point
    low = max(p[1] for p in d["tines"]["outer"] + d["tines"]["middle"] + d["tines"]["inner"])
    H = low - A[1]
    m["H_px"] = H; m["H_m"] = H / PPM
    foot = {}
    for name, path in d["tines"].items():
        rel = [((A[0] - x) / H, (A[1] - y) / H) for x, y in path]     # (forward, up) in H
        ia = None
        # arch top: flattest point (min |slope|) of the descending upper part, before the rearmost point
        irear = min(range(len(rel)), key=lambda i: rel[i][0])
        best = None
        for i in range(1, irear):
            dx = rel[i + 1][0] - rel[i - 1][0]; dy = rel[i + 1][1] - rel[i - 1][1]
            s = abs(dy / dx) if dx else 9e9
            if best is None or s < best: best, ia = s, i
        ilow = max(range(len(rel)), key=lambda i: (-rel[i][1], -i))
        ilow = min(i for i in range(len(rel)) if rel[i][1] <= rel[ilow][1] + 0.01)   # first ground point
        foot[name] = {"root": rel[0], "arch_top": rel[ia], "rearmost": rel[irear], "lowest": rel[ilow], "tip": rel[-1],
                      "path_len_H": plen(path) / H,
                      "thickness_m": {"root_third": tine_thickness(path, max(2, len(path) // 4)) / PPM,
                                      "mid": tine_thickness(path, len(path) // 2) / PPM,
                                      "tip_third": tine_thickness(path, len(path) * 3 // 4) / PPM}}
    m["foot_H"] = foot
    out[leg] = m

# pose consistency: best rigid rotation about the ankle mapping the near foot onto the far foot
P = np.array([out["near"]["foot_H"][t][k] for t in ("outer", "middle", "inner") for k in ("root", "arch_top", "rearmost", "tip")])
Q = np.array([out["far"]["foot_H"][t][k] for t in ("outer", "middle", "inner") for k in ("root", "arch_top", "rearmost", "tip")])
best = None
for deg in np.arange(-30, 30.01, 0.25):
    r = math.radians(deg); M = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]])
    res = np.sqrt(((P @ M.T - Q) ** 2).sum(1)).mean()
    if best is None or res < best[1]: best = (deg, res)
out["foot_pose_check"] = {"near_to_far_rotation_deg": best[0], "mean_landmark_residual_H": round(best[1], 3),
                          "note": "the two feet are the same shape up to a pitch about the ankle -> foot shape is pose-invariant"}
# plates (near, side view) and widths from the front view (legs_000.png, 496 px/m, AI view, approximate)
pf, pb = L["near"]["plate_front_edge"], L["near"]["plate_back_edge"]
out["plate"] = {"depth_side_m": {"z0.66 (y 500)": (168 - 105) / PPM, "z0.55 (y 550)": (180 - 112) / PPM,
                                 "bottom (y 578)": (184 - 114) / PPM},
                "width_front_m (legs_000)": {"upper": 0.13, "bottom": 0.10},
                "segment_lines_z_m": [z_m(467), z_m(515)],
                "bottom_z_m": {"back": z_m(576), "front (behind pod)": z_m(585)},
                "near_thigh_angle_from_vertical_deg (front/back edges)": [ang_v(pf[0], pf[-1]), ang_v(pb[0], pb[-1])]}
out["shin_width_front_m (legs_000, approx)"] = {"knee bulb": 0.08, "mid": 0.035, "bottom": 0.035}
out["tine_width_front_m (legs_000, approx)"] = 0.014

# landmarks that cannot be measured: the middle tine's upper part runs hidden behind the outer tine (one line),
# so its arch top is not visible (its traced upper points are an estimate); check_legs.py reports it as N/A
out["not_measurable"] = {"middle.arch_top": "hidden behind the outer tine in both feet (single line in the image)"}

# targets used by check_legs.py (rest pose: neutral; pose-dependent thigh angle not compared)
n, f = out["near"], out["far"]
out["targets"] = {
 "thigh_len_m": n["thigh_len_m"], "shin_len_m": (n["shin_len_m"] + f["shin_len_m"]) / 2,
 "meta_len_m": (n["meta_len_m"] + f["meta_len_m"]) / 2,
 "knee_angle_deg": n["knee_angle_deg"], "hock_angle_deg": n["hock_angle_deg"],
 "shin_thickness_m": {k: n["shin_thickness_m"][k] for k in n["shin_thickness_m"]},
 "foot_H_source": "far (planted) foot: the rest pose stands on the ground",
 "foot_H": f["foot_H"], "H_m": f["H_m"],
}

def rnd(o):
    if isinstance(o, float): return round(o, 4)
    if isinstance(o, (list, tuple)): return [rnd(x) for x in o]
    if isinstance(o, dict): return {k: rnd(v) for k, v in o.items()}
    return o
json.dump(rnd(out), open(OUT + "reference_landmarks.json", "w"), indent=1)

# ------------------------------------------------------------------ annotated overlay (3x, lower body)
img = load(R + "reference/hero/full_body.png")
k = 3; x0, y0, x1, y1 = 30, 370, 340, 807
a = np.repeat(np.repeat(img[y0:y1, x0:x1], k, 0), k, 1).copy()
def dot(p, col, r=3):
    cx, cy = int((p[0] - x0) * k), int((p[1] - y0) * k)
    a[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1] = col
def line(p, q, col):
    n_ = int(max(abs(q[0] - p[0]), abs(q[1] - p[1])) * k) + 1
    for i in range(n_ + 1):
        t = i / n_; dot((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), col, 0)
def poly(ps, col):
    for i in range(1, len(ps)): line(ps[i - 1], ps[i], col)
COL = {"near": (1, 0.2, 0.2), "far": (0.2, 0.6, 1)}
TC = {"outer": (1, 1, 0), "middle": (0.2, 1, 0.3), "inner": (1, 0.3, 1)}
for leg, d in L.items():
    c = COL[leg]
    for key in ("plate_front_edge", "plate_back_edge", "shin_front_edge", "shin_back_edge", "knee_pod_outline", "plate_bottom_edge"):
        if key in d: poly(d[key], c)
    for s in d.get("plate_segment_lines", []): poly(s, (1, 0.6, 0))
    if "hip_disc_centre" in d:
        dot(d["hip_disc_centre"], (1, 1, 1), 5); line(d["hip_disc_centre"], d["knee_centre"], (1, 1, 1))
    line(d["knee_centre"], d["hock"], (1, 1, 1)); line(d["hock"], d["ankle"], (1, 1, 1))
    for p in (d["knee_centre"], d["hock"], d["ankle"]): dot(p, (1, 1, 1), 5); dot(p, c, 3)
    for t, path in d["tines"].items():
        poly(path, TC[t])
        dot(path[0], TC[t], 4); dot(path[-1], TC[t], 4)
for yy, col in ((GROUND, (0, 1, 0)), (GROUND - out["far"]["H_px"], (0, 1, 0))):
    r = int((yy - y0) * k)
    if 0 <= r < a.shape[0]: a[r, ::4] = col
save(OUT + "reference_landmarks.png", a)
print(json.dumps(rnd({k_: out[k_] for k_ in ("targets", "foot_pose_check", "plate")}), indent=1))
for leg in ("near", "far"):
    print(leg, json.dumps(rnd({k_: v for k_, v in out[leg].items() if k_ != "foot_H"})))
