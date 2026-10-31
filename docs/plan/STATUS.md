# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/status-t039 | status | none |

## Next actions, in order
1. Human A/B on T039 pass 4 (Active task). Then `task.py finish T039`, push, PR; `done` after human merges.
2. T017 qa rerun on the fixed kit: change `test_rubble_flipped_edge_pairs_match_the_known_count` to 0 (pins 3 and 10
   become 0 and 0), default `vertex_color_is_srgb` to false in `crypt_assembly.gd`; review; finish; push; PR.
3. T018 module-dev (maze) after T017. T019 module-dev (player): hookup rules in godot/modules/player/CLAUDE.md.
4. T020 M2 milestone QA with videos.
5. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
6. M3: T021 export preset (exclude `res://tests/*`, T014 preview scenes, automation, and
   `res://assets/*/model/*_preview*`), T022, T023 (Mac).

## Active task
T039, modeler, branch `task/modeler/T039-crypt-kit-restore-stone-charac`, HEAD 49c69dc, not pushed. Human chose to
restore the stone (overrides the earlier keep-pass-4 decision). Review 1 of 69baa36 FAIL (voussoirs not restored, pale
pier base). Review 2 of 49c69dc PASS, fit for human A/B: all fix targets met, check_kit 195/195, demo_failures 38/38,
budgets pass (textures 64.0/64 MB, no margin), rig hash 037f98494763. Pass 4 is at
`.captures/t039/pass4/`, review evidence at `.captures/t039_review2/` (scratch, not versioned).
Known misses, reported not chased: spectrum 0.549 (guide 0.40), fine/coarse 1.21 (clean 0.85), mid 0.0269 (0.030-0.045).
Open for the human: soffit flecks and course lines vs plain limewash (likely a new task, not a tune); optional trial of
stain 0.40-0.45 with wash 0.46; pier joints darker than the photo; ring joints dark where the photo's are pale; course 0
reads as a plinth; ochre colour. Overall look is about 6.5/10, below the 8/10 bar: this task restores stone, it does
not reach the bar.
T017 paused at 1ee652c, not pushed, not reviewed. Lighting (human): keep wall lamps.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
