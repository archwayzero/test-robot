## Public facade of the `core` module, registered as the ONLY autoload, under the name `Core`.
##
## It is the typed event bus (the signals below) and the access point to core services.
## Other modules use it as `Core.<signal>` / `Core.state` / `Core.saves`; they never reference core internals.
##
## Owner: orchestrator. Implementation lives in res://modules/core/internal/ (module-dev), wired in via the
## installer contract described in godot/modules/core/CLAUDE.md.
class_name CoreAPI
extends Node

# --- Event bus ------------------------------------------------------------------------------------------
# Each signal names its only legitimate emitter. Listeners may be any module that depends on core.
# New gameplay signals are added here by the orchestrator, one per cross-module event, with typed arguments.

## Emitted by core (GameState implementation) after the game phase changed.
signal phase_changed(previous: StringName, current: StringName)

## Emitted by core (GameState implementation) after pause state changed.
signal pause_changed(paused: bool)

## Emitted by core (GameState implementation) after a value in the shared state changed.
signal state_value_changed(key: StringName, value: Variant)

## Emitted by core (SaveService implementation) after a save attempt. `error` is OK on success.
signal save_finished(slot: int, error: Error)

## Emitted by core (SaveService implementation) after a load attempt. `error` is OK on success.
signal load_finished(slot: int, error: Error)

## Emitted by the `player` module whenever the player's global position changed (at most once per physics frame).
## Listeners (e.g. exploration) convert it to maze cells themselves.
signal player_moved(position: Vector3)

# --- Services -------------------------------------------------------------------------------------------

## Shared game state. Set by the core installer before any other node's _ready().
var state: GameState

## Save/load. Set by the core installer.
var saves: SaveService

## Test automation API. Non-null ONLY in test runs (see is_test_run()); always null in normal play and exports.
var automation: Automation

## The single source of gameplay randomness. Gameplay code must use Core.rng, never randi()/randf()/
## randomize(), so a fixed seed makes runs reproducible. Automation.set_seed() reseeds it.
var rng := RandomNumberGenerator.new()

const _INSTALLER_PATH := "res://modules/core/internal/core_installer.gd"
const TEST_RUN_ARG := "--automation"


## True only for automated test runs: a debug build (editor or debug export) started with the user argument
## `--automation` (after `--`, e.g. `godot --headless --path godot -- --automation`). Never true in a release export.
static func is_test_run() -> bool:
	return OS.is_debug_build() and TEST_RUN_ARG in OS.get_cmdline_user_args()


func _enter_tree() -> void:
	if ResourceLoader.exists(_INSTALLER_PATH):
		load(_INSTALLER_PATH).install(self)
	else:
		push_warning("core: no implementation installed yet (%s missing)" % _INSTALLER_PATH)
