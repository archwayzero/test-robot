#!/bin/sh
# Apply a newer gamedev kit to an existing project. Run it in YOUR Ubuntu terminal (not through Claude):
#   cd ~/game
#   unzip -o "/mnt/c/Users/<you>/Downloads/gamedev-kit.zip" tools/kit_update.sh -d .    (always take it fresh from the zip)
#   sh tools/kit_update.sh "/mnt/c/Users/<you>/Downloads/gamedev-kit.zip"
#
# - Locked enforcement files (hooks, guards, policy) are always replaced: agents can't change them anyway.
# - Other kit files are replaced only if nobody changed them since the project's first commit. Changed ones are
#   put in .kit-update/ instead, for Claude to merge (it will tell you which).
# - Never touches your specs, docs/modules.json entries, your bucket setting, or game files.
# - .claude/settings.json is merged (new sandbox entries added, your values kept), not replaced.
# - Commits the result on the current branch (ALLOW_KIT_UPDATE=1 skips only the branch-scope check).
set -e
main() {
ZIP="$1"
[ -n "$ZIP" ] && [ -f "$ZIP" ] || { echo "usage: sh tools/kit_update.sh <path to gamedev-kit.zip>"; exit 1; }
cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "You have uncommitted changes to tracked files. Ask Claude to commit them first, then re-run."; exit 1
fi
FIRST=$(git rev-list --max-parents=0 HEAD | tail -1)

LOCKED=".claude/hooks/scope_guard.py .claude/hooks/bash_guard.py .claude/hooks/completion_gate.py .claude/hooks/log_event.py
tools/scope_lib.py tools/precommit_checks.py tools/githooks/pre-commit tools/githooks/pre-push tools/githooks/post-checkout
tools/setup.sh tools/envcheck.py tools/xdisplay.py tools/sandbox_selftest.py tools/kit_update.sh tools/comfy/comfy_client.py
tools/maintain.sh MAINTAINING.md .gitattributes .github/workflows/kit-tests.yml
tools/tests/run_all.sh tools/tests/test_guards_git.sh tools/tests/test_release.sh tools/tests/test_tools.sh
tools/tests/make_glb.py tools/tests/fake_comfy.py tools/tests/fwdproxy.py tools/tests/loopback_up.py
tools/tests/kit_copy.sh tools/tests/fixtures/budgets.json
docs/module-map.json"
OTHER=".claude/agents/module-dev.md .claude/agents/orchestrator.md .claude/agents/reviewer.md .claude/agents/qa.md
.claude/agents/modeler.md .claude/agents/rigger-animator.md .claude/agents/reference-director.md
.claude/skills/ref-to-video/SKILL.md tools/new_module.py tools/task.py tools/qa/check_budgets.py tools/qa/capture.py
tools/qa/record.py tools/qa/net_data_audit.py tools/release/make_mac_package.py tools/blender/render_snapshot.py
tools/blender/export_gltf.py .github/workflows/scope-check.yml CLAUDE.md README.md PROMPTS.md SETUP.md
docs/architecture/ARCHITECTURE.md docs/architecture/WORKFLOW.md docs/qa/TEST_PLAN.md docs/contracts/blender-godot-assets.md"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
unzip -q -o "$ZIP" -d "$TMP"
changed=""; asides=""
for f in $LOCKED; do
  [ -f "$TMP/$f" ] || continue
  mkdir -p "$(dirname "$f")"; chmod u+w "$f" 2>/dev/null || true
  if ! cmp -s "$TMP/$f" "$f"; then cp "$TMP/$f" "$f"; changed="$changed $f"; fi
done
for f in $OTHER; do
  [ -f "$TMP/$f" ] || continue
  cmp -s "$TMP/$f" "$f" 2>/dev/null && continue
  if [ ! -f "$f" ]; then
    mkdir -p "$(dirname "$f")"; cp "$TMP/$f" "$f"; changed="$changed $f"            # new in this kit
  elif git cat-file -e "$FIRST:$f" 2>/dev/null && git diff --quiet "$FIRST" HEAD -- "$f"; then
    cp "$TMP/$f" "$f"; changed="$changed $f"                                         # untouched since first commit
  else
    mkdir -p ".kit-update/$(dirname "$f")"; cp "$TMP/$f" ".kit-update/$f"; asides="$asides $f"
  fi
done
chmod +x tools/githooks/* tools/*.py .claude/hooks/*.py 2>/dev/null || true

# Removed in newer kits
if [ -d .claude/agent-templates ]; then git rm -rq .claude/agent-templates; changed="$changed .claude/agent-templates(removed)"; fi

# Module registry (orchestrator-owned): create if missing, never overwrite
if [ ! -f docs/modules.json ]; then printf '{\n  "modules": {}\n}\n' > docs/modules.json; changed="$changed docs/modules.json"; fi

# settings.json: merge new sandbox entries, keep everything you have (bucket address etc.)
python3 -I - "$TMP/.claude/settings.json" .claude/settings.json <<'PY'
import json, sys
new, cur_path = json.load(open(sys.argv[1])), sys.argv[2]
cur = json.load(open(cur_path))
def merge_list(path):
    a, b = cur, new
    for k in path[:-1]:
        a = a.setdefault(k, {}); b = b.get(k, {})
    lst = a.setdefault(path[-1], [])
    for x in b.get(path[-1], []):
        if x not in lst and "YOUR-BUCKET" not in x:
            lst.append(x)
for p in (("sandbox", "filesystem", "allowWrite"), ("sandbox", "filesystem", "denyWrite"),
          ("sandbox", "filesystem", "denyRead"), ("sandbox", "network", "allowedDomains"), ("permissions", "deny")):
    merge_list(p)
for k in ("enabled", "failIfUnavailable", "allowUnsandboxedCommands"):
    cur.setdefault("sandbox", {})[k] = new["sandbox"][k]
cur["hooks"] = new["hooks"]
out = json.dumps(cur, indent=2) + "\n"
if out != open(cur_path).read():
    open(cur_path, "w").write(out); print("merged .claude/settings.json")
PY

# .gitignore additions
for line in "/.kit-update/"; do grep -qxF "$line" .gitignore || echo "$line" >> .gitignore; done

# Machine-local fixes (not committed)
mkdir -p .dvc/tmp/site_cache "$HOME/.local/share/godot" "$HOME/.config/godot" "$HOME/.cache/godot"
dvc config --local core.site_cache_dir "$PWD/.dvc/tmp/site_cache" && echo "DVC state folder moved into the project"

git add -A -- .claude .github tools docs CLAUDE.md README.md PROMPTS.md SETUP.md MAINTAINING.md .gitignore .gitattributes 2>/dev/null || true
git reset -q -- .kit-update 2>/dev/null || true
if git diff --cached --quiet; then echo "Nothing to commit: already up to date."; else
  ALLOW_KIT_UPDATE=1 git commit -q -m "kit: update from gamedev-kit.zip" && echo "Committed on branch $(git branch --show-current)."
fi
echo
[ -n "$changed" ] && echo "Updated:$changed" | fold -s -w 110
if [ -n "$asides" ]; then
  echo; echo "Not replaced because they were changed in this project (new versions are in .kit-update/):"
  for f in $asides; do echo "  $f"; done
  echo "Tell Claude: \"Merge the kit updates in .kit-update/ into the matching files, keeping our project's changes, then delete .kit-update/.\""
fi
}
main "$@"
exit $?
