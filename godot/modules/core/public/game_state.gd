## Minimal shared game state: a phase, a pause flag, and a flat key/value store that modules publish into.
## Everything in it must be serializable (snapshot()/restore()), because saves and test snapshots use it.
##
## Owner: orchestrator. Implemented in core/internal by module-dev. Access it as `Core.state`.
@abstract
class_name GameState
extends RefCounted

## Valid state keys: `<module>/<name>`, lower-case letters, digits and `_`, more `/` segments allowed (e.g.
## `player/position`). set_value() and restore() reject other keys.
const KEY_PATTERN := "^[a-z0-9_]+(/[a-z0-9_]+)+$"

## Phase used before anything sets one.
const PHASE_BOOT := &"boot"


## Current phase, e.g. &"boot", &"menu", &"playing". Phase names are defined in docs/specs as mechanics land.
@abstract func get_phase() -> StringName


## Changes the phase. Emits Core.phase_changed(previous, current) if it changed.
@abstract func set_phase(phase: StringName) -> void


@abstract func is_paused() -> bool


## Emits Core.pause_changed(paused) if it changed. Does not touch SceneTree.paused by itself unless the
## implementation's docs say so.
@abstract func set_paused(paused: bool) -> void


## Reads a value. Keys are namespaced by owning module: &"<module>/<name>", e.g. &"player/health".
@abstract func get_value(key: StringName, default: Variant = null) -> Variant


## Writes a value (must be serializable with var_to_str). Emits Core.state_value_changed(key, value) if it changed.
## A module writes only keys in its own namespace.
@abstract func set_value(key: StringName, value: Variant) -> void


@abstract func has_value(key: StringName) -> bool


## Deep copy of the whole state as plain data: {"phase": StringName, "paused": bool, "values": Dictionary}.
@abstract func snapshot() -> Dictionary


## Replaces the whole state from a snapshot() result. Emits the change signals for what changed; a key that
## exists now but not in `data` is removed and reported as Core.state_value_changed(key, null).
## An invalid snapshot (wrong shape, non-plain values, or any key not matching KEY_PATTERN) leaves the state
## completely unchanged (no signals) and push_error()s. Callers that must know whether it applied compare the state
## afterwards (run 1 keeps the void signature; see docs/retrospective/run1-corrections.md).
@abstract func restore(data: Dictionary) -> void
