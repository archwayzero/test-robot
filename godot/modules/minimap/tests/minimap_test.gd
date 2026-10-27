## Unit tests for the minimap: colour model holds only visited cells, marker follows the player, open/close toggle
## and signal, small rect placement, taps (touch and mouse) toggle and are consumed, restored() refreshes.
## Uses Core public API, MazeFactory, ExplorationFactory and this module's factory (internal model for inspection).
extends TestCase

const UnhandledProbe := preload("res://modules/minimap/tests/support/unhandled_probe.gd")
const SEED := 777
const SIZE := Vector2i(6, 5)

var layout: MazeLayout
var exploration: Exploration
var minimap: Minimap
var probe: Node
var toggles: Array[bool] = []
var _initial_state: Dictionary


func before_all() -> void:
	_initial_state = Core.state.snapshot()
	layout = MazeFactory.create().make_layout(SEED, SIZE)


func after_all() -> void:
	Core.state.restore(_initial_state)


func before_each() -> void:
	Core.state.restore(_initial_state)
	for key in [StateKeys.EXPLORATION_VISITED, StateKeys.EXPLORATION_COUNT, StateKeys.PLAYER_POSITION,
			StateKeys.PLAYER_YAW]:
		Core.state.set_value(key, null)
	Core.state.set_value(StateKeys.MAZE_SEED, SEED)
	toggles.clear()
	exploration = ExplorationFactory.create()
	add_child(exploration)
	exploration.setup(layout)
	minimap = MinimapFactory.create()
	add_child(minimap)
	minimap.setup(layout, exploration)
	minimap.large_map_toggled.connect(func(open: bool) -> void: toggles.append(open))
	probe = UnhandledProbe.new()
	add_child(probe)


func after_each() -> void:
	for n: Node in [minimap, exploration, probe]:
		if n != null and is_instance_valid(n):
			if n.is_inside_tree():
				remove_child(n)
			n.free()
	minimap = null
	exploration = null
	probe = null
	Core.state.restore(_initial_state)


func _move_to(cell: Vector2i) -> void:
	Core.player_moved.emit(layout.cell_to_world(cell) + Vector3(0.1, 0.0, -0.1))


func _model() -> Dictionary:
	return minimap.call("get_cell_color_model")


func _sorted_keys(d: Dictionary) -> Array:
	var keys := d.keys()
	keys.sort()
	return keys


func _sorted(cells: Array) -> Array:
	var c := cells.duplicate()
	c.sort()
	return c


func _other_cells(n: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in SIZE.y:
		for x in SIZE.x:
			var c := Vector2i(x, y)
			if c != layout.start_cell() and out.size() < n:
				out.append(c)
	return out


func _tap_touch(pos: Vector2) -> void:
	automation().touch(pos, true)
	await wait_frames(2)
	automation().touch(pos, false)
	await wait_frames(2)


func _click(pos: Vector2) -> void:
	for pressed in [true, false]:
		var e := InputEventMouseButton.new()
		e.button_index = MOUSE_BUTTON_LEFT
		e.pressed = pressed
		e.position = pos
		e.global_position = pos
		automation().inject_event(e)
		await wait_frames(2)


# --- model ---------------------------------------------------------------------------------------------

func test_fresh_model_has_only_start_cell() -> void:
	assert_eq(_sorted_keys(_model()), [layout.start_cell()])


func test_only_visited_cells_in_model() -> void:
	var cells := _other_cells(3)
	for c in cells:
		_move_to(c)
	var expected: Array = [layout.start_cell()]
	expected.append_array(cells)
	assert_eq(_sorted_keys(_model()), _sorted(expected))
	assert_eq(_sorted_keys(_model()), _sorted(exploration.get_explored_cells()))
	for y in SIZE.y:
		for x in SIZE.x:
			var c := Vector2i(x, y)
			assert_eq(_model().has(c), exploration.is_explored(c), "cell %s" % c)


func test_low_passages_tinted() -> void:
	var floor_color: Color = _model()[layout.start_cell()]
	for y in SIZE.y:
		for x in SIZE.x:
			_move_to(Vector2i(x, y))
	var model := _model()
	assert_eq(model.size(), SIZE.x * SIZE.y)
	for c: Vector2i in model:
		if layout.clearance(c) == MazeLayout.Clearance.FULL:
			assert_eq(model[c], floor_color, "full-height cell %s uses floor colour" % c)
		else:
			assert_ne(model[c], floor_color, "low cell %s is tinted" % c)


func test_restored_refreshes_model() -> void:
	var cells := _other_cells(2)
	for c in cells:
		_move_to(c)
	assert_eq(_model().size(), 3)
	# Restore exploration to a state with only the start cell visited (as after loading an older save).
	var bits := PackedByteArray()
	bits.resize((SIZE.x * SIZE.y + 7) >> 3)
	bits.fill(0)
	var s := layout.start_cell()
	var i := s.y * SIZE.x + s.x
	bits[i >> 3] |= 1 << (i & 7)
	var restored := [false]
	exploration.restored.connect(func() -> void: restored[0] = true)
	Core.state.set_value(StateKeys.EXPLORATION_VISITED, Marshalls.raw_to_base64(bits))
	Core.state.set_value(StateKeys.EXPLORATION_COUNT, 1)
	# Simulate a successful load (no real save slot is touched): exploration re-reads the state on load_finished.
	Core.load_finished.emit(99, OK)
	assert_true(restored[0], "exploration announced restored()")
	assert_eq(_sorted_keys(_model()), _sorted(exploration.get_explored_cells()))
	assert_eq(_sorted_keys(_model()), [s])


# --- marker --------------------------------------------------------------------------------------------

func test_marker_follows_player_cell() -> void:
	assert_eq(minimap.call("get_marker_cell"), layout.start_cell())
	for c in _other_cells(4):
		_move_to(c)
		assert_eq(minimap.call("get_marker_cell"), layout.world_to_cell(layout.cell_to_world(c)))
		assert_eq(minimap.call("get_marker_cell"), c)


func test_marker_facing_from_yaw_state() -> void:
	Core.state.set_value(StateKeys.PLAYER_YAW, 0.0)
	var d: Vector2 = minimap.call("get_marker_direction")
	assert_almost_eq(d.x, 0.0, 1e-4, "yaw 0 faces -Z = up")
	assert_almost_eq(d.y, -1.0, 1e-4)
	Core.state.set_value(StateKeys.PLAYER_YAW, PI / 2.0)
	d = minimap.call("get_marker_direction")
	assert_almost_eq(d.x, -1.0, 1e-4, "yaw +90 deg faces -X = left")
	assert_almost_eq(d.y, 0.0, 1e-4)


func test_marker_facing_from_move_delta_without_yaw() -> void:
	var p := layout.cell_to_world(layout.start_cell())
	Core.player_moved.emit(p)
	Core.player_moved.emit(p + Vector3(0.5, 0.0, 0.0))  # moving +X
	var d: Vector2 = minimap.call("get_marker_direction")
	assert_almost_eq(d.x, 1.0, 1e-4, "moving +X faces right")
	assert_almost_eq(d.y, 0.0, 1e-4)
	Core.player_moved.emit(p + Vector3(0.5, 0.0, 0.5))  # moving +Z
	d = minimap.call("get_marker_direction")
	assert_almost_eq(d.x, 0.0, 1e-4)
	assert_almost_eq(d.y, 1.0, 1e-4, "moving +Z faces down")


# --- layout and toggle ---------------------------------------------------------------------------------

func test_small_rect_top_left() -> void:
	var r := minimap.get_small_rect()
	assert_eq(r.position, Minimap.MARGIN)
	assert_eq(r.size, Minimap.SMALL_SIZE)
	assert_true(minimap.process_mode == Node.PROCESS_MODE_ALWAYS)


func test_open_close_toggles_and_signals_once() -> void:
	assert_false(minimap.is_large_map_open())
	minimap.open_large_map()
	assert_true(minimap.is_large_map_open())
	minimap.open_large_map()
	assert_eq(toggles, [true], "second open is a no-op")
	minimap.close_large_map()
	minimap.close_large_map()
	assert_false(minimap.is_large_map_open())
	assert_eq(toggles, [true, false])


func test_touch_small_map_opens_and_large_map_closes() -> void:
	await wait_frames(1)
	await _tap_touch(minimap.get_small_rect().get_center())
	assert_true(minimap.is_large_map_open(), "tap on small map opens")
	assert_eq(toggles, [true])
	await _tap_touch(minimap.get_viewport_rect().get_center())
	assert_false(minimap.is_large_map_open(), "tap on large map closes")
	assert_eq(toggles, [true, false])
	assert_eq(probe.events.size(), 0, "taps on the map are consumed")


func test_click_small_map_opens_and_large_map_closes() -> void:
	await wait_frames(1)
	await _click(minimap.get_small_rect().get_center())
	assert_true(minimap.is_large_map_open(), "click on small map opens")
	await _click(Vector2(900, 400))
	assert_false(minimap.is_large_map_open(), "click on large map closes")
	assert_eq(toggles, [true, false])
	assert_eq(probe.events.size(), 0, "clicks on the map are consumed")


func test_touch_outside_small_map_passes_through() -> void:
	await wait_frames(1)
	await _tap_touch(Vector2(800, 400))
	assert_false(minimap.is_large_map_open())
	assert_eq(toggles, [])
	assert_true(probe.events.size() > 0, "touches outside the map reach gameplay")


func test_signals_disconnected_after_exit_tree() -> void:
	remove_child(minimap)
	var before: Vector2i = minimap.call("get_marker_cell")
	_move_to(_other_cells(1)[0])
	assert_eq(minimap.call("get_marker_cell"), before, "no Core listener while out of the tree")
	assert_false(Core.player_moved.is_connected(Callable(minimap, "_on_player_moved")))
	add_child(minimap)
	_move_to(_other_cells(1)[0])
	assert_eq(minimap.call("get_marker_cell"), _other_cells(1)[0], "reconnected on re-entry")
