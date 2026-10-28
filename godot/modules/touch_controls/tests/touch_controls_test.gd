extends TestCase

const UNHANDLED_PROBE := "res://modules/touch_controls/tests/support/unhandled_probe.gd"
const STRENGTH_PROBE := "res://modules/touch_controls/tests/support/strength_probe.gd"
const MOVES: Array[StringName] = [GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
		GameActions.MOVE_BACK]
const STICK_START := Vector2(300, 420)

var auto: Automation
var controls  # TouchControls implementation (internal script: layout helpers are not on the public type)
var probe


func before_each() -> void:
	auto = automation()
	for a in GameActions.ALL:
		Input.action_release(a)
	controls = TouchControlsFactory.create()
	add_child(controls)
	controls.set_controls_visible(true)
	probe = load(UNHANDLED_PROBE).new()
	add_child(probe)
	await auto.advance_frames(1)


func after_each() -> void:
	for i in 4:
		auto.touch(Vector2(-10, -10), false, i)
	controls.queue_free()
	probe.queue_free()
	await auto.advance_frames(1)
	for a in GameActions.ALL:
		Input.action_release(a)


func _move(pos: Vector2, index := 0) -> void:
	var d := InputEventScreenDrag.new()
	d.index = index
	d.position = pos
	auto.inject_event(d)
	await auto.advance_frames(1)


func _s(action: StringName) -> float:
	return Input.get_action_strength(action)


func _assert_moves(expected: Dictionary, tol: float, msg: String) -> void:
	for a in MOVES:
		var e: float = expected.get(a, 0.0)
		assert_almost_eq(_s(a), e, tol, "%s: %s" % [msg, a])
		if e == 0.0:
			assert_false(Input.is_action_pressed(a), "%s: %s not pressed" % [msg, a])


func test_layout_at_base_resolution() -> void:
	assert_eq(controls.size, Vector2(1280, 590), "fills the viewport")
	assert_eq(controls.mouse_filter, Control.MOUSE_FILTER_IGNORE)
	var j: Vector2 = controls.jump_center()
	var s: Vector2 = controls.stance_center()
	assert_true(j.x + controls.JUMP_RADIUS <= 1280 and j.y + controls.JUMP_RADIUS <= 590, "jump on screen %s" % j)
	assert_true(s.x - controls.STANCE_RADIUS > 640, "stance on the right half %s" % s)
	assert_true(j.distance_to(s) > controls.JUMP_RADIUS + controls.STANCE_RADIUS, "buttons do not overlap")
	assert_true(controls.visible, "shown on desktop with emulate_touch_from_mouse")


func test_stick_half_and_full_deflection() -> void:
	auto.touch(STICK_START, true, 0)
	assert_eq(controls.get_stick_vector(), Vector2.ZERO, "touch down alone does not move")
	assert_true(controls._stick_index == 0, "stick started")
	await _move(STICK_START + Vector2(0, -45))
	_assert_moves({GameActions.MOVE_FORWARD: 0.5}, 0.05, "45 px")
	assert_true(_s(GameActions.MOVE_FORWARD) < GameActions.RUN_THRESHOLD, "walk, not run")
	assert_almost_eq(controls.get_stick_vector().length(), 0.5, 0.05)
	await _move(STICK_START + Vector2(0, -90))
	_assert_moves({GameActions.MOVE_FORWARD: 1.0}, 0.05, "90 px")
	assert_true(_s(GameActions.MOVE_FORWARD) >= GameActions.RUN_THRESHOLD, "run")
	await _move(STICK_START + Vector2(0, -200))
	assert_almost_eq(controls.get_stick_vector().length(), 1.0, 1e-4, "clamped")
	auto.touch(STICK_START + Vector2(0, -200), false, 0)
	await auto.advance_frames(1)
	_assert_moves({}, 1e-6, "released")
	assert_eq(controls.get_stick_vector(), Vector2.ZERO)
	assert_eq(probe.events.size(), 0, "stick touches are consumed")


func test_automation_drag_strengths() -> void:
	# The E14 path: Core.automation.drag() (down, per-frame drags, up), sampled each frame like game code.
	for dist in [45.0, 90.0]:
		var sp = load(STRENGTH_PROBE).new()
		add_child(sp)
		await auto.drag(STICK_START, STICK_START + Vector2(0, -dist), 6, 0)
		await auto.advance_frames(1)
		var peak: float = sp.max_strength[GameActions.MOVE_FORWARD]
		assert_almost_eq(peak, dist / 90.0, 0.05, "peak forward for %s px" % dist)
		for a in [GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_BACK]:
			assert_eq(sp.max_strength[a], 0.0, "no %s" % a)
		_assert_moves({}, 1e-6, "after drag")
		sp.queue_free()


func test_diagonal() -> void:
	auto.touch(STICK_START, true, 0)
	await _move(STICK_START + Vector2(40, 40))
	var c := 40.0 / 90.0
	_assert_moves({GameActions.MOVE_RIGHT: c, GameActions.MOVE_BACK: c}, 0.02, "down-right")
	await _move(STICK_START + Vector2(-50, -30))
	_assert_moves({GameActions.MOVE_LEFT: 50.0 / 90.0, GameActions.MOVE_FORWARD: 30.0 / 90.0}, 0.02, "up-left")
	var v: Vector2 = controls.get_stick_vector()
	assert_true(v.x < 0 and v.y < 0, "x right, y back: %s" % v)


func test_minimap_area_does_not_start_stick() -> void:
	auto.touch(Vector2(100, 100), true, 0)
	await _move(Vector2(100, 40))
	assert_eq(controls.get_stick_vector(), Vector2.ZERO)
	_assert_moves({}, 1e-6, "minimap touch")
	auto.touch(Vector2(100, 40), false, 0)
	assert_true(probe.events.size() >= 2, "minimap touches pass through (%d events)" % probe.events.size())
	# Just below the reserved area the stick works.
	auto.touch(Vector2(100, 240), true, 1)
	await _move(Vector2(100, 195), 1)
	assert_almost_eq(_s(GameActions.MOVE_FORWARD), 0.5, 0.05, "stick starts below the minimap area")


func test_jump_and_stance_taps() -> void:
	for pair in [[controls.jump_center(), GameActions.JUMP], [controls.stance_center(), GameActions.STANCE_CYCLE]]:
		var pos: Vector2 = pair[0]
		var action: StringName = pair[1]
		auto.touch(pos, true, 0)
		await auto.advance_frames(1)
		assert_true(Input.is_action_pressed(action), "%s pressed while touched" % action)
		await _move(pos + Vector2(5, 5))
		assert_true(Input.is_action_pressed(action), "%s still held while the finger moves" % action)
		auto.touch(pos, false, 0)
		await auto.advance_frames(1)
		assert_false(Input.is_action_pressed(action), "%s released" % action)
		_assert_moves({}, 1e-6, "button does not move")
	assert_eq(probe.events.size(), 0, "button touches are consumed")


func test_stick_and_button_together() -> void:
	auto.touch(STICK_START, true, 0)
	await _move(STICK_START + Vector2(0, -60))
	auto.touch(controls.jump_center(), true, 1)
	await auto.advance_frames(1)
	assert_true(Input.is_action_pressed(GameActions.JUMP), "jump held")
	assert_almost_eq(_s(GameActions.MOVE_FORWARD), 60.0 / 90.0, 0.02, "stick still held")
	await _move(STICK_START + Vector2(0, -90))
	assert_almost_eq(_s(GameActions.MOVE_FORWARD), 1.0, 0.02, "stick moves while jump held")
	auto.touch(controls.jump_center(), false, 1)
	await auto.advance_frames(1)
	assert_false(Input.is_action_pressed(GameActions.JUMP), "jump released")
	assert_almost_eq(_s(GameActions.MOVE_FORWARD), 1.0, 0.02, "stick kept after the button is released")
	# A second finger on the left half does not hijack the stick.
	auto.touch(Vector2(500, 300), true, 2)
	await _move(Vector2(560, 300), 2)
	assert_almost_eq(controls.get_stick_vector().y, -1.0, 0.02, "stick unchanged")
	assert_eq(_s(GameActions.MOVE_RIGHT), 0.0, "second finger produced no move")
	auto.touch(Vector2(560, 300), false, 2)
	await auto.advance_frames(1)
	assert_almost_eq(_s(GameActions.MOVE_FORWARD), 1.0, 0.02, "stick survives the other finger lifting")
	# Stance with the stick still held.
	auto.touch(controls.stance_center(), true, 3)
	await auto.advance_frames(1)
	assert_true(Input.is_action_pressed(GameActions.STANCE_CYCLE))
	auto.touch(controls.stance_center(), false, 3)
	assert_false(Input.is_action_pressed(GameActions.STANCE_CYCLE))
	auto.touch(STICK_START + Vector2(0, -90), false, 0)
	await auto.advance_frames(1)
	_assert_moves({}, 1e-6, "all released")


func test_right_half_passes_through() -> void:
	auto.touch(Vector2(900, 200), true, 0)
	await _move(Vector2(950, 210))
	auto.touch(Vector2(950, 210), false, 0)
	await auto.advance_frames(1)
	var touches: Array = probe.events.filter(func(e): return e is InputEventScreenTouch)
	var drags: Array = probe.events.filter(func(e): return e is InputEventScreenDrag)
	assert_eq(touches.size(), 2, "down + up reach _unhandled_input")
	assert_eq(drags.size(), 1, "drag reaches _unhandled_input")
	for a in GameActions.ALL:
		assert_false(Input.is_action_pressed(a), "%s not pressed by a camera touch" % a)
	assert_eq(controls.get_stick_vector(), Vector2.ZERO)


func test_hide_releases_everything_and_emits() -> void:
	var seen: Array = []
	controls.visibility_toggled.connect(func(v: bool) -> void: seen.append(v))
	auto.touch(STICK_START, true, 0)
	await _move(STICK_START + Vector2(-90, 0))
	auto.touch(controls.jump_center(), true, 1)
	auto.touch(controls.stance_center(), true, 2)
	await auto.advance_frames(1)
	assert_true(Input.is_action_pressed(GameActions.MOVE_LEFT))
	assert_true(Input.is_action_pressed(GameActions.JUMP))
	controls.set_controls_visible(false)
	assert_false(controls.visible)
	for a in GameActions.ALL:
		assert_false(Input.is_action_pressed(a), "%s released on hide" % a)
	assert_eq(controls.get_stick_vector(), Vector2.ZERO)
	assert_eq(seen, [false], "visibility_toggled(false)")
	# While hidden nothing is consumed or pressed.
	for i in 3:
		auto.touch(Vector2.ZERO, false, i)
	probe.events.clear()
	auto.touch(controls.jump_center(), true, 0)
	await auto.advance_frames(1)
	assert_false(Input.is_action_pressed(GameActions.JUMP), "hidden button does nothing")
	assert_eq(probe.events.size(), 1, "hidden controls do not consume")
	auto.touch(controls.jump_center(), false, 0)
	controls.set_controls_visible(true)
	assert_eq(seen, [false, true], "visibility_toggled(true)")
	controls.set_controls_visible(true)
	assert_eq(seen, [false, true], "no signal without a change")


func test_does_not_release_keyboard_actions() -> void:
	Input.action_press(GameActions.MOVE_FORWARD, 1.0)  # e.g. the W key
	controls.set_controls_visible(false)
	assert_true(Input.is_action_pressed(GameActions.MOVE_FORWARD), "only its own actions are released")
	Input.action_release(GameActions.MOVE_FORWARD)


# --- T031: get_jump_rect() / get_stance_rect() test hooks ------------------------------------------------------

func _assert_rect_hooks(c, area: Rect2, msg: String) -> void:
	var j: Rect2 = c.get_jump_rect()
	var s: Rect2 = c.get_stance_rect()
	assert_true(j.has_area() and s.has_area(), "%s: rects non-empty %s %s" % [msg, j, s])
	assert_true(area.encloses(j) and area.encloses(s), "%s: inside %s: %s %s" % [msg, area, j, s])
	var mid := area.get_center()
	for r in [j, s]:
		assert_true(r.position.x > mid.x and r.position.y > mid.y, "%s: bottom-right %s" % [msg, r])
	assert_true(j.get_area() > s.get_area(), "%s: jump larger than stance" % msg)
	assert_false(j.intersects(s), "%s: no overlap" % msg)


func _assert_fires_at(pos: Vector2, action: StringName, msg: String) -> void:
	auto.touch(pos, true, 0)
	await auto.advance_frames(1)
	assert_true(Input.is_action_pressed(action), "%s: %s pressed at %s" % [msg, action, pos])
	auto.touch(pos, false, 0)
	await auto.advance_frames(1)
	assert_false(Input.is_action_pressed(action), "%s: %s released" % [msg, action])


func test_rect_hooks_at_base_resolution() -> void:
	var vp := Rect2(Vector2.ZERO, get_viewport().get_visible_rect().size)
	_assert_rect_hooks(controls, vp, "base")
	assert_almost_eq(controls.get_jump_rect().get_center().distance_to(controls.jump_center()), 0.0, 1e-3,
			"no offset at the root")
	await _assert_fires_at(controls.get_jump_rect().get_center(), GameActions.JUMP, "base")
	await _assert_fires_at(controls.get_stance_rect().get_center(), GameActions.STANCE_CYCLE, "base")
	assert_eq(probe.events.size(), 0, "button touches are consumed")


func test_rect_hooks_inside_offset_parent() -> void:
	var base_j: Rect2 = controls.get_jump_rect()
	var base_s: Rect2 = controls.get_stance_rect()
	controls.queue_free()
	var parent := Control.new()
	parent.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(parent)
	parent.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	parent.offset_left = 47  # safe-area left inset
	parent.offset_right = -47
	parent.offset_bottom = -21
	controls = TouchControlsFactory.create()
	parent.add_child(controls)
	controls.set_controls_visible(true)
	await auto.advance_frames(1)
	var area := parent.get_global_rect()
	_assert_rect_hooks(controls, area, "offset parent")
	assert_almost_eq(controls.get_jump_rect().position.x, base_j.position.x - 47.0, 1e-3, "jump shifts by the inset")
	assert_almost_eq(controls.get_stance_rect().end.y, base_s.end.y - 21.0, 1e-3, "stance shifts up")
	await _assert_fires_at(controls.get_jump_rect().get_center(), GameActions.JUMP, "offset parent")
	await _assert_fires_at(controls.get_stance_rect().get_center(), GameActions.STANCE_CYCLE, "offset parent")
	# Resize of the container (as after a viewport resize with stretch aspect expand): rects follow.
	parent.offset_right = -147
	await auto.advance_frames(1)
	assert_almost_eq(controls.get_jump_rect().position.x, base_j.position.x - 147.0, 1e-3, "follows resize")
	_assert_rect_hooks(controls, parent.get_global_rect(), "resized parent")
	await _assert_fires_at(controls.get_jump_rect().get_center(), GameActions.JUMP, "resized parent")
	await _assert_fires_at(controls.get_stance_rect().get_center(), GameActions.STANCE_CYCLE, "resized parent")
	assert_eq(probe.events.size(), 0, "button touches are consumed")
	# after_each frees `controls`; the parent goes too.
	parent.queue_free()
