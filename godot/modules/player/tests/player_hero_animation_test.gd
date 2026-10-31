## T019: hero rig and AnimationTree under the real controller, headless. Clip state is read from the tree's own
## parameters, heights from CPU-skinned vertices of the pose the tree produced. Assertions after an await live in
## plain _check_* helpers (TEST_PLAN "Test runner", N1).
extends "res://modules/player/tests/support/player_test_base.gd"

const HeroSkin := preload("res://modules/player/tests/support/hero_skin.gd")
const Stance := PlayerController.Stance
const OPEN_SPOT := Vector3(0.0, 0.0, 12.0)
const DT := 1.0 / 30.0
## Tops measured in T014 (contract "Asset: hero": crouch <= 1.234, crawl <= 0.695), +1 mm rounding.
const STAND_TOP := 1.752
const CROUCH_TOP := 1.235
const CRAWL_TOP := 0.696
## Crouch same-stance blends measured 1.237 m (idle <-> walk), a 3 mm overshoot of the clip top reported in T019.
const CROUCH_BLEND_TOP := 1.24
## Lowest vertex of a settled clip (T014 worst -2.2 mm) and of a same-stance blend (measured -0.052 m).
const FLOOR_MIN := -0.01
const BLEND_FLOOR_MIN := -0.06
## Highest lowest vertex with a blade on the floor, settled and in a blend (measured 0.031 m).
const FLOOR_MAX := 0.01
const BLEND_FLOOR_MAX := 0.04

var skin: HeroSkin


func before_each() -> void:
	await super.before_each()
	skin = HeroSkin.new(player)
	await spawn(OPEN_SPOT)


func _tree() -> AnimationTree:
	return player.get_node("Visual/Animator") as AnimationTree


func _clip() -> String:
	return str(_tree().get("parameters/locomotion/current_state"))


func _jump_active() -> bool:
	return _tree().get("parameters/jump/active")


func _position_of(clip: String) -> float:
	return _tree().get("parameters/clip_%s/current_position" % clip)


func _actual_speed() -> float:
	var v := player.get_real_velocity()
	return Vector2(v.x, v.z).length()


func _set_stance(target: Stance) -> void:
	for i in 3:
		await _tap_unless(target)
	await auto.advance_frames(1)


func _tap_unless(target: Stance) -> void:
	if player.get_stance() != target:
		await tap_stance()


## Holds the input until the stance's speed is reached, then records state for _check_moving().
func _sample_moving(input: Vector2) -> Dictionary:
	press_move(input)
	await auto.advance_frames(20)
	var out := {"clip": _clip(), "speed": _actual_speed()}
	release_move()
	await auto.advance_frames(10)
	out["after"] = _clip()
	return out


func _check_moving(s: Dictionary, clip: String, idle: String, speed: float, label: String) -> void:
	assert_eq(s["clip"], clip, label + " moving clip")
	assert_almost_eq(float(s["speed"]), speed, speed * 0.05, label + " actual speed")
	assert_eq(s["after"], idle, label + " back to idle clip")


# --- hookup --------------------------------------------------------------------------------------------

func test_hero_replaces_capsule() -> void:
	assert_true(player.get_node_or_null("Visual/Capsule") == null, "capsule placeholder gone")
	assert_true(player.get_node_or_null("Visual/Nose") == null, "nose placeholder gone")
	assert_eq(skin.mesh_instance.mesh.get_surface_count(), 2, "both hero materials present")
	assert_eq(skin.skeleton.get_bone_count(), 23, "rig skeleton")
	assert_true(_tree().active, "tree active")
	assert_eq(_tree().root_motion_track, NodePath(), "no root motion")


## Rest height of the conformed hero against the stand capsule.
func test_stand_height_matches_hero() -> void:
	assert_almost_eq(skin.mesh_instance.get_aabb().end.y, player.get_collision_height(), 0.005, "hero rest top vs capsule")
	assert_almost_eq(player.get_collision_height(), 1.75, 1e-6, "contract height")


func _shape_row(s: Shape3D) -> Array:
	if s is CapsuleShape3D:
		return ["capsule", (s as CapsuleShape3D).radius, (s as CapsuleShape3D).height]
	return ["cylinder", (s as CylinderShape3D).radius, (s as CylinderShape3D).height]


func _check_shape(stance: Stance, kind: String, height: float) -> void:
	var col := player.get_node("CollisionShape3D") as CollisionShape3D
	assert_eq(player.get_stance(), stance, "stance reached")
	var row := _shape_row(col.shape)
	assert_eq(row[0], kind, "shape kind")
	assert_almost_eq(float(row[1]), 0.3, 1e-6, "radius")
	assert_almost_eq(float(row[2]), height, 1e-6, "height")
	assert_almost_eq(col.position.y, height * 0.5, 1e-6, "shape rests on the feet")


func test_capsule_shapes_unchanged() -> void:
	_check_shape(Stance.STAND, "capsule", 1.75)
	await _set_stance(Stance.CROUCH)
	_check_shape(Stance.CROUCH, "capsule", 1.0)
	await _set_stance(Stance.CRAWL)
	_check_shape(Stance.CRAWL, "cylinder", 0.5)


func _displacement_for(frames: int) -> Vector3:
	var start := player.global_position
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(frames)
	release_move()
	var moved := player.global_position - start
	await auto.advance_frames(15)
	return moved


## The same input moves the body the same with the tree playing and with the tree off.
func test_animation_does_not_affect_movement() -> void:
	var with_tree: Vector3 = await _displacement_for(40)
	await spawn(OPEN_SPOT)
	_tree().active = false
	var without_tree: Vector3 = await _displacement_for(40)
	_check_same_motion(with_tree, without_tree)


func _check_same_motion(a: Vector3, b: Vector3) -> void:
	assert_true(a.length() > 2.0, "setup: moved (%.3f m)" % a.length())
	assert_true(a.distance_to(b) < 1e-3, "displacement differs by %.5f m" % a.distance_to(b))


func _check_facing(head: Vector3, hips: Vector3, hand_l: Vector3, hand_r: Vector3, fwd: Vector3, label: String) -> void:
	var left := Vector3.UP.cross(fwd)
	assert_true((head - hips).dot(fwd) > 0.2, "%s: head leads the hips (%.3f)" % [label, (head - hips).dot(fwd)])
	assert_true((hand_l - hand_r).dot(left) > 0.2, "%s: left hand on the left, not mirrored (%.3f)"
			% [label, (hand_l - hand_r).dot(left)])


## In crawl the head lies far ahead of the hips, so it shows which way the model really faces.
func test_model_faces_move_direction() -> void:
	await _set_stance(Stance.CRAWL)
	var dirs: Array[Vector2] = [Vector2(0.0, -1.0), Vector2(1.0, 0.0), Vector2(0.0, 1.0), Vector2(-1.0, 0.0)]
	for input in dirs:
		press_move(input)
		await auto.advance_frames(30)
		_check_facing(skin.bone_world("head"), skin.bone_world("hips"), skin.bone_world("hand_l"),
				skin.bone_world("hand_r"), Vector3(input.x, 0.0, input.y).rotated(Vector3.UP, cam_yaw()),
				"input %s" % input)
	release_move()


# --- clip choice ---------------------------------------------------------------------------------------

func test_clip_table() -> void:
	var animator := _tree()
	var rows := [
		[Stance.STAND, 0.0, "idle_loop"], [Stance.STAND, 0.04, "idle_loop"], [Stance.STAND, 0.06, "walk_loop"],
		[Stance.STAND, 1.6, "walk_loop"], [Stance.STAND, 2.5, "walk_loop"], [Stance.STAND, 2.6, "jog_loop"],
		[Stance.STAND, 4.0, "jog_loop"],
		[Stance.CROUCH, 0.0, "crouch_idle_loop"], [Stance.CROUCH, 1.0, "crouch_walk_loop"],
		[Stance.CRAWL, 0.0, "crawl_idle_loop"], [Stance.CRAWL, 0.5, "crawl_loop"],
	]
	for row in rows:
		assert_eq(str(animator.call("clip_for", row[0], row[1])), row[2], "stance %d at %.2f m/s" % [row[0], row[1]])


func test_stand_clips_follow_real_movement() -> void:
	assert_eq(_clip(), "idle_loop", "idle at rest")
	_check_moving(await _sample_moving(Vector2(0.0, -0.5)), "walk_loop", "idle_loop", 1.6, "walk")
	_check_moving(await _sample_moving(Vector2(0.0, -1.0)), "jog_loop", "idle_loop", 4.0, "run")


func test_crouch_clips_follow_real_movement() -> void:
	await _set_stance(Stance.CROUCH)
	await auto.advance_frames(10)
	assert_eq(_clip(), "crouch_idle_loop", "crouch idle at rest")
	_check_moving(await _sample_moving(Vector2(0.0, -1.0)), "crouch_walk_loop", "crouch_idle_loop", 1.0, "crouch walk")


func test_crawl_clips_follow_real_movement() -> void:
	await _set_stance(Stance.CRAWL)
	await auto.advance_frames(10)
	assert_eq(_clip(), "crawl_idle_loop", "crawl idle at rest")
	_check_moving(await _sample_moving(Vector2(0.0, -1.0)), "crawl_loop", "crawl_idle_loop", 0.5, "crawl")


## Input held against a wall: the body does not move, so the clip must be idle (real speed, not input).
func test_pushing_a_wall_head_on_shows_idle() -> void:
	await spawn(Arena.ROOM_CENTER + Vector3(0.0, 0.0, -1.0))
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(40)
	assert_almost_eq(_actual_speed(), 0.0, 0.01, "setup: stopped by the wall")
	assert_eq(_clip(), "idle_loop", "idle against a wall")


# --- playback scale ------------------------------------------------------------------------------------

## Clip seconds played per second over `frames` frames, loop wrap removed.
func _measure_rate(clip: String, frames: int) -> Array:
	var length: float = (player.get_node("Visual/Hero/AnimationPlayer") as AnimationPlayer).get_animation(clip).length
	var played := 0.0
	var last := _position_of(clip)
	for i in frames:
		await auto.advance_frames(1)
		played += fposmod(_position_of(clip) - last, length)
		last = _position_of(clip)
	return [played / (frames * DT), _actual_speed(), float(_tree().get("parameters/scale_%s/scale" % clip)), _clip()]


func _check_rate(m: Array, clip: String, clip_speed: float, want_speed: float, label: String) -> void:
	assert_eq(m[3], clip, label + ": clip")
	assert_almost_eq(float(m[1]), want_speed, want_speed * 0.08, label + ": setup speed")
	assert_almost_eq(float(m[2]), float(m[1]) / clip_speed, 0.02, label + ": scale = speed / clip speed")
	assert_almost_eq(float(m[0]), float(m[1]) / clip_speed, 0.04, label + ": measured clip rate")


func test_scale_at_authored_speeds() -> void:
	press_move(Vector2(0.0, -0.5))
	await auto.advance_frames(15)
	_check_rate(await _measure_rate("walk_loop", 20), "walk_loop", 1.6, 1.6, "walk")
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(15)
	_check_rate(await _measure_rate("jog_loop", 15), "jog_loop", 4.0, 4.0, "run")
	release_move()
	await _set_stance(Stance.CROUCH)
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(15)
	_check_rate(await _measure_rate("crouch_walk_loop", 20), "crouch_walk_loop", 1.0, 1.0, "crouch walk")
	release_move()
	await _set_stance(Stance.CRAWL)
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(15)
	_check_rate(await _measure_rate("crawl_loop", 20), "crawl_loop", 0.5, 0.5, "crawl")


## Sliding along a wall at 60 degrees into it: the body moves at half the input speed, the clip must follow.
func test_scale_follows_actual_speed_along_a_wall() -> void:
	await spawn(Arena.ROOM_CENTER + Vector3(1.3, 0.0, 1.3))
	press_move(Vector2(0.433, -0.25))
	await auto.advance_frames(15)
	_check_rate(await _measure_rate("walk_loop", 20), "walk_loop", 1.6, 0.8, "wall slide")


# --- jump ----------------------------------------------------------------------------------------------

## Presses jump and returns the jump clip position 2 frames later (input tick, then the tree's next process).
func _start_jump() -> float:
	auto.press_action(GameActions.JUMP)
	await auto.advance_frames(2)
	auto.release_action(GameActions.JUMP)
	return _position_of("jump")


func _check_jump_started(at: float, label: String) -> void:
	assert_true(player.velocity.y > 0.0, label + ": body jumped")
	assert_true(_jump_active(), label + ": jump clip active")
	assert_true(at >= 0.0 and at <= 2.0 * DT + 1e-3, "%s: clip at %.3f s two frames after pressing jump" % [label, at])


func test_jump_blend_times() -> void:
	var node := (_tree().tree_root as AnimationNodeBlendTree).get_node(&"jump") as AnimationNodeOneShot
	assert_almost_eq(node.fadein_time, 0.1, 0.02, "crossfade in about 0.1 s")


func test_jump_starts_at_frame_zero_and_returns_to_idle() -> void:
	_check_jump_started(await _start_jump(), "first jump")
	await auto.advance_frames(10)
	var mid := _position_of("jump")
	await auto.advance_frames(45)
	assert_true(mid > 0.25, "clip advancing in real time (%.3f)" % mid)
	assert_false(_jump_active(), "jump finished after landing")
	assert_true(player.is_grounded(), "landed")
	assert_eq(_clip(), "idle_loop", "idle")


## A jump during the recovery of the last one restarts the clip: the Transition cannot, the OneShot must.
func test_second_jump_restarts_clip() -> void:
	await _start_jump()
	await auto.advance_frames(1)
	var ok: bool = await auto.wait_until(player.is_grounded, 60)
	assert_true(ok, "landed")
	await auto.advance_frames(3)
	var before := _position_of("jump")
	var again: float = await _start_jump()
	_check_restart(before, again)


func _check_restart(before: float, again: float) -> void:
	assert_true(before > 0.7, "setup: first clip in recovery (%.3f)" % before)
	_check_jump_started(again, "second jump")


## Landing while moving goes to the moving clip at once, without waiting for the standing recovery.
func test_landing_while_moving_returns_to_locomotion() -> void:
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(15)
	await _start_jump()
	await auto.advance_frames(1)
	var ok: bool = await auto.wait_until(player.is_grounded, 60)
	var at_landing := _position_of("jump")
	await auto.advance_frames(8)
	_check_landed_moving(ok, at_landing)


func _check_landed_moving(ok: bool, at_landing: float) -> void:
	assert_true(ok, "landed")
	assert_true(at_landing < 1.0, "landed before the clip's end (%.3f)" % at_landing)
	assert_false(_jump_active(), "jump faded out 8 frames after landing")
	assert_eq(_clip(), "jog_loop", "jogging")


## Stance change in the air: the jump pose must go at once, and the landing shows the crouch clip.
func test_landing_into_crouch() -> void:
	await _start_jump()
	await auto.advance_frames(6)
	await tap_stance()
	await auto.advance_frames(8)
	var mid_air := [player.get_stance(), player.is_grounded(), _jump_active(), _clip()]
	await auto.wait_until(player.is_grounded, 60)
	await auto.advance_frames(5)
	assert_eq(mid_air[0], Stance.CROUCH, "crouched in the air")
	assert_false(mid_air[1], "setup: still airborne")
	assert_false(mid_air[2], "jump gone in the air")
	assert_eq(mid_air[3], "crouch_idle_loop", "crouch clip in the air")
	assert_false(_jump_active(), "no jump after landing")
	assert_eq(_clip(), "crouch_idle_loop", "crouch idle after landing")


## Crouched in the air, a low ceiling appears over the landing spot: the stand-up the next jump needs is refused and
## nothing plays the jump again.
func test_landing_under_a_blocked_stand() -> void:
	await _start_jump()
	await auto.advance_frames(6)
	await tap_stance()
	await auto.wait_until(_is_low_and_falling, 60)
	arena.add_ceiling(OPEN_SPOT.z, Arena.CROUCH_CEILING)
	(arena.get_child(-1) as Node3D).position.x = OPEN_SPOT.x
	await auto.wait_until(player.is_grounded, 60)
	await auto.advance_frames(5)
	await tap_jump()
	await auto.advance_frames(3)
	assert_eq(player.get_stance(), Stance.CROUCH, "stand refused, still crouched")
	assert_true(player.is_grounded(), "still on the floor")
	assert_false(_jump_active(), "refused jump plays no clip")
	assert_eq(_clip(), "crouch_idle_loop", "crouch idle")


func _is_low_and_falling() -> bool:
	return player.velocity.y < 0.0 and player.global_position.y < 0.25


# --- nothing stuck -------------------------------------------------------------------------------------

func _snapshot() -> Array:
	return [_clip(), _jump_active()]


func _check_snapshot(s: Array, clip: String, label: String) -> void:
	assert_eq(s[0], clip, label + ": clip")
	assert_false(s[1], label + ": no jump")


func test_stance_cycle_moves_with_the_tree() -> void:
	await tap_stance()
	await auto.advance_frames(3)
	_check_snapshot(_snapshot(), "crouch_idle_loop", "crouch")
	await tap_stance()
	await auto.advance_frames(3)
	_check_snapshot(_snapshot(), "crawl_idle_loop", "crawl")
	await tap_stance()
	await auto.advance_frames(3)
	_check_snapshot(_snapshot(), "idle_loop", "stand")


## Stance change at speed: the moving clip of the new stance, not the old one.
func test_stance_change_while_moving() -> void:
	press_move(Vector2(0.0, -0.5))
	await auto.advance_frames(15)
	await tap_stance()
	await auto.advance_frames(10)
	_check_snapshot(_snapshot(), "crouch_walk_loop", "moving crouch")
	await tap_stance()
	await auto.advance_frames(10)
	_check_snapshot(_snapshot(), "crawl_loop", "moving crawl")


## Load in the middle of a jump: restore_stance() to the saved stance, with the first frame already in that pose.
func test_restore_stance_during_jump() -> void:
	await _start_jump()
	await auto.advance_frames(4)
	var flying := _jump_active()
	player.spawn_at(OPEN_SPOT + Vector3(2.0, 0.0, 0.0), 0.0)
	player.restore_stance(Stance.CRAWL)
	await auto.advance_frames(1)
	var first := skin.heights()
	var state := _snapshot()
	assert_true(flying, "setup: jump playing")
	assert_true(float(first["top"]) < CRAWL_TOP, "first frame already in the crawl pose (top %.3f)" % float(first["top"]))
	_check_snapshot(state, "crawl_idle_loop", "restored crawl")


## restore_stance() with no stance change still clears the jump when spawn_at() came first.
func test_spawn_clears_jump_without_stance_change() -> void:
	await _start_jump()
	await auto.advance_frames(4)
	player.spawn_at(OPEN_SPOT, 0.0)
	player.restore_stance(Stance.STAND)
	await auto.advance_frames(3)
	_check_snapshot(_snapshot(), "idle_loop", "same stance")


## Saved STAND inside a crouch passage falls back to CROUCH: clip and pose follow the stance actually taken.
func test_restore_falls_back_in_low_passage() -> void:
	player.spawn_at(Vector3(16.0, 0.0, Arena.CROUCH_TUNNEL_Z), 0.0)
	player.restore_stance(Stance.CRAWL)
	await auto.advance_frames(5)
	_check_snapshot(_snapshot(), "crawl_idle_loop", "crawl")
	player.spawn_at(Vector3(16.0, 0.0, Arena.CROUCH_TUNNEL_Z), 0.0)
	player.restore_stance(Stance.STAND)
	await auto.advance_frames(1)
	var first := skin.heights()
	var state := _snapshot()
	assert_eq(player.get_stance(), Stance.CROUCH, "fell back to crouch")
	assert_true(float(first["top"]) < CROUCH_TOP, "first frame under the ceiling (top %.3f)" % float(first["top"]))
	_check_snapshot(state, "crouch_idle_loop", "crouch")


# --- heights and feet ----------------------------------------------------------------------------------

## Samples the pose for `frames` frames.
func _sample_heights(frames: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for i in frames:
		await auto.advance_frames(1)
		out.append(skin.heights())
	return out


## Returns "" when every sample holds, otherwise what failed. Also the target of the self-test below.
func _heights_problem(samples: Array[Dictionary], top_limit: float, low: float, high: float) -> String:
	if samples.is_empty():
		return "no samples"
	for s in samples:
		if float(s["top"]) > top_limit:
			return "top %.4f over %.3f" % [float(s["top"]), top_limit]
		if float(s["bottom"]) < low or float(s["bottom"]) > high:
			return "feet at %.4f outside %.3f..%.3f" % [float(s["bottom"]), low, high]
	return ""


func _check_settled(samples: Array[Dictionary], top_limit: float, label: String) -> void:
	assert_eq(_heights_problem(samples, top_limit, FLOOR_MIN, FLOOR_MAX), "", label)


## A body raised 0.2 m must fail the same helper, and the measured top must really follow the mesh.
func test_height_check_can_fail() -> void:
	await auto.advance_frames(2)
	var low := skin.heights()
	player.get_node("Visual").position.y = 0.2
	var raised := skin.heights()
	player.get_node("Visual").position.y = 0.0
	assert_almost_eq(float(raised["top"]) - float(low["top"]), 0.2, 1e-3, "measured top follows the mesh")
	var bad: Array[Dictionary] = [raised]
	assert_true(_heights_problem(bad, STAND_TOP, FLOOR_MIN, FLOOR_MAX) != "", "raised pose reported")
	var none: Array[Dictionary] = []
	assert_true(_heights_problem(none, STAND_TOP, FLOOR_MIN, FLOOR_MAX) != "", "no samples reported")


func test_stand_heights_and_feet() -> void:
	await auto.advance_frames(8)
	_check_settled(await _sample_heights(10), STAND_TOP, "idle")
	press_move(Vector2(0.0, -0.5))
	await auto.advance_frames(10)
	_check_settled(await _sample_heights(15), STAND_TOP, "walk")
	release_move()


func test_crouch_heights_and_feet() -> void:
	await _set_stance(Stance.CROUCH)
	await auto.advance_frames(8)
	_check_settled(await _sample_heights(10), CROUCH_TOP, "crouch idle")
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(10)
	_check_settled(await _sample_heights(15), CROUCH_TOP, "crouch walk")
	release_move()


func test_crawl_heights_and_feet() -> void:
	await _set_stance(Stance.CRAWL)
	await auto.advance_frames(8)
	_check_settled(await _sample_heights(10), CRAWL_TOP, "crawl idle")
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(10)
	_check_settled(await _sample_heights(15), CRAWL_TOP, "crawl")
	release_move()


## jog_loop has a flight phase in which both blades leave the floor, so only its top and lowest bound apply.
func test_jog_top() -> void:
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(10)
	var jog: Array[Dictionary] = await _sample_heights(10)
	release_move()
	assert_eq(_heights_problem(jog, STAND_TOP, FLOOR_MIN, INF), "", "jog")


## A real CROUCH passage: walk, stop, go again, drop to crawl and rise to crouch. Same-stance blends stay under the
## blend limit; both stance changes are cuts here, so the rise never blends past it.
func test_crouch_passage_stays_under_ceiling() -> void:
	player.spawn_at(Vector3(15.0, 0.0, Arena.CROUCH_TUNNEL_Z), -PI / 2.0)
	player.restore_stance(Stance.CROUCH)
	await auto.advance_frames(3)
	press_move(Vector2(0.0, -1.0))
	var a: Array[Dictionary] = await _sample_heights(30)
	release_move()
	var b: Array[Dictionary] = await _sample_heights(12)
	press_move(Vector2(0.0, -1.0))
	var c: Array[Dictionary] = await _sample_heights(12)
	await tap_stance()
	var d: Array[Dictionary] = await _sample_heights(10)
	await tap_stance()
	var e: Array[Dictionary] = await _sample_heights(14)
	release_move()
	_check_passage([a, b, c, d, e], Stance.CROUCH, CROUCH_BLEND_TOP, 1.2)


func test_crawl_passage_stays_under_ceiling() -> void:
	player.spawn_at(Vector3(15.0, 0.0, Arena.CRAWL_TUNNEL_Z), -PI / 2.0)
	player.restore_stance(Stance.CRAWL)
	await auto.advance_frames(3)
	press_move(Vector2(0.0, -1.0))
	var a: Array[Dictionary] = await _sample_heights(40)
	release_move()
	var b: Array[Dictionary] = await _sample_heights(12)
	press_move(Vector2(0.0, -1.0))
	var c: Array[Dictionary] = await _sample_heights(12)
	release_move()
	_check_passage([a, b, c], Stance.CRAWL, CRAWL_TOP, 0.65)


func _check_passage(groups: Array, stance: Stance, top_limit: float, top_floor: float) -> void:
	assert_eq(player.get_stance(), stance, "ended in the passage stance")
	var highest := -INF
	var lowest := INF
	for g in groups:
		var samples: Array[Dictionary] = []
		samples.assign(g)
		assert_eq(_heights_problem(samples, top_limit, BLEND_FLOOR_MIN, BLEND_FLOOR_MAX), "", "passage segment")
		for s in samples:
			highest = maxf(highest, float(s["top"]))
			lowest = minf(lowest, float(s["bottom"]))
	print("  passage top %.4f (limit %.3f), lowest %.4f" % [highest, top_limit, lowest])
	assert_true(highest > top_floor, "setup: the hero was in its clip pose (%.3f)" % highest)


# --- fade ----------------------------------------------------------------------------------------------

## Distance helper: to the body's axis, whichever height the point is at.
func test_body_distance_uses_the_whole_axis() -> void:
	var feet := player.global_position
	var d: float = player.call("get_body_distance", feet + Vector3(0.4, 0.3, 0.0))
	assert_almost_eq(d, 0.4, 1e-3, "beside the shins: 0.4 from the body, 1.3+ from the head")
	var top := feet + Vector3(0.0, 1.75 * 0.9, 0.0)
	assert_almost_eq(float(player.call("get_body_distance", top + Vector3(0.0, 0.5, 0.0))), 0.5, 1e-3, "above the head")


## Crawling in the 0.75 m passage the camera is flat behind the hero: the blades are near the lens, the body is not.
func test_blade_tips_near_the_lens_do_not_fade() -> void:
	player.spawn_at(Vector3(16.0, 0.0, Arena.CRAWL_TUNNEL_Z), -PI / 2.0)
	player.restore_stance(Stance.CRAWL)
	press_move(Vector2(0.0, -1.0))
	await auto.advance_frames(45)
	var cam := player.get_camera().global_position
	_check_tips_ignored(skin.nearest_vertex_distance(cam), float(player.call("get_body_distance", cam)))
	release_move()


func _check_tips_ignored(nearest_vertex: float, body: float) -> void:
	print("  camera: nearest hero vertex %.3f m, body %.3f m, fade %.2f" % [nearest_vertex, body, player.call("get_visual_fade")])
	assert_true(nearest_vertex < 0.8, "setup: a blade is inside the fade range (%.3f)" % nearest_vertex)
	assert_true(body > 0.8, "setup: body outside the fade range (%.3f)" % body)
	assert_almost_eq(float(player.call("get_visual_fade")), 0.0, 1e-3, "no fade from the blades")
