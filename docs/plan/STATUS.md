# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #53 | task/qa/T017-crypt-kit-wall-lamp-budgets-an | T017 | `task.py done T017` |
| (this) | arch/t018-ready | contract figures for T018, status | none |

## Next actions, in order
1. After both merge: T018 module-dev (maze), rules in docs/contracts/crypt-kit.md and docs/qa/reports/T017-crypt-kit-wall-lamp.md.
2. T019 module-dev (player): hookup rules in godot/modules/player/CLAUDE.md.
3. T020 M2 milestone QA with videos.
4. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
5. M3: T021 export preset (exclude `res://tests/*`, T014 preview scenes, automation, and
   `res://assets/*/model/*_preview*`), T022, T023 (Mac).

## Active task
None running. T039 done (#51). T017 PASS, HEAD 319567a, PR #53: 59/59 tests, budgets 100.0. Lighting (human): keep wall
lamps. Human accepted the kit look; no further texture or colour work.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
