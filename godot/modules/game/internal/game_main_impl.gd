## Composition root of the game (root script of internal/main.tscn). Builds every module through its public
## factory in the boot order documented in res://modules/game/public/game_main.gd and owns the game phases.
## No gameplay logic lives here.
extends GameMain

## Boot step names, appended to boot_log in order (tests check the order).
const STEP_LOADING := &"loading"
const STEP_MAZE_BUILT := &"maze_built"
const STEP_EXPLORATION_SETUP := &"exploration_setup"
const STEP_AUTOSAVE_SETUP := &"autosave_setup"
const STEP_AUTOSAVE_RESTORE := &"autosave_restore"
const STEP_PLAYER_SPAWNED := &"player_spawned"
## Logged only when restore_stance() was called (saved position used and a valid saved stance value).
const STEP_STANCE_RESTORED := &"stance_restored"
const STEP_TOUCH_CONTROLS := &"touch_controls"
const STEP_MINIMAP := &"minimap"
const STEP_PLAYING := &"playing"

## PLATFORM.md target frame rate on the device.
const IOS_MAX_FPS := 30

## Sane band for a saved player height (crypt-kit: floor at y=0, walls/vault top at 3.9 m).
const SAVED_Y_MIN := -1.0
const SAVED_Y_MAX := 4.0

## Boot steps in the order they ran (read-only use by tests).
var boot_log: Array[StringName] = []

var _layout: MazeLayout
var _maze_world: MazeWorld
var _exploration: Exploration
var _auto_save: AutoSave
var _player: PlayerController
var _hud_layer: CanvasLayer
var _hud: Control
var _touch_controls: TouchControls
var _minimap: Minimap
var _ready_to_play := false
var _spawned_from_save := false
## True while the app is in the background / unfocused (DECISIONS.md D12: paused then).
var _backgrounded := false

## Test seam: when valid, returns {"safe_area": Rect2i, "screen_size": Vector2i} instead of the DisplayServer
## values, and is used on every platform (desktop included).
var _safe_area_source: Callable
## Test seam: when valid, returns a bool replacing OS.has_feature("mobile") for the focus-loss pause (D12).
var _mobile_source: Callable
var _insets := {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}


func _ready() -> void:
	if OS.get_name() == "iOS":
		Engine.max_fps = IOS_MAX_FPS
	_boot()


func _exit_tree() -> void:
	# Never leave the tree paused or the phase at map_open behind us (Core is an autoload and outlives this scene),
	# e.g. scene freed while the large map was open or while backgrounded.
	var map_open := _minimap != null and _minimap.is_large_map_open()
	if map_open or _backgrounded:
		_set_paused(false)
	if map_open:
		Core.state.set_phase(StateKeys.PHASE_PLAYING)
	_backgrounded = false


## DECISIONS.md D12: pause while the app is backgrounded. Notifications reach every node regardless of pause, so
## AutoSave's own save on NOTIFICATION_APPLICATION_PAUSED still runs (whatever the order).
## APPLICATION_PAUSED/RESUMED act on every platform; FOCUS_OUT/FOCUS_IN only on mobile, so the desktop preview
## (and QA recordings in a window that loses focus) keeps running.
func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_PAUSED:
			_on_backgrounded()
		NOTIFICATION_APPLICATION_RESUMED:
			_on_foregrounded()
		NOTIFICATION_APPLICATION_FOCUS_OUT:
			if _is_mobile():
				_on_backgrounded()
		NOTIFICATION_APPLICATION_FOCUS_IN:
			if _is_mobile():
				_on_foregrounded()


func _is_mobile() -> bool:
	if _mobile_source.is_valid():
		return bool(_mobile_source.call())
	return OS.has_feature("mobile")


## Test seam: replaces OS.has_feature("mobile") for the focus-loss pause. `source` returns a bool; pass an
## invalid Callable to go back to the platform check.
func set_mobile_source(source: Callable) -> void:
	_mobile_source = source


func _on_backgrounded() -> void:
	_backgrounded = true
	_set_paused(true)


func _on_foregrounded() -> void:
	_backgrounded = false
	# Stay paused while the large map is open (or during boot: _boot() unpauses when it reaches playing).
	if _ready_to_play and not (_minimap != null and _minimap.is_large_map_open()):
		_set_paused(false)


## True while paused because the app is in the background.
func is_backgrounded() -> bool:
	return _backgrounded


func _boot() -> void:
	# 1. Loading phase, layout and world (build() writes MAZE_SEED, so it must precede Exploration.setup()).
	Core.state.set_phase(StateKeys.PHASE_LOADING)
	_log(STEP_LOADING)
	var maze_factory := MazeFactory.create()
	_layout = maze_factory.make_layout(MazeFactory.GAME_SEED, MazeFactory.GAME_SIZE)
	_maze_world = maze_factory.make_world()
	_maze_world.name = "MazeWorld"
	add_child(_maze_world)
	_maze_world.build(_layout)
	if not _maze_world.is_built():
		await _maze_world.built
	_log(STEP_MAZE_BUILT)

	# 2. Exploration, then autosave (setup before restore: restore compares cloud vs local via the backend).
	_exploration = ExplorationFactory.create()
	_exploration.name = "Exploration"
	add_child(_exploration)
	_exploration.setup(_layout)
	_log(STEP_EXPLORATION_SETUP)
	var cloud_factory := CloudSaveFactory.create()
	_auto_save = cloud_factory.make_auto_save()
	_auto_save.name = "AutoSave"
	add_child(_auto_save)
	_auto_save.setup(cloud_factory.make_platform_backend())
	_log(STEP_AUTOSAVE_SETUP)
	_auto_save.restore()
	_log(STEP_AUTOSAVE_RESTORE)

	# 3. Player at the saved position, or at the start cell, then the saved stance. Read the saved stance first:
	# the player writes PLAYER_STANCE (STAND) itself once it enters the tree.
	var saved_stance: Variant = Core.state.get_value(StateKeys.PLAYER_STANCE)
	_player = PlayerFactory.create_player()
	_player.name = "Player"
	add_child(_player)
	_spawn_player()
	_log(STEP_PLAYER_SPAWNED)
	if _spawned_from_save:
		_restore_saved_stance(saved_stance)

	# 4. HUD inside the safe area: touch controls first, minimap above them (drawn later, gets input first).
	_build_hud()

	# 5. Playing (stays paused if the app went to the background during boot).
	_set_paused(_backgrounded)
	Core.state.set_phase(StateKeys.PHASE_PLAYING)
	_ready_to_play = true
	_log(STEP_PLAYING)
	ready_to_play.emit()


func _spawn_player() -> void:
	var spawn_position := _layout.cell_to_world(_layout.start_cell())
	var spawn_yaw := _open_yaw(_layout.start_cell())
	_spawned_from_save = false
	var saved_position: Variant = Core.state.get_value(StateKeys.PLAYER_POSITION)
	var saved_seed: Variant = Core.state.get_value(StateKeys.MAZE_SEED)
	var same_maze: bool = saved_seed is int and saved_seed == _layout.get_seed()
	if same_maze and _valid_saved_position(saved_position):
		spawn_position = saved_position
		var saved_yaw: Variant = Core.state.get_value(StateKeys.PLAYER_YAW)
		if (saved_yaw is float or saved_yaw is int) and is_finite(float(saved_yaw)):
			spawn_yaw = float(saved_yaw)
		_spawned_from_save = true
	_player.spawn_at(spawn_position, spawn_yaw)


## Applies `saved` (StateKeys.PLAYER_STANCE as restored from the save, read before the player entered the tree);
## only after a spawn at a saved position, with the player in the tree.
## Accepts an int, or a float with an integral value (JSON-style saves); anything else leaves the default STAND.
## Out-of-range ints are passed on: restore_stance() treats them as STAND.
func _restore_saved_stance(saved: Variant) -> void:
	var stance: int
	if saved is int:
		stance = saved
	elif saved is float and is_finite(saved) and float(saved) == floorf(saved) and absf(saved) < 1.0e9:
		stance = int(saved)
	else:
		return
	_player.restore_stance(stance as PlayerController.Stance)
	_log(STEP_STANCE_RESTORED)


## A saved position is usable only if it is a finite Vector3 at a sane height inside the maze bounds.
func _valid_saved_position(value: Variant) -> bool:
	if not value is Vector3:
		return false
	var pos: Vector3 = value
	if not pos.is_finite() or pos.y <= SAVED_Y_MIN or pos.y >= SAVED_Y_MAX:
		return false
	return _layout.in_bounds(_layout.world_to_cell(pos))


## Yaw (Godot convention: 0 faces -Z, +PI/2 faces -X) toward the first open edge of `cell`, so a new game does
## not start facing a wall.
func _open_yaw(cell: Vector2i) -> float:
	var yaws := {
		MazeLayout.Dir.NORTH: 0.0, MazeLayout.Dir.WEST: PI / 2.0,
		MazeLayout.Dir.SOUTH: PI, MazeLayout.Dir.EAST: -PI / 2.0,
	}
	for dir: MazeLayout.Dir in yaws:
		if not _layout.has_wall(cell, dir):
			return yaws[dir]
	return 0.0


func _build_hud() -> void:
	_hud_layer = CanvasLayer.new()
	_hud_layer.name = "HUDLayer"
	add_child(_hud_layer)
	_hud = Control.new()
	_hud.name = "HUD"
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.process_mode = Node.PROCESS_MODE_ALWAYS
	_hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud_layer.add_child(_hud)
	_apply_safe_area()
	get_viewport().size_changed.connect(_apply_safe_area)

	_touch_controls = TouchControlsFactory.create()
	_touch_controls.name = "TouchControls"
	_touch_controls.process_mode = Node.PROCESS_MODE_ALWAYS
	_hud.add_child(_touch_controls)
	_touch_controls.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_touch_controls.set_controls_visible(_touch_wanted())
	_log(STEP_TOUCH_CONTROLS)

	_minimap = MinimapFactory.create()
	_minimap.name = "Minimap"
	_minimap.process_mode = Node.PROCESS_MODE_ALWAYS
	_hud.add_child(_minimap)  # later sibling: drawn above the controls and receives GUI input first
	_minimap.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_minimap.setup(_layout, _exploration)
	_minimap.large_map_toggled.connect(_on_large_map_toggled)
	_log(STEP_MINIMAP)


## Touch controls are shown on touch devices, and on desktop only with mouse-to-touch emulation (PC preview).
func _touch_wanted() -> bool:
	return DisplayServer.is_touchscreen_available() \
			or bool(ProjectSettings.get_setting("input_devices/pointing/emulate_touch_from_mouse", false))


func _on_large_map_toggled(open: bool) -> void:
	if open:
		Core.state.set_phase(StateKeys.PHASE_MAP_OPEN)
		_touch_controls.set_controls_visible(false)
		_set_paused(true)
	else:
		_set_paused(_backgrounded)
		_touch_controls.set_controls_visible(_touch_wanted())
		Core.state.set_phase(StateKeys.PHASE_PLAYING)


func _set_paused(paused: bool) -> void:
	if is_inside_tree():
		get_tree().paused = paused
	Core.state.set_paused(paused)


# --- HUD safe area (DECISIONS.md D17) -------------------------------------------------------------------

## Test seam: replaces the DisplayServer safe-area source. `source` returns
## {"safe_area": Rect2i, "screen_size": Vector2i}; pass an invalid Callable to go back to the platform source.
func set_safe_area_source(source: Callable) -> void:
	_safe_area_source = source
	_apply_safe_area()


## Current HUD insets in viewport pixels: {"left", "top", "right", "bottom"} (floats).
func get_hud_insets() -> Dictionary:
	return _insets.duplicate()


## The full-screen HUD Control that holds the minimap and touch controls.
func get_hud() -> Control:
	return _hud


## True if the player was placed at a saved position rather than the start cell.
func spawned_from_save() -> bool:
	return _spawned_from_save


func _apply_safe_area() -> void:
	_insets = _compute_insets()
	if _hud == null:
		return
	_hud.offset_left = _insets.left
	_hud.offset_top = _insets.top
	_hud.offset_right = -_insets.right
	_hud.offset_bottom = -_insets.bottom


func _compute_insets() -> Dictionary:
	var zero := {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}
	var safe_area: Rect2i
	var screen_size: Vector2i
	if _safe_area_source.is_valid():
		var data: Dictionary = _safe_area_source.call()
		safe_area = data.get("safe_area", Rect2i())
		screen_size = data.get("screen_size", Vector2i())
	elif OS.has_feature("mobile"):
		safe_area = DisplayServer.get_display_safe_area()
		screen_size = DisplayServer.screen_get_size()
	else:
		# Desktop: the window is not the screen, and the "safe area" there is just the taskbar-free rect.
		return zero
	if screen_size.x <= 0 or screen_size.y <= 0 or safe_area.size.x <= 0 or safe_area.size.y <= 0 \
			or not is_inside_tree():
		return zero
	var viewport_size := get_viewport().get_visible_rect().size
	var scale := viewport_size / Vector2(screen_size)
	return {
		"left": maxf(0.0, safe_area.position.x * scale.x),
		"top": maxf(0.0, safe_area.position.y * scale.y),
		"right": maxf(0.0, (screen_size.x - safe_area.end.x) * scale.x),
		"bottom": maxf(0.0, (screen_size.y - safe_area.end.y) * scale.y),
	}


func _log(step: StringName) -> void:
	boot_log.append(step)


# --- GameMain -------------------------------------------------------------------------------------------

func is_ready_to_play() -> bool:
	return _ready_to_play


func get_player() -> PlayerController:
	return _player


func get_maze_world() -> MazeWorld:
	return _maze_world


func get_exploration() -> Exploration:
	return _exploration


func get_minimap() -> Minimap:
	return _minimap


func get_touch_controls() -> TouchControls:
	return _touch_controls


func get_auto_save() -> AutoSave:
	return _auto_save
