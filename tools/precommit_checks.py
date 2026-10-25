#!/usr/bin/env python3
"""Git-level checks, used by the pre-commit hook and by CI.

  precommit_checks.py            check staged files (pre-commit)
  precommit_checks.py --ci BASE  check the diff BASE...HEAD (CI / pull request)

Checks: protected branch, binaries must be DVC-tracked, write scope per branch
(task/<agent>/<slug>, arch/<slug>), and module decoupling (res:// references).
"""
import os
import re
import sys

# Appended, not prepended: run with `python3 -I` so a file planted in tools/ can never shadow a standard module.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scope_lib import agent_for_branch, current_branch, git, load_map, matches_any, repo_root, write_scope  # noqa: E402

SCAN_EXT = {".gd", ".tscn", ".tres", ".cfg", ".gdshader"}
REF = re.compile(r"res://modules/([A-Za-z0-9_]+)/([^\s\"')]*)")


def main():
    ci_base = None
    if "--ci" in sys.argv:
        ci_base = sys.argv[sys.argv.index("--ci") + 1]
    root = repo_root(os.getcwd())
    os.chdir(root)
    cfg = load_map(root)
    errors = []

    if ci_base:
        _, out = git("diff", "--no-renames", "--name-only", f"{ci_base}...HEAD")
        branch = os.environ.get("GITHUB_HEAD_REF") or current_branch()
        blob = lambda p: git("show", f"HEAD:{p}")[1]  # noqa: E731
    else:
        _, out = git("diff", "--cached", "--no-renames", "--name-only")
        branch = current_branch()
        blob = lambda p: git("show", f":{p}")[1]  # noqa: E731
        has_head = git("rev-parse", "--verify", "HEAD")[0] == 0
        if (has_head and branch in cfg["protected_branches"]
                and os.environ.get("ALLOW_PROTECTED_COMMIT") != "1"):
            errors.append(f"Direct commits to '{branch}' are not allowed. Create a branch "
                          "(task/<agent>/<slug> or arch/<slug>) and open a PR.")
    files = [f for f in out.splitlines() if f]
    exists = lambda p: os.path.exists(p)  # noqa: E731

    bin_ext = {e.lower() for e in cfg["binary_extensions"]}
    for f in files:
        if os.path.splitext(f)[1].lower() in bin_ext and exists(f):
            errors.append(f"Binary file '{f}' must be tracked with DVC, not git. "
                          f"Run: git rm --cached '{f}' && dvc add '{f}' (then commit the .dvc pointer).")

    agent = agent_for_branch(branch)
    kit_update = not ci_base and os.environ.get("ALLOW_KIT_UPDATE") == "1"
    if kit_update:
        print("note: ALLOW_KIT_UPDATE=1 (human kit update): branch scope not checked.", file=sys.stderr)
    elif agent:
        scope = write_scope(cfg, agent, branch)
        if scope is None:
            errors.append(f"Branch '{branch}' has no write scope (unknown agent, or module-dev without a module "
                          "listed in docs/modules.json).")
        else:
            bad = [f for f in files if not matches_any(f, scope)]
            if bad:
                errors.append(f"Files outside the write scope of '{agent}': {', '.join(bad[:10])}. Allowed: {scope}")
    elif not ci_base and branch and branch not in cfg["protected_branches"]:
        print(f"note: branch '{branch}' has no scope (use task/<agent>/<slug> or arch/<slug>).", file=sys.stderr)

    for f in files:
        m = re.match(r"godot/modules/([^/]+)/", f)
        if not m or os.path.splitext(f)[1].lower() not in SCAN_EXT or not exists(f):
            continue
        mod = m.group(1)
        deps = cfg.get("modules", {}).get(mod, {}).get("depends_on", [])
        for other, sub in REF.findall(blob(f)):
            if other == mod:
                continue
            if other not in deps:
                errors.append(f"{f}: module '{mod}' uses '{other}' but does not declare it in depends_on.")
            elif not sub.startswith("public/"):
                errors.append(f"{f}: reaches into '{other}' internals ('{sub}'). Use res://modules/{other}/public/ only.")

    if errors:
        print("Commit checks failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
