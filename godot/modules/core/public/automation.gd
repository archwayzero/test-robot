## Test automation API. End-to-end tests drive the game through this and nothing else.
##
## Exists ONLY in test runs: Core.automation is null unless CoreAPI.is_test_run() (debug build + `-- --automation`).
## The implementation lives in res://modules/core/internal/automation/, which release exports exclude
## (export filter, see godot/modules/core/CLAUDE.md), so it is not shipped.
##
## Methods marked "coroutine" must be awaited: `await Core.automation.advance_frames(10)`.
## Owner: orchestrator. Implemented in core/internal by module-dev.
@abstract
class_name Automation
extends RefCounted


# --- Determinism ----------------------------------------------------------------------------------------

## Seeds Core.rng and the global RNG (seed()). Call before loading the scene under test.
@abstract func set_seed(seed_value: int) -> void


## Fixes time: physics runs at `physics_ticks_per_second`, and every process frame advances by exactly
## 1.0 / `frames_per_second` (no wall-clock dependence; Engine.time_scale = 1). Call before the scene under test.
@abstract func set_fixed_timestep(physics_ticks_per_second: int, frames_per_second: int) -> void


## Process frames elapsed since the automation started. Deterministic under a fixed timestep.
@abstract func get_frame() -> int


## Coroutine. Lets `frames` process frames pass.
@abstract func advance_frames(frames: int) -> void


## Coroutine. Advances frames until `predicate.call()` returns true or `timeout_frames` pass. Returns whether it
## became true.
@abstract func wait_until(predicate: Callable, timeout_frames: int) -> bool


# --- Input injection ------------------------------------------------------------------------------------
# Injected input goes through Input.parse_input_event, so game code sees it exactly like real input.

## Holds an InputMap action down (strength 0..1) until release_action().
@abstract func press_action(action: StringName, strength: float = 1.0) -> void


@abstract func release_action(action: StringName) -> void


## Coroutine. Presses `action`, holds it for `frames` frames, then releases it.
@abstract func tap_action(action: StringName, frames: int = 1) -> void


## Touch down/up at a viewport position (pixels). `index` is the finger.
@abstract func touch(position: Vector2, pressed: bool, index: int = 0) -> void


## Coroutine. Drags finger `index` from `from` to `to` over `frames` frames (touch down, drag events, touch up).
@abstract func drag(from: Vector2, to: Vector2, frames: int, index: int = 0) -> void


## Escape hatch for anything else (keys, mouse, joypad). Prefer the methods above.
@abstract func inject_event(event: InputEvent) -> void


# --- Observation and control ----------------------------------------------------------------------------

## Snapshot for assertions: Core.state.snapshot() plus {"frame": int, "seed": int, "scene": String (current
## scene path)}. Plain data only.
@abstract func snapshot() -> Dictionary


## Coroutine. Changes to the scene at `path` (res://...) and waits until its root's _ready() has run.
@abstract func load_scene(path: String) -> void


## Ends the test run with `exit_code` (0 = pass).
@abstract func quit(exit_code: int = 0) -> void
