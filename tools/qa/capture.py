#!/usr/bin/env python3
"""Render a Godot scene and save screenshots so an agent can SEE the result. Works inside the sandbox.

  python3 tools/qa/capture.py --scene res://modules/<m>/internal/<scene>.tscn
        [--frames 60] [--every 15] [--mode accurate|fast] [--resolution 960x540] [--out .captures/<name>]

Godot Movie Maker at a fixed 30 fps, on a private virtual display (tools/xdisplay.py). CPU rendering:
  --mode accurate  the project's own renderer (Mobile for iOS) on Vulkan via Mesa lavapipe. Right look, slower. Default.
  --mode fast      Compatibility renderer on OpenGL via Mesa llvmpipe. Layout / presence / timing checks;
                   lighting and materials differ from iOS.
Output: frame PNGs, contact_sheet.png, capture.json (device used). .captures/ is gitignored.
Frame rate here says NOTHING about iPhone performance. Never report it as such.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scope_lib import repo_root  # noqa: E402
from xdisplay import virtual_display  # noqa: E402

CPU_MARKERS = ("llvmpipe", "lavapipe", "softpipe", "swiftshader")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--mode", choices=("accurate", "fast"), default="accurate")
    ap.add_argument("--resolution", default="960x540")
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    root = repo_root()
    godot = shutil.which("godot") or sys.exit("godot not on PATH")
    if not re.fullmatch(r"\d+x\d+", a.resolution):
        sys.exit("--resolution must look like 960x540")
    if not a.scene.startswith("res://"):
        sys.exit("--scene must be a res:// path inside godot/")
    if not (root / "godot" / a.scene[len("res://"):]).exists():
        sys.exit(f"scene not found: godot/{a.scene[len('res://'):]}")
    out = Path(a.out) if a.out else root / ".captures" / Path(a.scene).stem
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    if a.mode == "fast":
        args = ["--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    else:
        project = (root / "godot" / "project.godot").read_text(errors="ignore")
        m = re.search(r'renderer/rendering_method(?:\.mobile)?="([^"]+)"', project)
        args = ["--rendering-driver", "vulkan", "--rendering-method", m.group(1) if m else "mobile"]

    with tempfile.TemporaryDirectory() as tmp, virtual_display(a.resolution) as display:
        env = dict(os.environ, DISPLAY=display)
        env.pop("WAYLAND_DISPLAY", None)
        cmd = [godot, "--path", str(root / "godot"), *args, "--display-driver", "x11", "--resolution", a.resolution,
               "--fixed-fps", "30", "--disable-vsync", "--audio-driver", "Dummy",
               "--write-movie", str(Path(tmp) / "frame.png"), "--quit-after", str(a.frames), a.scene,
               "--", "--automation"]  # test-run mode: Core.automation available, user:// data under automation/
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout, env=env)
        except subprocess.TimeoutExpired:
            sys.exit(f"timed out after {a.timeout}s (CPU rendering: lower --frames or --resolution)")
        log = r.stdout + r.stderr
        frames = sorted(Path(tmp).glob("frame*.png"))
        if not frames:
            print(log[-3000:], file=sys.stderr)
            sys.exit("Godot produced no frames (see log above)")
        kept = []
        for i, f in enumerate(frames):
            if i % max(1, a.every) == 0 or i == len(frames) - 1:
                dest = out / f"f{i:04d}.png"
                shutil.copy(f, dest)
                kept.append(dest.name)

    device = next((l.strip() for l in log.splitlines() if "Using Device" in l or re.match(r"^(OpenGL|Vulkan) API", l.strip())), "unknown")
    fell_back = a.mode == "accurate" and "OpenGL" in device
    info = {"scene": a.scene, "mode": a.mode, "device": device,
            "cpu_rendered": any(m in device.lower() for m in CPU_MARKERS),
            "accurate_fell_back_to_opengl": fell_back, "frames_rendered": len(frames),
            "kept": kept, "errors": [l for l in log.splitlines() if "ERROR" in l][:20]}
    if shutil.which("ffmpeg") and kept:
        cols = min(4, len(kept))
        rows = -(-len(kept) // cols)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(out / "f*.png"),
                        "-vf", f"scale=480:-1,tile={cols}x{rows}", "-frames:v", "1", str(out / "contact_sheet.png")])
    (out / "capture.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))
    if fell_back:
        print("WARNING: no Vulkan driver (install mesa-vulkan-drivers); Godot fell back to OpenGL. "
              "These images do NOT show the iOS renderer.")
    if info["errors"]:
        print("Godot printed errors during the run (listed above). Treat the capture as suspect.")


if __name__ == "__main__":
    main()
