# Test plan (orchestrator-owned; human approves)

Status: APPROVED FOR RUN 1 (human, 2026-10-25). Mechanic ids per docs/architecture/DECISIONS.md D15.

## Platform and limits
iOS, minimum iPhone 12 (A14 = Apple7 GPU family, 4 GB RAM, 2532x1170), landscape, target 30 fps, Godot 4.7.2,
Mobile renderer, Metal. Static and frame budgets: docs/qa/budgets.json (sources and estimates listed there).

## Where each thing can be checked
| Sandbox (agents) | PC preview (human) | Mac + iPhone 12 (human, M3) |
|---|---|---|
| Unit + end-to-end tests, headless | Look, lighting, camera feel | Frame rate (33.3 ms frame), thermals, battery |
| Static budgets per GLB (`check_budgets.py`) | Mouse-as-touch feel (approximate) | Real touch, multi-touch |
| Per-frame draw calls / rendered triangles at fixed camera points, CPU-rendered (counts valid, timings NOT) | | Memory (Xcode Instruments) |
| Screenshots and gameplay videos (CPU rendering, `capture.py` / `record.py`) | | iCloud sync, iOS 16+ install, ASTC textures |
| Animation clips vs reference frames | | |
| Network/data audit (`net_data_audit.py`) | | App Store privacy answers (not publishing in run 1) |

## Layers
| Layer | What | Who | Runs where | When |
|---|---|---|---|---|
| Unit | module logic | `module-dev` | headless Godot in sandbox | every module task |
| End-to-end | scripted playthroughs via `Core.automation` only | qa | headless Godot in sandbox | per milestone |
| Static budgets | tris, draw-call estimate, joints, textures | asset agents + qa | sandbox (`tools/qa/check_budgets.py`) | every asset task, every milestone |
| Frame counts | draw calls + rendered triangles at camera points P1-P4 | qa | sandbox, CPU renderer (virtual display) | per milestone |
| Animation vs reference | clips vs `reference/hero/<clip>/` frames + NOTES.md | qa | sandbox | after the hero rig |
| Gameplay videos | MP4 per scripted playthrough + what to look for | qa | sandbox (`tools/qa/record.py`) | every milestone |
| Visual / feel | watch videos; play merged builds | human | PC host | per milestone |
| Network and data audit | contacts, collected data, iOS permissions | qa (+ human) | sandbox (`tools/qa/net_data_audit.py`) | before the device build |
| Device performance | FPS, thermals, memory on iPhone 12 | human | Mac + Xcode + device | M3 |

Milestones: **M1** greybox playable (T002-T010), **M2** art integrated (T011-T020), **M3** iOS device build (T021+).

## Acceptance criteria per mechanic
All end-to-end tests: `Core.automation.set_seed(1)`, `set_fixed_timestep(60, 30)`, load `GameMain.MAIN_SCENE`, wait
for `ready_to_play`, then drive input through the automation API only.
Unit tests (module-dev) cover the same rules at module level; the module CLAUDE.md files list them.

| Id | Mechanic | Test (e2e, `godot/tests/`) | Steps | Expected |
|---|---|---|---|---|
| E1 | M1 | walk_and_run_speed | joystick 50% forward for 60 frames, then 100% for 60 frames | horizontal speed 1.6 +-5%, then 4.0 +-5% m/s |
| E2 | M1 | stance_cycle | tap stance 3x in an open cell | heights STAND > 1.0 > 0.5 (crouch, crawl), back to STAND; speeds 1.0 / 0.5 when moving |
| E3 | M1 | low_passage | crouch into a CROUCH cell, tap stance (to crawl) then try to stand twice | in the CROUCH cell standing is refused; in a CRAWL cell crouching is refused |
| E4 | M1 | jump | tap jump standing; then crawl and tap jump | `jumped` then `landed` within 60 frames; no jump while crawling |
| E5 | M1 | wall_collision | from the start cell push into the nearest wall at 8 angles, 120 frames each | player never closer than 0.29 m to any wall plane, never outside the grid |
| E6 | M2 | maze_layout | inspect `get_maze_world().get_layout()` | 20x20, all cells reachable, boundary closed, same layout on 2 runs |
| E7 | M2 | world_matches_layout | raycast across 40 sampled edges | hit iff `has_wall` |
| E8 | M3 | minimap_fresh | fresh save, look at exploration + minimap | exactly 1 explored cell (start); marker in start cell |
| E9 | M3 | minimap_reveal | scripted walk through 5 open cells | exactly those 6 cells explored, each `cell_explored` once |
| E10 | M3 | large_map | tap `get_small_rect()` centre; then tap screen centre | opens (phase map_open, tree paused, controls hidden); closes (phase playing) |
| E11 | M4 | autosave_throttle | explore 2 cells within 10 s, wait 12 s game time | 1 save immediately, 1 after the interval; fake backend got identical bytes |
| E12 | M4 | save_restore | explore, `save_now()`, reload main scene | same explored set, position within 0.1 m, same stance |
| E13 | M4 | cloud_unavailable | unavailable fake backend, explore a cell | local save OK, `cloud_error == ERR_UNAVAILABLE`, no visible error |
| E14 | M5 | touch_joystick | `drag()` from left-half point by 45 px and 90 px | `move_forward` strength ~0.5 then ~1.0; running only at ~1.0 |
| E15 | M5 | touch_buttons | `touch()` the Jump and Stance buttons while the stick is held | both actions fire; stick keeps moving the player |

Frame-count camera points (qa, CPU renderer, M2): P1 start cell looking down the longest corridor, P2 a 3-way
junction, P3 inside a CRAWL cell, P4 the large map open. Report draw calls and rendered triangles
(`Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME`, `RENDER_TOTAL_PRIMITIVES_IN_FRAME`) against budgets.json
`frame_budgets`.

Gameplay videos per milestone (`docs/qa/videos/<milestone>/`): `walkthrough.mp4` (60 s scripted walk incl. run),
`stances.mp4` (stand/crouch/crawl + low passages + jump), `minimap.mp4` (reveal + large map). The qa report lists
timestamps and what the human should look for (clipping, camera inside walls, foot sliding, fog-of-war correctness).

## Test runner
In-repo runner `godot/addons/test_runner/` (orchestrator-owned; gdUnit4 skipped: no release lists Godot 4.7.2, see
docs/architecture/THIRDPARTY.md). Test files are `*_test.gd` extending `TestCase` (assert helpers, `wait_frames`,
`automation()`); every `test_*` method runs, may `await`, and has a frame budget (`timeout_frames`, default 1800).

```
# everything (module tests + godot/tests e2e)
godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation
# one module / one folder, with a markdown report
godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation --filter maze
godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation --dir res://tests --report <file.md>
```
Exit code 0 = all passed, 1 = failures, 2 = nothing found / not a test run. Runner self-test:
`--dir res://addons/test_runner/selftest` must report 4 passed, 2 failed (intentional), exit 1.

## Score
The static budget score (0-100) covers only what the sandbox can measure. Report it with the PASS/FAIL list,
never alone.
