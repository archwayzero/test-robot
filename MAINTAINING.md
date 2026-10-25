# Maintaining the kit (instructions for the kit-maintenance Claude session)

You are the **kit-maintenance session**. You are NOT one of the game agents. Where this file and CLAUDE.md disagree,
this file wins for you. (CLAUDE.md describes the sandboxed game agents.)

## Your situation
- You run in WSL2 Ubuntu, **outside** Claude Code's sandbox and with the kit's hooks **off**, in a separate clone of
  the game repo (default `~/kit-maint`), started by `tools/maintain.sh`. The game agents work in a different folder
  (`~/game`) inside the sandbox. Never touch `~/game`, and never touch anything outside your clone except `/tmp`.
- **First, check you really are unsandboxed:** `touch .claude/maint-check && rm .claude/maint-check` must succeed.
  If it fails with a permission error, the sandbox is on: stop and tell the human to start you with
  `sh ~/game/tools/maintain.sh`.
- A human supervises you. Nothing you do reaches the game agents until the human merges your PR on GitHub and then
  runs `git pull` in `~/game` from their own terminal (the sandbox stops the agents from pulling protected files).
- You can edit the files the agents can't: `.claude/settings.json`, `.claude/hooks/**`, `tools/githooks/**`,
  `tools/scope_lib.py`, `tools/precommit_checks.py`, `tools/setup.sh`, `tools/envcheck.py`, `tools/xdisplay.py`,
  `tools/kit_update.sh`, `tools/maintain.sh`, `tools/sandbox_selftest.py`, `tools/comfy/comfy_client.py`,
  `docs/module-map.json`, `SETUP.md`, `MAINTAINING.md`. That is exactly why your work must be careful and reviewed.

## What the kit is (read these before changing anything)
- `README.md`: architecture overview and honest limits. `SETUP.md`: the human's setup guide (keep it beginner-proof).
- `docs/architecture/ARCHITECTURE.md`, `WORKFLOW.md`: module model, task lifecycle, version-control order.
- Enforcement layers, strongest first:
  1. **Claude Code sandbox** (`.claude/settings.json` → `sandbox`): agents' shell commands can only write inside the
     project (minus `denyWrite`), can't read `/mnt` or `~/.ssh`, and can only reach `allowedDomains`
     (GitHub, the project's S3 bucket, `localhost:8188` for ComfyUI). No GPU, no Unix sockets, read-only `/tmp`,
     each command has a private localhost. `failIfUnavailable` and `allowUnsandboxedCommands: false` are mandatory.
  2. **Hooks** (`.claude/hooks/`): `scope_guard.py` (per-agent write scopes for Claude's file tools, from
     `docs/module-map.json`; `module-dev` is scoped by its branch `task/module-dev/<module>/...`), `bash_guard.py`
     (heuristic: no `--no-verify`, no pushes to main, no remote/DVC config changes, no writes to locked files, no
     `sudo`, no `ALLOW_*` variables), `completion_gate.py`, `log_event.py`.
  3. **Git hooks** (`tools/githooks/`, via `core.hooksPath`) + **CI** (`.github/workflows/scope-check.yml`): branch
     scope, binaries only via DVC, module decoupling; `dvc push` before `git push`.
  4. **GitHub branch protection** on `main` and **human PR review**.
- Scripts the human runs outside the sandbox (`setup.sh`, `envcheck.py`, `kit_update.sh`, `maintain.sh`, git hooks)
  are locked and run Python with `-I` so a file planted in `tools/` can never shadow a standard module. Keep it so.

## Rules for every change
1. **Never weaken a protection unless the human explicitly asks for that specific change.** That includes: removing
   `denyWrite`/`denyRead` entries, adding `allowedDomains` or `allowWrite` beyond what a fix strictly needs, enabling
   `excludedCommands`/`allowUnsandboxedCommands`, widening a scope in `module-map.json`, loosening a guard, or running
   human-side scripts without `-I`. If a fix seems to need one, stop and explain the trade-off first.
2. **Never add `localhost:9876`** (Blender MCP) or any port that runs code on the host to `allowedDomains`.
3. **Work on a branch named `kit/<short-slug>`.** These branches have no agent scope, so the CI scope check allows
   locked files; the human's review is the gate. Never push to `main`.
4. **Test before every PR:** `bash tools/tests/run_all.sh` must end with `ALL SUITES PASSED`. Add or update a test for
   every bug you fix (a test that fails without your fix). The render tests run when `godot`, `Xvfb` and user
   namespaces are available (they are in WSL); say so if they were skipped.
5. **Simulate the sandbox when the bug is sandbox-specific.** `unshare --user --map-root-user --mount --net` with a
   read-only `/tmp` (see `tools/tests/test_tools.sh`) reproduces the main restrictions. If a fix can only be verified
   inside the real sandbox, write the exact check the human should ask a game agent to run after merging.
6. **Keep SETUP.md beginner-proof** when a change affects what the human does. Plain words, exact clicks/commands.
7. **Line endings stay LF** (`.gitattributes`). Don't reformat unrelated code.
8. **PR description:** what broke, root cause, the fix, what you tested (paste the test summary), any change to
   protections (say "none" if none), and what the human must do after merging, normally:
   `cd ~/game && git switch main && git pull` in their own Ubuntu terminal, then ask a game agent to run
   `python3 tools/sandbox_selftest.py`.

## How to ship a fix
```
git switch main && git pull
git switch -c kit/<slug>
# ... change, add/adjust a test ...
bash tools/tests/run_all.sh
git add -A && git commit -m "kit: <what and why>"
git push origin kit/<slug>
gh pr create --fill        # then edit the description per rule 8
```
Then report the PR link to the human and stop.

## Applying a newer gamedev-kit.zip (if the human gives you one)
Create a `kit/<slug>` branch, run `sh tools/kit_update.sh <zip>` (take `tools/kit_update.sh` fresh from the zip first:
`unzip -o <zip> tools/kit_update.sh -d .`), merge anything it put in `.kit-update/` into the matching files keeping
the project's changes, delete `.kit-update/`, run the tests, and open a PR as above.
