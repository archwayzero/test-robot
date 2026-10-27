## Unit tests for the maze layout generator (pure data).
extends TestCase

const D := MazeLayout.Dir
const DX := [0, 1, 0, -1]
const DY := [-1, 0, 1, 0]
const OPP := [2, 3, 0, 1]
const SEEDS := [MazeFactory.GAME_SEED, 1, 42, 7777, 123456789]

var factory: MazeFactory


func before_all() -> void:
	factory = MazeFactory.create()


func _signature(l: MazeLayout) -> PackedByteArray:
	var out := PackedByteArray()
	var sz := l.size()
	out.append_array(var_to_bytes([l.get_seed(), sz, l.start_cell()]))
	for y in sz.y:
		for x in sz.x:
			var c := Vector2i(x, y)
			var bits := 0
			for d in 4:
				if l.has_wall(c, d):
					bits |= 1 << d
			out.append(bits)
			out.append(int(l.clearance(c)))
	out.append_array(var_to_bytes(l.lamp_slots()))
	return out


## Cells reachable from start, never entering cells for which `blocked(cell)` is true.
func _reachable(l: MazeLayout, blocked: Callable) -> Dictionary:
	var seen := {l.start_cell(): true}
	var queue: Array[Vector2i] = [l.start_cell()]
	var head := 0
	while head < queue.size():
		var c := queue[head]
		head += 1
		for d in 4:
			if l.has_wall(c, d):
				continue
			var nb := Vector2i(c.x + DX[d], c.y + DY[d])
			if not seen.has(nb) and not blocked.call(nb):
				seen[nb] = true
				queue.append(nb)
	return seen


func test_factory_and_defaults() -> void:
	var l := factory.make_layout()
	assert_not_null(l)
	assert_eq(l.get_seed(), MazeFactory.GAME_SEED)
	assert_eq(l.size(), Vector2i(20, 20))
	assert_eq(l.cell_size_m(), 4.0)
	assert_true(l.in_bounds(l.start_cell()))
	assert_eq(l.clearance(l.start_cell()), MazeLayout.Clearance.FULL, "start cell must be standing height")


func test_determinism() -> void:
	var a := _signature(factory.make_layout())
	var b := _signature(factory.make_layout())
	assert_eq(a, b, "same seed must give an identical layout")
	var c := _signature(factory.make_layout(MazeFactory.GAME_SEED + 1))
	assert_ne(a, c, "different seed must give a different layout")
	# Printed so generator changes to the shipped maze are visible in test logs.
	print("maze_layout_test: GAME_SEED layout hash ", a.hex_encode().md5_text())


func test_other_sizes() -> void:
	for sz in [Vector2i(20, 20), Vector2i(8, 12), Vector2i(31, 17)]:
		var l := factory.make_layout(5, sz)
		assert_eq(l.size(), sz)
		assert_true(l.in_bounds(Vector2i(sz.x - 1, sz.y - 1)))
		assert_false(l.in_bounds(Vector2i(sz.x, 0)))
		assert_false(l.in_bounds(Vector2i(-1, 0)))
		assert_eq(_reachable(l, func(_c): return false).size(), sz.x * sz.y, "connectivity for size %s" % sz)


func test_connectivity_from_start() -> void:
	for s in SEEDS:
		var l := factory.make_layout(s)
		var n := l.size().x * l.size().y
		assert_eq(_reachable(l, func(_c): return false).size(), n, "all cells reachable, seed %d" % s)


func test_boundary_closed() -> void:
	for s in SEEDS:
		var l := factory.make_layout(s)
		var sz := l.size()
		for x in sz.x:
			assert_true(l.has_wall(Vector2i(x, 0), D.NORTH), "north boundary x=%d" % x)
			assert_true(l.has_wall(Vector2i(x, sz.y - 1), D.SOUTH), "south boundary x=%d" % x)
		for y in sz.y:
			assert_true(l.has_wall(Vector2i(0, y), D.WEST), "west boundary y=%d" % y)
			assert_true(l.has_wall(Vector2i(sz.x - 1, y), D.EAST), "east boundary y=%d" % y)
		assert_true(l.has_wall(Vector2i(-1, 3), D.EAST), "out of bounds counts as wall")


func test_has_wall_symmetric() -> void:
	var l := factory.make_layout()
	var sz := l.size()
	for y in sz.y:
		for x in sz.x:
			var c := Vector2i(x, y)
			for d in 4:
				var nb := Vector2i(x + DX[d], y + DY[d])
				if l.in_bounds(nb):
					assert_eq(l.has_wall(c, d), l.has_wall(nb, OPP[d]), "edge %s dir %d" % [c, d])


func test_has_loops() -> void:
	var l := factory.make_layout()
	var sz := l.size()
	var open_edges := 0
	for y in sz.y:
		for x in sz.x:
			if x < sz.x - 1 and not l.has_wall(Vector2i(x, y), D.EAST):
				open_edges += 1
			if y < sz.y - 1 and not l.has_wall(Vector2i(x, y), D.SOUTH):
				open_edges += 1
	var loops := open_edges - (sz.x * sz.y - 1)  # a perfect maze has exactly cells - 1 open edges
	assert_between(loops, 20, 60, "about 10% extra openings")


func test_low_cells_count_and_loop_only() -> void:
	for s in SEEDS:
		var l := factory.make_layout(s)
		var sz := l.size()
		var crouch := 0
		var crawl := 0
		var low := {}
		for y in sz.y:
			for x in sz.x:
				var c := Vector2i(x, y)
				match l.clearance(c):
					MazeLayout.Clearance.CROUCH:
						crouch += 1
						low[c] = true
					MazeLayout.Clearance.CRAWL:
						crawl += 1
						low[c] = true
		assert_between(crouch + crawl, 4, 8, "low cell count, seed %d" % s)
		assert_true(crouch >= 2, "at least 2 CROUCH, seed %d" % s)
		assert_true(crawl >= 2, "at least 2 CRAWL, seed %d" % s)
		assert_false(low.has(l.start_cell()), "start cell is not low")
		var reach := _reachable(l, func(c): return low.has(c))
		assert_eq(reach.size(), sz.x * sz.y - low.size(),
				"removing all low cells keeps every other cell reachable, seed %d" % s)
		for c in low:
			var openings := 0
			for d in 4:
				if not l.has_wall(c, d):
					openings += 1
			assert_true(openings >= 2, "low cell %s is a passage, not a dead end" % c)


func test_lamp_slots_on_existing_walls() -> void:
	var l := factory.make_layout()
	var slots := l.lamp_slots()
	var n := l.size().x * l.size().y
	assert_between(slots.size(), n / 8, n / 2, "about one lamp every ~3 corridor cells")
	var seen := {}
	for s in slots:
		assert_true(s.has("cell") and s.has("dir"), "slot format")
		var c: Vector2i = s["cell"]
		assert_true(l.in_bounds(c))
		assert_true(l.has_wall(c, s["dir"]), "lamp at %s hangs on an existing wall" % c)
		assert_eq(l.clearance(c), MazeLayout.Clearance.FULL, "no lamp in low cells")
		assert_false(seen.has(c), "one lamp per cell")
		seen[c] = true
	# Returned array is a copy.
	slots.clear()
	assert_ne(l.lamp_slots().size(), 0)


func test_world_cell_round_trip() -> void:
	var l := factory.make_layout()
	for y in l.size().y:
		for x in l.size().x:
			var c := Vector2i(x, y)
			var p := l.cell_to_world(c)
			assert_eq(p, Vector3((x + 0.5) * 4.0, 0.0, (y + 0.5) * 4.0))
			assert_eq(l.world_to_cell(p), c)
			assert_eq(l.world_to_cell(p + Vector3(1.99, 0, -1.99)), c)
	assert_eq(l.world_to_cell(Vector3(-0.1, 0, 0.1)), Vector2i(-1, 0))
	assert_eq(l.world_to_cell(Vector3(4.0, 0, 8.0)), Vector2i(1, 2))


func test_print_stats() -> void:
	var l := factory.make_layout()
	if "stats" in l:
		print("maze_layout_test: GAME_SEED stats ", l.get("stats"))
	assert_true(true)
