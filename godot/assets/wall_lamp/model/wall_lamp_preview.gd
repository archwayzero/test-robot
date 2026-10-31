## Review scene for wall_lamp: mounted at y = 2.0 on a plain stone-coloured wall, an unshadowed omni at the emitter as maze will
## add it, Mobile renderer. Switches view every FRAMES_PER_VIEW frames so tools/qa/capture.py --every 8 keeps one frame of each.
extends Node3D

const LAMP := preload("res://assets/wall_lamp/model/wall_lamp.glb")
const MOUNT := Vector3(0, 2.0, 0)
const FRAMES_PER_VIEW := 8
const EYE := 1.6
## name-free views: camera offset from the emitter on the floor plane (x along the wall, z out of it), eye height, look target.
const VIEWS := [
	[Vector3(0.6, EYE, 0.8 + 0.35), Vector3(0, 2.1, 0.2), 70.0],  # 1 m, quarter
	[Vector3(2.4, EYE, 3.2 + 0.35), Vector3(0, 2.1, 0.2), 70.0],  # 4 m, quarter
	[Vector3(0.0, EYE, 4.0), Vector3(0, 2.1, 0.2), 70.0],  # 4 m, square on
	[Vector3(3.3, EYE, 1.0), Vector3(0, 2.1, 0.2), 70.0],  # along the corridor, typical first sight
	[Vector3(0.45, 2.2, 0.85), Vector3(0, 2.1, 0.2), 45.0],  # close-up
	[Vector3(0.9, 2.1, 0.2), Vector3(0, 2.08, 0.2), 45.0],  # close-up, profile
]

var _cam: Camera3D
var _frame := 0


func _ready() -> void:
	var stone := StandardMaterial3D.new()
	stone.albedo_color = Color(0.56, 0.50, 0.42)
	stone.roughness = 0.9
	_box(Vector3(10, 4.15, 0.6), Vector3(0, 2.075, -0.3), stone)
	_box(Vector3(10, 0.2, 8), Vector3(0, -0.1, 3.5), stone)
	var lamp: Node3D = LAMP.instantiate()
	lamp.position = MOUNT
	add_child(lamp)
	var omni := OmniLight3D.new()
	omni.position = MOUNT + lamp.find_child("light_emitter", true, false).position
	omni.light_color = Color(1.0, 0.9, 0.78)
	omni.light_energy = 0.8
	omni.omni_range = 6.0
	add_child(omni)
	var env := _game_environment()  # review under the game's own environment
	if env:
		var world := WorldEnvironment.new()
		world.environment = env
		add_child(world)
	_cam = Camera3D.new()
	add_child(_cam)
	_cam.make_current()
	_view(0)


## The Environment of the first WorldEnvironment in the project's main scene, or null (with a warning) if there is none: the
## preview then renders under Godot's default environment and does not show the game's look.
func _game_environment() -> Environment:
	var path: String = ProjectSettings.get_setting("application/run/main_scene", "")
	var packed := load(path) as PackedScene if not path.is_empty() else null
	if packed == null:
		push_warning("wall_lamp_preview: no main scene to take the environment from (%s)" % path)
		return null
	var main_scene := packed.instantiate()
	var found := main_scene.find_children("*", "WorldEnvironment", true, false)
	var env: Environment = (found[0] as WorldEnvironment).environment if not found.is_empty() else null
	main_scene.free()
	if env == null:
		push_warning("wall_lamp_preview: no WorldEnvironment with an Environment in %s" % path)
	return env


func _process(_delta: float) -> void:
	_frame += 1
	_view(mini(_frame / FRAMES_PER_VIEW, VIEWS.size() - 1))


func _view(i: int) -> void:
	_cam.position = VIEWS[i][0]
	_cam.fov = VIEWS[i][2]
	_cam.look_at(VIEWS[i][1])


func _box(size: Vector3, at: Vector3, mat: Material) -> void:
	var m := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	b.material = mat
	m.mesh = b
	m.position = at
	add_child(m)
