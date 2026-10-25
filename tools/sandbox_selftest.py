#!/usr/bin/env python3
"""Verify, from INSIDE Claude Code's sandbox, that the protections are really active. Non-destructive:
it only checks permissions and tries connections; it never modifies a protected file.

Ask Claude to run:  python3 tools/sandbox_selftest.py
Every line must say PASS. Running it in your own terminal (outside the sandbox) will show FAILs; that is expected.
"""
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def via_proxy(url, timeout=10):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        return None, "no proxy configured (not sandboxed?)"
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    try:
        with op.open(url, timeout=timeout) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, ""
    except OSError as e:
        return None, str(e)


# Network
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3).close()
    check("direct internet is blocked", False, "a direct connection succeeded")
except OSError:
    check("direct internet is blocked", True)
code, err = via_proxy("https://example.com/")
check("unlisted website is blocked (example.com)", code is None or code >= 400, f"got HTTP {code}")
code, err = via_proxy("https://github.com/")
check("GitHub is reachable through the sandbox proxy", code is not None and code < 500, err or f"HTTP {code}")
settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
bucket_hosts = [d for d in settings.get("sandbox", {}).get("network", {}).get("allowedDomains", []) if ".s3." in d]
if bucket_hosts and not bucket_hosts[0].startswith("YOUR-BUCKET"):
    code, err = via_proxy(f"https://{bucket_hosts[0]}/")
    check(f"S3 bucket host is reachable ({bucket_hosts[0]})", code is not None, err)
else:
    check("S3 bucket host is configured in .claude/settings.json", False, "still YOUR-BUCKET: re-run tools/setup.sh with DVC_REMOTE_URL")

# Filesystem
locked = [".claude/settings.json", ".claude/hooks/scope_guard.py", "tools/githooks/pre-push", "tools/scope_lib.py",
          "tools/precommit_checks.py", "tools/comfy/comfy_client.py", "tools/setup.sh", "tools/envcheck.py",
          "docs/module-map.json", ".git/config"]
for rel in locked:
    p = ROOT / rel
    if p.exists():
        check(f"cannot write {rel}", not os.access(p, os.W_OK))
check("can write ordinary project files", os.access(ROOT / "docs", os.W_OK))
for d in ("~/.local/share/godot", "~/.config/godot", "~/.cache/godot"):
    pd = Path(d).expanduser()
    check(f"Godot can write {d}", pd.is_dir() and os.access(pd, os.W_OK), "missing or read-only: re-run tools/setup.sh")
check("can write /tmp (Xvfb's keyboard map)", os.access("/tmp", os.W_OK), "add /tmp to sandbox allowWrite")
sys.path.insert(0, str(ROOT / "tools"))
try:
    from xdisplay import virtual_display
    with virtual_display():
        pass
    check("virtual display starts (tools/xdisplay.py)", True)
except Exception as e:
    check("virtual display starts (tools/xdisplay.py)", False, str(e).strip()[-200:])
try:
    r = subprocess.run(["dvc", "status", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    check("DVC works inside the sandbox", r.returncode == 0, (r.stderr or r.stdout).strip()[-200:])
except (OSError, subprocess.TimeoutExpired) as e:
    check("DVC works inside the sandbox", False, str(e))
check("cannot write outside the project (home folder)", not os.access(Path.home(), os.W_OK))
check("cannot see Windows drives (/mnt/c)", not Path("/mnt/c/Windows").exists())
check("cannot read ~/.ssh", not any(Path.home().joinpath(".ssh").glob("*")) if Path.home().joinpath(".ssh").exists() else True)

# Windows programs (they would run outside the sandbox)
launched = False
for exe in ("cmd.exe", "/mnt/c/Windows/System32/cmd.exe", "powershell.exe"):
    try:
        r = subprocess.run([exe, "/c", "echo", "hi"], capture_output=True, timeout=10)
        launched = launched or r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
check("cannot launch Windows programs", not launched)

# Privileges
r = subprocess.run(["sudo", "-n", "true"], capture_output=True)
check("sudo does not work", r.returncode != 0)

print(f"\n{sum(results)}/{len(results)} checks passed.")
sys.exit(0 if all(results) else 1)
