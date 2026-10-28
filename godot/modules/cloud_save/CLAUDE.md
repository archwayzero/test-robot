# Module: cloud_save
Autosave policy and cloud backend (local + fake in sandbox, iCloud on iOS)

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/cloud_save/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `CloudSaveFactory.create()`, `make_auto_save() -> AutoSave`, `make_platform_backend() -> CloudBackend`,
  `make_fake_backend(available = true) -> CloudBackend`.
- `CloudBackend` (abstract): `is_available()`, `push(slot, data) -> Error`, `pull(slot) -> PackedByteArray`.
- `AutoSave` (abstract Node): `setup(backend)`, `restore() -> Error`, `save_now() -> Error`,
  test hook `decode_cloud_payload(data) -> Dictionary`; signal
  `autosaved(error, cloud_error)`; `SAVE_SLOT 0`, `MIN_INTERVAL_S 10.0`.

### Implementation requirements
- Trigger: `Core.state_value_changed` for `StateKeys.EXPLORATION_COUNT`, throttled to one save per 10 s of game time
  (pending trigger saved when the interval ends); `save_now()` on NOTIFICATION_APPLICATION_PAUSED and
  NOTIFICATION_WM_CLOSE_REQUEST.
- Save via `Core.saves.save_game(SAVE_SLOT)`; then push cloud_save's OWN envelope to the backend (never core's save
  file or path). **Envelope v3** (T029; text floats are not exact in Godot 4.7.2, ~12% of doubles change):
  UTF-8 JSON `{"format", "version": 3, "saved_at_unix": int, "snapshot_b64": Marshalls.raw_to_base64(var_to_bytes(snapshot))}`.
  Decode: payload size limit, exact JSON shape, strict canonical Base64, decoded size limit, `bytes_to_var` (NEVER
  `bytes_to_var_with_objects`), result must be a Dictionary, decoded-type walk (no Object/Callable/Signal/RID, no
  Object-typed containers, depth limit), `var_to_bytes(decoded) == bytes`. v2 envelopes
  (`JSON.from_native(..., false)` text) are still decoded for old cloud copies, never written. Before each push,
  verify the envelope decodes equal to the snapshot; otherwise don't push and report cloud_error ERR_INVALID_DATA.
  The local timestamp is kept in cloud_save's sidecar `CoreAPI.user_data_dir() + "cloud_save/meta.cfg"` (test runs:
  under `user://automation/`; T026). Keep verifying restores by comparing state (restore() stays void in run 1).
  Local save never waits for or depends on the cloud. If the local save fails, nothing is pushed (cloud_error ERR_SKIP).
  Throttle: the deferred save fires once >= MIN_INTERVAL_S of game time has passed since the previous save (T029).
- `decode_cloud_payload(data)` (public test hook): returns `{"saved_at_unix", "snapshot"}` or `{}` for v3 and v2.
- `restore()`: pull cloud + read the sidecar, load the newer one; a newer cloud snapshot is applied with
  `Core.state.restore()` and saved locally ONLY after verifying Core accepted it (otherwise keep the local save).
  Ties go to local. cloud_save is the only writer of slot 0.
- Backends now: LocalOnlyBackend, FakeCloudBackend. ICloudBackend is added at the Mac stage (M3): it must detect the
  plugin with `Engine.has_singleton(...)` and fall back to LocalOnly when absent; keep that seam ready.
- No network calls of its own (iCloud is the OS's). Nothing else leaves the device.
- Tests: throttle (two cells within 10 s -> one save, then one more after the interval), fake backend receives an
  envelope whose snapshot equals Core.state at save time, unavailable backend -> local OK + cloud_error ERR_UNAVAILABLE, restore picks the newer.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
