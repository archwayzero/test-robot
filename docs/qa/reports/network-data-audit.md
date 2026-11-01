RESULT: PASS

# T022 network and data audit, first Mac build (0.1.0)

**Open questions for the human, listed in section 5. Question 1 needs a decision before packaging; the PASS does not
decide it for you.** The PASS means: the game's own code contacts nothing, collects nothing, and every scan finding is
explained. It does not cover the Godot engine binary, which is not available in the sandbox.

Commit audited: main d8adff7. Method: `tools/qa/net_data_audit.py`, each finding read in the code, then wider searches of
the source for what the scan's patterns miss (all `OS.`, `FileAccess`, `DirAccess`, `DisplayServer`, `Time`, `IP`,
sensors, `ClassDB`, dynamic `.call`, every `://`, native libraries), then the pack's file table.

Scan scope matches the export: the scan skips `/tests/`, and the export excludes `res://tests/*`,
`res://modules/*/tests/*` and `res://addons/test_runner/*`; the pack holds 0 such files. The scan does cover the
automation folder, which the export excludes, so 2 of its findings are not in the shipped game. Scan output is in
`.captures/t022/net_scan.md` (not committed): 0 network, 4 data, 1 outside the engine, 0 permission texts, 1 addon.

## 1. Network destinations
**None.** No HTTP, socket, WebSocket, WebRTC, multiplayer or URL exists in game code or scenes, and the raw pack has no
URL. The game cannot open links.

| Addon | In the shipped game | Traffic |
|---|---|---|
| `test_runner` (in-repo) | No, 0 files in the pack | None; test runner only |

No third-party addon, native library, GDExtension, iOS plugin, C# or `.gdip` exists in `godot/`.

`cloud_save`:
- Real play calls `make_platform_backend()` (`game_main_impl.gd:139`), which always returns `LocalOnlyBackend`.
  That backend reports unavailable, its push fails, and its pull is empty, so `_save()` never pushes anything.
- `FakeCloudBackend` is in the pack but only holds data in memory, has no network code, and nothing outside tests calls
  `make_fake_backend`.
- The iCloud code is comment text only (`cloud_save_factory_impl.gd:20-25`). `icloud_backend.gd` and the plugin do not exist.

## 2. Player and device data
No account, name, email, device ID, advertising ID, location, contacts, photos, clipboard or sensor data is read.

| Data | Where | Why | Leaves the device |
|---|---|---|---|
| Position, yaw, stance, visited cells, cell count, maze seed | `user://saves` (`save_service_impl.gd`) | Autosave, spec MECHANICS.md | No |
| Local save time (unix time) | Save header and `user://cloud_save/meta.cfg` | Choose the newer copy on restore | No |
| OS name | `game_main_impl.gd:52` | iOS frame rate cap only; not stored | No |
| `OS.has_feature("mobile")`, debug flag, launch arguments after `--` | `game_main_impl.gd`, `core.gd:56` | Pause on focus loss; detect test runs, always off in release | No |
| Safe area, screen size, touchscreen present | `game_main_impl.gd:254,318`, `touch_controls_impl.gd:55` | HUD layout; not stored | No |
| Touch input | Touch controls | Gameplay; not stored | No |

The engine also keeps its own shader cache under `user://`, with no player data. On the PC it writes logs under `user://logs`.

### Every scan finding
| Finding | In export | Verdict |
|---|---|---|
| `OS.get_name` at `cloud_save_factory_impl.gd:21` | Comment only | Not run. Describes the planned iCloud path, D11 |
| `Engine.get_singleton` at `cloud_save_factory_impl.gd:23` | Comment only | Not run. No singleton is requested |
| `OS.get_name` at `automation_impl.gd:99` | No, excluded | Test code, Linux only |
| `/proc/self/cmdline` at `automation_impl.gd:101` | No, excluded | Reads the test process's own arguments for `--fixed-fps`, Linux only. Nothing in release code preloads it; `core_installer.gd` loads it by path in test runs only |
| `OS.get_name` at `game_main_impl.gd:52` | Yes | Sets `Engine.max_fps` on iOS; PLATFORM.md 30 fps target |

No device IDs, clipboard reads, program launches, or unexplained URLs. `str_to_var` reads only the game's own save file.
Cloud data decoding avoids objects (`bytes_to_var`, never `_with_objects`), and tests cover crafted payloads.

## 3. iOS permissions
**None requested.** `godot/export_presets.cfg` sets no `privacy/*` option and no usage text, `capabilities/access_wifi` is
false, and `project.godot` does not enable audio input. Nothing in the code needs camera, microphone, photos or location.
The final Info.plist comes from the export template on the Mac, so see question 2.

## 4. App Store privacy answers: DRAFT, for the human to confirm in App Store Connect
| Question | Draft answer |
|---|---|
| Data collected | Data Not Collected. Saves stay on the device |
| Linked to the player | Not applicable |
| Used for tracking | No |
| Third-party SDKs or analytics | None in the project |

Holds only for this build. Adding iCloud (T024) requires this audit again.

## 5. Open questions
1. **Decision needed: ship the first build with no cloud save?** MECHANICS.md says progress saves to the cloud.
   DECISIONS.md D11 builds that at the Mac stage, and T024 is optional, needing the Apple Developer entitlement. As
   built, progress lives only on the phone, and deleting the app loses it. This is fine for privacy, but it is a known
   gap against your spec. Accept it for this device test, or say otherwise.
2. **Could not determine: the engine binary and final iOS files.** No export templates exist in the sandbox, so I could
   not inspect the Godot iOS binary, the generated `Info.plist` or `PrivacyInfo.xcprivacy`. Check on the Mac that the
   exported plist has no usage text you did not expect, and that the privacy manifest's required-reason entries and
   tracking setting are right. Required before App Store submission, not for a personal device install.
3. **Could not determine: iOS device backup.** Whether Apple's own device backup copies `user://saves` depends on where
   iOS places the folder. Godot sends nothing itself, and only game progress is in there. Check if App Store answers depend on it.
4. **Not verified on a device:** no traffic capture was possible. "No network" comes from reading the code and pack.
