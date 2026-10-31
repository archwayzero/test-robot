## Visual and counter check of the assembled maze (tests only, not shipped), Mobile renderer. Switches view every
## `hold` frames; each view's engine counters go to .captures/t018/<tag>_counters.json (counts, not device performance).
## Env MAZE_PREVIEW="hold=16,tag=x,only=a+b,spec=0.1,energy=0.8,range=5,occ=0" overrides for tuning runs.
extends Node3D

const PITCH := -0.35
const CAM_H := 2.43
const DV: Array[Vector3] = [Vector3(0, 0, -1), Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0)]

var hold := 16
var tag := "run"
var only := PackedStringArray()
var overrides := {}
var layout: MazeLayout
var views: Array[Dictionary] = []
var counters := {}
var _cam: Camera3D
var _world: MazeWorld
var _frame := -1
var _shown := -1


func _ready() -> void:
	for pair in OS.get_environment("MAZE_PREVIEW").split(",", false):
		var kv := pair.split("=")
		match kv[0]:
			"hold":
				hold = int(kv[1])
			"tag":
				tag = kv[1]
			"only":
				only = kv[1].split("+")
			_:
				overrides[kv[0]] = float(kv[1])
	add_child(_game_environment())
	var factory := MazeFactory.create()
	layout = factory.make_layout()
	_world = factory.make_world()
	add_child(_world)
	_world.build(layout)
	_apply_overrides()
	_cam = Camera3D.new()
	_cam.near = 0.05
	add_child(_cam)
	_cam.make_current()
	_make_views()
	if not only.is_empty():
		views = views.filter(func(v: Dictionary) -> bool: return v.name in only)
	_show(0)


## Same values as WorldEnvironment in the game's main.tscn. Copied: maze may not depend on game. Keep them equal.
func _game_environment() -> WorldEnvironment:
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.015, 0.014, 0.02)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.42, 0.4, 0.5)
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 1.1
	e.glow_enabled = true
	e.glow_intensity = 0.6
	e.glow_bloom = 0.05
	e.glow_hdr_threshold = 1.2
	e.fog_enabled = true
	e.fog_mode = Environment.FOG_MODE_DEPTH
	e.fog_light_color = Color(0.03, 0.03, 0.04)
	e.fog_light_energy = 1.0
	e.fog_density = 1.0
	e.fog_sky_affect = 0.0
	e.fog_depth_curve = 1.4
	e.fog_depth_begin = 4.0
	e.fog_depth_end = 26.0
	var w := WorldEnvironment.new()
	w.environment = e
	return w


func _apply_overrides() -> void:
	if overrides.has("occ"):
		get_viewport().use_occlusion_culling = overrides.occ != 0.0
	for omni: OmniLight3D in _world.find_children("Light", "OmniLight3D", true, false):
		omni.light_specular = overrides.get("spec", omni.light_specular)
		omni.light_energy = overrides.get("energy", omni.light_energy)
		omni.omni_range = overrides.get("range", omni.omni_range)


func _process(_delta: float) -> void:
	_frame += 1
	var i := _frame / hold
	if _frame % hold == hold - 1 and _shown >= 0:
		counters[views[_shown].name] = {
			"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
			"objects": Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)}
		var f := FileAccess.open(ProjectSettings.globalize_path("res://../.captures/t018/%s_counters.json" % tag), FileAccess.WRITE)
		if f:
			f.store_string(JSON.stringify({"views": views.map(func(v: Dictionary) -> String: return v.name), "counters": counters}, " "))
			f.close()
	if i < views.size() and i != _shown:
		_show(i)


func _show(i: int) -> void:
	_shown = i
	var v := views[i]
	_cam.position = v.eye
	_cam.fov = v.get("fov", 70.0)
	_cam.look_at(v.look)
	print("T018 view %d %s frame %d" % [i, v.name, _frame])


func _add(view_name: String, eye: Vector3, look: Vector3, fov := 70.0) -> void:
	views.append({"name": view_name, "eye": eye, "look": look, "fov": fov})


func _ahead(eye: Vector3, v: Vector3) -> Vector3:
	return eye + v.normalized() * 4.0 + Vector3(0, tan(PITCH) * 4.0, 0)


## Same eyes as the T017 review, so counts compare: corridor, wall hug, pier, mixed edge, far, lamp at 1-4 m.
func _make_views() -> void:
	var slot := _corridor_lamp()
	var wall_dir: Vector3 = DV[slot.dir]
	var along := Vector3(wall_dir.z, 0, wall_dir.x)
	var c := layout.cell_to_world(slot.cell)
	var e := c + wall_dir * 1.35 + Vector3(0, 2.25, 0)
	var eye := c - along * 4.0 + Vector3(0, CAM_H, 0)
	_add("corridor_centre", eye, _ahead(eye, along))
	var hug := c - along * 4.0 + wall_dir * 1.35 + Vector3(0, CAM_H, 0)
	_add("wall_hug", hug, _ahead(hug, along * 2.0 + wall_dir * 0.2))
	_add("junction", _junction() + Vector3(0, CAM_H, 0), _junction() + Vector3(4.0, 0.9, 0))
	var cc := layout.cell_to_world(Vector2i(1, 7))
	var cw := layout.cell_to_world(Vector2i(9, 7))
	_add("crouch_cell_inside", cc + Vector3(0, 1.0, -1.3), cc + Vector3(0, 0.6, 2.0))
	_add("crawl_cell_inside", cw + Vector3(-1.5, 0.5, 0), cw + Vector3(2.0, 0.35, 0))
	_add("mixed_edge_crouch", cc + Vector3(0, CAM_H, -5.5), cc + Vector3(0, 0.7, -2.0))
	_add("mixed_edge_crawl", cw + Vector3(-5.5, CAM_H, 0.0), cw + Vector3(-2.0, 0.4, 0))
	_add("pier_capital", c + along * 1.2 - wall_dir * 0.6 + Vector3(0, 1.6, 0), c + along * 2.0 + wall_dir * 1.8 + Vector3(0, 2.1, 0), 55.0)
	_add("wall_frontal_lit", c + wall_dir * 1.7 - wall_dir * 3.2 + Vector3(0, 2.0, 0), c + wall_dir * 1.7 + Vector3(0, 2.0, 0), 60.0)
	var seam := c + wall_dir * 1.7 + along * 1.7
	_add("seam_far_16m", seam - along * 16.0 - wall_dir * 1.4 + Vector3(0, CAM_H, 0), seam + Vector3(0, 1.2, 0), 12.0)
	for d: float in [1.0, 2.0, 3.0, 4.0]:
		_add("lamp_%dm" % int(d), e - wall_dir * 0.7 - along * sqrt(d * d - 0.49) + Vector3(0, CAM_H - e.y, 0), e)
	var far := layout.cell_to_world(Vector2i(19, 0)) + Vector3(0, 0, -1.0)
	_add("far_corridor_game", far + Vector3(0, CAM_H, 0), far + Vector3(0, 0.9, 8.0))
	_add("far_corridor_level", far + Vector3(0, 1.6, 0), far + Vector3(0, 1.6, 32.0))
	var long_eye := c - along * 2.2 + wall_dir * 1.4 + Vector3(0, 1.8, 0)
	_add("long_view_wall_face", long_eye, long_eye + along * 8.0 - wall_dir * 8.0)


func _junction() -> Vector3:
	for y in range(2, layout.size().y - 2):
		for x in range(2, layout.size().x - 2):
			var c := Vector2i(x, y)
			var open := 0
			for d in 4:
				open += 0 if layout.has_wall(c, d) else 1
			if open == 3 and layout.clearance(c) == MazeLayout.Clearance.FULL:
				return layout.cell_to_world(c)
	return layout.cell_to_world(layout.start_cell())


## A lamp slot in the middle of the longest straight FULL run that holds one, as in the T017 review.
func _corridor_lamp() -> Dictionary:
	var best: Dictionary = layout.lamp_slots()[0]
	var best_run := -1
	for slot: Dictionary in layout.lamp_slots():
		var v: Vector3 = DV[slot.dir]
		var o := Vector2i(int(v.z), int(v.x))
		var fwd := _run(slot.cell, o)
		var back := _run(slot.cell, -o)
		if fwd >= 2 and back >= 2 and fwd + back > best_run:
			best_run = fwd + back
			best = slot
	return best


func _run(from: Vector2i, o: Vector2i) -> int:
	var d := DV.find(Vector3(o.x, 0, o.y))
	var n := 0
	var c := from
	while not layout.has_wall(c, d) and layout.clearance(c + o) == MazeLayout.Clearance.FULL:
		c += o
		n += 1
	return n
