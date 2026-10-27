#!/usr/bin/env python3
"""Run a command under a memory guard (Linux/WSL). Owner: orchestrator.

  python3 tools/qa/memguard.py [--expect-peak-mb N] [--spare-mb 4096] [--floor-mb 4096] [--log FILE] -- <cmd...>

- Before starting: refuses (exit 75) unless MemAvailable - expected peak >= spare (default 4 GB spare).
- While running: samples MemAvailable and the job's process-tree RSS every second; if MemAvailable drops below
  --floor-mb, kills the whole process tree (exit 137) so a runaway job cannot take down the session.
- After: prints one line to stderr: `memguard: exit=.. killed=.. duration=..s peak_drop=..MB peak_rss=..MB`.
- Exit code: the command's exit code (or 75 refused / 137 killed).
Measured peaks on the dev machine (28 GB, 2026-10-26): Godot capture (accurate) ~0.5 GB, Godot 20 s recording
~0.3 GB, headless test suites < 0.1 GB, Godot --import ~0.6 GB, Blender Cycles CPU render/bake
~1.2 GB (use --expect-peak-mb 2000).
"""
import argparse
import os
import signal
import subprocess
import sys
import time


def mem_available_mb() -> int:
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    return 0


def tree(pid: int) -> list[int]:
    out = subprocess.run(["ps", "-e", "-o", "pid=,ppid="], capture_output=True, text=True).stdout.split("\n")
    kids: dict[int, list[int]] = {}
    for line in out:
        p = line.split()
        if len(p) == 2:
            kids.setdefault(int(p[1]), []).append(int(p[0]))
    res, stack = [], [pid]
    while stack:
        q = stack.pop()
        res.append(q)
        stack += kids.get(q, [])
    return res


def tree_rss_mb(pid: int) -> int:
    total = 0
    for p in tree(pid):
        try:
            with open(f"/proc/{p}/statm") as f:
                total += int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except OSError:
            pass
    return total // (1024 * 1024)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-peak-mb", type=int, default=1024)
    ap.add_argument("--spare-mb", type=int, default=4096)
    ap.add_argument("--floor-mb", type=int, default=4096)
    ap.add_argument("--log", default="")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("missing command after --")
    base = mem_available_mb()
    if base - a.expect_peak_mb < a.spare_mb:
        print(f"memguard: refused: available {base} MB - expected peak {a.expect_peak_mb} MB < spare {a.spare_mb} MB. "
              "Wait for running jobs to finish.", file=sys.stderr)
        return 75
    out = open(a.log, "w") if a.log else None
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT if out else None, start_new_session=True)
    min_avail, peak_rss, killed = base, 0, False
    while proc.poll() is None:
        avail = mem_available_mb()
        min_avail = min(min_avail, avail)
        peak_rss = max(peak_rss, tree_rss_mb(proc.pid))
        if avail < a.floor_mb:
            killed = True
            for p in reversed(tree(proc.pid)):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
            break
        time.sleep(1)
    code = proc.wait()
    print(f"memguard: exit={code} killed={killed} duration={time.time() - t0:.0f}s baseline_avail={base}MB "
          f"peak_drop={base - min_avail}MB peak_rss={peak_rss}MB", file=sys.stderr)
    return 137 if killed else code


if __name__ == "__main__":
    sys.exit(main())
