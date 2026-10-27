## Shared setup for player tests: own test arena (layer-1 boxes) + a player from PlayerFactory, input via
## Core.automation only. Not a test file itself (no _test.gd suffix).
extends TestCase

const Arena := preload("res://modules/player/tests/support/test_arena.gd")
const TPS := 60
const FPS := 30

var auto: Automation
var arena: Node3D
var player: PlayerController


func before_each() -> void:
	auto = automation()
	auto.set_fixed_timestep(TPS, FPS)
	arena = Arena.new()
	arena.with_meshes = false
	add_child(arena)
	player = PlayerFactory.create_player()
	add_child(player)
	await auto.advance_frames(2)


func after_each() -> void:
	for a in GameActions.ALL:
		auto.release_action(a)
	player.queue_free()
	arena.queue_free()
	await auto.advance_frames(2)


## Teleports and lets the player settle on the floor.
func spawn(pos: Vector3, yaw: float = 0.0) -> void:
	player.spawn_at(pos, yaw)
	await auto.advance_frames(5)


## Presses the move actions for a camera-relative input direction (x right, y back), length = deflection.
func press_move(input: Vector2) -> void:
	_set_axis(GameActions.MOVE_RIGHT, GameActions.MOVE_LEFT, input.x)
	_set_axis(GameActions.MOVE_BACK, GameActions.MOVE_FORWARD, input.y)


func release_move() -> void:
	for a in [GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD, GameActions.MOVE_BACK]:
		auto.release_action(a)


func _set_axis(positive: StringName, negative: StringName, value: float) -> void:
	auto.release_action(positive)
	auto.release_action(negative)
	if value > 1e-4:
		auto.press_action(positive, value)
	elif value < -1e-4:
		auto.press_action(negative, -value)


## Horizontal speed (m/s) measured over `frames` process frames, timed by physics ticks.
func measure_speed(frames: int) -> float:
	var p0 := player.global_position
	var t0 := Engine.get_physics_frames()
	await auto.advance_frames(frames)
	var p1 := player.global_position
	var dt := float(Engine.get_physics_frames() - t0) / Engine.physics_ticks_per_second
	return Vector2(p1.x - p0.x, p1.z - p0.z).length() / dt


func tap_stance() -> void:
	await auto.tap_action(GameActions.STANCE_CYCLE, 1)
	await auto.advance_frames(1)


func tap_jump() -> void:
	await auto.tap_action(GameActions.JUMP, 1)


## Distance from p to the nearest layer-1 hit along the ray from -> to (INF if clear).
func ray_clear(from: Vector3, to: Vector3) -> bool:
	var q := PhysicsRayQueryParameters3D.create(from, to, 1)
	return player.get_world_3d().direct_space_state.intersect_ray(q).is_empty()


## Implementation extras (not in the public interface), called dynamically.
func cam_yaw() -> float:
	return player.call("get_camera_yaw")


func cam_pivot() -> Vector3:
	return player.call("get_camera_pivot")
