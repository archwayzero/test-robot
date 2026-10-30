# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/crypt-kit-arch-relief | crypt_kit crown 4.15, status | none |

## Next actions, in order
1. After merges: `git switch main && git pull --ff-only origin main && dvc checkout`, then `task.py done T014`.
2. T015 modeler: crypt_kit modular pieces (docs/contracts/crypt-kit.md). Per ARCHITECTURE.md "Turnaround
   references": decide if the kit needs reference-director stills from `reference/map/crypt.jpg` first.
   Give the modeler measured pass/fail targets and a check script, as in T011.
3. T016 modeler: wall_lamp prop. Then T017 qa (kit + lamp budgets, visual).
4. T019 module-dev (player): hero rig + AnimationTree; hookup rules are in godot/modules/player/CLAUDE.md (from T014).
   Can start once #42 is merged (depends on T010, T014), in parallel planning with T015.
5. T018 module-dev (maze) after T017; T020 M2 milestone QA with videos.
6. N1 follow-ups: T033 (qa), T034-T036 (module-dev audits) - small, slot between asset tasks.
7. M3: T021 export preset (exclude `res://tests/*`, incl. the T014 preview scenes, and automation), T022, T023 (Mac).

## Active task
T015, modeler, branch `task/modeler/T015-crypt-kit-modular-pieces`, started 2026-10-30 (session 4). T014 is done.
Bar (human): reviewer scores against the reference; loop until met, then report. No turnaround: crypt.jpg is a real
photo, so an orbit would only add AI invention. Bar set: structure 10/10, look >= 8.5/10.
Pass 1 result (last commit 7590125): all measured targets pass, modeler look 8.2, orchestrator look ~7.5. Arch relief
impossible under the shared 3.9 crown, so this branch raises vault/wall top to 4.15. Pass 2 builds to that contract.
Brief: contract exact (7 pieces, one GLB, -colonly, UV2, <= 2 materials, baked tileable, 64 MB, 21,000 tris, 14 draw
calls), tri guides floor 200, wall 400, pier 300, arch 800, vault_bay 1500, ceilings 1200; check_kit.py must be shown
able to fail; arcade render at the crypt.jpg camera, side by side. Scope: blender/models/crypt_kit/**,
godot/assets/crypt_kit/model/**. No wall_lamp (T016). Reviewer must examine: the seam metric denominator change
(mean -> p90 after ashlar ORM V failed at 1.61) and texture memory at 64.0/64 with no margin.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
