# Workflow and version-control order

## Task lifecycle
`add` -> `start` (branch) -> delegate -> agent commits -> `reviewer` -> `finish` -> push branch -> human merges PR -> `done`
Commands: `python3 tools/task.py ...`. One task at a time per checkout (branch switches affect the shared working tree).
Parallel work needs separate git worktrees; note that worktree-isolated subagents branch from the default branch,
so merge architecture changes to main first.

## Branches
- `arch/<slug>`: orchestrator work (docs, interfaces, scaffolding). Scope: orchestrator.
- `task/<agent>/<id>-<slug>`: one task by one agent. Scope: that agent only.
- `main`: protected. No direct commits or pushes (hooks + enable branch protection on GitHub too).
  The very first commit of an empty repo is the only exception.

## Binary assets (git + DVC)
1. `dvc add <file>` (core.autostage stages the `.dvc` pointer and `.gitignore`)
2. `git add -A && git commit` (pre-commit rejects binaries that are staged directly)
3. `git push origin <branch>` (no `-u`: the sandbox protects .git/config) (pre-push runs `dvc push` first and aborts the push if it fails)
4. After switching branches, post-checkout runs `dvc checkout`; on a fresh clone run `dvc pull`.

## What is enforced, and where
| Rule | Enforced by | Strength |
|---|---|---|
| Per-agent write scope | PreToolUse hook (agent_type) + pre-commit + CI | strong for Edit/Write; Bash is heuristic, git/CI are the backstop |
| Binaries only via DVC | pre-commit, completion gate, CI | strong |
| DVC push before git push | pre-push | strong unless hooks are skipped (`--no-verify` is blocked for agents) |
| No push/commit to main | pre-commit, pre-push, bash guard, GitHub branch protection | strong with branch protection on |
| Module decoupling | pre-commit + CI (res:// scan) | covers res:// references, not runtime tricks |
| Locked config files | scope guard (Claude's file tools) + Claude Code sandbox denyWrite (shell commands) | strong while the sandbox is on |
| Stay in the project folder, no uploads | Claude Code sandbox (WSL2): writes only in the project, Windows drives unreadable, network only to listed hosts | OS-enforced for shell commands; check with tools/sandbox_selftest.py |

## Testing
- Module unit tests: written by `module-dev` in the module's `tests/`.
- End-to-end tests and budget reports: `qa`, per docs/qa/TEST_PLAN.md.
- Static budgets (`tools/qa/check_budgets.py`): run by the producing asset agent before commit, and by qa.
- Rendering, FPS and device performance: not measurable in this sandbox. Preview on the PC host; profile on
  device via Xcode as the last step.

## What is not enforced
Quality, correctness, art direction, and anything a shell command can do that the guards do not recognize.
Human PR review is the final gate.
