## Unit tests for exploration: visited cells from Core.player_moved, persistence in Core.state, restore.
## Uses only Core public API, the maze factory and this module's factory.
extends TestCase

const VISITED := StateKeys.EXPLORATION_VISITED
const COUNT := StateKeys.EXPLORATION_COUNT
const SEED_KEY := StateKeys.MAZE_SEED
const SEED := 4242
const SIZE := Vector2i(5, 3)  # 15 cells: 2 bytes, with padding bits in the last byte
const SLOT := 91

var layout: MazeLayout
var exploration: Exploration
var explored: Array[Vector2i] = []
var restored_count := 0
var _initial_state: Dictionary


func before_all() -> void:
	_initial_state = Core.state.snapshot()
	layout = MazeFactory.create().make_layout(SEED, SIZE)


func after_all() -> void:
	if Core.saves.has_save(SLOT):
		Core.saves.delete_save(SLOT)
	Core.state.restore(_initial_state)


func before_each() -> void:
	Core.state.restore(_initial_state)
	Core.state.set_value(VISITED, null)
	Core.state.set_value(COUNT, null)
	Core.state.set_value(SEED_KEY, SEED)
	explored.clear()
	restored_count = 0


func after_each() -> void:
	if exploration != null:
		if exploration.is_inside_tree():
			remove_child(exploration)
		exploration.free()
		exploration = null
	if Core.saves.has_save(SLOT):
		Core.saves.delete_save(SLOT)
	Core.state.restore(_initial_state)


func _start() -> void:
	exploration = ExplorationFactory.create()
	add_child(exploration)
	exploration.cell_explored.connect(func(c: Vector2i) -> void: explored.append(c))
	exploration.restored.connect(func() -> void: restored_count += 1)
	exploration.setup(layout)


func _move_to(cell: Vector2i) -> void:
	Core.player_moved.emit(layout.cell_to_world(cell) + Vector3(0.1, 0.0, -0.1))


## Three distinct in-bounds cells other than the start cell.
func _three_cells() -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in SIZE.y:
		for x in SIZE.x:
			var c := Vector2i(x, y)
			if c != layout.start_cell() and out.size() < 3:
				out.append(c)
	return out


func _bits_for(cells: Array[Vector2i]) -> String:
	var b := PackedByteArray()
	b.resize((SIZE.x * SIZE.y + 7) >> 3)
	b.fill(0)
	for c in cells:
		var i := c.y * SIZE.x + c.x
		b[i >> 3] |= 1 << (i & 7)
	return Marshalls.raw_to_base64(b)


# --- fresh start ---------------------------------------------------------------------------------------

func test_fresh_start_has_only_start_cell() -> void:
	_start()
	assert_eq(exploration.explored_count(), 1)
	assert_true(exploration.is_explored(layout.start_cell()))
	assert_eq(exploration.get_explored_cells(), [layout.start_cell()] as Array[Vector2i])
	assert_eq(explored.size(), 0, "start cell is not announced via cell_explored")
	assert_eq(Core.state.get_value(VISITED), _bits_for([layout.start_cell()] as Array[Vector2i]), "start persisted")
	assert_eq(Core.state.get_value(COUNT), 1)


func test_no_work_before_setup() -> void:
	exploration = ExplorationFactory.create()
	add_child(exploration)
	exploration.cell_explored.connect(func(c: Vector2i) -> void: explored.append(c))
	_move_to(_three_cells()[0])
	assert_eq(explored.size(), 0)
	assert_eq(exploration.explored_count(), 0)
	assert_false(exploration.is_explored(layout.start_cell()))
	assert_null(Core.state.get_value(VISITED))


# --- moving --------------------------------------------------------------------------------------------

func test_moving_through_three_cells_emits_once_each() -> void:
	_start()
	var cells := _three_cells()
	for c in cells:
		_move_to(c)
		_move_to(c)  # repeated position updates inside the same cell
	assert_eq(explored, cells)
	assert_eq(exploration.explored_count(), 4)
	assert_eq(Core.state.get_value(COUNT), 4)
	var expected: Array[Vector2i] = [layout.start_cell()]
	expected.append_array(cells)
	assert_eq(Core.state.get_value(VISITED), _bits_for(expected))


func test_revisits_emit_nothing() -> void:
	_start()
	var cells := _three_cells()
	for c in cells:
		_move_to(c)
	explored.clear()
	_move_to(layout.start_cell())
	for c in cells:
		_move_to(c)
	_move_to(cells[0])
	assert_eq(explored.size(), 0)
	assert_eq(exploration.explored_count(), 4)


func test_out_of_bounds_ignored() -> void:
	_start()
	var cs := layout.cell_size_m()
	for p in [Vector3(-0.5 * cs, 0, 0.5 * cs), Vector3(0.5 * cs, 0, -0.5 * cs),
			Vector3((SIZE.x + 0.5) * cs, 0, 0.5 * cs), Vector3(0.5 * cs, 0, (SIZE.y + 2) * cs)]:
		Core.player_moved.emit(p)
	assert_eq(explored.size(), 0)
	assert_eq(exploration.explored_count(), 1)
	assert_false(exploration.is_explored(Vector2i(-1, 0)))
	assert_false(exploration.is_explored(Vector2i(SIZE.x, 0)))


func test_disconnects_when_leaving_tree() -> void:
	_start()
	remove_child(exploration)
	_move_to(_three_cells()[0])
	assert_eq(explored.size(), 0, "no tracking outside the tree")
	add_child(exploration)
	_move_to(_three_cells()[0])
	assert_eq(explored.size(), 1, "tracking resumes when re-added")


# --- persistence ---------------------------------------------------------------------------------------

func test_bitset_round_trip() -> void:
	_start()
	var cells := _three_cells()
	cells.append(Vector2i(SIZE.x - 1, SIZE.y - 1))  # last bit (index 14, inside the padded byte)
	for c in cells:
		_move_to(c)
	var saved := exploration.get_explored_cells()
	remove_child(exploration)
	exploration.free()
	exploration = null
	_start()
	assert_eq(explored.size(), cells.size(), "restore does not emit cell_explored")
	assert_eq(exploration.explored_count(), saved.size())
	assert_eq(exploration.get_explored_cells(), saved)
	for c in cells:
		assert_true(exploration.is_explored(c), "restored %s" % c)


func test_restores_stored_bits_from_state() -> void:
	var cells: Array[Vector2i] = [Vector2i(0, 0), Vector2i(4, 2), Vector2i(2, 1)]
	Core.state.set_value(VISITED, _bits_for(cells))
	Core.state.set_value(COUNT, 3)
	_start()
	assert_eq(exploration.explored_count(), 3)
	for c in cells:
		assert_true(exploration.is_explored(c))


func test_wrong_seed_discards_stored_data() -> void:
	Core.state.set_value(VISITED, _bits_for([Vector2i(0, 0), Vector2i(4, 2), Vector2i(2, 1)] as Array[Vector2i]))
	Core.state.set_value(COUNT, 3)
	Core.state.set_value(SEED_KEY, SEED + 1)
	_start()
	assert_eq(exploration.get_explored_cells(), [layout.start_cell()] as Array[Vector2i])
	assert_eq(Core.state.get_value(COUNT), 1)
	assert_eq(Core.state.get_value(VISITED), _bits_for([layout.start_cell()] as Array[Vector2i]))


func test_missing_seed_discards_stored_data() -> void:
	Core.state.set_value(VISITED, _bits_for([Vector2i(4, 2)] as Array[Vector2i]))
	Core.state.set_value(SEED_KEY, null)
	_start()
	assert_eq(exploration.get_explored_cells(), [layout.start_cell()] as Array[Vector2i])


func test_corrupt_or_short_bitset_discarded() -> void:
	var too_long := PackedByteArray([255, 255, 255])
	for bad in ["", "not base64!", "AA", Marshalls.raw_to_base64(PackedByteArray([255])),
			Marshalls.raw_to_base64(too_long), 12345, Vector2i(1, 1)]:
		Core.state.set_value(VISITED, bad)
		Core.state.set_value(COUNT, 99)
		_start()
		assert_eq(exploration.get_explored_cells(), [layout.start_cell()] as Array[Vector2i], "discarded %s" % [bad])
		assert_eq(Core.state.get_value(COUNT), 1)
		remove_child(exploration)
		exploration.free()
		exploration = null


func test_padding_bits_ignored_and_count_fixed() -> void:
	# All 16 bits set but only 15 cells exist; the stored count is wrong too.
	Core.state.set_value(VISITED, Marshalls.raw_to_base64(PackedByteArray([255, 255])))
	Core.state.set_value(COUNT, 7)
	_start()
	assert_eq(exploration.explored_count(), SIZE.x * SIZE.y)
	assert_eq(Core.state.get_value(COUNT), SIZE.x * SIZE.y, "count corrected to the bitset")


# --- load ----------------------------------------------------------------------------------------------

func test_load_finished_restores_and_emits() -> void:
	var cells: Array[Vector2i] = [Vector2i(0, 0), Vector2i(4, 2), Vector2i(2, 1)]
	var expected: Array[Vector2i] = [layout.start_cell()]
	for c in cells:
		if c not in expected:
			expected.append(c)
	Core.state.set_value(VISITED, _bits_for(expected))
	Core.state.set_value(COUNT, expected.size())
	assert_eq(Core.saves.save_game(SLOT), OK)
	Core.state.set_value(VISITED, null)
	Core.state.set_value(COUNT, null)
	_start()
	assert_eq(exploration.explored_count(), 1)
	assert_eq(Core.saves.load_game(SLOT), OK)
	assert_eq(restored_count, 1)
	assert_eq(explored.size(), 0, "restore does not emit cell_explored")
	assert_eq(exploration.explored_count(), expected.size())
	for c in expected:
		assert_true(exploration.is_explored(c))
	# After restore, a known cell is still not re-announced but a new one is.
	_move_to(cells[1])
	assert_eq(explored.size(), 0)


func test_failed_load_changes_nothing() -> void:
	_start()
	_move_to(_three_cells()[0])
	if Core.saves.has_save(SLOT):
		Core.saves.delete_save(SLOT)
	assert_ne(Core.saves.load_game(SLOT), OK)
	assert_eq(restored_count, 0)
	assert_eq(exploration.explored_count(), 2)


func test_load_of_other_seed_resets_to_start() -> void:
	_start()
	_move_to(_three_cells()[0])
	_move_to(_three_cells()[1])
	Core.state.set_value(SEED_KEY, SEED + 7)
	assert_eq(Core.saves.save_game(SLOT), OK)
	Core.state.set_value(SEED_KEY, SEED)
	assert_eq(Core.saves.load_game(SLOT), OK)
	assert_eq(restored_count, 1)
	assert_eq(exploration.get_explored_cells(), [layout.start_cell()] as Array[Vector2i])
	assert_eq(Core.state.get_value(COUNT), 1)
