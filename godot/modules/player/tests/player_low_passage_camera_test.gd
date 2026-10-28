## T030 (M1 finding F6): the camera in low passages keeps the passage visible. Corridors with walls under the
## arena's 1.3 m (CROUCH) and 0.75 m (CRAWL) ceilings; the camera must stay long along the passage, below the
## ceiling, outside geometry, and fade the player visual when it does get close. Open areas stay unchanged.
extends "res://modules/player/tests/support/player_test_base.gd"

const FACING_PLUS_X := -PI / 2.0  # camera behind = toward -X
const SETTLE := 90


func before_each() -> void:
	await super.before_each()
	# Corridor walls like the crypt kit (0.6 thick, centred on the cell edges, clear width 3.4 m).
	for z in [Arena.CROUCH_TUNNEL_Z, Arena.CRAWL_TUNNEL_Z]:
		for side in [-1.0, 1.0]:
			arena.add_box(Vector3((Arena.TUNNEL_X0 + Arena.TUNNEL_X1) * 0.5, 1.5, z + side * 2.0),
					Vector3(Arena.TUNNEL_X1 - Arena.TUNNEL_X0, 3.0, 0.6))
	await auto.advance_frames(2)


func _cam() -> Vector3:
	return player.get_camera().global_position


func _head() -> Vector3:
	return player.global_position + Vector3(0.0, player.get_collision_height() * 0.9, 0.0)


func _fade() -> float:
	return player.call("get_visual_fade")


func _in_body(p: Vector3) -> bool:
	var q := PhysicsPointQueryParameters3D.new()
	q.position = p
	q.collision_mask = 1
	return not player.get_world_3d().direct_space_state.intersect_point(q).is_empty()


## Spawn + restore in the same frame (a standing capsule must never overlap the low ceiling), then settle.
func _spawn_low(pos: Vector3, yaw: float, stance: PlayerController.Stance) -> void:
	player.spawn_at(pos, yaw)
	player.restore_stance(stance)
	await auto.advance_frames(SETTLE)
	assert_eq(player.get_stance(), stance, "restored stance")
	assert_almost_eq(player.global_position.y, 0.0, 0.02, "player on the floor")


## Shared checks after settling in a passage with ceiling underside `ceiling` (relative to the floor at y = 0).
func _assert_camera_in_passage(ceiling: float, min_dist: float, label: String) -> void:
	var cam := _cam()
	var dist := cam.distance_to(_head())
	print("  %s: camera %s, %.3f m from the head, pivot y %.3f, pitch %.3f, fade %.2f"
			% [label, cam, dist, cam_pivot().y, player.call("get_camera_pitch"), _fade()])
	assert_true(dist >= min_dist, "%s: camera %.3f m from the head (>= %.2f)" % [label, dist, min_dist])
	assert_true(cam.y < ceiling - 0.1, "%s: camera below the ceiling (y %.3f, ceiling %.2f)" % [label, cam.y, ceiling])
	assert_true(cam_pivot().y < ceiling - 0.2, "%s: pivot just below the ceiling (%.3f)" % [label, cam_pivot().y])
	assert_true(ray_clear(cam_pivot(), cam), "%s: pivot -> camera ray hits nothing" % label)
	assert_false(_in_body(cam), "%s: camera not inside geometry" % label)
	# Behind the player along the passage (toward -X), not swung up or sideways.
	assert_true(cam.x < player.global_position.x - min_dist * 0.9, "%s: camera behind along the passage" % label)
	assert_true(absf(cam.z - player.global_position.z) < 0.2, "%s: camera on the passage axis" % label)
	assert_almost_eq(_fade(), 0.0, 1e-3, "%s: player visible (camera far enough)" % label)
	# Over-the-shoulder shift so the body does not hide the passage ahead; the shifted view is outside geometry.
	var shoulder: float = player.call("get_camera_shoulder")
	var view := player.get_camera().get_camera_transform().origin
	assert_true(shoulder > 0.3, "%s: view shifted sideways (%.3f m)" % [label, shoulder])
	assert_true(ray_clear(cam, view) and not _in_body(view), "%s: shifted view %s outside geometry" % [label, view])


func test_crouch_passage_camera_stays_long() -> void:
	await _spawn_low(Vector3(16.0, 0.0, Arena.CROUCH_TUNNEL_Z), FACING_PLUS_X, PlayerController.Stance.CROUCH)
	_assert_camera_in_passage(Arena.CROUCH_CEILING, 1.2, "crouch in CROUCH passage")


func test_crawl_passage_camera_stays_long() -> void:
	await _spawn_low(Vector3(16.0, 0.0, Arena.CRAWL_TUNNEL_Z), FACING_PLUS_X, PlayerController.Stance.CRAWL)
	_assert_camera_in_passage(Arena.CRAWL_CEILING, 0.8, "crawl in CRAWL passage")


func test_crawl_in_crouch_passage() -> void:
	await _spawn_low(Vector3(16.0, 0.0, Arena.CROUCH_TUNNEL_Z), FACING_PLUS_X, PlayerController.Stance.CRAWL)
	_assert_camera_in_passage(Arena.CROUCH_CEILING, 0.8, "crawl in CROUCH passage")


## Walk crouched from the open into the passage and on: every physics frame the camera is outside geometry, below
## the ceiling while under it, and moves smoothly (no per-frame popping).
func test_walk_into_crouch_passage_smooth_and_clear() -> void:
	await _walk_in(Arena.CROUCH_TUNNEL_Z, Arena.CROUCH_CEILING, 1, 240, 1.2)


func test_crawl_into_crawl_passage_smooth_and_clear() -> void:
	await _walk_in(Arena.CRAWL_TUNNEL_Z, Arena.CRAWL_CEILING, 2, 480, 0.8)


func _walk_in(z: float, ceiling: float, taps: int, frames: int, min_inside: float) -> void:
	await spawn(Vector3(Arena.TUNNEL_X0 - 3.0, 0.0, z), FACING_PLUS_X)
	for i in taps:
		await tap_stance()
	assert_eq(int(player.get_stance()), taps)
	await auto.advance_frames(30)
	var stats := {"bad": 0, "max_step": 0.0, "min_dist": INF, "last": _cam(), "frames": 0}
	var sample := func() -> void:
		var cam := _cam()
		stats.frames += 1
		stats.max_step = maxf(stats.max_step, cam.distance_to(stats.last))
		stats.last = cam
		var under := cam.x > Arena.TUNNEL_X0 and cam.x < Arena.TUNNEL_X1
		var view := player.get_camera().get_camera_transform().origin
		if (not ray_clear(cam_pivot(), cam) or _in_body(cam) or (under and cam.y > ceiling - 0.1)
				or not ray_clear(cam, view) or _in_body(view)):
			stats.bad += 1
		if player.global_position.x > Arena.TUNNEL_X0 + min_inside + 0.5:
			stats.min_dist = minf(stats.min_dist, cam.distance_to(_head()))
	get_tree().physics_frame.connect(sample)
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(frames)  # crouch 8 s at 1 m/s, crawl 16 s at 0.5 m/s: ~8 m
	release_move()
	await auto.advance_frames(2)
	get_tree().physics_frame.disconnect(sample)
	print("  walk-in: %d frames, max camera step %.3f m, min distance inside %.3f m, bad %d"
			% [stats.frames, stats.max_step, stats.min_dist, stats.bad])
	assert_true(player.global_position.x > Arena.TUNNEL_X0 + 3.0 and player.global_position.y > -0.02, "walked into the passage (%s)" % player.global_position)
	assert_eq(stats.bad, 0, "frames with the camera in geometry or above the ceiling")
	assert_true(stats.max_step < 0.12, "smooth: max camera step per physics frame %.3f m" % stats.max_step)
	assert_true(stats.min_dist >= min_inside, "arm stays long inside: min %.3f m" % stats.min_dist)


## Backed against a wall at the passage end the arm must be short: the player visual fades/hides.
func test_close_camera_fades_player() -> void:
	arena.add_box(Vector3(Arena.TUNNEL_X1 + 0.3, 1.5, Arena.CROUCH_TUNNEL_Z), Vector3(0.6, 3.0, 4.0))  # face at x 20
	await auto.advance_frames(2)
	# Facing -X, camera behind -> the end wall.
	await _spawn_low(Vector3(Arena.TUNNEL_X1 - 0.45, 0.0, Arena.CROUCH_TUNNEL_Z), PI / 2.0, PlayerController.Stance.CROUCH)
	var cam := _cam()
	var dist := cam.distance_to(_head())
	print("  backed against the end wall: camera %.3f m from the head, fade %.2f" % [dist, _fade()])
	assert_true(dist < 0.6, "setup: camera close (%.3f m)" % dist)
	assert_true(_fade() >= 0.5, "player visual faded/hidden when the camera is %.3f m away (fade %.2f)" % [dist, _fade()])
	var capsule := player.get_node("Visual/Capsule") as GeometryInstance3D
	assert_true(capsule.transparency >= 0.5 or not capsule.is_visible_in_tree(), "capsule transparent or hidden")
	assert_true(ray_clear(cam_pivot(), cam), "pivot -> camera ray hits nothing")
	assert_false(_in_body(cam), "camera not inside geometry")
	assert_true(cam.y < Arena.CROUCH_CEILING - 0.1, "camera below the ceiling")
	# Walking away from the wall brings the visual back.
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(60)
	release_move()
	await auto.advance_frames(30)
	assert_almost_eq(_fade(), 0.0, 1e-3, "visible again once the camera is far enough")
	assert_true(player.get_node("Visual").visible, "visual node visible again")
	assert_almost_eq(capsule.transparency, 0.0, 1e-3, "capsule opaque again")


## Open floor: arm lengths 2.5/1.8/1.2, default pitch, pivot at 0.9 x height, visual opaque (unchanged by T030).
func test_open_area_unchanged() -> void:
	await spawn(Vector3(0.0, 0.0, 8.0), 0.0)
	var expected := [2.5, 1.8, 1.2]
	for i in 3:
		await auto.advance_frames(60)
		var d := _cam().distance_to(cam_pivot())
		assert_almost_eq(d, expected[i], 0.03, "arm length, stance %d" % player.get_stance())
		assert_almost_eq(float(player.call("get_camera_pitch")), -0.35, 1e-3, "default pitch in the open")
		assert_almost_eq(cam_pivot().y - player.global_position.y, player.get_collision_height() * 0.9, 1e-3, "pivot")
		assert_almost_eq(_fade(), 0.0, 1e-6, "visual opaque in the open")
		assert_almost_eq(player.get_camera().h_offset, 0.0, 1e-6, "no sideways shift in the open")
		await tap_stance()
