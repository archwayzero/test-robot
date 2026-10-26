## Names of the InputMap actions shared by all modules (defined in project.godot, with keyboard defaults for the
## PC preview). Producers: touch_controls (on-screen), keyboard, and Core.automation in tests. Consumer: player.
## Nobody calls the player directly for input; everything goes through these actions.
## Owner: orchestrator.
class_name GameActions
extends RefCounted

## Analog movement. Strength 0..1 per direction (joystick deflection). Running = deflection >= RUN_THRESHOLD,
## or the `run` action held (keyboard Shift).
const MOVE_LEFT := &"move_left"
const MOVE_RIGHT := &"move_right"
const MOVE_FORWARD := &"move_forward"
const MOVE_BACK := &"move_back"

## Held = run regardless of deflection (keyboard). Touch uses deflection instead.
const RUN := &"run"

## Pressed = jump (ignored while crawling).
const JUMP := &"jump"

## Pressed = cycle stance stand -> crouch -> crawl -> stand.
const STANCE_CYCLE := &"stance_cycle"

## Joystick deflection (0..1) from which the player runs instead of walks.
const RUN_THRESHOLD := 0.7

const ALL: Array[StringName] = [MOVE_LEFT, MOVE_RIGHT, MOVE_FORWARD, MOVE_BACK, RUN, JUMP, STANCE_CYCLE]
