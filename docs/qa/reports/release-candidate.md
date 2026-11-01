RESULT: PASS

# T022 release candidate check, first Mac build (0.1.0)

Commit tested: main d8adff7, Godot 4.7.2 stable. Sandbox only: nothing here measures an iPhone. No frame rate, memory,
GPU, touch or thermal result exists for this build.

**One decision for the human before packaging:** see question 1 in `network-data-audit.md`. This build saves on the
device only; nothing reaches the cloud yet.

## Results
| Check | Result |
|---|---|
| Static budget score | **100.0**, PASS, exit 0 (budget status: approved for run 1 only) |
| Budget limits exceeded | 0 |
| Full suite | **359 passed, 0 failed**, 29 files, exit 0 |
| End-to-end subset (`--dir res://tests`) | 73 passed, 0 failed, 9 files, exit 0 |
| Runner selftest | 5 passed, 3 failed as designed, exit 1, so the runner can report failure |
| Pack export, preset "iOS" | exit 0, 0 ERROR or WARNING lines, 34,683,252 bytes |
| Pack boot, `--quit-after 150` | exit 0, 0 ERROR or WARNING lines, verbose log |
| Tree after all runs | clean; nothing under `godot/` changed |

The suite log has engine ERROR lines. The backtraces I sampled and the tests next to them are the save and game state
tests feeding in bad data on purpose (for example `test_v3_crafted_payloads_rejected_without_objects`), and those tests
pass. I did not trace every line.

Budget detail, measured from exported .glb files. Texture memory is an uncompressed upper bound and draw calls are an
estimate, not device numbers.

| Asset | Triangles | Draw calls (est) | Joints | Max texture | Texture MB (upper bound) |
|---|---|---|---|---|---|
| crypt_kit | 4552 / 21000 | 14 / 14 | 0 / 0 | 2048 / 2048 | 64.0 / 64 |
| hero | 19949 / 20000 | 2 / 4 | 23 / 64 | 2048 / 2048 | 60.0 / 64 |
| wall_lamp | 880 / 1000 | 2 / 2 | 0 / 0 | 512 / 2048 | 4.02 / 16 |

All assets on screen at once: 25381 / 150000 triangles, 128.02 / 512 MB, 18 / 32 draw calls. crypt_kit is at its limit
on draw calls and texture memory, and hero is 51 triangles under its limit.

## Export check
Read from the pack's own file table and the `.ctex` headers, not only from the export log.

| Check | Result |
|---|---|
| Files in pack | 127 (pack format 4, engine 4.7.2, not encrypted) |
| Under tests, `addons/test_runner`, `modules/core/internal/automation`, `*_preview*`, `assets/hero/model` | **0** |
| Any file from `addons/` | 0 |
| `.ctex` textures | **16, all `.astc.ctex`**, header format 35 (`FORMAT_ASTC_4x4`), mipmapped |
| Compiled scripts | 39 `.gdc`, exactly the 41 non-test scripts minus 2 excluded preview scripts |
| URLs in the raw pack bytes | 0 (compiled scripts are compressed; their sources were checked in the audit) |

The boot log loads core, maze, exploration, cloud_save, player, touch_controls and minimap from `.gdc`. The boot does not
prove rendering, because headless Godot draws nothing. It also ended before any autosave, so the save path has been
exercised by tests only, not in the exported pack.

## Findings
None of these fails the RC. No new defect was found.

| Item | State | Owner |
|---|---|---|
| F1: hero disappears after stopping just past a low passage's mouth | Open, deferred; judge on the phone | `module-dev` player |
| F2: 8-frame fade after boot; partial fades show the hero's face and chest from behind | Open, deferred; judge on the phone | `module-dev` player |
| Hero fill light: dark hero | Deferred; judge on the phone | orchestrator |
| Lighting (reviewer 7.0/10): pale plaster near lamps, dark corridor ends, crawl ceiling wedges | Deferred | orchestrator |
| T020 scope left over: motion, shimmer, occlusion pop, TEST_PLAN P1-P4, 28 unmeasured views | Deferred | qa |
| N1 audits T033-T036 | Deferred | orchestrator |
| Tooling: `tools/xdisplay.py` docstring and `_free_display` stale lock; Godot hangs on a parse error in a capture probe | Deferred, not in the game | orchestrator |
| No app icon | Open. The handoff covers it; Godot may report missing required icons at export. Needed before any App Store submission | orchestrator, human |
| App Store Team ID empty | Intended; human fills it in on the Mac | human |
| No cloud save in this build | Local-only backend, as planned by DECISIONS.md D11; iCloud is T024, optional, M3 | human decision |
| `FakeCloudBackend` is in the pack | In-memory, no caller outside tests, harmless | `module-dev` cloud_save, later |

## Known risks for the device
All unmeasured, for T023 to check per `docs/IOS_HANDOFF.md`.
- Frame rate against the 30 FPS target, including occlusion culling when turning corners. The estimates above say nothing about it.
- Real ASTC memory use and load time.
- Heat and memory over 10 minutes.
- Metal driver on real hardware: the sandbox renders on the CPU, and the iOS simulator cannot run the Mobile renderer.
- Real touch and the safe area on a notched screen: tests inject touch and use a test seam for the safe area.
- Hero readability, F1 and F2, which are design calls for a real screen.
- Background and foreground saving on real iOS, tested here only through injected notifications.
- Personal-team installs expire after 7 days.
- The package contains the whole `godot/` folder. The test exclusions come from the preset at export, so export with the
  committed preset unchanged.
