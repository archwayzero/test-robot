## World tests: geometry and collision built from the layout match it.
extends TestCase

const D := MazeLayout.Dir
const DX := [0, 1, 0, -1]
const DY := [-1, 0, 1, 0]
const RAY_Y := 0.4  # below the CRAWL underside (0.75)

var factory: MazeFactory
var layout: MazeLayout
var world: MazeWorld
var built_count := 0


func before_all() -> void:
	factory = MazeFactory.create()
	layout = factory.make_layout()
	core().state.set_value(StateKeys.MAZE_SEED, -1)
	world = factory.make_world()
	world.built.connect(func(): built_count += 1)
	get_tree().root.add_child(world)
	assert_false(world.is_built())
	assert_null(world.get_layout())
	world.build(layout)
	await automation().wait_until(world.is_built, 120)


func after_all() -> void:
	world.queue_free()
	await wait_frames(2)


func _ray(from: Vector3, to: Vector3) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(from, to, 1)
	return world.get_world_3d().direct_space_state.intersect_ray(q)


func test_built_and_seed_written() -> void:
	assert_true(world.is_built())
	assert_eq(built_count, 1)
	assert_eq(world.get_layout(), layout)
	assert_eq(core().state.get_value(StateKeys.MAZE_SEED), MazeFactory.GAME_SEED)


func _count_chunks() -> int:
	var n := 0
	for child in world.get_children():
		if child.has_meta(&"maze_chunk"):
			n += 1
	return n


func test_chunks() -> void:
	var chunks := 0
	for c in world.get_children():
		if c.has_meta(&"maze_chunk"):
			chunks += 1
			var r: Rect2i = c.get_meta(&"maze_chunk")
			assert_true(r.size.x <= 2 and r.size.y <= 2, "chunk at most 2x2 cells")
			var body := c.get_node("Collision") as StaticBody3D
			assert_eq(body.collision_layer, 1, "world geometry on physics layer 1")
	assert_eq(chunks, 100, "20x20 maze -> 10x10 chunks")


func test_raycasts_match_has_wall() -> void:
	await get_tree().physics_frame
	var sz := layout.size()
	var sampled := 0
	var walls := 0
	# Every 3rd cell in a fixed pattern, checking EAST and SOUTH edges (plus the boundary): > 200 edges.
	for y in sz.y:
		for x in sz.x:
			if (x + y * 7) % 3 != 0:
				continue
			var c := Vector2i(x, y)
			for d in [D.EAST, D.SOUTH, D.NORTH, D.WEST]:
				var from := layout.cell_to_world(c) + Vector3(0, RAY_Y, 0)
				var to := from + Vector3(DX[d], 0, DY[d]) * layout.cell_size_m()
				var hit := _ray(from, to)
				var expect := layout.has_wall(c, d)
				sampled += 1
				if expect:
					walls += 1
				assert_eq(not hit.is_empty(), expect, "edge %s dir %d" % [c, d])
				if expect and not hit.is_empty():
					# Wall face is exactly 0.3 m in front of the edge line (1.7 m from the centre).
					assert_almost_eq(from.distance_to(hit.position), 1.7, 0.01, "wall face of %s dir %d" % [c, d])
	assert_true(sampled >= 40, "sampled %d edges" % sampled)
	assert_true(walls > 0 and walls < sampled, "both walls and openings sampled")


func test_floor_at_zero() -> void:
	await get_tree().physics_frame
	var sz := layout.size()
	for c in [Vector2i(0, 0), Vector2i(sz.x - 1, sz.y - 1), layout.start_cell(), Vector2i(7, 13)]:
		var p := layout.cell_to_world(c)
		var hit := _ray(p + Vector3(0.3, 0.5, 0.7), p + Vector3(0.3, -1.0, 0.7))
		assert_false(hit.is_empty(), "floor under %s" % c)
		if not hit.is_empty():
			assert_almost_eq(hit.position.y, 0.0, 0.001, "floor top at y=0 in %s" % c)


func test_ceiling_heights() -> void:
	await get_tree().physics_frame
	var expected := {
		MazeLayout.Clearance.FULL: 4.148,  # vault crown, collision matches the render mesh (T017)
		MazeLayout.Clearance.CROUCH: 1.3,
		MazeLayout.Clearance.CRAWL: 0.75,
	}
	var counts := {}
	var sz := layout.size()
	for y in sz.y:
		for x in sz.x:
			var c := Vector2i(x, y)
			var cl := layout.clearance(c)
			if cl == MazeLayout.Clearance.FULL and (x + y) % 9 != 0:
				continue  # sample FULL cells, check every low cell
			var p := layout.cell_to_world(c)
			var hit := _ray(p + Vector3(0, 0.1, 0), p + Vector3(0, 5.0, 0))
			assert_false(hit.is_empty(), "ceiling over %s" % c)
			if not hit.is_empty():
				assert_almost_eq(hit.position.y, expected[cl], 0.001, "ceiling underside in %s (clearance %d)" % [c, cl])
			counts[cl] = counts.get(cl, 0) + 1
	assert_true(counts.get(MazeLayout.Clearance.CROUCH, 0) >= 2)
	assert_true(counts.get(MazeLayout.Clearance.CRAWL, 0) >= 2)


func test_rebuild_is_idempotent() -> void:
	var before := built_count
	var other := factory.make_layout(42)
	world.build(other)
	assert_false(world.is_built(), "not built while rebuilding")
	await world.built
	assert_true(world.is_built(), "first rebuild finished")
	assert_eq(core().state.get_value(StateKeys.MAZE_SEED), 42)
	world.build(layout)
	await world.built
	assert_true(world.is_built(), "second rebuild finished")
	assert_eq(built_count, before + 2)
	assert_eq(_count_chunks(), 100, "old chunks removed on rebuild")
	assert_eq(world.get_layout(), layout)
	assert_eq(core().state.get_value(StateKeys.MAZE_SEED), MazeFactory.GAME_SEED)
	# Collision matches the rebuilt layout again.
	await get_tree().physics_frame
	var start := layout.start_cell()
	for d in 4:
		var from := layout.cell_to_world(start) + Vector3(0, RAY_Y, 0)
		var to := from + Vector3(DX[d], 0, DY[d]) * 4.0
		var hit: bool = not _ray(from, to).is_empty()
		var wall: bool = layout.has_wall(start, d)
		assert_eq(hit, wall, "start cell dir %d after rebuild" % d)
