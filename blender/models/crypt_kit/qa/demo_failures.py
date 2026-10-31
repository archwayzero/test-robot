#!/usr/bin/env python3
"""Failure demonstration: run check_kit.py on every altered copy (make_bad_copies.py) and show that each one fails on the check
it was made to break. Exit 1 if a copy passes, or fails only on other checks.

  python3 blender/models/crypt_kit/qa/demo_failures.py [first last]

first and last index the table, so that the demonstration can run in parts of under 3 minutes.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BAD = ROOT / ".captures/t015/bad"
CHECK = "blender/models/crypt_kit/qa/check_kit.py"
GUARD = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--"]
INTENDED = {
    "renamed_node": "exactly the seven root nodes",
    "moved_origin": "arch origin/transform identity",
    "wall_collision_off_1cm": "wall collision",
    "crouch_underside_low": "ceiling_crouch underside",
    "vault_crown_high": "vault crown",
    "web_flush_crown": "ring proud of web at the crown",
    "web_sunk_haunch": r"ring proud at \d+ deg",
    "wall_top_old": "wall top",
    "extra_draw_call": "draw calls",
    "no_soiling": "wall has height-varying COLOR_0",
    "floor_no_collision": "floor has a -colonly child",
    "third_material": "<= 2 materials",
    "uv2_overlap": "wall UV2 non-overlapping",
    "ashlar_seam_broken": "stone_ashlar_color band A wrap V / bed joint",
    "groin_landing_low": "visible groin landing",
    "rubble_flat": "ceiling_crouch underside has depth steps",
    "pier_behind_wall": "pier shaft 1-3 mm proud",
    "pier_collision_wide": "pier shaft collision exactly 0.6",
    "floor_not_tileable": "stone_floor_color edge seam",
    "wall_split_moved": "wall face f split on every bed joint",
    "wall_v_off_course": "V follows the course heights",
    "wall_u_not_atlas": "wall U offsets equal atlas.json",
    "wall_diff_whole_metre": "wall face difference stays off whole metres",
    "wall_diff_same": "wall face differences spread",
    "wall_two_metre_repeat": "lags 1-7 m",
    "wall_joints_aligned": "wall head joints do not line up",
    "ashlar_course_dark": "no course stripes",
    "ceiling_dark_crevice": "ceiling_crouch COLOR_0 crevice",
    "ceiling_big_facet": "ceiling_crouch largest facet",
    "ceiling_gap": "ceiling_crouch visible underside to collision",
    "ceiling_side_deep": "ceiling_crouch side set back",
    "ceiling_plates": "ceiling_crouch no plates",
    "ceiling_crack": "ceiling_crouch closed surface",
}


def main():
    wrong = 0
    missing = sorted(set(INTENDED) ^ {p.stem for p in BAD.glob("*.glb")} - {"pier_sunk"})
    if missing:
        print("copies and table differ:", missing)
        wrong += 1
    table = list(INTENDED.items())
    if len(sys.argv) == 3:
        table = table[int(sys.argv[1]):int(sys.argv[2])]
    for name, want in table:
        r = subprocess.run(GUARD + ["blender", "-b", "--factory-startup", "--python-exit-code", "1", "-P", CHECK, "--", "--glb",
                                    str(BAD / (name + ".glb")), "--no-exit-code"], cwd=ROOT, capture_output=True, text=True)
        fails = [re.sub(r"\s+", " ", ln[5:]).strip() for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
        hit = [f for f in fails if re.search(want, f)]
        print("%-4s %-24s %2d failed; intended [%s]: %s" % ("ok" if hit else "MISS", name, len(fails), want, hit[0][:120] if hit else fails[:3]))
        wrong += not hit
    print("FAILURE DEMO %s: %d copies, %d wrong" % ("PASS" if not wrong else "FAIL", len(table), wrong))
    sys.exit(1 if wrong else 0)


main()
