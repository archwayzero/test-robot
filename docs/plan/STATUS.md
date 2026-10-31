# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, session 4 (2026-10-31).

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/wall-lamp-orientation | wall_lamp +Z orientation, status | none |

## Next actions, in order
1. Close T016; human merges its PR.
2. T017 after T016 is merged, then T018 after T017.
3. T016 modeler: wall_lamp prop. T017 qa: kit + lamp budgets, judged in a Mobile scene, not the Cycles frame.
4. T019 module-dev (player): hero rig + AnimationTree; hookup rules are in godot/modules/player/CLAUDE.md (from T014).
   Can start once #42 is merged (depends on T010, T014), in parallel planning with T015.
5. T018 module-dev (maze) after T017; T020 M2 milestone QA with videos.
6. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
7. M3: T021 export preset (exclude `res://tests/*`, incl. the T014 preview scenes, and automation), T022, T023 (Mac).

## Active task
T016, modeler, branch `task/modeler/T016-wall-lamp-prop`, HEAD 1ccc9fe, independent review running. Bar agreed up front:
structure 10/10, look >= 8/10 in Godot Mobile at 1-4 m. T015 is done (#46 merged; human kept pass 4).
Also running: reviewer texture triage in a clone under `.captures/t015_triage/`, then a modeler-side triage. Result goes
into docs/retrospective/ with snapshots (DVC) on a new arch/ branch. T017 next after T016 merges, then T018.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
