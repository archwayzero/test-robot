## Wall collision (8 push angles in a closed 4 m cell, a thin wall at run speed) and camera behaviour.
extends "res://modules/player/tests/support/player_test_base.gd"

const MIN_WALL_DISTANCE := 0.29


func test_wall_push_8_angles() -> void:
	var min_dist := [INF]
	var sample := func() -> void:
		min_dist[0] = minf(min_dist[0], Arena.room_wall_distance(player.global_position))
	for k in 8:
		await spawn(Arena.ROOM_CENTER, 0.0)
		var a := k * PI / 4.0
		var before: float = min_dist[0]
		min_dist[0] = INF
		get_tree().physics_frame.connect(sample)
		press_move(Vector2(sin(a), -cos(a)))
		await auto.advance_frames(120)
		release_move()
		await auto.advance_frames(1)
		get_tree().physics_frame.disconnect(sample)
		var d: float = min_dist[0]
		print("  wall push %d deg: closest %.4f m" % [k * 45, d])
		assert_true(d >= MIN_WALL_DISTANCE, "angle %d deg: closest %.4f m" % [k * 45, d])
		assert_true(d < 0.31, "angle %d deg: actually reached the wall (%.4f m)" % [k * 45, d])
		assert_almost_eq(player.global_position.y, 0.0, 0.02, "still on the floor")
		min_dist[0] = minf(before, d)


func test_no_tunnel_through_thin_wall_at_run_speed() -> void:
	arena.add_box(Vector3(0.0, 1.5, 2.0), Vector3(6.0, 3.0, 0.1))  # thin wall, front face at z = 2.05
	await spawn(Vector3(0.0, 0.0, 7.0), 0.0)
	var min_z := [INF]
	var sample := func() -> void: min_z[0] = minf(min_z[0], player.global_position.z)
	get_tree().physics_frame.connect(sample)
	press_move(Vector2(0, -1.0))
	await auto.advance_frames(60)
	release_move()
	get_tree().physics_frame.disconnect(sample)
	assert_true(min_z[0] >= 2.05 + MIN_WALL_DISTANCE, "closest z %.4f (wall face 2.05)" % min_z[0])


func test_camera_current_and_behind_above() -> void:
	await spawn(Vector3(0.0, 0.0, 8.0), 0.0)
	var cam := player.get_camera()
	assert_not_null(cam)
	assert_true(cam.current, "camera is current")
	assert_eq(player.get_viewport().get_camera_3d(), cam)
	await auto.advance_frames(5)
	var rel := cam.global_position - player.global_position
	assert_true(rel.z > 1.5, "behind (+Z when facing -Z): %s" % rel)
	assert_true(rel.y > player.get_collision_height(), "above the head: %s" % rel)


func test_arm_length_per_stance() -> void:
	await spawn(Vector3(0.0, 0.0, 8.0), 0.0)
	var expected := [2.5, 1.8, 1.2]
	for i in 3:
		await auto.advance_frames(60)
		var d := player.get_camera().global_position.distance_to(cam_pivot())
		assert_almost_eq(d, expected[i], 0.03, "arm length, stance %d" % player.get_stance())
		await tap_stance()


func test_camera_never_inside_wall_in_corner() -> void:
	# Facing the room's -X/-Z corner; walking back pushes the player (and the camera behind it) into the
	# +X/+Z corner.
	await spawn(Arena.ROOM_CENTER, PI / 4.0)
	var bad := [0]
	var check := func() -> void:
		var cam := player.get_camera().global_position
		if not ray_clear(cam_pivot(), cam) or Arena.room_wall_distance(cam) < 0.0:
			bad[0] += 1
	get_tree().process_frame.connect(check)
	press_move(Vector2(0, 1.0))
	await auto.advance_frames(90)
	release_move()
	await auto.advance_frames(30)
	get_tree().process_frame.disconnect(check)
	var cam_pos := player.get_camera().global_position
	assert_true(Arena.room_wall_distance(player.global_position) < 0.31, "pushed into the corner")
	assert_true(ray_clear(cam_pivot(), cam_pos), "head -> camera ray hits nothing")
	assert_true(Arena.room_wall_distance(cam_pos) > 0.0, "camera inside the room: %s" % cam_pos)
	var q := PhysicsPointQueryParameters3D.new()
	q.position = cam_pos
	q.collision_mask = 1
	assert_true(player.get_world_3d().direct_space_state.intersect_point(q).is_empty(), "camera not in a body")
	assert_true(cam_pos.distance_to(cam_pivot()) < 2.0, "arm shortened")
	assert_eq(bad[0], 0, "frames with the camera behind/inside a wall")
