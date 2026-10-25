#!/usr/bin/env python3
"""Record a short gameplay video for the human to review, without them running any game code.

  python3 tools/qa/record.py --scene res://tests/e2e/<playthrough>.tscn --seconds 20
        [--mode accurate|fast] [--resolution 960x540] [--out docs/qa/videos/<milestone>/<name>.mp4]

Runs the scene (normally a scripted playthrough driven through core's automation API) in Godot's Movie Maker at a
fixed 30 fps on a private virtual display inside the sandbox, then converts it to an MP4 any video player opens.
Movie Maker renders every frame, so the video plays smoothly at real speed even though CPU rendering takes longer
than real time to record. Use the resolution/orientation from docs/specs/PLATFORM.md (e.g. 540x960 for portrait).
The MP4 is a binary: `dvc add` it before committing (docs/qa/videos/ is in the qa agent's scope).
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

FPS = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--mode", choices=("accurate", "fast"), default="accurate")
    ap.add_argument("--resolution", default="960x540")
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    root = repo_root()
    godot = shutil.which("godot") or sys.exit("godot not on PATH")
    ffmpeg = shutil.which("ffmpeg") or sys.exit("ffmpeg not on PATH")
    if not re.fullmatch(r"\d+x\d+", a.resolution):
        sys.exit("--resolution must look like 960x540")
    if not 1 <= a.seconds <= 300:
        sys.exit("--seconds must be between 1 and 300")
    if not a.scene.startswith("res://") or not (root / "godot" / a.scene[len("res://"):]).exists():
        sys.exit(f"scene not found: {a.scene}")
    out = Path(a.out) if a.out else root / ".captures" / "videos" / (Path(a.scene).stem + ".mp4")
    out = out.resolve()
    if root.resolve() not in out.parents:
        sys.exit("--out must be inside the repository")
    out.parent.mkdir(parents=True, exist_ok=True)

    if a.mode == "fast":
        args = ["--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    else:
        project = (root / "godot" / "project.godot").read_text(errors="ignore")
        m = re.search(r'renderer/rendering_method(?:\.mobile)?="([^"]+)"', project)
        args = ["--rendering-driver", "vulkan", "--rendering-method", m.group(1) if m else "mobile"]
    frames = int(a.seconds * FPS)

    with tempfile.TemporaryDirectory() as tmp, virtual_display(a.resolution) as display:
        env = dict(os.environ, DISPLAY=display)
        env.pop("WAYLAND_DISPLAY", None)
        avi = Path(tmp) / "movie.avi"
        cmd = [godot, "--path", str(root / "godot"), *args, "--display-driver", "x11", "--resolution", a.resolution,
               "--fixed-fps", str(FPS), "--disable-vsync", "--write-movie", str(avi), "--quit-after", str(frames),
               a.scene]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout, env=env)
        except subprocess.TimeoutExpired:
            sys.exit(f"timed out after {a.timeout}s (CPU rendering: shorten --seconds or lower --resolution)")
        log = r.stdout + r.stderr
        if not avi.exists() or avi.stat().st_size == 0:
            print(log[-3000:], file=sys.stderr)
            sys.exit("Godot produced no video (see log above)")
        enc = subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", str(avi), "-c:v", "libx264", "-preset",
                              "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                              "-movflags", "+faststart", str(out)], capture_output=True, text=True)
        if enc.returncode != 0:
            sys.exit("ffmpeg failed: " + enc.stderr[-1500:])

    device = next((l.strip() for l in log.splitlines() if "Using Device" in l), "unknown")
    info = {"scene": a.scene, "video": str(out.relative_to(root.resolve())), "seconds": a.seconds, "fps": FPS,
            "resolution": a.resolution, "mode": a.mode, "device": device,
            "accurate_fell_back_to_opengl": a.mode == "accurate" and "OpenGL" in device,
            "errors": [l for l in log.splitlines() if "ERROR" in l][:20]}
    out.with_suffix(".json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))
    if info["accurate_fell_back_to_opengl"]:
        print("WARNING: no Vulkan driver; recorded with OpenGL. This does NOT show the iOS renderer's look.")
    if info["errors"]:
        print("Godot printed errors during the recording (listed above): mention them in the report.")


if __name__ == "__main__":
    main()
