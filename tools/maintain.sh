#!/bin/sh
# Start the kit-maintenance Claude session: a SEPARATE clone, outside the sandbox, kit hooks off.
# Run it in your own Ubuntu terminal:   sh ~/game/tools/maintain.sh
# It is not sandboxed: stay with it while it works, and review its PRs carefully.
set -e
main() {
  LIVE="$(cd "$(dirname "$0")/.." && pwd)"
  URL=$(git -C "$LIVE" remote get-url origin) || { echo "No GitHub remote in $LIVE (SETUP.md F2)."; exit 1; }
  DIR="${KIT_MAINT_DIR:-$HOME/kit-maint}"
  if [ ! -d "$DIR/.git" ]; then
    git clone -q -c core.autocrlf=false "$URL" "$DIR" && echo "Cloned the repo into $DIR"
  fi
  cd "$DIR"
  if [ -z "$(git status --porcelain --untracked-files=no)" ] && [ "$(git branch --show-current)" = "main" ]; then
    git pull -q --ff-only origin main || echo "note: could not fast-forward main; Claude will sort it out."
  fi
  echo "Starting the kit-maintenance session in $DIR (NOT sandboxed, kit hooks off)."
  exec claude --agent claude --settings '{"sandbox":{"enabled":false},"disableAllHooks":true}' \
    "You are the kit-maintenance session. Read MAINTAINING.md and follow it exactly. Then wait for my instructions."
}
main "$@"
