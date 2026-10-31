#!/usr/bin/env python3
"""Script test of the replacement-map path (MAPS.md). Writes only under .captures/t015/maps_test/.

  python3 blender/models/crypt_kit/qa/test_replacement_maps.py

Makes a trivial set of maps, builds the kit from them into a scratch folder, exports, runs check_kit and check_budgets on the result,
then proves the maps arrived: band A and the floor equal the test files, the plaster band equals the generated one. Also proves
that a wrong size and an unknown file stop the build. Exit 1 on any failure.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
KIT = "blender/models/crypt_kit"
WORK = ROOT / ".captures/t015/maps_test"
GUARD = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--"]
BL = ["blender", "-b", "--python-exit-code", "1"]
HELP = f"{KIT}/qa/replacement_maps_helper.py"
GLB = WORK / "root/crypt_kit/model/crypt_kit.glb"


def run(cmd, want=0):
    cmd = cmd if cmd[0] == "python3" and "memguard" not in cmd[1] and "check_budgets" in cmd[1] else GUARD + cmd
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.startswith(("CHECK_KIT", "FAIL", "MAPS ", "SystemExit")) or "must be" in ln
            or "unknown files" in ln or "crypt_kit " in ln[:12]]
    print("rc", r.returncode, " ".join(str(c) for c in cmd[-6:]))
    print("\n".join("   " + ln[:150] for ln in tail))
    if (r.returncode != 0) != (want != 0):
        print(r.stdout[-2000:] + r.stderr[-1000:])
        sys.exit(1)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "in").mkdir(parents=True)
    GLB.parent.mkdir(parents=True)
    run(BL + ["--factory-startup", "-P", HELP, "--", "make", str(WORK / "in")])
    build = BL + ["--factory-startup", "-P", f"{KIT}/build.py", "--", "--out-dir", str(WORK / "kit")]
    # the two refusals
    bad = WORK / "bad"
    bad.mkdir()
    (bad / "stone_ashlr_color.png").write_bytes(b"")
    run(build + ["--maps", str(bad)], want=1)
    (bad / "stone_ashlr_color.png").unlink()
    run(BL + ["--factory-startup", "-P", HELP, "--", "small", str(bad)])
    run(build + ["--maps", str(bad)], want=1)
    # the real one
    run(build + ["--maps", str(WORK / "in")])
    run(BL + [str(WORK / "kit/crypt_kit_model.blend"), "-P", "tools/blender/export_gltf.py", "--", "--out", str(GLB), "--no-anim"])
    run(BL + ["--factory-startup", "-P", f"{KIT}/qa/check_kit.py", "--", "--glb", str(GLB), "--atlas", str(WORK / "kit/atlas.json")])
    run(BL + ["--factory-startup", "-P", HELP, "--", "verify", str(WORK / "in"), str(GLB)])
    run(["python3", "tools/qa/check_budgets.py", "--root", str(WORK / "root"), "--json", str(WORK / "budgets.json")])
    print("REPLACEMENT MAPS PASS")


main()
