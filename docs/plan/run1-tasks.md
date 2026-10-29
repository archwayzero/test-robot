# Run 1 task plan

Mirror of the task ledger (`.claude/state/ledger.json`, not versioned). Order of execution follows dependencies;
one task at a time; a task starts only after its dependencies are merged. Milestone tasks (qa) produce reports in
`docs/qa/reports/` and videos in `docs/qa/videos/<milestone>/`.

| ID | Agent | Module / asset | Title | Depends on | Milestone |
|---|---|---|---|---|---|
| T000 | modeler | hero | Track provided hero model with DVC, unchanged | | done |
| T001 | reference-director | crypt ref | Track crypt reference image with DVC, unchanged | | done |
| T002 | module-dev | core | Implement installer, GameState, SaveService, Automation + tests | arch/run1-plan | M1 |
| T003 | module-dev | maze | Layout generator (seeded, closed, low passages, lamp slots) + greybox world | T002 | M1 |
| T004 | module-dev | player | Controller, stances, jump, camera, capsule placeholder | T002 | M1 |
| T005 | module-dev | touch_controls | Joystick + Jump/Stance buttons -> actions | T002 | M1 |
| T006 | module-dev | exploration | Visited cells, persisted in GameState | T003 | M1 |
| T007 | module-dev | minimap | Fog-of-war mini-map + large map | T006 | M1 |
| T008 | module-dev | cloud_save | Autosave policy, local + fake backend | T002 | M1 |
| T009 | module-dev | game | Main scene composition, environment, phases | T003-T008 | M1 |
| T010 | qa | - | M1: e2e tests E1-E15, budgets, gameplay videos | T009 | M1 |
| T037 | reference-director | hero | Track human-provided `reference/hero/full_body.png` with DVC, unchanged | | M2 |
| T038 | reference-director | hero | Turnaround reference (orbit videos, 8-angle stills, notes) for modeler self-check | T037 | M2 |
| T011 | modeler | hero | Conform hero: generate digitigrade legs from reference, attach to Tripo upper body; 1.75 m, -Z, PBR, textures <= 2048 | T037 | M2 |
| T012 | reference-director | hero | Hero reference clips (8, see asset contract) | T011 | M2 |
| T013 | rigger-animator | hero | Hero rig (humanoid, digitigrade legs, I-pose rest, armpit weight isolation) + 8 clips | T012 | M2 |
| T014 | qa | hero | Hero budgets + animation vs reference | T013 | M2 |
| T015 | modeler | crypt_kit | Modular crypt pieces per docs/contracts/crypt-kit.md | arch/run1-plan | M2 |
| T016 | modeler | wall_lamp | Wall lamp prop | arch/run1-plan | M2 |
| T017 | qa | crypt_kit, wall_lamp | Kit + lamp budgets and visual check | T015, T016 | M2 |
| T018 | module-dev | maze | Swap in crypt_kit + lamps, lights/lightmaps, occluders | T010, T017 | M2 |
| T019 | module-dev | player | Hero rig + AnimationTree | T010, T014 | M2 |
| T020 | qa | - | M2: e2e, budgets, frame counts P1-P4, videos | T018, T019 | M2 |
| T021 | orchestrator | - | iOS export preset (min iOS 16, ASTC, exclude automation), Mac package | T020 | M3 |
| T022 | qa | - | Network/data audit + release checklist | T021 | M3 |
| T023 | human (Mac) | - | Xcode build, sign (personal team), install on iPhone 12, profile | T022 | M3 |
| T025 | module-dev | core | Hardening: set_value()/restore() validate key namespaces (found in T008 review); `CoreAPI.user_data_dir()` so test runs save under user://automation/ | | M1 (before T010) |
| T026 | module-dev | cloud_save | Sidecar meta under `CoreAPI.user_data_dir()` (tests never touch the player's files) | T025 | M1 (before T010) |
| T027 | module-dev | player | Implement `PlayerController.restore_stance()` (saved stance on load; found in T009) | | M1 (before T010) |
| T028 | module-dev | game | Call `restore_stance()` after spawn from a save; E12 stance check | T027 | M1 (before T010) |
| T029 | module-dev | cloud_save | Envelope float precision (E11, F1); throttle not 1 frame early (F2) | T010 | M1 fix |
| T030 | module-dev | player | Camera in low passages keeps the passage visible (F6) | T010 | M1 fix |
| T031 | module-dev | touch_controls | `get_jump_rect()`/`get_stance_rect()` test hooks (F4) | T010 | M1 fix |
| T032 | qa | - | M1 re-run: E1-E15 via public hooks (E11 via `AutoSave.decode_cloud_payload`), playthroughs in automation mode, re-record videos | T029-T031 | M1 |
| T033 | qa | - | e2e N1 hardening: E9 colour loop, E5/E7 failure branches into plain helpers | T032 | M1 follow-up |
| T034 | module-dev | player | Tests N1 audit: post-await assertions into plain helpers | T032 | M1 follow-up |
| T035 | module-dev | game | Tests N1 audit: post-await assertions into plain helpers | T032 | M1 follow-up |
| T036 | module-dev | core | Tests N1 audit (automation_test, others using await) | T032 | M1 follow-up |
| T024 | module-dev | cloud_save | ICloudBackend (native plugin) — only if Apple Developer account + iCloud capability are available | T023 | M3 (optional) |

Notes:
- T011 and T015/T016 have no code dependencies and may run between M1 tasks (still one task at a time).
- If lightmaps cannot be baked headless (T018), the fallback is real-time lights; the decision is recorded in the
  task report and in docs/retrospective/run1-corrections.md Part C.
