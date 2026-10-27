## Stance heights, cycle order, refusals under low ceilings, jumping.
extends "res://modules/player/tests/support/player_test_base.gd"

const OPEN := Vector3(0.0, 0.0, 8.2)
const FACE_PLUS_X := -PI / 2


func _record_stances() -> Array:
	var log: Array = []
	player.stance_changed.connect(func(s: PlayerController.Stance) -> void: log.append(s))
	return log


func test_heights_and_cycle_order() -> void:
	await spawn(OPEN)
	var log := _record_stances()
	assert_eq(player.get_stance(), PlayerController.Stance.STAND)
	assert_almost_eq(player.get_collision_height(), 1.75, 1e-6, "stand")
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.CROUCH)
	assert_almost_eq(player.get_collision_height(), 1.0, 1e-6, "crouch")
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	assert_almost_eq(player.get_collision_height(), 0.5, 1e-6, "crawl")
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.STAND)
	assert_eq(log, [PlayerController.Stance.CROUCH, PlayerController.Stance.CRAWL, PlayerController.Stance.STAND])


func test_collision_shape_matches_height() -> void:
	await spawn(OPEN)
	for i in 3:
		var cs := player.get_node("CollisionShape3D") as CollisionShape3D
		var top := cs.position.y + _shape_half_height(cs.shape)
		var bottom := cs.position.y - _shape_half_height(cs.shape)
		assert_almost_eq(top, player.get_collision_height(), 1e-4, "shape top, stance %d" % player.get_stance())
		assert_almost_eq(bottom, 0.0, 1e-4, "feet at the origin, stance %d" % player.get_stance())
		assert_almost_eq(_shape_radius(cs.shape), 0.3, 1e-6, "radius")
		await tap_stance()
	assert_eq(player.collision_layer, 2)
	assert_eq(player.collision_mask, 1)


func _shape_half_height(s: Shape3D) -> float:
	if s is CapsuleShape3D:
		return (s as CapsuleShape3D).height * 0.5
	if s is CylinderShape3D:
		return (s as CylinderShape3D).height * 0.5
	return 0.0


func _shape_radius(s: Shape3D) -> float:
	if s is CapsuleShape3D:
		return (s as CapsuleShape3D).radius
	if s is CylinderShape3D:
		return (s as CylinderShape3D).radius
	return 0.0


## Walks +X from x = 9 until the player is well under the ceiling at `z`.
func _enter_tunnel(z: float) -> void:
	await spawn(Vector3(9.0, 0.0, z), FACE_PLUS_X)
	press_move(Vector2(0, -1.0))
	var ok: bool = await auto.wait_until(func() -> bool: return player.global_position.x >= 14.0, 600)
	release_move()
	await auto.advance_frames(5)
	assert_true(ok, "reached the tunnel (x = %s)" % player.global_position.x)
	assert_almost_eq(player.global_position.z, z, 0.05, "walked straight")


func test_stand_refused_under_crouch_ceiling() -> void:
	await spawn(Vector3(9.0, 0.0, Arena.CROUCH_TUNNEL_Z), FACE_PLUS_X)
	await tap_stance()  # crouch outside
	await _enter_tunnel(Arena.CROUCH_TUNNEL_Z)
	assert_eq(player.get_stance(), PlayerController.Stance.CROUCH)
	var log := _record_stances()
	await tap_stance()  # -> crawl
	await tap_stance()  # -> stand refused, skip to crouch
	await tap_stance()  # -> crawl
	await tap_stance()  # -> crouch again
	assert_eq(log, [PlayerController.Stance.CRAWL, PlayerController.Stance.CROUCH,
			PlayerController.Stance.CRAWL, PlayerController.Stance.CROUCH], "never stands under 1.3 m")
	assert_almost_eq(player.get_collision_height(), 1.0, 1e-6)
	# No jump from a crouch under the low ceiling (would need to stand up).
	var jumps := [0]
	player.jumped.connect(func() -> void: jumps[0] += 1)
	await tap_jump()
	await auto.advance_frames(20)
	assert_eq(jumps[0], 0, "no jump under a low ceiling")
	assert_eq(player.get_stance(), PlayerController.Stance.CROUCH)
	assert_true(player.global_position.y < 0.01, "still on the floor")
	# Leave the tunnel backwards: standing is allowed again in the open.
	press_move(Vector2(0, 1.0))
	await auto.wait_until(func() -> bool: return player.global_position.x <= 10.5, 600)
	release_move()
	await auto.advance_frames(3)
	await tap_stance()  # crawl
	await tap_stance()  # stand
	assert_eq(player.get_stance(), PlayerController.Stance.STAND, "stands up in the open")


func test_crouch_refused_under_crawl_ceiling() -> void:
	await spawn(Vector3(9.0, 0.0, Arena.CRAWL_TUNNEL_Z), FACE_PLUS_X)
	await tap_stance()
	await tap_stance()  # crawl outside
	await _enter_tunnel(Arena.CRAWL_TUNNEL_Z)
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	var log := _record_stances()
	for i in 3:
		await tap_stance()
	assert_eq(log, [], "no stance change under 0.75 m")
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	assert_almost_eq(player.get_collision_height(), 0.5, 1e-6)


func test_jump_then_land() -> void:
	await spawn(OPEN)
	var events: Array = []
	player.jumped.connect(func() -> void: events.append(["jumped", Engine.get_process_frames()]))
	player.landed.connect(func() -> void: events.append(["landed", Engine.get_process_frames()]))
	var f0 := Engine.get_process_frames()
	var max_y := [0.0]
	var track := func() -> void: max_y[0] = maxf(max_y[0], player.global_position.y)
	get_tree().physics_frame.connect(track)
	await tap_jump()
	var ok: bool = await auto.wait_until(func() -> bool: return events.size() >= 2, 60)
	get_tree().physics_frame.disconnect(track)
	assert_true(ok, "jumped and landed within 60 frames: %s" % [events])
	if events.size() >= 2:
		assert_eq(events[0][0], "jumped")
		assert_eq(events[1][0], "landed")
		assert_true(events[1][1] - f0 <= 61)
	# Apex h = v^2 / 2g = 16 / 19.6 = 0.816 m
	assert_almost_eq(max_y[0], 0.816, 0.05, "apex height")
	assert_true(player.is_grounded())


func test_no_jump_while_crawling() -> void:
	await spawn(OPEN)
	await tap_stance()
	await tap_stance()
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	var jumps := [0]
	player.jumped.connect(func() -> void: jumps[0] += 1)
	await tap_jump()
	await auto.advance_frames(30)
	assert_eq(jumps[0], 0)
	assert_true(player.global_position.y < 0.01)
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)


func test_jump_from_crouch_in_the_open_stands_up() -> void:
	await spawn(OPEN)
	await tap_stance()
	var jumps := [0]
	player.jumped.connect(func() -> void: jumps[0] += 1)
	await tap_jump()
	await auto.advance_frames(2)
	assert_eq(jumps[0], 1)
	assert_eq(player.get_stance(), PlayerController.Stance.STAND)
