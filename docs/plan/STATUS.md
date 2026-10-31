# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #51 | task/modeler/T039-crypt-kit-restore-stone-charac | T039 | `task.py done T039`, then T017 rerun |
| (this) | arch/retro-stone-restored | retrospective, status | none |

## Next actions, in order
1. After #51 merges: T017 qa rerun on the fixed kit: change `test_rubble_flipped_edge_pairs_match_the_known_count` to 0
   (pins 3 and 10 become 0 and 0), default `vertex_color_is_srgb` to false in `crypt_assembly.gd`; review; finish; push; PR.
2. T018 module-dev (maze) after T017. T019 module-dev (player): hookup rules in godot/modules/player/CLAUDE.md.
3. T020 M2 milestone QA with videos.
4. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
5. M3: T021 export preset (exclude `res://tests/*`, T014 preview scenes, automation, and
   `res://assets/*/model/*_preview*`), T022, T023 (Mac).

## Active task
None running. T039 accepted by the human at pass 4 (49c69dc, review PASS, about 6.5/10, below the 8/10 bar): no further
texture or colour work. Known misses accepted: spectrum 0.549, fine/coarse 1.21, mid 0.0269; soffit stays flecked stone.
T017 paused at 1ee652c, not pushed, not reviewed. Lighting (human): keep wall lamps.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
