## M5 controls end-to-end tests: TEST_PLAN.md E14 touch_joystick, E15 touch_buttons. Owner: qa.
##
## Touches go through Core.automation.touch()/drag()/inject_event() at viewport pixels (headless root resized to
## 1280x590). The public TouchControls interface does not expose the button positions, so E15 derives them from
## the layout documented in godot/modules/touch_controls/CLAUDE.md and its implementation constants
## (Jump radius 60 and Stance radius 45, margins right 48 / bottom 32, gap 28) - a reported finding.
extends "res://tests/e2e/e2e_base.gd"

## Joystick radius from touch_controls/CLAUDE.md ("radius 90 px").
const STICK_RADIUS := 90.0
## A left-half point outside the minimap's reserved corner.
const STICK_START := Vector2(320, 420)


func _init() -> void:
	timeout_frames = 2000


func _place_in_corridor() -> void:
	var corridor := longest_corridor()
	var d: MazeLayout.Dir = corridor.dir
	player().spawn_at(layout().cell_to_world(corridor.cell), dir_yaw(d))
	await automation().advance_frames(5)


## Moves finger `index` (already down) to `pos` with one drag event.
func _drag_to(index: int, from: Vector2, pos: Vector2) -> void:
	var ev := InputEventScreenDrag.new()
	ev.index = index
	ev.position = pos
	ev.relative = pos - from
	ev.screen_relative = pos - from
	automation().inject_event(ev)


func test_e14_touch_joystick() -> void:
	assert_true(await start_game())
	await _place_in_corridor()
	var controls := main.get_touch_controls()
	assert_true(controls.visible, "touch controls shown (emulate_touch_from_mouse)")
	# Held drag, sampled while the finger is down: 45 px (half deflection), then 90 px (full).
	automation().touch(STICK_START, true, 0)
	await automation().advance_frames(1)
	_drag_to(0, STICK_START, STICK_START + Vector2(0, -STICK_RADIUS * 0.5))
	await automation().advance_frames(10)
	var half_strength := Input.get_action_strength(GameActions.MOVE_FORWARD)
	var half_stick := controls.get_stick_vector().length()
	var half_running := player().is_running()
	_drag_to(0, STICK_START + Vector2(0, -STICK_RADIUS * 0.5), STICK_START + Vector2(0, -STICK_RADIUS))
	await automation().advance_frames(10)
	var full_strength := Input.get_action_strength(GameActions.MOVE_FORWARD)
	var full_stick := controls.get_stick_vector().length()
	var full_running := player().is_running()
	automation().touch(STICK_START + Vector2(0, -STICK_RADIUS), false, 0)
	await automation().advance_frames(3)
	assert_almost_eq(half_strength, 0.5, 0.05, "45 px -> move_forward ~0.5")
	assert_almost_eq(half_stick, 0.5, 0.05, "stick vector ~0.5")
	assert_false(half_running, "no running at ~0.5")
	assert_almost_eq(full_strength, 1.0, 0.05, "90 px -> move_forward ~1.0")
	assert_almost_eq(full_stick, 1.0, 0.05, "stick vector ~1.0")
	assert_true(full_running, "running at ~1.0")
	assert_almost_eq(Input.get_action_strength(GameActions.MOVE_FORWARD), 0.0, 0.001, "released")
	# The same through Automation.drag() (touch down, drag events, touch up): strength sampled mid-drag.
	var samples: Array = []
	var sampler := func() -> void:
		for i in 14:
			await automation().advance_frames(1)
			samples.append(Input.get_action_strength(GameActions.MOVE_FORWARD))
	sampler.call()
	await automation().drag(STICK_START, STICK_START + Vector2(0, -STICK_RADIUS), 10, 0)
	await automation().advance_frames(4)
	var peak := 0.0
	for s: float in samples:
		peak = maxf(peak, s)
	assert_almost_eq(peak, 1.0, 0.05, "drag() by 90 px reaches ~1.0 (samples %s)" % [samples])
	assert_almost_eq(Input.get_action_strength(GameActions.MOVE_FORWARD), 0.0, 0.001, "released after drag()")
	print("E14 measured: 45 px -> %.3f (stick %.3f, running %s); 90 px -> %.3f (stick %.3f, running %s)"
			% [half_strength, half_stick, half_running, full_strength, full_stick, full_running])


func test_e15_touch_buttons() -> void:
	assert_true(await start_game())
	await _place_in_corridor()
	var controls := main.get_touch_controls()
	var rect := controls.get_global_rect()
	var jump_pos := rect.position + Vector2(rect.size.x - 48.0 - 60.0, rect.size.y - 32.0 - 60.0)
	var stance_pos := Vector2(jump_pos.x - 60.0 - 28.0 - 45.0, rect.position.y + rect.size.y - 32.0 - 45.0)
	var jumps := [0]
	var stances: Array = []
	player().jumped.connect(func() -> void: jumps[0] += 1)
	player().stance_changed.connect(func(s: PlayerController.Stance) -> void: stances.append(s))
	# Hold the stick at full forward with finger 0.
	automation().touch(STICK_START, true, 0)
	await automation().advance_frames(1)
	_drag_to(0, STICK_START, STICK_START + Vector2(0, -STICK_RADIUS))
	await automation().advance_frames(5)
	var p0 := player().global_position
	# Jump with finger 1 while the stick is held.
	automation().touch(jump_pos, true, 1)
	await automation().advance_frames(2)
	automation().touch(jump_pos, false, 1)
	await automation().advance_frames(20)
	var stick_after_jump := controls.get_stick_vector().length()
	var p1 := player().global_position
	# Stance with finger 2 while the stick is held.
	automation().touch(stance_pos, true, 2)
	await automation().advance_frames(2)
	automation().touch(stance_pos, false, 2)
	await automation().advance_frames(20)
	var stick_after_stance := controls.get_stick_vector().length()
	var p2 := player().global_position
	automation().touch(STICK_START + Vector2(0, -STICK_RADIUS), false, 0)
	await automation().advance_frames(3)
	assert_eq(jumps[0], 1, "Jump button fired once (touched at %s)" % jump_pos)
	assert_eq(stances, [PlayerController.Stance.CROUCH], "Stance button fired once (touched at %s)" % stance_pos)
	assert_almost_eq(stick_after_jump, 1.0, 0.05, "stick still held after Jump")
	assert_almost_eq(stick_after_stance, 1.0, 0.05, "stick still held after Stance")
	assert_true(flat(p1 - p0).length() > 1.0, "kept moving during the jump (%.2f m in 22 frames)" % flat(p1 - p0).length())
	assert_true(flat(p2 - p1).length() > 0.5, "kept moving after Stance (%.2f m in 22 frames)" % flat(p2 - p1).length())
	assert_false(main.get_minimap().is_large_map_open(), "no stray minimap tap")
