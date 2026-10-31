# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #57 | task/module-dev/game/T040-game-environment-ambient-backg | T040 | `task.py done T040` |
| (this) | arch/after-t040 | occlusion project setting, maze note, status | none |

## Next actions, in order
1. After both merge: T041 module-dev (maze): in tests/support/maze_preview.gd set ambient (0.42, 0.4, 0.4) and
   `fog_sky_affect` 1.0; remove the occlusion setter in `build()` now that project.godot enables it.
2. T019 module-dev (player): hookup rules in godot/modules/player/CLAUDE.md.
3. T020 M2 milestone QA with videos (motion, shimmer, occlusion pop, TEST_PLAN P1-P4, the 28 unmeasured views).
4. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits).
5. M3: T021 export preset (exclude `res://tests/*`, T014 preview scenes, automation, `res://assets/*/model/*_preview*`),
   T022, T023 (Mac). Device checks: occlusion on iOS, load stall, `fog_sky_affect` output and cost.
Tooling: tools/xdisplay.py docstring wrongly says no lock file, and `_free_display` misses a stale display-90 lock.
Lighting still weak (reviewer 7.0/10): pale plaster near lamps, dark corridor ends, crawl ceiling wedges.

## Active task
None running. T040 review PASS, PR #57: 313/313 before the final `.uid` commit, budgets 100. Lighting (human): keep wall
lamps. Kit look accepted.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
