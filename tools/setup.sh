#!/bin/sh
# One-time setup for a fresh clone: git hooks, DVC, permissions, self-test.
#   DVC_REMOTE_URL=<url> sh tools/setup.sh        (or: sh tools/setup.sh --local-remote /data/dvc-remote)
#   S3: DVC_REMOTE_URL=s3://<bucket>/dvc DVC_REMOTE_REGION=us-east-2 DVC_REMOTE_PROFILE=<profile> sh tools/setup.sh
set -e
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING: $1"; MISSING=1; }; }
MISSING=0; need git; need python3; need dvc; need bwrap; need socat; need Xvfb
for t in blender godot ffmpeg gh claude; do command -v "$t" >/dev/null 2>&1 || echo "warning: '$t' not on PATH"; done
if [ "$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null)" = "1" ]; then
  echo "WARNING: AppArmor blocks the sandbox here (kernel.apparmor_restrict_unprivileged_userns=1)."
  echo "         Follow the bwrap AppArmor step in Claude Code's sandboxing docs, then re-run this script."
fi
[ "$MISSING" = 1 ] && { echo "Install the missing tools first (tell the human; do not guess installers)."; exit 1; }

[ -d .git ] || git init -b main
# A bind-mounted repo may be owned by another UID; without this git refuses to run ("dubious ownership").
git rev-parse --git-dir >/dev/null 2>&1 || git config --global --add safe.directory "$PWD"
git config core.hooksPath tools/githooks
# Files may already be locked (root-owned, read-only). Only chmod what is not executable yet.
for f in tools/githooks/* tools/*.py .claude/hooks/*.py; do
  [ -x "$f" ] || chmod +x "$f" 2>/dev/null || { echo "ERROR: $f is not executable and cannot be changed (locked?). Fix as root: chmod a+x $f"; exit 1; }
done

if [ ! -d .dvc ]; then dvc init; fi
dvc config core.autostage true
dvc config core.analytics false   # no usage statistics leave this machine
# DVC's default state/lock folder (/var/tmp/dvc) is read-only inside the sandbox: keep it in the project instead.
mkdir -p .dvc/tmp/site_cache && dvc config --local core.site_cache_dir "$PWD/.dvc/tmp/site_cache"
# Godot's per-user folders; the sandbox allows writes to exactly these (see .claude/settings.json).
mkdir -p "$HOME/.local/share/godot" "$HOME/.config/godot" "$HOME/.cache/godot"
if ! dvc remote list 2>/dev/null | grep -q .; then
  if [ "$1" = "--local-remote" ] && [ -n "$2" ]; then
    mkdir -p "$2"; dvc remote add -d storage "$2"
  elif [ -n "$DVC_REMOTE_URL" ]; then
    dvc remote add -d storage "$DVC_REMOTE_URL"
    [ -n "$DVC_REMOTE_REGION" ] && dvc remote modify storage region "$DVC_REMOTE_REGION"
    # profile is machine-specific: keep it in .dvc/config.local (not committed)
    [ -n "$DVC_REMOTE_PROFILE" ] && dvc remote modify --local storage profile "$DVC_REMOTE_PROFILE"
  else
    echo "No DVC remote configured. Re-run with DVC_REMOTE_URL=<url> or --local-remote <path>."; exit 1
  fi
fi

# Let the sandbox reach exactly this S3 bucket (virtual-hosted address) and nothing else on S3.
case "$DVC_REMOTE_URL" in
  s3://*)
    BUCKET=$(printf '%s' "$DVC_REMOTE_URL" | sed 's|^s3://||; s|/.*||')
    REGION=${DVC_REMOTE_REGION:-us-east-2}
    if grep -q 'YOUR-BUCKET.s3' .claude/settings.json; then
      sed -i "s|YOUR-BUCKET.s3.us-east-2.amazonaws.com|$BUCKET.s3.$REGION.amazonaws.com|" .claude/settings.json \
        && echo "sandbox network: allowed $BUCKET.s3.$REGION.amazonaws.com"
    fi ;;
esac

# Self-test: do the guards actually block what they should?
# (rc is captured with '|| rc=$?' so 'set -e' does not abort on the expected exit-2 cases)
fail=0
t() { # name expected_exit script json
  rc=0; out=$(printf '%s' "$4" | CLAUDE_PROJECT_DIR="$PWD" python3 "$3" 2>&1) || rc=$?
  if [ "$rc" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1 (exit $rc, expected $2): $out"; fail=1; fi
}
S=.claude/hooks/scope_guard.py; B=.claude/hooks/bash_guard.py
t "orchestrator may write docs"          0 $S "{\"agent_type\":\"orchestrator\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/docs/x.md\"}}"
t "orchestrator may not write internals" 2 $S "{\"agent_type\":\"orchestrator\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/godot/modules/core/internal/a.gd\"}}"
t "nobody may edit hooks"                2 $S "{\"agent_type\":\"orchestrator\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/.claude/hooks/scope_guard.py\"}}"
t "modeler may write its scope"          0 $S "{\"agent_type\":\"modeler\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/blender/models/a/build.py\"}}"
t "modeler may not write rigs"           2 $S "{\"agent_type\":\"modeler\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/blender/rigs/a/rig.py\"}}"
t "unknown agent is denied"              2 $S "{\"agent_type\":\"general-purpose\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/docs/x.md\"}}"
t "git status allowed"                   0 $B '{"tool_input":{"command":"git status"}}'
t "--no-verify blocked"                  2 $B '{"tool_input":{"command":"git commit -m x --no-verify"}}'
t "push to main blocked"                 2 $B '{"tool_input":{"command":"git push origin main"}}'
t "dvc remote change blocked"            2 $B '{"tool_input":{"command":"dvc remote modify storage url s3://x"}}'
t "qa may write e2e tests"               0 $S "{\"agent_type\":\"qa\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/godot/tests/e2e/t.gd\"}}"
t "qa may not edit budgets"              2 $S "{\"agent_type\":\"qa\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/docs/qa/budgets.json\"}}"
t "reference-director scope"             0 $S "{\"agent_type\":\"reference-director\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/reference/a/walk/NOTES.md\"}}"
t "module-dev without module branch denied" 2 $S "{\"agent_type\":\"module-dev\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/godot/modules/x/internal/a.gd\"}}"
t "nobody may edit setup.sh"             2 $S "{\"agent_type\":\"orchestrator\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/tools/setup.sh\"}}"
t "reference-director not into rigs"     2 $S "{\"agent_type\":\"reference-director\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/blender/rigs/a/rig.py\"}}"
[ "$fail" = 0 ] || { echo "Self-test failed; do not proceed."; exit 1; }


echo; echo "Environment (this terminal is OUTSIDE the sandbox):"; python3 -I tools/envcheck.py || true
cat <<'MSG'

Setup complete. Next:
 1. Start `claude` in this folder, accept the folder trust prompt, and run /sandbox and /hooks to review them.
 2. Ask Claude to run: python3 tools/sandbox_selftest.py   (every line must say PASS)
MSG
