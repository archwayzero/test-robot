#!/usr/bin/env python3
"""Check the environment the agents will work in. Run it both in your WSL terminal and, via Claude,
inside the sandbox (ask Claude: "run python3 tools/envcheck.py").

  python3 tools/envcheck.py
Reports: tools on PATH, whether this command is network-isolated (i.e. sandboxed), whether ComfyUI answers,
and which device Godot renders with (always CPU inside the sandbox).
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from xdisplay import virtual_display  # noqa: E402

TOOLS = ["git", "python3", "dvc", "ffmpeg", "Xvfb", "blender", "godot", "claude", "gh", "bwrap", "socat"]


def run(cmd, env=None, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout + r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def godot_device(driver, method):
    godot = shutil.which("godot")
    if not godot:
        return "godot not on PATH"
    try:
        with tempfile.TemporaryDirectory() as d, virtual_display("320x240") as display:
            Path(d, "project.godot").write_text('config_version=5\n\n[application]\nrun/main_scene="res://p.tscn"\n')
            Path(d, "p.tscn").write_text('[gd_scene format=3]\n\n[node name="P" type="Node"]\n')
            env = dict(os.environ, DISPLAY=display)
            env.pop("WAYLAND_DISPLAY", None)
            _, out = run([godot, "--path", d, "--display-driver", "x11", "--rendering-driver", driver,
                          "--rendering-method", method, "--quit-after", "2", "--audio-driver", "Dummy"], env=env)
    except RuntimeError as e:
        return f"cannot start virtual display: {e}"
    line = next((l.strip() for l in out.splitlines() if "Using Device" in l), "")
    if driver == "vulkan" and "OpenGL" in line:
        return "NO Vulkan driver (fell back to OpenGL); install mesa-vulkan-drivers"
    if line:
        return line
    return "failed: " + (out.strip().splitlines()[-1][:160] if out.strip() else "no output")


def isolated():
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=3).close()
        return False
    except OSError:
        return True


def main():
    print("Tools:")
    for t in TOOLS:
        print(f"  {'ok ' if shutil.which(t) else 'MISSING'} {t}")
    iso = isolated()
    print(f"\nNetwork: {'isolated (looks sandboxed)' if iso else 'direct internet access (NOT sandboxed)'}")
    rc, out = run([sys.executable, "-I", str(Path(__file__).parent / "comfy" / "comfy_client.py"), "ping"], timeout=20)
    last = out.strip().splitlines()[-1][:160] if out.strip() else ""
    print(f"ComfyUI: {'reachable' if rc == 0 else 'NOT reachable: ' + last}")
    print(f"Godot OpenGL (fast captures):     {godot_device('opengl3', 'gl_compatibility')}")
    print(f"Godot Vulkan (accurate captures): {godot_device('vulkan', 'mobile')}")
    if shutil.which("nvidia-smi"):
        rc, out = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        print(f"GPU (outside the sandbox only): {out.strip() if rc == 0 else 'not visible here'}")


if __name__ == "__main__":
    main()
