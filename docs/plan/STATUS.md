# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, session 4 (2026-10-31).

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/run1-retro-lighting-alarms | retrospective, memory figures, status | none |

## Next actions, in order
1. Human decides stone (Active task); then kit fix, T017 review and merge, T018 module-dev.
3. T016 modeler: wall_lamp prop. T017 qa: kit + lamp budgets, judged in a Mobile scene, not the Cycles frame.
4. T019 module-dev (player): hero rig + AnimationTree; hookup rules are in godot/modules/player/CLAUDE.md (from T014).
   Can start once #42 is merged (depends on T010, T014), in parallel planning with T015.
5. T018 module-dev (maze) after T017; T020 M2 milestone QA with videos.
6. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
7. M3: T021 export preset (exclude `res://tests/*`, incl. the T014 preview scenes, and automation), T022, T023 (Mac).

## Active task
T017, qa, branch `task/qa/T017-crypt-kit-wall-lamp-budgets-an`, HEAD 1ee652c, not pushed, not reviewed. FAIL on 5 of 58
tests from 3 kit defects, none blocks T018: arch collision reversed (all 96 faces, build.py:1050), pier missing top
(before build.py:977), ceiling_crawl flips (before build.py:1519). Tests stay failing until fixed.
Waiting on human: restore better stone in one kit pass with those fixes, or keep pass 4. If restored: v2 spectrum with
more mid, not a straight revert; see docs/retrospective/t015-texture-regression.md. New T0xx modeler task either way
for the defects, then qa changes `test_rubble_flipped_edge_pairs_match_the_known_count` to 0.
Top course 1.66-2.00 m is brighter and check_kit skips it. Lighting (human): keep wall lamps.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
