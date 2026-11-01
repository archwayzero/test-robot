# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #62 | task/rigger-animator/T042-hero-textures-import-as-astc | T042 | `task.py done T042` |
| (this) | arch/before-t020 | status, retrospective | none |

## Priority (human, 2026-10-31)
Reach running on the phone fastest. Lighting and occlusion wait until after the first device build. Order below.

## Next actions, in order
1. T020 qa, slimmed (human kept it): movement, stances, jump, budgets, one short video.
2. T021 orchestrator: export preset (exclude `res://tests/*`, T014 preview scenes, automation,
   `res://assets/*/model/*_preview*`, unused `res://assets/hero/model/*`), min iOS 16, ASTC, Mac package.
3. T022 qa: network/data audit + release checklist. T023 human (Mac): Xcode build, sign, install on iPhone 12, profile.
   Device checks: frame rate, occlusion on iOS, load stall, first-fade hitch, `fog_sky_affect` output and cost.

## Deferred until after the first device build
Hero fill light (human: judge the dark hero on a phone; spec in the T019 review, hero-only omni on the camera, layer 20).
Lighting (reviewer 7.0/10): pale plaster near lamps, dark corridor ends, crawl ceiling wedges. T020's full scope: motion,
shimmer, occlusion pop, TEST_PLAN P1-P4, the 28 unmeasured views. N1 audits T033-T036.
Tooling: tools/xdisplay.py docstring wrongly says no lock file, and `_free_display` misses a stale display-90 lock.
Godot hangs instead of exiting on a script parse error in a capture probe.

## Active task
None running. T019 done (#61). T042 awaiting merge: 345/345, all six hero textures ASTC. Lighting (human): keep wall lamps.
Kit look accepted.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
