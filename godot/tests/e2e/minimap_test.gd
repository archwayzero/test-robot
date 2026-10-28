## M3 mini-map end-to-end tests: TEST_PLAN.md E8 minimap_fresh, E9 minimap_reveal, E10 large_map. Owner: qa.
##
## What the map draws is read through the public Minimap test hooks get_marker_cell() and get_cell_color_model()
## (public/minimap.gd; M1 finding F3, fixed in #28). No minimap internals are used.
extends "res://tests/e2e/e2e_base.gd"


func _init() -> void:
	timeout_frames = 3000


func _marker_cell() -> Vector2i:
	return main.get_minimap().get_marker_cell()


## Cells the map draws (keys of the public colour model: visited cells only).
func _drawn_cells() -> Array:
	return _sorted(main.get_minimap().get_cell_color_model().keys())


## Plain (untyped) sorted copy, so typed and untyped arrays compare by content.
static func _sorted(cells: Variant) -> Array:
	var out: Array = []
	for c: Variant in cells:
		out.append(c)
	out.sort()
	return out


func test_e8_minimap_fresh() -> void:
	assert_false(Core.saves.has_save(AutoSave.SAVE_SLOT), "fresh save")
	assert_true(await start_game())
	await automation().advance_frames(5)
	var start := layout().start_cell()
	var ex := main.get_exploration()
	assert_eq(ex.explored_count(), 1, "exactly 1 explored cell")
	assert_eq(ex.get_explored_cells(), [start] as Array[Vector2i], "the start cell")
	assert_eq(Core.state.get_value(StateKeys.EXPLORATION_COUNT), 1, "count published")
	assert_eq(player_cell(), start, "player in the start cell")
	assert_eq(_marker_cell(), start, "minimap marker in the start cell")
	assert_eq(_drawn_cells(), [start], "only the start cell drawn")
	assert_false(main.get_minimap().is_large_map_open())
	checkpoint("end")


func test_e9_minimap_reveal() -> void:
	assert_true(await start_game())
	var start := layout().start_cell()
	var tree := bfs(start, true)
	var target := start
	for c: Vector2i in tree:
		if int(tree[c][0]) == 5:
			target = c
			break
	var path := path_to(tree, target)
	assert_eq(path.size(), 6, "a 5-cell route from start: %s" % [path])
	var explored: Array = []
	var expected_new: Array = []
	for c in path.slice(1):
		expected_new.append(c)
	main.get_exploration().cell_explored.connect(func(c: Vector2i) -> void: explored.append(c))
	assert_true(await walk_path(path.slice(1)), "walked %s" % [path])
	# Walk back two cells: revisits must not emit.
	var back: Array[Vector2i] = [path[4], path[3]]
	assert_true(await walk_path(back))
	await automation().advance_frames(5)
	var ex := main.get_exploration()
	assert_eq(_sorted(ex.get_explored_cells()), _sorted(path), "exactly the 6 walked cells explored")
	assert_eq(ex.explored_count(), 6)
	assert_eq(explored, expected_new, "cell_explored once per new cell, in order")
	assert_eq(_drawn_cells(), _sorted(path), "minimap draws exactly the explored cells")
	var model := main.get_minimap().get_cell_color_model()
	for c: Variant in model:
		var col: Variant = model[c]
		assert_true(col is Color and (col as Color) != Color.BLACK,
				"visited cell %s drawn in a non-black colour (%s)" % [c, col])
	assert_eq(_marker_cell(), player_cell(), "marker follows the player")
	print("E9 route: %s" % [path])
	checkpoint("end")


func test_e10_large_map() -> void:
	assert_true(await start_game())
	var minimap := main.get_minimap()
	var controls := main.get_touch_controls()
	var toggles: Array = []
	minimap.large_map_toggled.connect(func(open: bool) -> void: toggles.append(open))
	assert_true(controls.visible, "controls visible before")
	var small := minimap.get_small_rect()
	automation().touch(small.get_center(), true)
	await automation().advance_frames(1)
	automation().touch(small.get_center(), false)
	await automation().advance_frames(2)
	assert_true(minimap.is_large_map_open(), "tap on the small map opens the large map")
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_MAP_OPEN)
	assert_true(get_tree().paused, "tree paused")
	assert_true(Core.state.is_paused())
	assert_false(controls.visible, "controls hidden")
	# The player does not move while the map is open.
	var before := player().global_position
	automation().press_action(GameActions.MOVE_FORWARD, 1.0)
	await automation().advance_frames(10)
	automation().release_action(GameActions.MOVE_FORWARD)
	assert_almost_eq(player().global_position.distance_to(before), 0.0, 0.001, "player frozen")
	var centre := get_viewport().get_visible_rect().size * 0.5
	automation().touch(centre, true)
	await automation().advance_frames(1)
	automation().touch(centre, false)
	await automation().advance_frames(2)
	assert_false(minimap.is_large_map_open(), "tap on the screen centre closes it")
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_PLAYING)
	assert_false(get_tree().paused, "tree running")
	assert_true(controls.visible, "controls back")
	assert_eq(toggles, [true, false], "large_map_toggled once each way")
	checkpoint("end")
