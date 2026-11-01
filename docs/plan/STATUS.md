# Run status (orchestrator-maintained; read this first in a new session)

Last updated: 2026-10-31, session 4.

## Where we are
- Milestone: **M2 art**. M1 complete (T032 merged, #33).
- Hero asset chain finished: T037/T038 references (#36, #38), T011 model (#37, 10/10 structure), T012 motion clips
  (#40), T013 rig + 8 clips (#41, all clips >= 8.5/10), T014 QA in Godot (PR #42).

## Open PRs (human to review/merge)
| PR | Branch | Task | State after merge |
|---|---|---|---|
| #65 | arch/t021-export | T021: iOS preset, name The Crypt, bundle ID, handoff, status | none |

## Priority (human, 2026-10-31)
Reach running on the phone fastest. Lighting and occlusion wait until after the first device build. Order below.

## Next actions, in order
1. T022 qa after #65 merges: net_data_audit, `docs/qa/reports/network-data-audit.md` and `release-candidate.md`, each with
   a line `RESULT: PASS`, committed after the last change to godot/.
2. After that merges: `python3 tools/release/make_mac_package.py --version 0.1.0` on clean, current main.
3. T023 human (Mac), per docs/IOS_HANDOFF.md: report the device checks listed there.

## Deferred until after the first device build
F1 hero hidden past low-passage mouths, F2 partial fade looks wrong (T020 report): judge on the phone.
Hero fill light (human: judge the dark hero on a phone; spec in the T019 review, hero-only omni on the camera, layer 20).
Lighting (reviewer 7.0/10): pale plaster near lamps, dark corridor ends, crawl ceiling wedges. T020's full scope: motion,
shimmer, occlusion pop, TEST_PLAN P1-P4, the 28 unmeasured views. N1 audits T033-T036.
Tooling: tools/xdisplay.py docstring wrongly says no lock file, and `_free_display` misses a stale display-90 lock.
Godot hangs instead of exiting on a script parse error in a capture probe.

## Active task
None running. T021 on PR: export preset done; pack export 127 files, 0 test or preview files, 16 ASTC textures, boots
headless without errors. App Store Team ID is left empty for the human. No app icon yet.

## Process notes that worked in session 3
- Quality loops: reviewer measures independently and scores out of 10 against the reference; send back with numbered,
  measured targets until the bar is met (model 10/10 structure, rig >= 8.5 per clip). Look at the strips yourself.
- QA tests must be shown able to fail (T014: the first seam check was vacuous).
