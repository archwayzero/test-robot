# Module: core
Event bus, game state, save/load interfaces

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/core/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: none.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
`core` is the only autoload, registered in project.godot as `Core` -> `public/core.gd` (`class_name CoreAPI`).
Abstract classes use GDScript `@abstract` (Godot 4.5+); implementations extend them in `internal/`.

### `Core` (public/core.gd, CoreAPI): event bus and service access
Signals (each emitted only by the named core service; any module may listen):
| Signal | Emitted by | When |
|---|---|---|
| `phase_changed(previous: StringName, current: StringName)` | GameState impl | phase changed |
| `pause_changed(paused: bool)` | GameState impl | pause flag changed |
| `state_value_changed(key: StringName, value: Variant)` | GameState impl | a state value changed |
| `save_finished(slot: int, error: Error)` | SaveService impl | after each save attempt |
| `load_finished(slot: int, error: Error)` | SaveService impl | after each load attempt |
| `player_moved(position: Vector3)` | `player` module | player's global position changed (max once per physics frame) |

### Shared constants (no implementation needed)
- `GameActions` (public/game_actions.gd): InputMap action names `move_left/right/forward/back`, `run`, `jump`,
  `stance_cycle`, `RUN_THRESHOLD = 0.7`. The actions are defined in project.godot (keyboard defaults for PC preview).
- `StateKeys` (public/state_keys.gd): GameState keys and their single writer (`player/*`, `exploration/*`,
  `maze/seed`) and the phases `loading`, `playing`, `map_open` (set by `game`).

New cross-module gameplay signals are added to `core.gd` by the orchestrator (typed arguments, one named emitter).

Members: `state: GameState`, `saves: SaveService`, `automation: Automation` (null unless a test run),
`rng: RandomNumberGenerator` (the ONLY gameplay randomness source), `static is_test_run() -> bool`
(debug build AND user arg `--automation`, i.e. `godot ... -- --automation`).

### `GameState` (public/game_state.gd)
`get_phase()/set_phase(StringName)` (starts at `GameState.PHASE_BOOT`), `is_paused()/set_paused(bool)`,
`get_value(key, default)/set_value(key, value)/has_value(key)` with keys namespaced `&"<module>/<name>"` (a module
writes only its own namespace; values must survive `var_to_str`), `snapshot() -> Dictionary`
(`{"phase", "paused", "values"}`, deep copy), `restore(Dictionary)`. Setters emit the Core signals only on change.

### `SaveService` (public/save_service.gd)
`save_game(slot) -> Error`, `load_game(slot) -> Error`, `has_save(slot) -> bool`, `delete_save(slot) -> Error`.
Stores `Core.state.snapshot()` under `user://`; a failed load leaves the state unchanged
(ERR_FILE_NOT_FOUND / ERR_FILE_CORRUPT). Emits `save_finished` / `load_finished`.

### `Automation` (public/automation.gd): test runs only
Determinism: `set_seed(int)` (Core.rng + global seed), `set_fixed_timestep(physics_tps, fps)` (fixed delta per
frame, no wall-clock dependence), `get_frame()`, `advance_frames(n)`*, `wait_until(predicate, timeout_frames) -> bool`*.
Input (via `Input.parse_input_event`): `press_action`, `release_action`, `tap_action(action, frames)`*,
`touch(pos, pressed, index)`, `drag(from, to, frames, index)`*, `inject_event(InputEvent)`.
Observation/control: `snapshot()` (state snapshot + `frame`, `seed`, `scene`), `load_scene(path)`*, `quit(code)`.
(* = coroutine, must be awaited.)

### Implementation contract (for module-dev)
- `internal/core_installer.gd` must exist with `static func install(core: CoreAPI) -> void`. `Core._enter_tree()`
  calls it, before any other node's `_ready()`. It must set `core.state` and `core.saves`, and set `core.automation`
  only when `CoreAPI.is_test_run()`; otherwise leave it null and never load the automation scripts.
- Put the Automation implementation under `internal/automation/` and load it only from the installer. Release
  exports exclude `res://modules/core/internal/automation/*` (export filter, set when the Mac export preset is made),
  so no `preload` of it anywhere.
- Services get the CoreAPI passed in (to emit signals); they must not use `/root/...` node paths.
- `advance_frames(n)` / `get_frame()` must count `Engine.get_process_frames()`, not `process_frame` signal
  emissions (awaiting process_frame from code resumed by process_frame can resume in the same frame).
- Tests live in `tests/` and run headless (test runner: docs/qa/TEST_PLAN.md, "Test runner").
