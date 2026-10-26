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
- `AutoSave` (abstract Node): `setup(backend)`, `restore() -> Error`, `save_now() -> Error`; signal
  `autosaved(error, cloud_error)`; `SAVE_SLOT 0`, `MIN_INTERVAL_S 10.0`.

### Implementation requirements
- Trigger: `Core.state_value_changed` for `StateKeys.EXPLORATION_COUNT`, throttled to one save per 10 s of game time
  (pending trigger saved when the interval ends); `save_now()` on NOTIFICATION_APPLICATION_PAUSED and
  NOTIFICATION_WM_CLOSE_REQUEST.
- Save via `Core.saves.save_game(SAVE_SLOT)`; then push the saved bytes (plus a UTC timestamp header) to the backend.
  Local save never waits for or depends on the cloud.
- `restore()`: pull cloud + read local, load the newer one (cloud bytes are written to the local slot first).
- Backends now: LocalOnlyBackend, FakeCloudBackend. ICloudBackend is added at the Mac stage (M3): it must detect the
  plugin with `Engine.has_singleton(...)` and fall back to LocalOnly when absent; keep that seam ready.
- No network calls of its own (iCloud is the OS's). Nothing else leaves the device.
- Tests: throttle (two cells within 10 s -> one save, then one more after the interval), fake backend receives bytes
  equal to the local file, unavailable backend -> local OK + cloud_error ERR_UNAVAILABLE, restore picks the newer.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
