# Test plan (orchestrator-owned; human approves)

Status: TEMPLATE. The orchestrator fills this in during planning (Prompt 2, Phase A) from the specs.

## Platform and limits
Summarize docs/specs/PLATFORM.md and the approved values in docs/qa/budgets.json (with sources).

## Layers
| Layer | What | Who | Runs where | When |
|---|---|---|---|---|
| Unit | module logic | `module-dev` | headless Godot in sandbox | every module task |
| End-to-end | scripted playthroughs via core automation API | qa | headless Godot in sandbox | per mechanic, per milestone |
| Static budgets | tris, draw-call estimate, joints, textures | asset agents + qa | sandbox (`tools/qa/check_budgets.py`) | every asset task, every milestone |
| Animation vs reference | clips vs `reference/` notes/frames/keypoints | qa | sandbox | per animated asset |
| Gameplay videos | MP4 of each scripted playthrough, with timestamps to check | qa | sandbox (`tools/qa/record.py`) | every milestone |
| Visual / feel | watch the videos; play only merged builds | human | PC host | per milestone |
| Network and data audit | what the game contacts, collects, sends; iOS permissions; App Store privacy draft | qa (+ human) | sandbox (`tools/qa/net_data_audit.py`) | every release candidate |
| Device performance | FPS, thermals, memory on iPhone 12 | human | Mac + Xcode + device | final step |

## Acceptance criteria per mechanic
(One row per M# from docs/specs/MECHANICS.md: test name, steps via automation API, expected state.)

## Test runner
Undecided (bootstrap 2026-10-25). gdUnit4 v6.2.2 was evaluated and not installed: compatibility with Godot 4.7.2
not confirmed (details: docs/architecture/THIRDPARTY.md). Next options, for the human to choose before the first
module task: (a) a gdUnit4 release that lists 4.7.2, re-verified the same way; (b) a minimal in-repo runner under
tools/ (headless `godot --headless --path godot -s <runner> -- --automation`). End-to-end tests use only the core
Automation API (godot/modules/core/public/automation.gd) either way.

## Score
The static budget score (0-100) covers only what the sandbox can measure. Report it with the PASS/FAIL list,
never alone.
