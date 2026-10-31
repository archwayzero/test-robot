#!/usr/bin/env python3
"""Render the frozen rig, one shot per job through the memory guard. Output .captures/t039/<tag>/{lit,flat}/, peaks in render_log.json.

  python3 blender/models/crypt_kit/qa/look/render_pass.py <tag> [--shots lit:close_wall,flat:arcade_flat] [--glb f] [--tex dir]

Default GLB: the exported kit. --tex swaps maps on that GLB's geometry (trial only)."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
tag = sys.argv[1]
a = sys.argv


def arg(n, d=None):
    return a[a.index(n) + 1] if n in a else d


ALL = ["lit:arcade_crypt_camera", "lit:close_wall", "lit:close_pier", "lit:close_web", "flat:arcade_flat", "flat:close_wall",
       "flat:close_pier", "flat:close_web"]
shots = arg("--shots", ",".join(ALL)).split(",")
glb = arg("--glb", str(ROOT / "godot/assets/crypt_kit/model/crypt_kit.glb"))
base = ROOT / ".captures/t039" / tag
logf = base / "render_log.json"
base.mkdir(parents=True, exist_ok=True)
log = json.loads(logf.read_text()) if logf.exists() else {}
for s in shots:
    rig, name = s.split(":")
    out = base / rig
    cmd = ["python3", "tools/qa/memguard.py", "--expect-peak-mb", "2000", "--", "blender", "-b", "--factory-startup", "--python-exit-code", "1",
           "-P", str(HERE / "rig.py"), "--", "--glb", glb, "--out", str(out), "--only", "arcade" if rig == "lit" else "flat"]
    cmd += ["--names", "crypt", "--closes", "none"] if name.startswith("arcade") else ["--names", "none", "--closes", name]
    if arg("--tex"):
        cmd += ["--tex", arg("--tex")]
    t = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"memguard: .*", r.stderr)
    print(s, "exit", r.returncode, "%.0fs" % (time.time() - t), m.group(0) if m else r.stderr[-300:], flush=True)
    if r.returncode:
        print(r.stdout[-800:])
        sys.exit(r.returncode)
    log[s] = m.group(0) if m else ""
    logf.write_text(json.dumps(log, indent=1))
