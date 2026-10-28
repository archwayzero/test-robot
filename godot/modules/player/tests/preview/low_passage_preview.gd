## T030 visual check (capture.py): the camera in low passages. Corridors with walls under the test arena's 1.3 m
## (CROUCH) and 0.75 m (CRAWL) ceilings. Frames 0-119: crouch-walking down the CROUCH passage; from frame 120:
## crawling down the CRAWL passage. Presses GameActions directly through Input (works with or without automation).
extends Node3D

const Arena := preload("res://modules/player/tests/support/test_arena.gd")
const SWITCH_FRAME := 120

var _player: PlayerController
var _frame := 0


func _ready() -> void:
	var arena := Arena.new()
	add_child(arena)
	for z in [Arena.CROUCH_TUNNEL_Z, Arena.CRAWL_TUNNEL_Z]:
		for side in [-1.0, 1.0]:
			arena.add_box(Vector3((Arena.TUNNEL_X0 + Arena.TUNNEL_X1) * 0.5, 1.5, z + side * 2.0),
					Vector3(Arena.TUNNEL_X1 - Arena.TUNNEL_X0, 3.0, 0.6), Color(0.6, 0.5, 0.4))
		# A marker at the passage end so "the view ahead" has something to see.
		arena.add_box(Vector3(Arena.TUNNEL_X1 - 0.5, 0.3, z), Vector3(0.4, 0.6, 0.4), Color(0.8, 0.2, 0.2))
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-55.0), deg_to_rad(30.0), 0.0)
	sun.shadow_enabled = true
	add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.2, 0.22, 0.26)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.6, 0.6, 0.65)
	add_child(env)
	_player = PlayerFactory.create_player()
	add_child(_player)
	_enter(Arena.CROUCH_TUNNEL_Z, PlayerController.Stance.CROUCH)


func _enter(z: float, stance: PlayerController.Stance) -> void:
	_player.spawn_at(Vector3(Arena.TUNNEL_X0 + 1.5, 0.0, z), -PI / 2.0)  # facing +X, down the passage
	_player.restore_stance(stance)


func _process(_delta: float) -> void:
	_frame += 1
	if _frame == 2:
		Input.action_press(GameActions.MOVE_FORWARD, 1.0)
	elif _frame == SWITCH_FRAME:
		_enter(Arena.CRAWL_TUNNEL_Z, PlayerController.Stance.CRAWL)
