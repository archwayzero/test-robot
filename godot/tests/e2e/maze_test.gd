## M2 maze end-to-end tests: TEST_PLAN.md E6 maze_layout, E7 world_matches_layout. Owner: qa.
extends "res://tests/e2e/e2e_base.gd"

const SAMPLED_EDGES := 40
## Ray height: above the floor top (0) and below the CRAWL ceiling underside (0.75 m), so only walls can be hit.
const RAY_Y := 0.4


## Every edge and clearance of the layout as a string (layout fingerprint).
func _fingerprint(l: MazeLayout) -> String:
	var parts := PackedStringArray()
	parts.append("%s|%s|%s|%s" % [l.size(), l.get_seed(), l.start_cell(), l.cell_size_m()])
	for y in l.size().y:
		for x in l.size().x:
			var c := Vector2i(x, y)
			var walls := 0
			for d in DIRS:
				if l.has_wall(c, d):
					walls |= 1 << int(d)
			parts.append("%d%d" % [walls, int(l.clearance(c))])
	return ",".join(parts)


func test_e6_maze_layout() -> void:
	assert_true(await start_game())
	var l := layout()
	assert_eq(l.size(), Vector2i(20, 20), "20x20")
	assert_eq(l.get_seed(), MazeFactory.GAME_SEED)
	# Boundary closed.
	var open_boundary := []
	for i in 20:
		for pair: Array in [[Vector2i(i, 0), MazeLayout.Dir.NORTH], [Vector2i(i, 19), MazeLayout.Dir.SOUTH],
				[Vector2i(0, i), MazeLayout.Dir.WEST], [Vector2i(19, i), MazeLayout.Dir.EAST]]:
			if not l.has_wall(pair[0], pair[1]):
				open_boundary.append(pair)
	assert_eq(open_boundary, [], "boundary closed")
	# Wall symmetry (an edge seen from both sides agrees).
	var asym := 0
	for y in 20:
		for x in 20:
			var c := Vector2i(x, y)
			for d in [MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH]:
				var n := c + dir_offset(d)
				if l.in_bounds(n) and l.has_wall(c, d) != l.has_wall(n, ((int(d) + 2) % 4) as MazeLayout.Dir):
					asym += 1
	assert_eq(asym, 0, "walls consistent from both sides")
	# All cells reachable from start (any stance), and also without low passages (D5: never the only route).
	assert_eq(bfs(l.start_cell()).size(), 400, "all 400 cells reachable")
	var full_cells := 0
	var low_cells := 0
	for y in 20:
		for x in 20:
			if l.clearance(Vector2i(x, y)) == MazeLayout.Clearance.FULL:
				full_cells += 1
			else:
				low_cells += 1
	assert_eq(bfs(l.start_cell(), true).size(), full_cells, "every FULL cell reachable without low passages")
	assert_between(low_cells, 4, 8, "4-8 low-passage cells (D5)")
	# Same layout on 2 runs (scene reloaded) and from a fresh factory.
	var first := _fingerprint(l)
	await _unload()
	assert_true(await start_game())
	assert_eq(_fingerprint(layout()), first, "same layout on the second run")
	assert_eq(_fingerprint(MazeFactory.create().make_layout()), first, "same layout from MazeFactory")
	print("E6 measured: start %s, %d low-passage cells" % [l.start_cell(), low_cells])
	checkpoint("end")


func test_e7_world_matches_layout() -> void:
	assert_true(await start_game())
	await automation().advance_frames(3)
	var l := layout()
	var space := main.get_maze_world().get_world_3d().direct_space_state
	var rng := RandomNumberGenerator.new()
	rng.seed = 1
	var edges: Array = []
	var walls := 0
	# 40 distinct interior edges, half with a wall and half open (so both outcomes are exercised).
	var guard := 0
	while edges.size() < SAMPLED_EDGES and guard < 10000:
		guard += 1
		var c := Vector2i(rng.randi_range(0, 19), rng.randi_range(0, 19))
		var d: MazeLayout.Dir = [MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH][rng.randi_range(0, 1)]
		var n := c + dir_offset(d)
		if not l.in_bounds(n):
			continue
		var has := l.has_wall(c, d)
		if has and walls >= SAMPLED_EDGES / 2 or not has and edges.size() - walls >= SAMPLED_EDGES / 2:
			continue
		if [c, d] in edges:
			continue
		edges.append([c, d])
		if has:
			walls += 1
	assert_eq(edges.size(), SAMPLED_EDGES)
	var mismatches := []
	for e: Array in edges:
		var c: Vector2i = e[0]
		var n: Vector2i = c + dir_offset(e[1])
		var from := l.cell_to_world(c) + Vector3(0, RAY_Y, 0)
		var to := l.cell_to_world(n) + Vector3(0, RAY_Y, 0)
		var q := PhysicsRayQueryParameters3D.create(from, to, 1)
		var hit := space.intersect_ray(q)
		var expected := l.has_wall(c, e[1])
		if hit.is_empty() == expected:
			mismatches.append("%s %s: has_wall=%s hit=%s" % [c, e[1], expected, hit.get("position")])
	assert_eq(mismatches, [], "ray hit iff has_wall")
	print("E7 measured: %d edges (%d walls), %d mismatches" % [edges.size(), walls, mismatches.size()])
	checkpoint("end")
