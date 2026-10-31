## T017 (qa): review scene for capture.py: the whole seed maze assembled by crypt_assembly.gd under the game's own
## Environment (taken from the main scene through GameMain.MAIN_SCENE), Mobile renderer. Switches view every `hold` frames;
## `capture.py --every 2` keeps one frame of each. Camera: game height 2.43 m, pitch -0.35 rad, fov 70, unless noted.
## Writes the engine's per-view counters to .captures/t017/<name>_counters.json (counts, not device performance).
## One scene for every capture: set env T017_PREVIEW="key=value,..." (keys below) before capture.py, for example
## T017_PREVIEW="srgb=0,first=6,max=3,tag=srgb_false_low". Reading the env var is the only outside input.
## only=a+b picks views by name; magenta=1 paints the background magenta, so any pixel through a hole counts.
## nonormal=1 turns the normal maps off and omnispec=0 turns lamp specular off (cause checks); only= keeps its own order.
## nocull=1 draws back faces: the difference from a normal run is exactly the pixels a missing or flipped face changes.
extends Node3D

const Assembly := preload("res://tests/assets/crypt_assembly.gd")
const PITCH := -0.35
const CAM_H := 2.43

@export var vertex_color_srgb := true
@export var use_occluders := false
@export var name_tag := "srgb_true"
## Frames per view. The first view of a run needs 3: the counters read 0 until a frame has been drawn.
@export var hold := 2
## Slice of the view list (max_views 0 = to the end): CPU rendering takes about 6 s per frame, so runs stay short.
@export var first_view := 0
@export var max_views := 0

var only := PackedStringArray()
var magenta := false
var no_cull := false
var no_normal := false
var omni_specular := 1.0
var layout: MazeLayout
var asm: Assembly
var views: Array[Dictionary] = []
var counters := {}
var _cam: Camera3D
var _frame := 0
var _shown := -1


func _ready() -> void:
	_read_env()
	layout = MazeFactory.create().make_layout()
	asm = Assembly.new(layout, self)
	asm.vertex_color_srgb = vertex_color_srgb
	asm.with_occluders = use_occluders
	asm.build()
	if no_cull:
		for m: StandardMaterial3D in asm.all_materials():
			m.cull_mode = BaseMaterial3D.CULL_DISABLED
	for m: StandardMaterial3D in asm.all_materials():
		if no_normal:
			m.normal_enabled = false
	for l in asm.lamps:
		(l.omni as OmniLight3D).light_specular = omni_specular
	get_viewport().use_occlusion_culling = use_occluders
	var env := _game_environment()
	if env:
		print("T017 environment: background mode %d colour %s ambient source %d" % [env.background_mode, env.background_color, env.ambient_light_source])
		if magenta:
			env = env.duplicate() as Environment
			env.background_mode = Environment.BG_COLOR
			env.background_color = Color.MAGENTA
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		var w := WorldEnvironment.new()
		w.environment = env
		add_child(w)
	_cam = Camera3D.new()
	_cam.fov = 70.0
	_cam.near = 0.05
	add_child(_cam)
	_cam.make_current()
	_make_views()
	views = views.slice(first_view, first_view + max_views if max_views > 0 else views.size())
	if not only.is_empty():
		var picked: Array[Dictionary] = []
		for wanted in only:
			picked.append_array(views.filter(func(v: Dictionary) -> bool: return v.name == wanted))
		views = picked
	_show(0)


## srgb and occ are 0/1; hold, first and max are integers; tag names the counters file.
func _read_env() -> void:
	for pair in OS.get_environment("T017_PREVIEW").split(",", false):
		var kv := pair.split("=")
		match kv[0]:
			"srgb":
				vertex_color_srgb = kv[1] == "1"
			"occ":
				use_occluders = kv[1] == "1"
			"tag":
				name_tag = kv[1]
			"hold":
				hold = int(kv[1])
			"first":
				first_view = int(kv[1])
			"max":
				max_views = int(kv[1])
			"only":
				only = kv[1].split("+")
			"magenta":
				magenta = kv[1] == "1"
			"nocull":
				no_cull = kv[1] == "1"
			"nonormal":
				no_normal = kv[1] == "1"
			"omnispec":
				omni_specular = float(kv[1])


func _game_environment() -> Environment:
	var scene := load(GameMain.MAIN_SCENE) as PackedScene
	var main := scene.instantiate()
	var found := main.find_children("*", "WorldEnvironment", true, false)
	var env: Environment = (found[0] as WorldEnvironment).environment if not found.is_empty() else null
	main.free()
	return env


func _process(_delta: float) -> void:
	_frame += 1
	var i := _frame / hold
	if _frame % hold == hold - 1 and _shown >= 0:
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
	# Square-on walls, for the height profile of the courses (tools side: mean luminance per image row).
	var face := c + wall_dir * 1.7
	_add("wall_frontal_lit", face - wall_dir * 3.2 + Vector3(0, 2.0, 0), face + Vector3(0, 2.0, 0), 60.0)
	var dark := _unlit_wall(0)
	_add("wall_frontal_unlit", dark.at - dark.n * 3.2 + Vector3(0, 2.0, 0), dark.at + Vector3(0, 2.0, 0), 60.0)
	# Collinear pier faces and wall faces are coplanar (both 0.3 m from the wall line): look at one edge on, close.
	var seam := c + wall_dir * 1.7 + along * 1.7
	_add("collinear_pier_seam", seam - wall_dir * 0.9 - along * 0.2 + Vector3(0, 1.1, 0), seam + Vector3(0, 1.0, 0), 30.0)
	_add("collinear_pier_seam_shift", seam - wall_dir * 0.9 - along * 0.17 + Vector3(0, 1.12, 0), seam + Vector3(0, 1.0, 0), 30.0)
	_add("collinear_pier_far", seam - wall_dir * 3.0 - along * 1.0 + Vector3(0, 1.6, 0), seam + Vector3(0, 1.0, 0), 30.0)
	for parity: int in [0, 1]:  # seen from the same side, parity selects the wall's face
		var w := _unlit_wall(parity, true)
		_add("wall_face_%d_unlit" % parity, w.at - w.n * 3.2 + Vector3(0, 2.0, 0), w.at + Vector3(0, 2.0, 0), 60.0)
	_add("seam_far_16m_a", seam - along * 16.0 - wall_dir * 1.4 + Vector3(0, CAM_H, 0), seam + Vector3(0, 1.2, 0), 12.0)
	_add("seam_far_16m_b", seam - along * 16.03 - wall_dir * 1.4 + Vector3(0, CAM_H, 0), seam + Vector3(0, 1.2, 0), 12.0)
	# Reachable cameras over the open capital top: the arm reaches 1.575 + 2.5 sin(1.2) = 3.9 m at the lowest orbit pitch.
	var free := _free_pier()
	var top := free + Vector3(0.3, 2.2, 0.3)
	_add("pier_top_orbit_high", free + Vector3(1.2, 3.3, 1.2), top)
	_add("pier_top_orbit_mid", free + Vector3(1.0, 2.8, 0.8), top)
	_add("pier_top_game_height", free + Vector3(1.3, 2.43, 0.6), top)
	_add("pier_top_close", free + Vector3(0.75, 2.5, 0.65), top, 40.0)
	_add("control_void_above_the_maze", Vector3(38, 6, 30), Vector3(38, 20, 31))  # must be magenta: proves the hole count works
	# The low cell's flips at the game's field of view, from the eye of the fan rays that hit them.
	_add("crawl_flip_game_fov_room", Vector3(37.3, 0.45, 30.7), Vector3(39.98, 0.946, 28.34))
	_add("crawl_flip_game_fov_full", Vector3(34.7, 0.8, 30.7), Vector3(36.04, 1.108, 28.48))


## World position of a corner with arches on all four sides (capital ledge on every side); the first found.
func _free_pier() -> Vector3:
	for y in range(1, layout.size().y):
		for x in range(1, layout.size().x):
			var c := Vector2i(x, y)  # cell whose north-west corner this is
			var nw := c - Vector2i(1, 1)
			if not (layout.has_wall(c, MazeLayout.Dir.NORTH) or layout.has_wall(c, MazeLayout.Dir.WEST)
					or layout.has_wall(nw, MazeLayout.Dir.SOUTH) or layout.has_wall(nw, MazeLayout.Dir.EAST)):
				return Vector3(x * layout.cell_size_m(), 0, y * layout.cell_size_m())
	return Vector3(4, 0, 4)


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


## The wall of world parity `parity` farthest from any lamp: {at (world point on the wall face at floor level), n (from the cell to the wall)}.
func _unlit_wall(parity: int, north_only := false) -> Dictionary:
	var best := {"at": Vector3.ZERO, "n": Vector3.FORWARD}
	var best_d := -1.0
	for y in layout.size().y:
		for x in layout.size().x:
			var cell := Vector2i(x, y)
			if layout.clearance(cell) != MazeLayout.Clearance.FULL:
				continue
			for d in Assembly.DIRS:
				if not layout.has_wall(cell, d) or (north_only and d != MazeLayout.Dir.NORTH):
					continue
				var along_x := d == MazeLayout.Dir.NORTH or d == MazeLayout.Dir.SOUTH
				if posmod(x if along_x else y, 2) != parity:
					continue
				var n := Assembly.dir_vector(d)
				var at := layout.cell_to_world(cell) + n * 1.7
				var nearest := INF
				for l in asm.lamps:
					nearest = minf(nearest, (l.omni as OmniLight3D).position.distance_to(at))
				if nearest > best_d:
					best_d = nearest
					best = {"at": at, "n": n}
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
