# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, session 4 (2026-10-31).

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #48 | task/modeler/T016-wall-lamp-prop | T016 wall_lamp | `python3 tools/task.py done T016` |
| (this) | arch/run1-retro-lighting-alarms | retrospective, memory figures, status | none |

## Next actions, in order
1. Human merges #48, then T017 qa, then T018 module-dev.
2. Finish retrospective texture analysis.
3. T016 modeler: wall_lamp prop. T017 qa: kit + lamp budgets, judged in a Mobile scene, not the Cycles frame.
4. T019 module-dev (player): hero rig + AnimationTree; hookup rules are in godot/modules/player/CLAUDE.md (from T014).
   Can start once #42 is merged (depends on T010, T014), in parallel planning with T015.
5. T018 module-dev (maze) after T017; T020 M2 milestone QA with videos.
6. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
7. M3: T021 export preset (exclude `res://tests/*`, incl. the T014 preview scenes, and automation), T022, T023 (Mac).

## Active task
T016 PASS, pushed, PR #48 awaiting human merge (then `task.py done T016`). Look 8.5, structure 10/10. T015 done.
Lighting decision (human, 2026-10-31): keep the wall lamps, D9 stands; no windows or hidden uplights.
Texture triage still running in `.captures/t015_triage/`; a modeler-side triage follows; both go into this branch's
retrospective with snapshots via DVC.
T017 after #48 merges. Judge at real camera height (about 2.43 m), shipped light level, wall-hug passes. T021 must also
exclude `res://assets/*/model/*_preview*`.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
