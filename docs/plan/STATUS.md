# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-30, end of session 3.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).
- No agent is running. Nothing is left in the background.

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #42 | task/qa/T014-hero-budgets-animation-vs-refe | T014 hero QA (PASS, ready for T019) | `python3 tools/task.py done T014` |
| (this) | arch/session-continuity-hero-lessons | contract/player notes, STATUS.md, continuity rules, retro | none |

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
None. When a task starts, record here: id, agent, branch, the brief (paste it), last commit, review verdict.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
