# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #55 | task/module-dev/maze/T018-maze-crypt-kit-lamps-lighting- | T018 | `task.py done T018` |
| (this) | arch/after-t018 | maze docs, retrospective, status | none |

## Next actions, in order
1. After #55: T040 module-dev (game): tune `ambient_light_color` away from the cool cast and match background OUTPUT to fog
   output by measuring pixels ([8,8,8]; copying 0.03 left [0,0,0]). Removes the slit on run (0,6)/(0,7) south. Update
   the Environment copy in maze_preview.gd only through a maze task, or report it. Human judges lighting from captures.
2. Orchestrator: set the occlusion project setting in project.godot, then remove the setter at maze_world_impl.gd:58.
3. T019 module-dev (player): hookup rules in godot/modules/player/CLAUDE.md.
4. T020 M2 milestone QA with videos (motion, shimmer, occlusion pop, TEST_PLAN P1-P4, the 28 unmeasured views).
5. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits).
6. M3: T021 export preset (exclude `res://tests/*`, T014 preview scenes, automation, `res://assets/*/model/*_preview*`),
   T022, T023 (Mac). Verify occlusion on iOS and the load stall on device.

## Active task
None running. T018 review finished at 756a78e, PR #55: 308/308, budgets 100, assembly 8.5/10, lighting 6.5/10. Known limits
in the PR. Lighting (human): keep wall lamps. Kit look accepted.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
