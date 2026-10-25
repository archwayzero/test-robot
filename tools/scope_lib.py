#!/usr/bin/env python3
"""Shared helpers for the scope guard, git pre-commit checks and the CI check."""
import json
import os
import re
import subprocess
from pathlib import Path


def git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def repo_root(start=None):
    start = start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    rc, out = git("rev-parse", "--show-toplevel", cwd=start)
    return Path(out) if rc == 0 and out else Path(start)


def load_map(root):
    """Locked policy (who may write what) plus the orchestrator-owned module registry (docs/modules.json)."""
    with open(Path(root) / "docs" / "module-map.json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["modules"] = load_modules(root)
    return cfg


def load_modules(root):
    p = Path(root) / "docs" / "modules.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    mods = data.get("modules", {}) if isinstance(data, dict) else {}
    return {k: v for k, v in mods.items() if re.fullmatch(r"[a-z][a-z0-9_]*", k) and isinstance(v, dict)}


def glob_to_regex(pat):
    i, out = 0, ""
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i:i + 3] == "**/":
                out += "(?:.*/)?"
                i += 3
                continue
            if pat[i:i + 2] == "**":
                out += ".*"
                i += 2
                continue
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def matches_any(path, patterns):
    return any(glob_to_regex(p).match(path) for p in patterns)


def rel_in_repo(file_path, cwd=None):
    """Repo-relative POSIX path of file_path, or None if it is outside any repo."""
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(cwd or os.getcwd()) / p
    p = Path(os.path.realpath(p))
    d = p.parent
    while not d.exists() and d != d.parent:
        d = d.parent
    rc, top = git("rev-parse", "--show-toplevel", cwd=str(d))
    candidates = [top] if rc == 0 and top else []
    # Fallback when git refuses to run (e.g. "dubious ownership" on a bind mount owned by another UID).
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        candidates.append(os.environ["CLAUDE_PROJECT_DIR"])
    for c in candidates:
        try:
            return p.relative_to(os.path.realpath(c)).as_posix()
        except ValueError:
            continue
    return None


def current_branch(cwd=None):
    rc, out = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return out if rc == 0 else ""


def agent_for_branch(branch):
    """task/<agent>/<slug> -> <agent>; arch/<slug> -> orchestrator; else None."""
    m = re.match(r"^task/([^/]+)/", branch)
    if m:
        return m.group(1)
    if branch.startswith("arch/"):
        return "orchestrator"
    return None


def module_for_branch(branch):
    """task/module-dev/<module>/<id>-<slug> -> <module>; else None."""
    m = re.match(r"^task/module-dev/([a-z][a-z0-9_]*)/", branch or "")
    return m.group(1) if m else None


def write_scope(cfg, agent, branch):
    """Write patterns for an agent. module-dev is scoped to the module named in its task branch."""
    if agent == "module-dev":
        module = module_for_branch(branch)
        if not module or module not in cfg.get("modules", {}):
            return None
        return [f"godot/modules/{module}/internal/**", f"godot/modules/{module}/tests/**"]
    spec = cfg["agents"].get(agent)
    return None if spec is None else spec.get("write", [])
