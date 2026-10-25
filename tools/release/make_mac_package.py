#!/usr/bin/env python3
"""Build the package to take to the Mac (Godot project + DVC assets) from an APPROVED commit.

  python3 tools/release/make_mac_package.py [--version 0.1.0]

The iOS export itself (Xcode project) must be made on macOS, so this packages the source project.
Refuses to build unless ALL gates pass:
  1. HEAD is on main (only the human can merge there), the tree is clean, and HEAD matches origin/main
     when a remote exists.
  2. docs/qa/budgets.json is no longer a placeholder, and the static budget check passes now.
  3. docs/qa/reports/release-candidate.md and network-data-audit.md say RESULT: PASS and were committed after
     the last change to godot/.
  4. Every DVC-tracked file under godot/ is present locally (runs `dvc pull` first).
Output: dist/<name>-<version>-<sha>-mac.zip containing godot/, docs/IOS_HANDOFF.md, docs/specs/PLATFORM.md, MANIFEST.json.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scope_lib import current_branch, git, repo_root  # noqa: E402

QA_REPORT = "docs/qa/reports/release-candidate.md"
AUDIT_REPORT = "docs/qa/reports/network-data-audit.md"


def fail(msg):
    print(f"NOT PACKAGED: {msg}", file=sys.stderr)
    sys.exit(1)


def dvc_outs(root):
    outs = []
    for dvcfile in root.rglob("*.dvc"):
        parts = dvcfile.relative_to(root).parts
        if not dvcfile.is_file() or ".dvc" in parts[:-1] or ".git" in parts or "dist" in parts[:1]:
            continue
        for line in dvcfile.read_text(errors="ignore").splitlines():
            m = re.match(r"\s*-?\s*path:\s*(.+?)\s*$", line)
            if m:
                outs.append((dvcfile.parent / m.group(1).strip("'\"")).resolve())
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.0.0")
    a = ap.parse_args()
    root = repo_root()
    os.chdir(root)

    # Gate 1: approved commit
    if current_branch() != "main":
        fail("must run on main (the human-merged, approved branch). `git switch main && git pull` first.")
    if git("status", "--porcelain")[1]:
        fail("working tree is not clean.")
    if git("remote")[1]:
        git("fetch", "--quiet", "origin", "main")
        rc, remote_sha = git("rev-parse", "origin/main")
        if rc == 0 and remote_sha != git("rev-parse", "HEAD")[1]:
            fail("local main differs from origin/main. Pull the approved state first.")
    sha = git("rev-parse", "HEAD")[1]

    # Gate 2: budgets
    try:
        budgets = json.loads(Path("docs/qa/budgets.json").read_text())
    except (OSError, ValueError) as e:
        fail(f"cannot read docs/qa/budgets.json: {e}")
    if "PLACEHOLDER" in str(budgets.get("status", "")):
        fail("budgets are still placeholders; approved, cited budgets are required for release.")

    # Gate 4 first part: make sure assets are present before measuring them
    if Path(".dvc").is_dir():
        if not shutil.which("dvc"):
            fail("dvc is not installed; cannot fetch assets.")
        if subprocess.run(["dvc", "pull"]).returncode != 0:
            fail("dvc pull failed.")
    godot_dir = (root / "godot").resolve()
    missing = [str(p.relative_to(root)) for p in dvc_outs(root)
               if godot_dir in p.parents and not p.exists()]
    if missing:
        fail(f"DVC-tracked files missing locally: {missing[:10]}")

    report_json = root / "dist" / f".budget-{sha[:8]}.json"
    report_json.parent.mkdir(exist_ok=True)
    r = subprocess.run([sys.executable, "tools/qa/check_budgets.py", "--json", str(report_json)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        fail("static budget check does not pass on this commit.")
    budget = json.loads(report_json.read_text())

    # Gate 3: QA release report and network/data audit, both newer than the last game change
    game_commit = git("log", "-1", "--format=%H", "--", "godot")[1]
    qa_commit = None
    for report, task in ((QA_REPORT, "release QA"), (AUDIT_REPORT, "network and data audit")):
        rp = Path(report)
        if not rp.exists() or not re.search(r"^RESULT:\s*PASS\s*$", rp.read_text(), re.M):
            fail(f"{report} missing or does not contain a line 'RESULT: PASS'. Run the {task} task.")
        commit = git("log", "-1", "--format=%H", "--", report)[1]
        if not commit:
            fail(f"{report} is not committed.")
        if game_commit and git("merge-base", "--is-ancestor", game_commit, commit)[0] != 0:
            fail(f"godot/ changed after {report} was committed. Re-run the {task}.")
        qa_commit = qa_commit or commit

    # Package
    m = re.search(r'config/name="([^"]+)"', (godot_dir / "project.godot").read_text()) if (godot_dir / "project.godot").exists() else None
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", m.group(1)).strip("-") if m else "game"
    feats = re.search(r"config/features=PackedStringArray\(([^)]*)\)", (godot_dir / "project.godot").read_text()) if m else None
    out = root / "dist" / f"{name}-{a.version}-{sha[:8]}-mac.zip"
    files = {}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(godot_dir.rglob("*")):
            rel = p.relative_to(root)
            if p.is_dir() or ".godot" in rel.parts or p.suffix == ".blend1":
                continue
            z.write(p, rel.as_posix())
            files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        for extra in ("docs/IOS_HANDOFF.md", "docs/specs/PLATFORM.md", QA_REPORT, AUDIT_REPORT):
            if Path(extra).exists():
                z.write(extra, extra)
        manifest = {"commit": sha, "version": a.version,
                    "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "godot_features": feats.group(1) if feats else None,
                    "static_budget_score": budget.get("static_budget_score"),
                    "qa_report_commit": qa_commit, "file_count": len(files), "sha256": files}
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    report_json.unlink(missing_ok=True)
    print(f"PACKAGED {out.relative_to(root)} ({len(files)} files, commit {sha[:8]}, "
          f"static budget score {budget.get('static_budget_score')})")
    if not Path("docs/IOS_HANDOFF.md").exists():
        print("warning: docs/IOS_HANDOFF.md not found; the Mac steps are not included.")


if __name__ == "__main__":
    main()
