#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|NotebookEdit): enforce per-agent write scopes.

Exit 2 = block (stderr goes back to the agent). Scopes live in docs/module-map.json.
A session without --agent is treated as the orchestrator. Agents not listed in the
map get no write access at all (default deny).
"""
import json
import os
import sys
import tempfile

sys.path.append(os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "."), "tools"))
from scope_lib import current_branch, load_map, matches_any, rel_in_repo, repo_root, write_scope  # noqa: E402


def deny(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


data = json.load(sys.stdin)
tin = data.get("tool_input") or {}
file_path = tin.get("file_path") or tin.get("notebook_path")
if not file_path:
    sys.exit(0)

agent = data.get("agent_type") or "orchestrator"
cfg = load_map(repo_root(os.environ.get("CLAUDE_PROJECT_DIR")))
rel = rel_in_repo(file_path, data.get("cwd"))

if rel is None:
    allowed_dirs = [tempfile.gettempdir(), data.get("scratchpad_dir")]
    real = os.path.realpath(file_path)
    if any(d and real.startswith(os.path.realpath(d) + os.sep) for d in allowed_dirs):
        sys.exit(0)
    deny(f"Blocked: '{file_path}' is outside the repository. Write only inside the repo (or a temp dir).")

if matches_any(rel, cfg.get("locked", [])):
    deny(f"Blocked: '{rel}' is locked (enforcement/config). Only the human may change it.")

branch = current_branch(data.get("cwd") or None)
scope = write_scope(cfg, agent, branch)
if scope is None:
    if agent == "module-dev":
        deny(f"Blocked: module-dev may only write while on a branch task/module-dev/<module>/<id>-<slug> for a module "
             f"listed in docs/modules.json (current branch: '{branch}'). Ask the orchestrator to start the task.")
    deny(f"Blocked: agent '{agent}' has no write scope in docs/module-map.json (default deny).")
if matches_any(rel, scope):
    sys.exit(0)
deny(f"Blocked: '{rel}' is outside the write scope of '{agent}'. Allowed: {scope}. "
     "If this file must change, stop and report the exact change you need back to the orchestrator.")
