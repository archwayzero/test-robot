# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-11-06, session 5.

## Where we are
- First device build (0.1.0, T023) ran on the human's iPhone: smooth, not hot.
- New work (human, 2026-11-06): hero cloak, white mantle + gray floor-length cloak, looser hood; idle still, run streams,
  jump flares. Decision D18; spec in docs/contracts/blender-godot-assets.md "Asset: hero cloak". Then ship 0.2.0 to the phone.

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| (this) | arch/hero-cloak | cloak spec, D18, tasks T043-T047, preset code sign identity = Apple Development | none |

## Next actions, in order
1. T043 reference-director: DVC-track the two cloak reference images.
2. T044 modeler: cloak + looser hood inside 20,000 tris / 64 MB / 4 draw calls.
3. T045 rigger-animator: cloak bones, cloth simulation baked per clip, limits on every frame.
4. T046 qa: budgets, import test, limits, e2e, frame counts. Look at the strips.
5. T047 qa: rerun both release reports (godot/ changed: preset + hero), then package 0.2.0 on clean main.
6. App icon: not in the repo yet (human sets it on the Mac; `dist/the_crypt_icon_1024.png`). Optional modeler task to
   track it under godot/assets/app_icon/model/ and set config/icon.

## Deferred until after the first device build
F1 hero hidden past low-passage mouths, F2 partial fade looks wrong (T020 report): judge on the phone.
Hero fill light (human: judge the dark hero on a phone; spec in the T019 review, hero-only omni on the camera, layer 20).
Lighting (reviewer 7.0/10): pale plaster near lamps, dark corridor ends, crawl ceiling wedges. T020's full scope: motion,
shimmer, occlusion pop, TEST_PLAN P1-P4, the 28 unmeasured views. N1 audits T033-T036.
Tooling: tools/xdisplay.py docstring wrongly says no lock file, and `_free_display` misses a stale display-90 lock.
Godot hangs instead of exiting on a script parse error in a capture probe.

## Active task
T043 (see Next actions). T023 done on device. Cloud save: not in this build (human, D11).
Lighting (human): keep wall lamps. Kit look accepted.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
