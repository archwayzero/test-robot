#!/usr/bin/env python3
"""Private virtual display for rendering inside Claude Code's sandbox.

The sandbox blocks Unix sockets and gives each command its own private loopback network, so the usual
xvfb-run (Unix socket) does not work there; /tmp is also read-only, so Xvfb runs with -nolock (no
/tmp/.X<N>-lock file). This starts Xvfb listening only on TCP loopback and returns a DISPLAY like 127.0.0.1:N. Rendering is on the CPU (Mesa llvmpipe for OpenGL, lavapipe for Vulkan): sandboxed
commands cannot see the GPU.
"""
import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time


def _free_display():
    for n in range(90, 140):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", 6000 + n)) != 0:
                return n
    raise RuntimeError("no free X display number")


@contextlib.contextmanager
def virtual_display(resolution="960x540"):
    if not shutil.which("Xvfb"):
        raise RuntimeError("Xvfb not installed (sudo apt install xvfb)")
    n = _free_display()
    proc = subprocess.Popen(["Xvfb", f":{n}", "-screen", "0", f"{resolution}x24", "-listen", "tcp",
                             "-nolisten", "unix", "-nolisten", "local", "-ac", "-nolock"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("Xvfb exited: " + proc.stderr.read().decode(errors="ignore")[-500:])
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", 6000 + n)) == 0:
                break
        time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("Xvfb did not start")
    # Mesa's shader cache defaults to ~/.cache, which is read-only in the sandbox.
    os.environ.setdefault("MESA_SHADER_CACHE_DIR", os.path.join(tempfile.gettempdir(), "mesa_shader_cache"))
    try:
        yield f"127.0.0.1:{n}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
