## T017 (qa): review scene for capture.py: the whole seed maze assembled by crypt_assembly.gd under the game's own
## Environment (taken from the main scene through GameMain.MAIN_SCENE), Mobile renderer. Switches view every HOLD frames;
## `capture.py --every 3` keeps one frame of each. Camera: game height 2.43 m, pitch -0.35 rad, fov 70, unless noted.
## Writes the engine's per-view counters to .captures/t017/<name>_counters.json (counts, not device performance).
extends Node3D

const Assembly := preload("res://tests/assets/crypt_assembly.gd")
const HOLD := 3
const PITCH := -0.35
const CAM_H := 2.43

@export var vertex_color_srgb := true
@export var use_occluders := false
@export var name_tag := "srgb_true"
## Limit of the view list (0 = all). Variant scenes only need the wall/lamp views.
@export var max_views := 0

var layout: MazeLayout
var asm: Assembly
var views: Array[Dictionary] = []
var counters := {}
var _cam: Camera3D
var _frame := 0
var _shown := -1


func _ready() -> void:
	layout = MazeFactory.create().make_layout()
	asm = Assembly.new(layout, self)
	asm.vertex_color_srgb = vertex_color_srgb
	asm.with_occluders = use_occluders
	asm.build()
	get_viewport().use_occlusion_culling = use_occluders
	var env := _game_environment()
	if env:
		var w := WorldEnvironment.new()
		w.environment = env
		add_child(w)
	_cam = Camera3D.new()
	_cam.fov = 70.0
	_cam.near = 0.05
	add_child(_cam)
	_cam.make_current()
	_make_views()
	_show(0)


func _game_environment() -> Environment:
	var scene := load(GameMain.MAIN_SCENE) as PackedScene
	var main := scene.instantiate()
	var found := main.find_children("*", "WorldEnvironment", true, false)
	var env: Environment = (found[0] as WorldEnvironment).environment if not found.is_empty() else null
	main.free()
	return env


func _process(_delta: float) -> void:
	_frame += 1
	var i := _frame / HOLD
	if _frame % HOLD == HOLD - 1 and _shown >= 0:
		counters[views[_shown].name] = {
			"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
			"objects": Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)}
		var f := FileAccess.open(ProjectSettings.globalize_path("res://../.captures/t017/%s_counters.json" % name_tag), FileAccess.WRITE)
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
	print("T017 view %d %s eye %s look %s" % [i, v.name, v.eye, v.look])


func _add(view_name: String, eye: Vector3, look: Vector3, fov := 70.0) -> void:
	if max_views > 0 and views.size() >= max_views:
		return
	views.append({"name": view_name, "eye": eye, "look": look, "fov": fov})


## Target that gives the game's pitch from `eye` along horizontal direction `v`.
func _ahead(eye: Vector3, v: Vector3) -> Vector3:
	return eye + v.normalized() * 4.0 + Vector3(0, tan(PITCH) * 4.0, 0)


func _make_views() -> void:
	var slot: Dictionary = _corridor_lamp()
	var cell: Vector2i = slot.cell
	var wall_dir: Vector3 = Assembly.dir_vector(slot.dir)
	var along := Vector3(wall_dir.z, 0, wall_dir.x)  # corridor direction, parallel to the lamp wall
	var c := layout.cell_to_world(cell)
	var e := c + wall_dir * 1.35 + Vector3(0, 2.25, 0)  # emitter
	# Wall, lamp and top-course views first: the srgb variants stop after these.
	_add("corridor_centre", c - along * 4.0 + Vector3(0, CAM_H, 0), _ahead(c - along * 4.0 + Vector3(0, CAM_H, 0), along))
	var hug := c - along * 4.0 + wall_dir * 1.35 + Vector3(0, CAM_H, 0)
	_add("wall_hug", hug, _ahead(hug, along * 2.0 + wall_dir * 0.2))
	var graze := c - along * 2.2 + wall_dir * 1.4 + Vector3(0, 1.8, 0)
	_add("grazing_lit_wall", graze, c + along * 0.6 + wall_dir * 1.7 + Vector3(0, 1.6, 0), 50.0)
	_add("top_course", c - along * 1.2 + Vector3(0, 1.6, 0), c + wall_dir * 1.7 - along * 1.0 + Vector3(0, 1.85, 0), 45.0)
	_add("lamp_1_4m", e - wall_dir * 1.05 - along * 0.9 + Vector3(0, -0.15, 0), e)
	_add("lamp_0_5m", e - wall_dir * 0.35 - along * 0.35 + Vector3(0, -0.1, 0), e + Vector3(0, -0.05, 0))
	var crouch := Vector2i(1, 7)
	var crawl := Vector2i(9, 7)
	var cc := layout.cell_to_world(crouch)
	var cw := layout.cell_to_world(crawl)
	_add("crouch_cell_inside", cc + Vector3(0, 1.0, -1.3), cc + Vector3(0, 0.6, 2.0))
	_add("crawl_cell_inside", cw + Vector3(-1.5, 0.5, 0), cw + Vector3(2.0, 0.35, 0))
	_add("mixed_edge_crouch_from_full", cc + Vector3(0, CAM_H, -5.5), cc + Vector3(0, 0.7, -2.0))
	_add("mixed_edge_crawl_from_full", cw + Vector3(-5.5, CAM_H, 0.0), cw + Vector3(-2.0, 0.4, 0))
	_add("mixed_edge_oblique", cw + Vector3(-4.2, 1.2, 1.2), cw + Vector3(-1.9, 1.1, -1.0), 50.0)
	_add("crawl_flip_from_room", Vector3(37.3, 0.2, 30.7), Vector3(39.98, 0.946, 28.34), 25.0)
	_add("crawl_flip_from_full", Vector3(34.7, 0.5, 30.7), Vector3(36.04, 1.108, 28.48), 25.0)
	var pier_eye := Vector3(27.3, 2.43, 3.3)
	_add("capital_top_strip", pier_eye, Vector3(23.625, 2.159, 3.758), 25.0)
	_add("arch_vault_up", c - along * 1.5 + Vector3(0, 1.5, 0), c + along * 2.0 + Vector3(0, 3.6, 0))
	_add("pier_capital", c + along * 1.2 - wall_dir * 0.6 + Vector3(0, 1.6, 0), c + along * 2.0 + wall_dir * 1.8 + Vector3(0, 2.1, 0), 55.0)


## A lamp slot in the middle of the longest straight run of FULL cells that holds one; falls back to the first slot.
func _corridor_lamp() -> Dictionary:
	var best: Dictionary = layout.lamp_slots()[0]
	var best_run := -1
	for slot: Dictionary in layout.lamp_slots():
		var wall_dir: Vector3 = Assembly.dir_vector(slot.dir)
		var along := Vector2i(int(wall_dir.z), int(wall_dir.x))
		var d_fwd := _dir_of(along)
		var d_back := _dir_of(-along)
		var run := _run(slot.cell, d_fwd) + _run(slot.cell, d_back)
		if _run(slot.cell, d_fwd) >= 2 and _run(slot.cell, d_back) >= 2 and run > best_run:
			best_run = run
			best = slot
	return best


func _dir_of(o: Vector2i) -> MazeLayout.Dir:
	for d in Assembly.DIRS:
		if Assembly.dir_offset(d) == o:
			return d
	return MazeLayout.Dir.NORTH


func _run(from: Vector2i, d: MazeLayout.Dir) -> int:
	var n := 0
	var c := from
	while not layout.has_wall(c, d) and layout.clearance(c + Assembly.dir_offset(d)) == MazeLayout.Clearance.FULL:
		c += Assembly.dir_offset(d)
		n += 1
	return n
