## End-to-end smoke tests of the main scene (module game): boot order, ready_to_play, fresh start in the start cell
## with exactly one explored cell, large map pause/phase, HUD safe-area insets, HUD input order.
## Every test starts from a fresh state (no save in slot 0, no player/exploration keys) and frees the scene.
extends TestCase

const MainImpl := preload("res://modules/game/internal/game_main_impl.gd")
const READY_TIMEOUT := 300

var main: GameMain
var phases: Array[StringName] = []
var ready_frames := -1
var _initial_state: Dictionary


func before_all() -> void:
	_initial_state = Core.state.snapshot()


func after_all() -> void:
	get_tree().paused = false
	_delete_save()
	Core.state.restore(_initial_state)


func before_each() -> void:
	get_tree().paused = false
	Core.state.restore(_initial_state)
	_delete_save()
	for key in [StateKeys.PLAYER_POSITION, StateKeys.PLAYER_YAW, StateKeys.PLAYER_STANCE,
			StateKeys.EXPLORATION_VISITED, StateKeys.EXPLORATION_COUNT, StateKeys.MAZE_SEED]:
		Core.state.set_value(key, null)
	Core.state.set_paused(false)
	phases.clear()
	ready_frames = -1
	Core.phase_changed.connect(_on_phase_changed)


func after_each() -> void:
	if Core.phase_changed.is_connected(_on_phase_changed):
		Core.phase_changed.disconnect(_on_phase_changed)
	if main != null and is_instance_valid(main):
		if main.is_inside_tree():
			remove_child(main)
		main.free()
	main = null
	get_tree().paused = false
	_delete_save()
	Core.state.restore(_initial_state)


func _delete_save() -> void:
	if Core.saves.has_save(AutoSave.SAVE_SLOT):
		Core.saves.delete_save(AutoSave.SAVE_SLOT)


func _on_phase_changed(_previous: StringName, current: StringName) -> void:
	phases.append(current)


## Instantiates the main scene under the test node and waits for ready_to_play.
func _start() -> bool:
	main = (load(GameMain.MAIN_SCENE) as PackedScene).instantiate() as GameMain
	var start_frame := Engine.get_process_frames()
	main.ready_to_play.connect(func() -> void: ready_frames = Engine.get_process_frames() - start_frame)
	add_child(main)
	var ok := await automation().wait_until(func() -> bool: return main.is_ready_to_play(), READY_TIMEOUT)
	return ok


func _player_cell() -> Vector2i:
	var layout := main.get_maze_world().get_layout()
	return layout.world_to_cell(main.get_player().global_position)


func test_reaches_ready_to_play_within_300_frames() -> void:
	assert_true(await _start(), "ready_to_play within %d frames" % READY_TIMEOUT)
	assert_true(main.is_ready_to_play())
	assert_between(ready_frames, 0, READY_TIMEOUT, "ready_to_play emitted in time")
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_PLAYING)
	assert_false(get_tree().paused)
	assert_not_null(main.get_player())
	assert_not_null(main.get_maze_world())
	assert_not_null(main.get_exploration())
	assert_not_null(main.get_minimap())
	assert_not_null(main.get_touch_controls())
	assert_not_null(main.get_auto_save())
	assert_true(main.get_maze_world().is_built())
	assert_eq(main.get_player().get_camera(), get_viewport().get_camera_3d(), "player camera is current")


func test_boot_order() -> void:
	assert_true(await _start())
	var expected: Array[StringName] = [
		MainImpl.STEP_LOADING, MainImpl.STEP_MAZE_BUILT, MainImpl.STEP_EXPLORATION_SETUP,
		MainImpl.STEP_AUTOSAVE_SETUP, MainImpl.STEP_AUTOSAVE_RESTORE, MainImpl.STEP_PLAYER_SPAWNED,
		MainImpl.STEP_TOUCH_CONTROLS, MainImpl.STEP_MINIMAP, MainImpl.STEP_PLAYING]
	assert_eq(main.get("boot_log"), expected)
	# Observed from outside through Core signals: loading first, playing last.
	assert_true(phases.size() >= 2, "phases %s" % [phases])
	assert_eq(phases.front(), StateKeys.PHASE_LOADING)
	assert_eq(phases.back(), StateKeys.PHASE_PLAYING)
	# Maze build wrote the seed (it must precede Exploration.setup).
	assert_eq(Core.state.get_value(StateKeys.MAZE_SEED), MazeFactory.GAME_SEED)
	# HUD: minimap after the touch controls under the same HUD control (drawn above, gets input first).
	var hud: Control = main.call("get_hud")
	assert_eq(main.get_touch_controls().get_parent(), hud)
	assert_eq(main.get_minimap().get_parent(), hud)
	assert_true(main.get_minimap().get_index() > main.get_touch_controls().get_index(), "minimap above controls")
	assert_true(hud.get_parent() is CanvasLayer)
	assert_eq(main.get_minimap().process_mode, Node.PROCESS_MODE_ALWAYS)
	assert_eq(main.get_touch_controls().process_mode, Node.PROCESS_MODE_ALWAYS)


func test_fresh_start_in_start_cell_with_one_explored_cell() -> void:
	assert_true(await _start())
	await wait_frames(5)
	var layout := main.get_maze_world().get_layout()
	assert_eq(_player_cell(), layout.start_cell(), "player stands in the start cell")
	assert_false(main.call("spawned_from_save"))
	assert_true(main.get_player().is_grounded() or main.get_player().global_position.y < 0.5, "on the floor")
	assert_eq(main.get_exploration().explored_count(), 1)
	assert_eq(main.get_exploration().get_explored_cells(), [layout.start_cell()] as Array[Vector2i])
	# The minimap draws from this same Exploration (its public API has no draw model to inspect).
	assert_eq(Core.state.get_value(StateKeys.EXPLORATION_COUNT), 1)


func test_spawns_at_saved_position() -> void:
	var layout := MazeFactory.create().make_layout()
	var cell := Vector2i(3, 2) if layout.start_cell() != Vector2i(3, 2) else Vector2i(4, 2)
	var pos := layout.cell_to_world(cell) + Vector3(0.2, 0.0, -0.3)
	Core.state.set_value(StateKeys.MAZE_SEED, MazeFactory.GAME_SEED)
	Core.state.set_value(StateKeys.PLAYER_POSITION, pos)
	Core.state.set_value(StateKeys.PLAYER_YAW, 1.0)
	assert_true(await _start())
	assert_true(main.call("spawned_from_save"))
	assert_eq(_player_cell(), cell)
	var p := main.get_player().global_position
	assert_almost_eq(Vector2(p.x, p.z).distance_to(Vector2(pos.x, pos.z)), 0.0, 0.1)


func test_saved_position_outside_maze_falls_back_to_start() -> void:
	Core.state.set_value(StateKeys.MAZE_SEED, MazeFactory.GAME_SEED)
	Core.state.set_value(StateKeys.PLAYER_POSITION, Vector3(-50.0, 0.0, -50.0))
	assert_true(await _start())
	assert_false(main.call("spawned_from_save"))
	assert_eq(_player_cell(), main.get_maze_world().get_layout().start_cell())


func test_large_map_pauses_and_restores() -> void:
	assert_true(await _start())
	var minimap := main.get_minimap()
	var controls := main.get_touch_controls()
	var controls_visible_before := controls.visible
	minimap.open_large_map()
	await wait_frames(2)
	assert_true(minimap.is_large_map_open())
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_MAP_OPEN)
	assert_true(get_tree().paused, "tree paused while the map is open")
	assert_true(Core.state.is_paused())
	assert_false(controls.visible, "touch controls hidden")
	# The player is frozen: no movement even with input held.
	var before := main.get_player().global_position
	automation().press_action(GameActions.MOVE_FORWARD, 1.0)
	await wait_frames(10)
	automation().release_action(GameActions.MOVE_FORWARD)
	assert_almost_eq(main.get_player().global_position.distance_to(before), 0.0, 0.001, "player frozen")
	minimap.close_large_map()
	await wait_frames(2)
	assert_false(minimap.is_large_map_open())
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_PLAYING)
	assert_false(get_tree().paused)
	assert_false(Core.state.is_paused())
	assert_eq(controls.visible, controls_visible_before, "controls back")


func test_free_while_map_open_unpauses() -> void:
	assert_true(await _start())
	main.get_minimap().open_large_map()
	assert_true(get_tree().paused)
	remove_child(main)
	main.free()
	main = null
	assert_false(get_tree().paused)


func test_hud_insets_zero_on_desktop() -> void:
	assert_true(await _start())
	var insets: Dictionary = main.call("get_hud_insets")
	for side in ["left", "top", "right", "bottom"]:
		assert_eq(insets[side], 0.0, side)
	var hud: Control = main.call("get_hud")
	assert_eq(hud.get_global_rect(), Rect2(Vector2.ZERO, get_viewport().get_visible_rect().size))


func test_hud_insets_from_injected_safe_area() -> void:
	assert_true(await _start())
	# iPhone 12 landscape-like: notch 141 px left, home indicator 63 px bottom, 2532x1170 screen.
	var screen := Vector2i(2532, 1170)
	var safe := Rect2i(141, 0, 2532 - 141 * 2, 1170 - 63)
	main.call("set_safe_area_source", func() -> Dictionary: return {"safe_area": safe, "screen_size": screen})
	var vp := get_viewport().get_visible_rect().size
	var scale := vp / Vector2(screen)
	var insets: Dictionary = main.call("get_hud_insets")
	assert_almost_eq(insets.left, 141 * scale.x, 0.01)
	assert_almost_eq(insets.right, 141 * scale.x, 0.01)
	assert_almost_eq(insets.top, 0.0, 0.01)
	assert_almost_eq(insets.bottom, 63 * scale.y, 0.01)
	var hud: Control = main.call("get_hud")
	var rect := hud.get_global_rect()
	assert_almost_eq(rect.position.x, insets.left, 0.01)
	assert_almost_eq(rect.end.x, vp.x - insets.right, 0.01)
	assert_almost_eq(rect.end.y, vp.y - insets.bottom, 0.01)
	# The minimap is laid out inside the safe area.
	var small := main.get_minimap().get_small_rect()
	assert_true(small.position.x >= insets.left, "minimap right of the notch: %s" % [small])
	# Re-applied on viewport size change; removing the override goes back to zero on desktop.
	get_viewport().size_changed.emit()
	assert_almost_eq((main.call("get_hud_insets") as Dictionary).left, 141 * scale.x, 0.01)
	main.call("set_safe_area_source", Callable())
	assert_eq((main.call("get_hud_insets") as Dictionary).left, 0.0)


func test_touch_in_left_half_reaches_joystick_not_minimap() -> void:
	assert_true(await _start())
	var controls := main.get_touch_controls()
	# Headless desktop with emulate_touch_from_mouse on (project.godot): the controls must be shown.
	assert_true(controls.visible, "touch controls shown with touch emulation")
	var vp := get_viewport().get_visible_rect().size
	var from := Vector2(vp.x * 0.2, vp.y * 0.75)
	automation().touch(from, true, 0)
	await wait_frames(1)
	var drag := InputEventScreenDrag.new()
	drag.index = 0
	drag.position = from + Vector2(0, -90)
	drag.relative = Vector2(0, -90)
	automation().inject_event(drag)
	await wait_frames(2)
	assert_true(controls.get_stick_vector().length() > 0.5, "stick %s" % [controls.get_stick_vector()])
	assert_false(main.get_minimap().is_large_map_open())
	automation().touch(from + Vector2(0, -90), false, 0)
	await wait_frames(2)
	assert_almost_eq(controls.get_stick_vector().length(), 0.0, 0.01)
