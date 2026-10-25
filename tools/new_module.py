#!/usr/bin/env python3
"""Scaffold a decoupled Godot module (works inside the sandbox).

  python3 tools/new_module.py <name> "<one-line description>" [--depends a,b]

Creates godot/modules/<name>/{public,internal,tests} and a module CLAUDE.md, and registers the module in
docs/modules.json. Implementation is done by the generic `module-dev` agent on a branch
task/module-dev/<name>/<id>-<slug> (tools/task.py add ... --module <name>), which scopes its writes to this
module's internal/ and tests/.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from scope_lib import load_modules, repo_root  # noqa: E402

MODULE_CLAUDE = """# Module: {name}
{desc}

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/{name}/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: {deps}.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
(The orchestrator documents signals and functions here.)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("description")
    ap.add_argument("--depends", default="")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", a.name):
        sys.exit("name must be snake_case: [a-z][a-z0-9_]*")
    deps = [d for d in a.depends.split(",") if d]
    root = repo_root()
    reg_path = root / "docs" / "modules.json"
    modules = load_modules(root)
    if a.name in modules:
        sys.exit(f"module '{a.name}' already exists")
    missing = [d for d in deps if d not in modules]
    if missing:
        sys.exit(f"unknown dependencies: {missing}")

    base = root / "godot" / "modules" / a.name
    for sub in ("public", "internal", "tests"):
        (base / sub).mkdir(parents=True, exist_ok=True)
        (base / sub / ".gitkeep").touch()
    (base / "CLAUDE.md").write_text(MODULE_CLAUDE.format(name=a.name, desc=a.description, deps=", ".join(deps) or "none"))
    modules[a.name] = {"description": a.description, "depends_on": deps}
    reg_path.write_text(json.dumps({"modules": modules}, indent=2) + "\n")
    print(f"created module '{a.name}'. Implementation tasks: tools/task.py add <id> module-dev \"<title>\" --module {a.name}")


if __name__ == "__main__":
    main()
