## Visual check scene for the greybox maze (tests only, not shipped). Builds the GAME_SEED maze with the ceilings
## hidden and a temporary sun; the camera shows an overview from above a corner, then close-ups of the first
## CROUCH and first CRAWL cell seen from an open neighbour.
extends Node3D

const DX := [0, 1, 0, -1]
const DY := [-1, 0, 1, 0]

var _world: MazeWorld
var _camera: Camera3D
var _views: Array = []  # [eye, target]
var _frame := 0


func _ready() -> void:
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.25, 0.3, 0.38)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.5, 0.5, 0.55)
	env.environment.ambient_light_energy = 0.9
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 1.1
	sun.shadow_enabled = false
	add_child(sun)
	_camera = Camera3D.new()
	_camera.fov = 60
	_camera.far = 400
	add_child(_camera)
	_camera.make_current()

	var factory := MazeFactory.create()
	var layout := factory.make_layout()
	_world = factory.make_world()
	add_child(_world)
	_world.build(layout)
	for chunk in _world.get_children():
		var ceiling := chunk.get_node_or_null("Ceiling") as Node3D
		if ceiling:
			ceiling.visible = false

	var span := Vector3(layout.size().x, 0, layout.size().y) * layout.cell_size_m()
	_views.append([Vector3(-0.15 * span.x, 0.75 * span.x, -0.15 * span.z), span * 0.55])
	for cl in [MazeLayout.Clearance.CROUCH, MazeLayout.Clearance.CRAWL]:
		var v := _close_view(layout, cl)
		if not v.is_empty():
			_views.append(v)
	_apply(0)


func _close_view(layout: MazeLayout, cl: MazeLayout.Clearance) -> Array:
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			if layout.clearance(c) != cl:
				continue
			for d in 4:
				if layout.has_wall(c, d):
					continue
				var target := layout.cell_to_world(c) + Vector3(0, 0.6, 0)
				# Eye inside the open neighbour, 1.5 m behind its centre, at standing eye height.
				var back := Vector3(DX[d], 0, DY[d]) * (layout.cell_size_m() + 1.5)
				return [target + back + Vector3(0, 1.0, 0), target]
	return []


func _apply(i: int) -> void:
	var v: Array = _views[i]
	_camera.position = v[0]
	_camera.look_at(v[1], Vector3.UP)


func _process(_delta: float) -> void:
	_frame += 1
	# capture.py takes 60 frames, a shot every 15: overview for the first 30, then each close-up.
	var i := 0
	if _frame >= 30:
		i = mini(1 + (_frame - 30) / 15, _views.size() - 1)
	_apply(i)
