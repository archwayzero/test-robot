## Speeds per stance and run, camera-relative input, turning, spawn_at, player_moved and state keys.
extends "res://modules/player/tests/support/player_test_base.gd"

const START := Vector3(0.0, 0.0, 8.2)  # walking -Z crosses the floor tile seam at z = 8 and z = 4
const ACCEL_FRAMES := 10
const MEASURE_FRAMES := 30


func _speed_case(input: Vector2, expected: float, label: String) -> float:
	await spawn(START, 0.0)
	press_move(input)
	await auto.advance_frames(ACCEL_FRAMES)
	var v: float = await measure_speed(MEASURE_FRAMES)
	assert_almost_eq(v, expected, expected * 0.05, label)
	print("  measured %s: %.4f m/s" % [label, v])
	return v


func test_walk_speed_half_deflection() -> void:
	await _speed_case(Vector2(0, -0.5), PlayerController.WALK_SPEED, "walk at 50%")
	assert_false(player.is_running())


func test_walk_speed_just_below_threshold() -> void:
	await _speed_case(Vector2(0, -0.65), PlayerController.WALK_SPEED, "walk at 65%")
	assert_false(player.is_running())


func test_run_speed_full_deflection() -> void:
	await _speed_case(Vector2(0, -1.0), PlayerController.RUN_SPEED, "run at 100%")
	assert_true(player.is_running())


func test_run_speed_at_threshold() -> void:
	await _speed_case(Vector2(0, -GameActions.RUN_THRESHOLD), PlayerController.RUN_SPEED, "run at 70%")
	assert_true(player.is_running())


func test_run_held() -> void:
	auto.press_action(GameActions.RUN)
	await _speed_case(Vector2(0, -0.5), PlayerController.RUN_SPEED, "run held at 50%")
	assert_true(player.is_running())


func test_crouch_speed() -> void:
	await spawn(START, 0.0)
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.CROUCH)
	auto.press_action(GameActions.RUN)
	press_move(Vector2(0, -1.0))
	await auto.advance_frames(ACCEL_FRAMES)
	var v: float = await measure_speed(MEASURE_FRAMES)
	assert_almost_eq(v, PlayerController.CROUCH_SPEED, PlayerController.CROUCH_SPEED * 0.05, "crouch")
	print("  measured crouch: %.4f m/s" % v)
	assert_false(player.is_running(), "no running while crouched")


func test_crawl_speed_over_tile_seams() -> void:
	await spawn(START, 0.0)
	await tap_stance()
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	press_move(Vector2(0, -1.0))
	await auto.advance_frames(ACCEL_FRAMES)
	var v: float = await measure_speed(MEASURE_FRAMES)
	assert_almost_eq(v, PlayerController.CRAWL_SPEED, PlayerController.CRAWL_SPEED * 0.05, "crawl")
	print("  measured crawl: %.4f m/s" % v)
	assert_false(player.is_running(), "no running while crawling")
	assert_true(player.global_position.z < 8.0, "crossed the seam at z = 8")
	assert_almost_eq(player.global_position.y, 0.0, 0.02, "stays on the floor")


func test_movement_is_camera_relative_and_body_turns() -> void:
	await spawn(START, 0.0)
	# Orbit the camera with a drag on the right half of the screen.
	var size := player.get_viewport().get_visible_rect().size
	var yaw0: float = cam_yaw()
	await auto.drag(Vector2(size.x * 0.75, size.y * 0.5), Vector2(size.x * 0.75 - 150.0, size.y * 0.5), 6)
	var yaw: float = cam_yaw()
	assert_true(absf(angle_difference(yaw0, yaw)) > 0.3, "right-half drag orbits the camera (%s -> %s)" % [yaw0, yaw])
	var p0 := player.global_position
	press_move(Vector2(0, -0.5))
	await auto.advance_frames(30)
	release_move()
	var moved := player.global_position - p0
	var cam_forward := Vector3(-sin(yaw), 0.0, -cos(yaw))
	assert_true(Vector3(moved.x, 0, moved.z).normalized().dot(cam_forward) > 0.99,
			"forward follows the camera yaw: moved %s, camera forward %s" % [moved, cam_forward])
	assert_true(absf(angle_difference(player.rotation.y, yaw)) < 0.05, "body faces the move direction")
	# Right: body turns to face camera-right.
	press_move(Vector2(1.0, 0))
	await auto.advance_frames(20)
	release_move()
	assert_true(absf(angle_difference(player.rotation.y, yaw - PI / 2)) < 0.05, "body turned right")


func test_left_half_drag_does_not_orbit() -> void:
	await spawn(START, 0.0)
	var size := player.get_viewport().get_visible_rect().size
	var yaw0: float = cam_yaw()
	await auto.drag(Vector2(size.x * 0.25, size.y * 0.5), Vector2(size.x * 0.25 + 150.0, size.y * 0.5), 6)
	assert_almost_eq(cam_yaw(), yaw0, 1e-6)


func test_spawn_at_resets_velocity_and_position() -> void:
	await spawn(START, 0.0)
	press_move(Vector2(0, -1.0))
	await auto.advance_frames(20)
	assert_true(player.velocity.length() > 3.0)
	var target := Vector3(-4.0, 0.0, 4.0)
	player.spawn_at(target, 1.0)
	assert_eq(player.velocity, Vector3.ZERO)
	assert_true(player.global_position.is_equal_approx(target))
	assert_almost_eq(player.rotation.y, 1.0, 1e-6)
	release_move()
	await auto.advance_frames(10)
	assert_true(player.global_position.distance_to(target) < 0.01, "stays put after spawn: %s" % player.global_position)
	assert_true(player.is_grounded())


func test_player_moved_when_moving_not_when_idle() -> void:
	await spawn(START, 0.0)
	await auto.advance_frames(5)
	var events: Array = []
	var cb := func(p: Vector3) -> void: events.append([Engine.get_physics_frames(), p])
	core().player_moved.connect(cb)
	await auto.advance_frames(30)
	assert_eq(events.size(), 0, "idle: no player_moved")
	var t0 := Engine.get_physics_frames()
	press_move(Vector2(0, -0.5))
	await auto.advance_frames(30)
	var ticks := Engine.get_physics_frames() - t0
	release_move()
	core().player_moved.disconnect(cb)
	assert_true(events.size() >= ticks - 3, "emitted nearly every physics frame while moving (%d/%d)" % [events.size(), ticks])
	var frames := {}
	for e in events:
		assert_false(frames.has(e[0]), "at most once per physics frame")
		frames[e[0]] = true


func test_state_keys_written_throttled() -> void:
	await spawn(START, 0.0)
	await auto.advance_frames(40)  # past the throttle window of the spawn write
	var writes: Array = []
	var cb := func(key: StringName, value: Variant) -> void: writes.append([key, Engine.get_physics_frames(), value])
	core().state_value_changed.connect(cb)
	press_move(Vector2(0, -0.5))
	await auto.advance_frames(75)  # 2.5 s
	release_move()
	var pos_frames: Array = []
	for w in writes:
		if w[0] == StateKeys.PLAYER_POSITION:
			pos_frames.append(w[1])
	assert_between(pos_frames.size(), 4, 6, "position writes in 2.5 s of walking: %s" % [pos_frames])
	for i in range(1, pos_frames.size()):
		assert_true(pos_frames[i] - pos_frames[i - 1] >= TPS / 2, "throttle >= 0.5 s: %s" % [pos_frames])
	# Stance change writes immediately (even inside the throttle window).
	writes.clear()
	await tap_stance()
	var stance_written := false
	for w in writes:
		if w[0] == StateKeys.PLAYER_STANCE and w[2] == int(PlayerController.Stance.CROUCH):
			stance_written = true
	assert_true(stance_written, "stance written on change: %s" % [writes])
	# Turn, stop, and the last position/yaw is published within 0.5 s.
	press_move(Vector2(1.0, 0))
	await auto.advance_frames(20)
	release_move()
	await auto.advance_frames(20)
	core().state_value_changed.disconnect(cb)
	var st := core().state
	assert_true((st.get_value(StateKeys.PLAYER_POSITION) as Vector3).distance_to(player.global_position) < 0.01,
			"final position written")
	assert_almost_eq(float(st.get_value(StateKeys.PLAYER_YAW)), player.rotation.y, 1e-4, "yaw written")
	assert_eq(st.get_value(StateKeys.PLAYER_STANCE), int(PlayerController.Stance.CROUCH))
