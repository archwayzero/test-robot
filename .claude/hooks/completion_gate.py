#!/usr/bin/env python3
"""Stop / SubagentStop hook: do not let an agent finish with untracked binaries or
uncommitted work on a task branch. Blocks once (stop_hook_active prevents loops)."""
import json
import os
import subprocess
import sys

sys.path.append(os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "."), "tools"))
from scope_lib import current_branch, load_map, repo_root  # noqa: E402

data = json.load(sys.stdin)
if data.get("stop_hook_active"):
    sys.exit(0)

cwd = data.get("cwd") or os.getcwd()
root = repo_root(cwd)
cfg = load_map(repo_root(os.environ.get("CLAUDE_PROJECT_DIR")))
bin_ext = {e.lower() for e in cfg.get("binary_extensions", [])}

r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                   capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if l.strip()]
problems = []

untracked_bin = [l[3:] for l in lines if l.startswith("??") and os.path.splitext(l[3:])[1].lower() in bin_ext]
if untracked_bin:
    problems.append("Binary assets are not tracked by DVC yet: " + ", ".join(untracked_bin[:8]) +
                    ". Run `dvc add <file>`, then commit the .dvc pointer.")
if current_branch(str(root)).startswith("task/") and lines:
    problems.append("Uncommitted changes on a task branch. Run `git add -A && git commit` "
                    "(the hooks will run the scope and DVC checks).")

if problems:
    print("Not done yet:\n- " + "\n- ".join(problems), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
