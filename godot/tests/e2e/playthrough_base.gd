## Base of the scripted gameplay-video playthroughs (TEST_PLAN.md "Gameplay videos"). Owner: qa.
##
## Run by tools/qa/record.py, which starts the scene WITHOUT `-- --automation`, so Core.automation is null there.
## The playthroughs therefore drive the game the way a player does: Input.action_press/action_release on the
## GameActions (as touch_controls does) and Input.parse_input_event for touches (minimap taps, camera orbit drags).
## They read the game only through GameMain's public accessors and the modules' public APIs.
##
## Not a test run: saves go to user:// (the sandbox user's Godot data dir). Slot 0 is deleted before the main scene
## is loaded so every recording starts from a fresh game.
##
## A caption (step name + video time mm:ss) is drawn at the top centre, and every step is appended to
## .captures/t010/<scene>_timeline.txt, so the report can list exact moments.
extends Node

const FPS := 30.0
const ORBIT_FINGER := 7
## Right half, away from the buttons (bottom-right) and the minimap (top-left): camera orbit area.
const ORBIT_POS := Vector2(900, 160)
const ORBIT_SENSITIVITY := 0.006  # rad per px (player module constant, used only to size the drags)
const MAX_TURN_PER_FRAME := 0.10
const MOVE_ACTIONS: Array[StringName] = [GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
		GameActions.MOVE_BACK]
const DIRS: Array[MazeLayout.Dir] = [MazeLayout.Dir.NORTH, MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH,
		MazeLayout.Dir.WEST]

var main: GameMain
var _caption: Label
var _start_frame := 0
var _timeline := PackedStringArray()
var _orbit_pos := ORBIT_POS
var _orbit_down := false
var steer_camera := true


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS  # keep scripting while the large map pauses the tree
	_start_frame = Engine.get_process_frames()
	if Core.saves.has_save(AutoSave.SAVE_SLOT):
		Core.saves.delete_save(AutoSave.SAVE_SLOT)
	var layer := CanvasLayer.new()
	layer.layer = 100
	add_child(layer)
	_caption = Label.new()
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	_caption.offset_top = 8.0
	_caption.offset_bottom = 38.0
	_caption.add_theme_font_size_override("font_size", 20)
	_caption.add_theme_color_override("font_outline_color", Color.BLACK)
	_caption.add_theme_constant_override("outline_size", 6)
	_caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_caption)
	main = (load(GameMain.MAIN_SCENE) as PackedScene).instantiate() as GameMain
	add_child(main)
	move_child(layer, -1)
	while not main.is_ready_to_play():
		await get_tree().process_frame
	step("start")
	await play()
	step("end")
	_write_timeline()


## Overridden by each playthrough.
func play() -> void:
	pass


# --- timeline -------------------------------------------------------------------------------------------

func video_time() -> String:
	var t := float(Engine.get_process_frames() - _start_frame) / FPS
	return "%02d:%04.1f" % [int(t / 60.0), fmod(t, 60.0)]


func step(text: String) -> void:
	_caption.text = "%s  %s" % [video_time(), text]
	_timeline.append("%s %s" % [video_time(), text])
	print("[playthrough] ", _timeline[-1])
	_write_timeline()


func _write_timeline() -> void:
	var dir := ProjectSettings.globalize_path("res://").path_join("../.captures/t010").simplify_path()
	DirAccess.make_dir_recursive_absolute(dir)
	var name_ := scene_file_path.get_file().get_basename()
	var f := FileAccess.open(dir.path_join(name_ + "_timeline.txt"), FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(_timeline) + "\n")


# --- game access ----------------------------------------------------------------------------------------

func player() -> PlayerController:
	return main.get_player()


func layout() -> MazeLayout:
	return main.get_maze_world().get_layout()


func player_cell() -> Vector2i:
	return layout().world_to_cell(player().global_position)


func wait(frames: int) -> void:
	var target := Engine.get_process_frames() + frames
	while Engine.get_process_frames() < target:
		await get_tree().process_frame


func wait_s(seconds: float) -> void:
	await wait(int(seconds * FPS))


static func dir_offset(d: MazeLayout.Dir) -> Vector2i:
	match d:
		MazeLayout.Dir.NORTH:
			return Vector2i(0, -1)
		MazeLayout.Dir.EAST:
			return Vector2i(1, 0)
		MazeLayout.Dir.SOUTH:
			return Vector2i(0, 1)
	return Vector2i(-1, 0)


func open_neighbours(cell: Vector2i, full_only := true) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for d in DIRS:
		var n := cell + dir_offset(d)
		if not layout().has_wall(cell, d) and layout().in_bounds(n) \
				and (not full_only or layout().clearance(n) == MazeLayout.Clearance.FULL):
			out.append(n)
	return out


## BFS from `from`: {cell: [dist, parent]} over FULL cells (plus `allow` cells).
func bfs(from: Vector2i, allow: Array[Vector2i] = []) -> Dictionary:
	var seen := {from: [0, from]}
	var queue: Array[Vector2i] = [from]
	while not queue.is_empty():
		var c: Vector2i = queue.pop_front()
		for n in open_neighbours(c, false):
			if seen.has(n):
				continue
			if layout().clearance(n) != MazeLayout.Clearance.FULL and not (n in allow):
				continue
			seen[n] = [int(seen[c][0]) + 1, c]
			queue.append(n)
	return seen


static func path_to(tree: Dictionary, target: Vector2i) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	var c := target
	while true:
		path.push_front(c)
		var parent: Vector2i = tree[c][1]
		if parent == c:
			break
		c = parent
	return path


# --- input (as a player would) --------------------------------------------------------------------------

func camera_yaw() -> float:
	var fwd := -player().get_camera().global_basis.z
	return atan2(-fwd.x, -fwd.z)


func hold_move(world_dir: Vector3, strength: float) -> void:
	var local := Vector3(world_dir.x, 0.0, world_dir.z).normalized().rotated(Vector3.UP, -camera_yaw()) * strength
	_axis(GameActions.MOVE_RIGHT, GameActions.MOVE_LEFT, local.x)
	_axis(GameActions.MOVE_BACK, GameActions.MOVE_FORWARD, local.z)


func _axis(positive: StringName, negative: StringName, value: float) -> void:
	if value > 0.001:
		Input.action_press(positive, value)
		Input.action_release(negative)
	elif value < -0.001:
		Input.action_press(negative, -value)
		Input.action_release(positive)
	else:
		Input.action_release(positive)
		Input.action_release(negative)


func release_move() -> void:
	for a in MOVE_ACTIONS:
		Input.action_release(a)


func tap(action: StringName, hold_frames := 3) -> void:
	Input.action_press(action)
	await wait(hold_frames)
	Input.action_release(action)
	await wait(2)


## Viewport pixels -> window pixels. Injected events are in window coordinates and the canvas_items stretch scales
## them to the 1280x590 viewport; in a real 1280x590 window (record.py) this is 1:1.
func to_window(v: Vector2) -> Vector2:
	var visible := get_viewport().get_visible_rect().size
	var window := Vector2(get_tree().root.size)
	if visible.x <= 0.0 or window.x <= 0.0:
		return v
	return v * (window.x / visible.x)


func touch(pos: Vector2, pressed: bool, index := 0) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = index
	ev.position = to_window(pos)
	ev.pressed = pressed
	Input.parse_input_event(ev)


func tap_screen(pos: Vector2, index := 0) -> void:
	touch(pos, true, index)
	await wait(2)
	touch(pos, false, index)
	await wait(2)


## Turns the camera toward world yaw `yaw` by at most MAX_TURN_PER_FRAME, with an orbit drag on the right half
## (the same input a player's thumb gives).
func turn_camera_toward(yaw: float) -> void:
	var delta := wrapf(yaw - camera_yaw(), -PI, PI)
	if absf(delta) < 0.01:
		return
	delta = clampf(delta, -MAX_TURN_PER_FRAME, MAX_TURN_PER_FRAME)
	if not _orbit_down:
		_orbit_pos = ORBIT_POS
		touch(_orbit_pos, true, ORBIT_FINGER)
		_orbit_down = true
	var rel := Vector2(-delta / ORBIT_SENSITIVITY, 0.0)
	var ev := InputEventScreenDrag.new()
	ev.index = ORBIT_FINGER
	ev.position = to_window(_orbit_pos + rel)
	ev.relative = to_window(rel)
	ev.screen_relative = to_window(rel)
	Input.parse_input_event(ev)
	# Keep the virtual finger near ORBIT_POS: lift and put it down again when it drifts too far.
	_orbit_pos += rel
	if absf(_orbit_pos.x - ORBIT_POS.x) > 200.0:
		release_orbit()


func release_orbit() -> void:
	if _orbit_down:
		touch(_orbit_pos, false, ORBIT_FINGER)
		_orbit_down = false


func turn_camera_to(yaw: float, max_frames := 40) -> void:
	for i in max_frames:
		if absf(wrapf(yaw - camera_yaw(), -PI, PI)) < 0.01:
			break
		turn_camera_toward(yaw)
		await wait(1)
	release_orbit()


static func yaw_of(dir: Vector3) -> float:
	return atan2(-dir.x, -dir.z)


func walk_to(target: Vector3, strength := 0.5, max_frames := 900, tolerance := 0.15) -> bool:
	for i in max_frames:
		var diff := Vector2(target.x - player().global_position.x, target.z - player().global_position.z)
		if diff.length() < tolerance:
			return true
		var dir := Vector3(diff.x, 0.0, diff.y)
		if steer_camera:
			turn_camera_toward(yaw_of(dir))
		hold_move(dir, strength)
		await wait(1)
	return false


## Walks centre to centre along `cells`; keeps moving through corners (no stop between cells).
func walk_path(cells: Array[Vector2i], strength := 0.5, tolerance := 0.25) -> bool:
	for c in cells:
		if not await walk_to(layout().cell_to_world(c), strength, 900, tolerance):
			release_move()
			release_orbit()
			step("stuck before %s" % c)
			return false
	release_move()
	release_orbit()
	return true
