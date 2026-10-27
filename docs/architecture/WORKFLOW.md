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

## Memory and heavy jobs
Rule (human, 2026-10-26): start a render-heavy job only if available memory minus its measured peak leaves >= 4 GB
spare; otherwise wait for the running job. All Godot/Blender/ffmpeg commands go through `tools/qa/memguard.py`, which
enforces that check and kills runaway jobs. Scratch output (captures, benchmarks, logs) goes under `.captures/`.

Measured peaks (dev machine: 28 GB RAM, 24 GB swap, 28 threads; each job run alone, sampled every second):
| Job | Peak (drop in available memory / process RSS) | Duration |
|---|---|---|
| Godot capture, accurate, maze-sized test scene | ~0.5 GB / 0.7 GB | 6 s |
| Godot recording, 20 s, accurate | ~0.3 GB / 0.5 GB | 16 s |
| Godot `--import` | ~0.6 GB | ~10 s |
| Headless test suite (core) | < 0.1 GB | 1 s |
| Blender 5.2.3 Cycles CPU still, 1024 px, 32 samples, provided hero.glb (9.7 MB) | ~1.0 GB / 1.15 GB | 5 s |
| Blender 5.2.3 Cycles CPU bake, 3 passes at 2048x2048, 16 samples, procedural material | ~0.8 GB / 1.0 GB | 16 s |

Use `--expect-peak-mb 2000` for Blender jobs (headroom for larger scenes and 4096 px bakes; re-measure if a
job's `peak_drop` exceeds 1.5 GB). Measured 2026-10-27 before T011.

Incident: run 1's first core test re-launched Godot recursively (~300 MB/s) and the session was killed by the OOM
killer. Since then: no process spawning in code or tests, and every heavy command runs under memguard.
