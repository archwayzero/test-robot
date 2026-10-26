#!/bin/bash
S="$KIT_TEST_TMP"
rm -rf $S/t $S/rem; bash "$KIT_ROOT/tools/tests/kit_copy.sh" $S/t; cd $S/t
export PATH=$KIT_TEST_SHIM:$PATH CLAUDE_PROJECT_DIR=$S/t
sh tools/setup.sh --local-remote $S/rem >/dev/null 2>&1 || { echo "SETUP FAILED"; exit 1; }
pass=0; failn=0
# expect <name> <expected exit> <cmd...>
expect() { n="$1"; e="$2"; shift 2; out=$("$@" 2>&1); rc=$?; if [ "$rc" = "$e" ]; then echo "PASS  $n"; pass=$((pass+1)); else echo "FAIL  $n (exit $rc, expected $e)"; echo "$out" | tail -4; failn=$((failn+1)); fi; }
expect "first commit on empty repo allowed" 0 sh -c 'git add -A && git commit -qm "chore: bootstrap kit"'
echo x > docs/extra.md
expect "direct commit to main blocked" 1 sh -c 'git add -A && git commit -qm direct'
git reset -q; rm -f docs/extra.md
git switch -qc arch/bootstrap
python3 tools/new_module.py core "Event bus, state" >/dev/null && python3 tools/new_module.py combat "Combat" --depends core >/dev/null && python3 tools/new_module.py ui "UI" --depends core >/dev/null
expect "module scaffolding commit allowed on arch branch" 0 sh -c 'git add -A && git commit -qm "arch: modules"'
printf 'extends Node\nsignal damage_dealt(amount)\n' > godot/modules/core/public/events.gd
expect "orchestrator writes public interface" 0 sh -c 'git add -A && git commit -qm "arch: core public"'
git switch -q main && git merge -q --ff-only arch/bootstrap
expect "module-dev task without --module refused" 1 python3 tools/task.py add T009 module-dev "x"
python3 tools/task.py add T001 module-dev "Implement hit logic" --module combat >/dev/null; python3 tools/task.py add T002 module-dev "Second" --depends T001 --module combat >/dev/null
expect "start task with unmet dependency fails" 1 python3 tools/task.py start T002
expect "start T001 creates task branch" 0 python3 tools/task.py start T001
[ "$(git branch --show-current)" = "task/module-dev/combat/T001-implement-hit-logic" ] && echo "PASS  on branch task/module-dev/combat/T001-implement-hit-logic" || echo "FAIL  branch name: $(git branch --show-current)"
printf 'extends Node\nfunc hit(): pass\n' > godot/modules/combat/internal/hit.gd
expect "in-scope commit allowed" 0 sh -c 'git add -A && git commit -qm "T001: hit"'
sg() { echo "{\"agent_type\":\"module-dev\",\"cwd\":\"$PWD\",\"tool_input\":{\"file_path\":\"$PWD/$1\"}}" | python3 .claude/hooks/scope_guard.py; }
expect "module-dev hook: own module internal allowed" 0 sg godot/modules/combat/internal/z.gd
expect "module-dev hook: other module blocked" 2 sg godot/modules/ui/internal/z.gd
expect "module-dev hook: own public blocked" 2 sg godot/modules/combat/public/api.gd
expect "module-dev hook: module registry blocked" 2 sg docs/modules.json
echo 'extends Node' > godot/modules/core/public/hack.gd
expect "out-of-scope commit blocked" 1 sh -c 'git add -A && git commit -qm bad'
git reset -q; rm godot/modules/core/public/hack.gd
printf 'extends Node\nvar a = preload("res://modules/core/internal/secret.gd")\n' > godot/modules/combat/internal/bad.gd
expect "reaching into another module's internals blocked" 1 sh -c 'git add -A && git commit -qm bad2'
printf 'extends Node\nvar a = preload("res://modules/ui/public/x.gd")\n' > godot/modules/combat/internal/bad.gd
expect "undeclared dependency blocked" 1 sh -c 'git add -A && git commit -qm bad3'
printf 'extends Node\nvar a = preload("res://modules/core/public/events.gd")\n' > godot/modules/combat/internal/bad.gd
expect "declared public reference allowed" 0 sh -c 'git add -A && git commit -qm ok2'
head -c 100 /dev/urandom > godot/modules/combat/internal/model.glb
expect "binary committed to git blocked" 1 sh -c 'git add -A && git commit -qm bin'
# completion gate: untracked binary present -> must block (exit 2); clean -> allow
expect "completion gate blocks untracked binary" 2 sh -c "echo '{\"cwd\":\"$S/t\"}' | python3 .claude/hooks/completion_gate.py"
expect "completion gate: stop_hook_active never loops" 0 sh -c "echo '{\"cwd\":\"$S/t\",\"stop_hook_active\":true}' | python3 .claude/hooks/completion_gate.py"
rm godot/modules/combat/internal/model.glb; git reset -q
echo "# change" >> godot/modules/combat/internal/hit.gd
expect "completion gate blocks uncommitted work on task branch" 2 sh -c "echo '{\"cwd\":\"$S/t\"}' | python3 .claude/hooks/completion_gate.py"
git add -A; git commit -qm "T001: bad.gd ref"
expect "completion gate passes when clean" 0 sh -c "echo '{\"cwd\":\"$S/t\"}' | python3 .claude/hooks/completion_gate.py"
expect "finish T001 returns to main" 0 python3 tools/task.py finish T001
[ "$(git branch --show-current)" = "main" ] && echo "PASS  back on main" || echo "FAIL  not on main"
# push guards (no remote needed for the hook itself): simulate pre-push stdin
expect "pre-push to main blocked" 1 sh -c 'echo "refs/heads/x 0 refs/heads/main 0" | sh tools/githooks/pre-push'
expect "pre-push of task branch runs dvc push (stub) and passes" 0 sh -c 'echo "refs/heads/t 0 refs/heads/task/module-dev/combat/T001 0" | sh tools/githooks/pre-push'
# bash guard extras
B=.claude/hooks/bash_guard.py
bg() { echo "{\"tool_input\":{\"command\":$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$2")}}" | python3 $B; }
expect "bash: git commit -n blocked" 2 bg x "git commit -n -m x"
expect "bash: force push blocked" 2 bg x "git push --force origin task/x"
expect "bash: -c hooksPath override blocked" 2 bg x "git -c core.hooksPath=/dev/null commit -m x"
expect "bash: chained push to main blocked" 2 bg x "git add -A && git push origin HEAD:main"
expect "bash: nested bash -c commit --no-verify blocked" 2 bg x "bash -c 'git commit --no-verify -m x'"
expect "bash: writing hooks via redirect blocked" 2 bg x "echo 'exit 0' > .claude/hooks/scope_guard.py"
expect "bash: env var override blocked" 2 bg x "ALLOW_PROTECTED_PUSH=1 git push origin main"
expect "bash: git remote add blocked" 2 bg x "git remote add evil https://x/y.git"
expect "bash: normal workflow commands allowed" 0 bg x "dvc add blender/models/crate/crate.blend && git add -A && git commit -m 'T001: crate' && git push origin task/modeler/T003-crate"
expect "bash: reading hooks allowed" 0 bg x "cat .claude/hooks/scope_guard.py"
expect "bash: push -u blocked" 2 bg x "git push -u origin task/x"
expect "bash: sudo blocked" 2 bg x "sudo apt install foo"
expect "bash: writing comfy client blocked" 2 bg x "echo x > tools/comfy/comfy_client.py"
echo "== $pass passed, $failn failed"
