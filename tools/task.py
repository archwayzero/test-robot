#!/usr/bin/env python3
"""Tiny local task ledger (gitignored: .claude/state/ledger.json).

  task.py add <id> <agent> "<title>" [--spec path] [--depends T1,T2] [--module <name>]   (--module required for module-dev)
  task.py start <id> [--base main]   create/switch to branch task/<agent>/<id>-<slug>
                                     (module-dev: task/module-dev/<module>/<id>-<slug>)
  task.py finish <id>                switch back to the branch you started from (status: review)
  task.py done <id>                  mark merged/done
  task.py list                       ID | STATUS | AGENT | BRANCH | TITLE
Commit/push are plain git commands; the hooks enforce scope, DVC and ordering.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from scope_lib import current_branch, load_modules, repo_root  # noqa: E402


def load(path):
    return json.loads(path.read_text()) if path.exists() else {"tasks": {}}


def run(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr.strip() or "git failed")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add"); a.add_argument("id"); a.add_argument("agent"); a.add_argument("title")
    a.add_argument("--spec", default=""); a.add_argument("--depends", default=""); a.add_argument("--module", default="")
    s = sp.add_parser("start"); s.add_argument("id"); s.add_argument("--base", default="main")
    for n in ("finish", "done"):
        sp.add_parser(n).add_argument("id")
    sp.add_parser("list")
    args = ap.parse_args()

    root = repo_root()
    path = root / ".claude" / "state" / "ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    led = load(path)
    tasks = led["tasks"]

    if args.cmd == "add":
        if args.id in tasks:
            sys.exit("task id exists")
        if args.agent == "module-dev" and args.module not in load_modules(root):
            sys.exit("module-dev tasks need --module <name> of a module listed in docs/modules.json")
        tasks[args.id] = {"agent": args.agent, "title": args.title, "spec": args.spec, "module": args.module,
                          "depends": [d for d in args.depends.split(",") if d],
                          "status": "todo", "branch": "", "return_branch": ""}
    elif args.cmd == "list":
        for tid, t in sorted(tasks.items()):
            print(f"{tid} | {t['status']} | {t['agent']} | {t['branch'] or '-'} | {t['title']}")
        return
    else:
        t = tasks.get(args.id) or sys.exit("unknown task id")
        if args.cmd == "start":
            # Untracked files (e.g. a model the human just dropped in) carry over to the new branch; that's fine.
            if run("status", "--porcelain", "--untracked-files=no"):
                sys.exit("working tree has uncommitted changes to tracked files; commit or stash first")
            unmet = [d for d in t["depends"] if tasks.get(d, {}).get("status") != "done"]
            if unmet:
                sys.exit(f"unmet dependencies: {unmet}")
            slug = re.sub(r"[^a-z0-9]+", "-", t["title"].lower()).strip("-")[:30]
            if t["agent"] == "module-dev":
                branch = f"task/module-dev/{t.get('module')}/{args.id}-{slug}"
            else:
                branch = f"task/{t['agent']}/{args.id}-{slug}"
            t["return_branch"] = current_branch()
            exists = subprocess.run(["git", "rev-parse", "--verify", branch], capture_output=True).returncode == 0
            run("switch", branch) if exists else run("switch", "-c", branch, args.base)
            t.update(branch=branch, status="in_progress")
        elif args.cmd == "finish":
            if run("status", "--porcelain"):
                sys.exit("uncommitted changes; commit first")
            run("switch", t["return_branch"] or "main")
            t["status"] = "review"
        elif args.cmd == "done":
            t["status"] = "done"
    path.write_text(json.dumps(led, indent=2) + "\n")
    print("ok")


if __name__ == "__main__":
    main()
