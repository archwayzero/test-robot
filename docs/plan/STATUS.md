# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, session 4 (2026-10-31).

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/t015-look-decision-retro | look decision, retrospective, status | none |

## Next actions, in order
1. Close T015 (see Active task); human merges its PR.
2. T016, then T017 after T015 and T016 are merged, then T018 after T017.
3. T016 modeler: wall_lamp prop. T017 qa: kit + lamp budgets, judged in a Mobile scene, not the Cycles frame.
4. T019 module-dev (player): hero rig + AnimationTree; hookup rules are in godot/modules/player/CLAUDE.md (from T014).
   Can start once #42 is merged (depends on T010, T014), in parallel planning with T015.
5. T018 module-dev (maze) after T017; T020 M2 milestone QA with videos.
6. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
7. M3: T021 export preset (exclude `res://tests/*`, incl. the T014 preview scenes, and automation), T022, T023 (Mac).

## Active task
T015 review PASS at 3905db7 (structure 10/10, 178/178 checks, 33/33 failure demos). Being finished and pushed.
Look decision (human, 2026-10-31): keep pass 4 as is, knowing plaster is blotchier and the first reviewed stone looked
crisper; no replacement stone maps and no revert. 8.5 no longer applies to T015.
T017 notes from close-out: re-check `vertex_color_is_srgb`; top course 1.66-2.00 m is brighter (0.614 vs about 0.55);
consider a rubble winding or first-hit backface check; judge webs and piers in the Mobile scene under real lamp levels.
Do not run `run_pipeline.py --import` during a Godot job: it deletes `godot/.godot`. A rebuild changes the .blend md5.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
