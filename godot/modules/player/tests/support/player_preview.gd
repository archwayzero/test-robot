## Visual check scene (capture.py): test arena + player + temporary light, short scripted path.
## Runs without Core.automation (plain capture run), so it presses the GameActions directly through Input.
## Path: run toward the 1.3 m ceiling, crouch at frame 20, walk in under it.
extends Node3D

const Arena := preload("res://modules/player/tests/support/test_arena.gd")

var _player: PlayerController
var _frame := 0


func _ready() -> void:
	var arena := Arena.new()
	add_child(arena)
	# A few walls along the approach.
	for side in [-1.0, 1.0]:
		arena.add_box(Vector3(8.0, 1.5, side * 2.3), Vector3(8.0, 3.0, 0.6))
	arena.add_box(Vector3(6.0, 1.5, -5.0), Vector3(0.6, 3.0, 4.0))
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-55.0), deg_to_rad(30.0), 0.0)
	sun.shadow_enabled = true
	add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.2, 0.22, 0.26)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.5, 0.5, 0.55)
	add_child(env)
	_player = PlayerFactory.create_player()
	add_child(_player)
	_player.spawn_at(Vector3(8.5, 0.0, 0.0), -PI / 2.0)


func _process(_delta: float) -> void:
	_frame += 1
	if _frame == 2:
		Input.action_press(GameActions.MOVE_FORWARD, 1.0)
	elif _frame == 20:
		Input.action_press(GameActions.STANCE_CYCLE)
	elif _frame == 22:
		Input.action_release(GameActions.STANCE_CYCLE)
