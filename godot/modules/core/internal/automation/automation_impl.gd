## Automation implementation (test runs only; loaded by path from core_installer.gd, excluded from release exports).
##
## Fixed timestep: Godot computes the process delta from the wall clock, and no script API can change that
## (Engine.time_scale scales physics too, Engine.max_fps only paces the loop). The only engine mechanism that gives
## an exact, wall-clock independent delta is the engine argument `--fixed-fps <fps>` (must come before `--`).
## set_fixed_timestep() therefore:
##   - sets Engine.physics_ticks_per_second, time_scale = 1, enough max_physics_steps_per_frame;
##   - if the engine was started with `--fixed-fps <fps>` (detected from the engine arguments, see engine_fixed_fps()), that is it: every
##     process frame advances exactly 1/fps and physics_ticks_per_second/fps physics steps, as fast as the CPU allows;
##   - otherwise it falls back to Engine.max_fps = fps (approximate, wall-clock paced) and warns once.
## is_fixed_timestep_exact() reports which mode is active.
##
## Input: events go through Input.parse_input_event() and are flushed immediately (Input.flush_buffered_events()),
## so Input.is_action_pressed()/get_vector() and Controls see them in the same frame.
## Headless runs: the headless display server reports a 64x64 root window; the root viewport is resized to the
## project's viewport size so pixel positions (touch, drag) and layouts match the PC preview.
extends Automation

const _CHANGE_SCENE_TIMEOUT_FRAMES := 600

var _core: CoreAPI
var _start_frame: int
var _seed := 0
var _fixed_fps := 0
var _exact := false
var _touch_positions: Dictionary = {}


func _init(core: CoreAPI) -> void:
	_core = core
	_start_frame = Engine.get_process_frames()
	if DisplayServer.get_name() == "headless":
		_fit_headless_root.call_deferred()


# --- Determinism ----------------------------------------------------------------------------------------

func set_seed(seed_value: int) -> void:
	_seed = seed_value
	_core.rng.seed = seed_value
	seed(seed_value)


func set_fixed_timestep(physics_ticks_per_second: int, frames_per_second: int) -> void:
	if physics_ticks_per_second <= 0 or frames_per_second <= 0:
		push_error("Automation.set_fixed_timestep: arguments must be > 0")
		return
	_fixed_fps = frames_per_second
	Engine.time_scale = 1.0
	Engine.physics_ticks_per_second = physics_ticks_per_second
	var steps := ceili(float(physics_ticks_per_second) / frames_per_second) + 1
	Engine.max_physics_steps_per_frame = maxi(Engine.max_physics_steps_per_frame, steps)
	_exact = is_engine_step_exact(frames_per_second)
	if _exact:
		Engine.max_fps = 0
	else:
		Engine.max_fps = frames_per_second
		push_warning(("Automation: process delta is wall-clock based (approximate fixed timestep). Start Godot with "
				+ "`--fixed-fps %d` (before `--`) for an exact 1/%d s step.") % [frames_per_second, frames_per_second])


## True if the last set_fixed_timestep() got an exact engine step (engine started with matching --fixed-fps).
func is_fixed_timestep_exact() -> bool:
	return _exact


## True if the engine was started with `--fixed-fps <fps>` (engine argument, before `--`), which makes every
## process frame advance exactly 1/fps. Judged from the command line, not from a measured delta: the first few
## frames after startup can differ from 1/fps even in fixed-fps mode.
static func is_engine_step_exact(fps: int) -> bool:
	return engine_fixed_fps() == fps and fps > 0


## The value of the engine argument `--fixed-fps`, or 0 if absent/invalid.
## Godot removes the engine arguments it consumes (--fixed-fps, --headless, --path, ...) from OS.get_cmdline_args(),
## so on Linux the full process command line is read from /proc/self/cmdline (only arguments before `--`, i.e. engine
## arguments, count). Where neither source has it (e.g. macOS without /proc), this returns 0 (approximate mode).
static func engine_fixed_fps() -> int:
	var value := _fixed_fps_in(OS.get_cmdline_args())
	if value == 0:
		value = _fixed_fps_in(_proc_engine_args())
	return value


static func _fixed_fps_in(args: PackedStringArray) -> int:
	for i in args.size():
		var a := args[i]
		if a == "--fixed-fps" and i + 1 < args.size() and args[i + 1].is_valid_int():
			return maxi(args[i + 1].to_int(), 0)
		if a.begins_with("--fixed-fps="):
			var v := a.trim_prefix("--fixed-fps=")
			return maxi(v.to_int(), 0) if v.is_valid_int() else 0
	return 0


## Engine arguments of this process from /proc/self/cmdline (NUL-separated), stopping at `--`. Empty if unavailable.
static func _proc_engine_args() -> PackedStringArray:
	var out := PackedStringArray()
	if OS.get_name() != "Linux" or not FileAccess.file_exists("/proc/self/cmdline"):
		return out
	var f := FileAccess.open("/proc/self/cmdline", FileAccess.READ)
	if f == null:
		return out
	var raw := f.get_buffer(1 << 20)  # procfs reports length 0, so read up to a bound instead of get_length()
	f.close()
	var start := 0
	for i in raw.size() + 1:
		if i == raw.size() or raw[i] == 0:
			if i > start:
				var arg := raw.slice(start, i).get_string_from_utf8()
				if arg == "--" or arg == "++":
					break
				out.append(arg)
			start = i + 1
	return out


func get_frame() -> int:
	return Engine.get_process_frames() - _start_frame


func advance_frames(frames: int) -> void:
	var target := Engine.get_process_frames() + maxi(frames, 0)
	while Engine.get_process_frames() < target:
		await _tree().process_frame


func wait_until(predicate: Callable, timeout_frames: int) -> bool:
	if predicate.call():
		return true
	var deadline := Engine.get_process_frames() + maxi(timeout_frames, 0)
	while Engine.get_process_frames() < deadline:
		await advance_frames(1)
		if predicate.call():
			return true
	return false


# --- Input injection ------------------------------------------------------------------------------------

func press_action(action: StringName, strength: float = 1.0) -> void:
	if not InputMap.has_action(action):
		push_error("Automation.press_action: unknown action '%s'" % action)
		return
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = true
	ev.strength = clampf(strength, 0.0, 1.0)
	inject_event(ev)


func release_action(action: StringName) -> void:
	if not InputMap.has_action(action):
		push_error("Automation.release_action: unknown action '%s'" % action)
		return
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = false
	ev.strength = 0.0
	inject_event(ev)


func tap_action(action: StringName, frames: int = 1) -> void:
	press_action(action)
	await advance_frames(maxi(frames, 1))
	release_action(action)


func touch(position: Vector2, pressed: bool, index: int = 0) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = index
	ev.position = position
	ev.pressed = pressed
	if pressed:
		_touch_positions[index] = position
	else:
		_touch_positions.erase(index)
	inject_event(ev)


func drag(from: Vector2, to: Vector2, frames: int, index: int = 0) -> void:
	touch(from, true, index)
	var steps := maxi(frames, 1)
	var last := from
	var dt := 1.0 / (_fixed_fps if _fixed_fps > 0 else 60)
	for i in range(1, steps + 1):
		await advance_frames(1)
		var pos := from.lerp(to, float(i) / steps)
		var ev := InputEventScreenDrag.new()
		ev.index = index
		ev.position = pos
		ev.relative = pos - last
		ev.screen_relative = pos - last
		ev.velocity = (pos - last) / dt
		ev.screen_velocity = ev.velocity
		last = pos
		_touch_positions[index] = pos
		inject_event(ev)
	await advance_frames(1)
	touch(to, false, index)


func inject_event(event: InputEvent) -> void:
	if event == null:
		return
	Input.parse_input_event(event)
	Input.flush_buffered_events()


# --- Observation and control ----------------------------------------------------------------------------

func snapshot() -> Dictionary:
	var snap: Dictionary = _core.state.snapshot() if _core.state != null else {}
	snap["frame"] = get_frame()
	snap["seed"] = _seed
	var scene := _tree().current_scene
	snap["scene"] = scene.scene_file_path if scene != null else ""
	return snap


func load_scene(path: String) -> void:
	var tree := _tree()
	var old := tree.current_scene
	var old_id := old.get_instance_id() if old != null else 0
	var err := tree.change_scene_to_file(path)
	if err != OK:
		push_error("Automation.load_scene: cannot change to '%s' (%s)" % [path, error_string(err)])
		return
	var deadline := Engine.get_process_frames() + _CHANGE_SCENE_TIMEOUT_FRAMES
	while Engine.get_process_frames() < deadline:
		var cur := tree.current_scene
		if cur != null and cur.get_instance_id() != old_id and cur.is_node_ready():
			return
		await tree.process_frame
	push_error("Automation.load_scene: '%s' not ready after %d frames" % [path, _CHANGE_SCENE_TIMEOUT_FRAMES])


func quit(exit_code: int = 0) -> void:
	_tree().quit(exit_code)


# --- internal -------------------------------------------------------------------------------------------

func _tree() -> SceneTree:
	return _core.get_tree() if _core.is_inside_tree() else Engine.get_main_loop() as SceneTree


func _fit_headless_root() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return
	var size := Vector2i(
		ProjectSettings.get_setting("display/window/size/viewport_width", 1152),
		ProjectSettings.get_setting("display/window/size/viewport_height", 648))
	if tree.root.size != size:
		tree.root.size = size
