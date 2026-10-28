## restore_stance() (T027): saved stance applied right after spawn_at() on load.
## restore_stance is called dynamically (player.call) so the test does not depend on how the public stub is typed.
extends "res://modules/player/tests/support/player_test_base.gd"

const OPEN := Vector3(0.0, 0.0, 8.2)
const UNDER_CROUCH_CEILING := Vector3(16.0, 0.0, Arena.CROUCH_TUNNEL_Z)
const UNDER_CRAWL_CEILING := Vector3(16.0, 0.0, Arena.CRAWL_TUNNEL_Z)

var _initial_state: Dictionary
var _log: Array


func before_each() -> void:
	_initial_state = Core.state.snapshot()
	await super.before_each()
	_log = []
	player.stance_changed.connect(func(s: PlayerController.Stance) -> void: _log.append(s))


func after_each() -> void:
	await super.after_each()
	Core.state.restore(_initial_state)


func _restore(stance: int) -> void:
	player.call("restore_stance", stance)


func _saved_stance() -> Variant:
	return Core.state.get_value(StateKeys.PLAYER_STANCE)


func _assert_stance(expected: PlayerController.Stance, height: float, label: String) -> void:
	assert_eq(player.get_stance(), expected, label + ": stance")
	assert_almost_eq(player.get_collision_height(), height, 1e-6, label + ": collision height")
	var cs := player.get_node("CollisionShape3D") as CollisionShape3D
	assert_almost_eq(cs.position.y, height * 0.5, 1e-4, label + ": shape centred on the new height")
	assert_eq(_saved_stance(), int(expected), label + ": PLAYER_STANCE written")


func test_restore_crouch_in_open_space() -> void:
	await spawn(OPEN)
	_restore(PlayerController.Stance.CROUCH)
	_assert_stance(PlayerController.Stance.CROUCH, 1.0, "crouch")
	assert_eq(_log, [PlayerController.Stance.CROUCH], "one signal, no stepping through the cycle")
	assert_almost_eq(cam_pivot().y - player.global_position.y, 0.9, 1e-3, "camera pivot at crouch height")


func test_restore_crawl_in_open_space() -> void:
	await spawn(OPEN)
	_restore(PlayerController.Stance.CRAWL)
	_assert_stance(PlayerController.Stance.CRAWL, 0.5, "crawl")
	assert_eq(_log, [PlayerController.Stance.CRAWL], "direct STAND -> CRAWL, one signal")
	assert_almost_eq(cam_pivot().y - player.global_position.y, 0.45, 1e-3, "camera pivot at crawl height")


func test_restore_same_stance_emits_nothing() -> void:
	await spawn(OPEN)
	Core.state.set_value(StateKeys.PLAYER_STANCE, 99)
	_restore(PlayerController.Stance.STAND)
	assert_eq(_log, [], "STAND -> STAND: no signal")
	assert_eq(_saved_stance(), StateKeys.STANCE_STAND, "PLAYER_STANCE still written")
	_restore(PlayerController.Stance.CRAWL)
	_log.clear()
	_restore(PlayerController.Stance.CRAWL)
	assert_eq(_log, [], "CRAWL -> CRAWL: no signal")
	_assert_stance(PlayerController.Stance.CRAWL, 0.5, "crawl kept")


func test_restore_stand_under_crouch_ceiling_becomes_crouch() -> void:
	player.spawn_at(UNDER_CROUCH_CEILING)
	_restore(PlayerController.Stance.STAND)  # same frame as spawn_at, like a load
	_assert_stance(PlayerController.Stance.CROUCH, 1.0, "under 1.3 m")
	assert_eq(_log, [PlayerController.Stance.CROUCH])
	await auto.advance_frames(10)
	assert_eq(player.get_stance(), PlayerController.Stance.CROUCH, "still crouched after physics")
	assert_almost_eq(player.global_position.x, UNDER_CROUCH_CEILING.x, 0.01, "not pushed out of the tunnel")
	assert_true(player.global_position.y < 0.01, "on the floor")


func test_restore_stand_under_crawl_ceiling_becomes_crawl() -> void:
	player.spawn_at(UNDER_CRAWL_CEILING)
	_restore(PlayerController.Stance.STAND)
	_assert_stance(PlayerController.Stance.CRAWL, 0.5, "under 0.75 m")
	assert_eq(_log, [PlayerController.Stance.CRAWL], "straight to CRAWL, one signal")
	await auto.advance_frames(10)
	assert_eq(player.get_stance(), PlayerController.Stance.CRAWL)
	assert_true(player.global_position.y < 0.01, "on the floor")


func test_restore_crouch_under_crawl_ceiling_becomes_crawl() -> void:
	player.spawn_at(UNDER_CRAWL_CEILING)
	_restore(PlayerController.Stance.CROUCH)
	_assert_stance(PlayerController.Stance.CRAWL, 0.5, "crouch does not fit under 0.75 m")
	assert_eq(_log, [PlayerController.Stance.CRAWL])


func test_restore_crouch_under_crouch_ceiling_is_exact() -> void:
	player.spawn_at(UNDER_CROUCH_CEILING)
	_restore(PlayerController.Stance.CROUCH)
	_assert_stance(PlayerController.Stance.CROUCH, 1.0, "crouch fits under 1.3 m")
	assert_eq(_log, [PlayerController.Stance.CROUCH])


func test_invalid_values_mean_stand() -> void:
	await spawn(OPEN)
	_restore(PlayerController.Stance.CRAWL)
	_log.clear()
	_restore(7)
	_assert_stance(PlayerController.Stance.STAND, 1.75, "7 -> STAND")
	assert_eq(_log, [PlayerController.Stance.STAND])
	_restore(PlayerController.Stance.CROUCH)
	_log.clear()
	_restore(-1)
	_assert_stance(PlayerController.Stance.STAND, 1.75, "-1 -> STAND")
	assert_eq(_log, [PlayerController.Stance.STAND])


func test_invalid_value_under_low_ceiling_uses_fit_rule() -> void:
	player.spawn_at(UNDER_CROUCH_CEILING)
	_restore(7)
	_assert_stance(PlayerController.Stance.CROUCH, 1.0, "7 -> STAND -> does not fit -> CROUCH")


func test_open_space_after_tunnel_same_frame() -> void:
	# Crawling in the crawl tunnel, then loaded into the open in the same frame: the probe sees the new position.
	player.spawn_at(UNDER_CRAWL_CEILING)
	_restore(PlayerController.Stance.CRAWL)
	await auto.advance_frames(3)
	_log.clear()
	player.spawn_at(OPEN)
	_restore(PlayerController.Stance.STAND)
	_assert_stance(PlayerController.Stance.STAND, 1.75, "stands in the open right after the teleport")
	assert_eq(_log, [PlayerController.Stance.STAND])
