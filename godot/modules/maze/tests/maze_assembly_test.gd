## T018 rules: assembly, materials, omni limit, lamps, collision, occluders, determinism. Rules live in
## support/maze_rules.gd as plain helpers; each is also fed a broken input here.
extends TestCase

const Rules := preload("res://modules/maze/tests/support/maze_rules.gd")
const Assembly := preload("res://modules/maze/internal/maze_assembly.gd")
const Kit := preload("res://modules/maze/internal/maze_kit.gd")
const SEEDS: Array[int] = [MazeFactory.GAME_SEED, 42, 7, 1234, 99]

var factory: MazeFactory
var layout: MazeLayout
var world: Node3D  # the implementation: assembly_items() is not part of MazeWorld
var items: Array[Dictionary] = []
var other_worlds: Array[Node3D] = []  # one per seed in SEEDS after the first


func before_all() -> void:
	factory = MazeFactory.create()
	layout = factory.make_layout()
	world = await _make_world(layout)
	items = world.assembly_items()
	for sd in SEEDS.slice(1):
		other_worlds.append(await _make_world(factory.make_layout(sd), Vector3(0, 0, 1000.0 * (other_worlds.size() + 1))))
	await get_tree().physics_frame


## Worlds share one physics space, so each extra one stands far off.
func _make_world(l: MazeLayout, at := Vector3.ZERO) -> Node3D:
	var w := factory.make_world()
	w.position = at
	get_tree().root.add_child(w)
	w.build(l)
	await w.built
	return w


func after_all() -> void:
	world.queue_free()
	for w in other_worlds:
		w.queue_free()
	await wait_frames(2)


func _count(list: Array, piece: StringName) -> int:
	var n := 0
	for item in list:
		if item.piece == piece:
			n += 1
	return n


func _without(piece: StringName, index := 0) -> Array:
	var copy := items.duplicate(true)
	var seen := 0
	for i in copy.size():
		if copy[i].piece == piece:
			if seen == index:
				copy.remove_at(i)
				return copy
			seen += 1
	return copy


func _space() -> PhysicsDirectSpaceState3D:
	return world.get_world_3d().direct_space_state


func _chunks(root: Node3D = null) -> Array[Node]:
	var out: Array[Node] = []
	for c in (root if root else world).get_children():
		if c.has_meta(&"maze_chunk"):
			out.append(c)
	return out


func _lamp_nodes(root: Node3D = null) -> Array[Node]:
	var out: Array[Node] = []
	for chunk in _chunks(root):
		for c in chunk.get_children():
			if c.has_meta(&"maze_lamp"):
				out.append(c)
	return out


# --- assembly -----------------------------------------------------------------------------------------------

func test_piece_counts_for_the_game_seed() -> void:
	# The T017 reference assembler measured these on this seed; the plan must agree.
	var want := {&"floor": 400, &"vault_bay": 394, &"wall": 401, &"arch": 439, &"ceiling_crawl": 4,
			&"ceiling_crouch": 2, &"pier": 441}
	for piece: StringName in want:
		assert_eq(_count(items, piece), want[piece], String(piece))
	assert_eq(items.size(), 2081, "nothing else in the plan")


func test_every_edge_holds_a_wall_or_an_arch() -> void:
	assert_eq(Rules.edge_errors(items, layout), PackedStringArray())


func test_every_mixed_edge_has_an_arch() -> void:
	var mixed := 0
	var arches := {}
	for item in items:
		if item.piece == &"arch":
			arches[Rules._edge_key(item.xform.origin)] = true
	for y in layout.size().y:
		for x in layout.size().x:
			for d: MazeLayout.Dir in [MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH]:
				var c := Vector2i(x, y)
				if layout.has_wall(c, d) or layout.clearance(c) == layout.clearance(c + Assembly.dir_offset(d)):
					continue
				mixed += 1
				assert_true(arches.has(Rules._edge_key(layout.cell_to_world(c) + Assembly.dir_vector(d) * 2.0)), "%s dir %d" % [c, d])
	assert_eq(mixed, 12, "contract: 12 mixed open edges on the game seed")


func test_edge_check_fails_on_a_missing_arch_or_wall() -> void:
	assert_false(Rules.edge_errors(_without(&"arch", 17), layout).is_empty(), "missing arch")
	assert_false(Rules.edge_errors(_without(&"wall", 17), layout).is_empty(), "missing wall")


func test_every_corner_has_a_pier_with_no_collinear_skip() -> void:
	assert_eq(Rules.pier_errors(items, layout), PackedStringArray())
	var collinear := Rules.collinear_corners(layout)
	assert_true(collinear.size() > 40, "the seed has many collinear corners, got %d" % collinear.size())


func test_pier_check_fails_with_the_greybox_collinear_skip() -> void:
	var skipped := {}
	for c in Rules.collinear_corners(layout):
		skipped[c] = true
	var broken: Array = items.filter(func(it: Dictionary) -> bool:
		return it.piece != &"pier" or not skipped.has(Vector2i(roundi(it.xform.origin.x / 4.0), roundi(it.xform.origin.z / 4.0))))
	assert_eq(Rules.pier_errors(broken, layout).size(), skipped.size(), "every skipped corner reported")


func test_floors_and_low_ceilings_not_rotated() -> void:
	assert_eq(Rules.cell_errors(items, layout), PackedStringArray())


func test_cell_check_fails_on_a_rotated_floor_or_ceiling() -> void:
	for piece: StringName in [&"floor", &"ceiling_crawl", &"ceiling_crouch"]:
		var broken := items.duplicate(true)
		for item in broken:
			if item.piece == piece:
				item.xform.basis = Assembly.YAW_90
				break
		assert_eq(Rules.cell_errors(broken, layout).size(), 1, String(piece))


func test_walls_alternate_by_world_cell_parity() -> void:
	assert_eq(Rules.wall_parity_errors(items, layout), PackedStringArray())
	assert_eq(Rules.wall_run_errors(items, layout.cell_size_m()), PackedStringArray())
	var flipped := 0
	for item in items:
		if item.piece == &"wall" and item.flipped:
			flipped += 1
	assert_between(flipped, 120, 280, "both rotations in use")


func test_wall_checks_fail_on_instance_order_pattern() -> void:
	# The contract's rejected 0,0,1,1 pattern, by instance order.
	var broken := items.duplicate(true)
	var n := 0
	for item in broken:
		if item.piece == &"wall":
			var along_x: bool = absf(item.xform.basis.x.x) > 0.5
			var flip := n % 4 >= 2
			var basis := Assembly.YAW_180 if flip else Assembly.YAW_0
			if not along_x:
				basis = Assembly.YAW_270 if flip else Assembly.YAW_90
			item.xform.basis = basis
			n += 1
	assert_false(Rules.wall_parity_errors(broken, layout).is_empty(), "parity")
	assert_false(Rules.wall_run_errors(broken, layout.cell_size_m()).is_empty(), "run")


func test_built_meshes_hold_the_plan() -> void:
	var kit := Kit.new()
	var kit_mesh := {}
	for piece in Kit.PIECES:
		var arrays: Array = (kit.meshes[piece] as Mesh).surface_get_arrays(0)
		kit_mesh[piece] = {"vertices": arrays[Mesh.ARRAY_VERTEX], "uvs": arrays[Mesh.ARRAY_TEX_UV]}
	var by_chunk := {}
	for item in items:
		var key: Vector2i = (item.cell as Vector2i) / 2
		if not by_chunk.has(key):
			by_chunk[key] = []
		by_chunk[key].append(item)
	var tris := 0
	var checked := 0
	var moved_seen := 0
	var flips := 0
	var flips_seen := 0
	for chunk in _chunks():
		var mi := chunk.get_node("Mesh") as MeshInstance3D
		var merged := {}
		for s in mi.mesh.get_surface_count():
			var arrays: Array = mi.mesh.surface_get_arrays(s)
			tris += (arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
			for i in vertices.size():
				var at := Rules.snap_key(vertices[i])
				if not merged.has(at):
					merged[at] = PackedVector2Array()
				merged[at].append(uvs[i])
		var key: Vector2i = (chunk.get_meta(&"maze_chunk").position as Vector2i) / 2
		var chunk_items: Array = by_chunk[key]
		var origin := (chunk as Node3D).position
		assert_eq(Rules.missing_items(chunk_items, merged, kit_mesh, origin), PackedStringArray())
		checked += chunk_items.size()
		# Proofs: a piece planned elsewhere, and each wall turned half a circle onto its own outline, are reported.
		var moved: Dictionary = chunk_items[0].duplicate(true)
		moved.xform.origin += Vector3(100, 0, 0)
		moved_seen += Rules.missing_items([moved], merged, kit_mesh, origin).size()
		for item: Dictionary in chunk_items:
			if item.piece == &"wall":
				var turned := item.duplicate(true)
				turned.xform.basis = item.xform.basis * Assembly.YAW_180
				flips += 1
				flips_seen += Rules.missing_items([turned], merged, kit_mesh, origin).size()
	assert_eq(moved_seen, _chunks().size(), "moved piece reported in every chunk")
	assert_eq(flips, 401, "every wall tried turned")
	print("T018 walls turned 180 and reported: %d of %d" % [flips_seen, flips])
	assert_eq(flips_seen, flips, "every turned wall reported")
	assert_eq(checked, items.size())
	assert_eq(tris, 910278, "full maze triangles, same as the T017 measurement")


func test_tint_varies_baked_wall_colours() -> void:
	var kit := Kit.new()
	var base: PackedColorArray = kit.meshes[&"wall"].surface_get_arrays(0)[Mesh.ARRAY_COLOR]
	var seen := {}
	for item in items:
		if item.piece == &"wall":
			seen[item.tint] = true
			var c: Color = kit.mesh_for(item).surface_get_arrays(0)[Mesh.ARRAY_COLOR][0]
			assert_almost_eq(c.r, base[0].r * item.tint, 0.02, "tint in COLOR_0")
	assert_eq(seen.size(), 3, "all three tints in use")


# --- materials ----------------------------------------------------------------------------------------------

func test_kit_materials_have_the_contract_flags() -> void:
	var names := {}
	for chunk in _chunks():
		var mesh: Mesh = chunk.get_node("Mesh").mesh
		for s in mesh.get_surface_count():
			var mat := mesh.surface_get_material(s)
			if mat.resource_name.begins_with("stone_"):
				names[mat.resource_name] = true
				assert_eq(Rules.material_errors(mat), PackedStringArray())
	assert_eq(names.size(), 2, "stone_ashlar and stone_floor both merged")


func test_material_check_fails_on_the_imported_material() -> void:
	var kit := (load(Kit.KIT_PATH) as PackedScene).instantiate()
	var raw: Material = (kit.get_node("wall") as MeshInstance3D).mesh.surface_get_material(0)
	kit.free()
	assert_true(Rules.material_errors(raw).size() >= 2, "raw GLB material misses the flags")
	var wrong := Kit.kit_material(raw)
	wrong.vertex_color_is_srgb = true
	assert_eq(Rules.material_errors(wrong).size(), 1, "srgb on")


# --- omni limit ---------------------------------------------------------------------------------------------

func test_no_mesh_lit_by_more_than_8_omnis_on_any_tested_seed() -> void:
	assert_true(Rules.max_omnis_per_mesh(world) <= Rules.OMNI_LIMIT, "game seed: %d" % Rules.max_omnis_per_mesh(world))
	for i in other_worlds.size():
		var worst := Rules.max_omnis_per_mesh(other_worlds[i])
		assert_true(worst <= Rules.OMNI_LIMIT, "seed %d: %d" % [SEEDS[i + 1], worst])
	assert_true(Rules.max_omnis_per_mesh(world) >= 4, "helper sees omnis at all")
	print("T018 omni max per mesh: game seed %d, others %s" % [Rules.max_omnis_per_mesh(world),
			other_worlds.map(func(w: Node3D) -> int: return Rules.max_omnis_per_mesh(w))])


func test_omni_check_fails_at_the_rejected_range_and_chunk() -> void:
	# 6 m (1.5 cells) on seed 1234's chunks, and a 4x4 box at the shipped range: both exceed 8.
	var at_six := Rules.max_omnis_per_mesh(other_worlds[2], 6.0)
	assert_true(at_six > Rules.OMNI_LIMIT, "range 6 exceeds, got %d" % at_six)
	var worst := 0
	for y in range(0, 20, 4):
		for x in range(0, 20, 4):
			var box := AABB(Vector3(x * 4 - 0.375, -0.2, y * 4 - 0.375), Vector3(16.75, 4.35, 16.75))
			worst = maxi(worst, Rules.omnis_touching(world, box))
	assert_true(worst > Rules.OMNI_LIMIT, "4x4 chunks exceed, got %d" % worst)


# --- lamps --------------------------------------------------------------------------------------------------

func test_lamp_count_and_mounts_match_the_slots() -> void:
	var slots := layout.lamp_slots()
	var nodes := _lamp_nodes()
	assert_eq(nodes.size(), slots.size(), "one lamp per slot")
	assert_eq(slots.size(), 89, "game seed")
	var remaining := {}
	for slot in slots:
		remaining["%s %d" % [slot.cell, slot.dir]] = slot
	for node: Node3D in nodes:
		var slot: Dictionary = node.get_meta(&"maze_lamp")
		assert_eq(Rules.lamp_errors(node.global_transform, slot, layout), PackedStringArray())
		assert_true(remaining.erase("%s %d" % [slot.cell, slot.dir]), "slot used once")
	assert_true(remaining.is_empty(), "every slot has a lamp")


func test_lamp_check_fails_on_a_bad_mount() -> void:
	var slot: Dictionary = layout.lamp_slots()[0]
	var good := Assembly.lamp_mount(layout, slot)
	assert_eq(Rules.lamp_errors(good, slot, layout), PackedStringArray())
	var flipped := Transform3D(good.basis * Assembly.YAW_180, good.origin)
	assert_false(Rules.lamp_errors(flipped, slot, layout).is_empty(), "faces into the wall")
	var sunk := good.translated(Assembly.dir_vector(slot.dir) * 0.3)
	assert_false(Rules.lamp_errors(sunk, slot, layout).is_empty(), "on the edge line, not the wall face")
	var low := good.translated(Vector3(0, -0.5, 0))
	assert_false(Rules.lamp_errors(low, slot, layout).is_empty(), "wrong height")


func test_lamp_lights_follow_the_lighting_decision() -> void:
	var kit := Kit.new()
	for node: Node3D in _lamp_nodes():
		var omni := node.get_node("Light") as OmniLight3D
		assert_false(omni.shadow_enabled, "no shadows")
		assert_true(omni.omni_range <= 6.0, "range <= 1.5 cells")
		assert_eq(omni.light_specular, 0.0, "white pier hairlines and font cap")
		assert_true(omni.global_position.is_equal_approx(node.global_transform * kit.lamp_emitter), "at the emitter")
		assert_almost_eq(omni.global_position.y, 2.25, 0.001, "emitter height")
	assert_eq(world.find_children("*", "LightmapGI", true, false).size(), 0, "no half-baked lightmap")
	assert_eq(world.find_children("*", "DirectionalLight3D", true, false).size(), 0, "no sun")


func test_lamp_meshes_merged_without_collision() -> void:
	var kit := Kit.new()
	var flames := 0
	var irons := 0
	var flame_tris: int = kit.lamp_flame.surface_get_array_index_len(0) / 3
	var iron_tris: int = kit.lamp_iron.surface_get_array_index_len(0) / 3
	for chunk in _chunks():
		var mesh: Mesh = chunk.get_node("Mesh").mesh
		for s in mesh.get_surface_count():
			var mat := mesh.surface_get_material(s)
			if mat.resource_name == "wall_lamp_flame":
				flames += mesh.surface_get_array_index_len(s) / 3 / flame_tris
				assert_true((mat as StandardMaterial3D).emission_enabled, "flame emits")
				assert_true((mat as StandardMaterial3D).emission_energy_multiplier > 0.0, "flame lit")
			elif mat.resource_name == "wall_lamp_iron":
				irons += mesh.surface_get_array_index_len(s) / 3 / iron_tris
	assert_eq(flames, 89, "flame per lamp")
	assert_eq(irons, 89, "iron per lamp")
	for node in _lamp_nodes():
		assert_eq(node.find_children("*", "CollisionObject3D", true, false).size(), 0, "no lamp collision")
	# A vertical ray through the bracket, 0.2 m off the wall, hits nothing: the lamp is not on layer 1.
	var slot: Dictionary = layout.lamp_slots()[0]
	var at := Assembly.lamp_mount(layout, slot).origin - Assembly.dir_vector(slot.dir) * 0.2
	var hit := _space().intersect_ray(PhysicsRayQueryParameters3D.create(at + Vector3(0, 0.3, 0), at - Vector3(0, 0.4, 0), 1))
	assert_true(hit.is_empty(), "no collision at the bracket")


# --- collision ----------------------------------------------------------------------------------------------

func test_collision_matches_has_wall_on_every_edge() -> void:
	for height in Rules.COLLISION_HEIGHTS:
		assert_eq(Rules.collision_errors(_space(), layout, height), PackedStringArray(), "height %.1f" % height)


func test_collision_check_fails_against_another_layout() -> void:
	assert_true(Rules.collision_errors(_space(), other_worlds[0].get_layout(), 0.4).size() > 100, "seed 42 walls differ")
	assert_true(Rules.collision_errors(_space(), other_worlds[0].get_layout(), 2.1).size() > 100, "at the top height too")


func test_collision_layer_is_world_only() -> void:
	for chunk in _chunks():
		var body := chunk.get_node("Collision") as StaticBody3D
		assert_eq(body.collision_layer, 1, "layer 1")
		assert_eq(body.collision_mask, 0, "static")
		assert_eq(body.get_child_count(), 1, "one merged shape")


func test_player_passes_at_full_crouch_and_crawl() -> void:
	assert_eq(Rules.passage_errors(_space(), layout), PackedStringArray())


func test_passage_check_reaches_the_piers_at_a_wider_offset() -> void:
	# 1.45 m to the side puts a 0.3 m body 0.05 m into a pier: the offset really moves the body.
	assert_true(Rules.passage_errors(_space(), layout, 1.45).size() > 100, "piers block a body that wide")


func test_body_has_the_real_shape_and_radius() -> void:
	var crawl := Rules.body_shape(0.5) as CylinderShape3D
	assert_not_null(crawl, "crawl body is a cylinder")
	assert_almost_eq(crawl.radius, 0.3, 0.0001)
	assert_almost_eq(crawl.height, 0.5, 0.0001)
	var crouch := Rules.body_shape(1.0) as CapsuleShape3D
	assert_not_null(crouch, "crouch body is a capsule")
	assert_almost_eq(crouch.radius, 0.3, 0.0001)
	# Cell (0, 0) has the boundary wall face at x = 0.3: the old 0.28 radius would pass at 0.59.
	for height: float in [0.5, 1.0, 1.75]:
		assert_true(Rules.body_blocked(_space(), Vector3(0.59, 0, 2.0), height), "radius 0.3 reaches the wall, height %.2f" % height)
		assert_false(Rules.body_blocked(_space(), Vector3(0.61, 0, 2.0), height), "and stops short of it, height %.2f" % height)


func test_low_cells_block_the_next_stance_up() -> void:
	assert_eq(Rules.low_cell_errors(_space(), layout), PackedStringArray())
	var low := 0
	for y in layout.size().y:
		for x in layout.size().x:
			if layout.clearance(Vector2i(x, y)) != MazeLayout.Clearance.FULL:
				low += 1
	assert_eq(low, 6, "game seed")


func test_passage_check_fails_for_a_standing_capsule_in_a_low_cell() -> void:
	var blocked := 0
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			if layout.clearance(c) != MazeLayout.Clearance.FULL and Rules.body_blocked(_space(), layout.cell_to_world(c), 1.75):
				blocked += 1
	assert_eq(blocked, 6, "stand capsule blocked in all 6 low cells")
	assert_true(Rules.body_blocked(_space(), Vector3(0.4, 0, 2.0), 1.0), "and across a wall face")


func test_boundary_is_closed() -> void:
	var s := layout.cell_size_m()
	var far := Vector3(layout.size().x, 0, layout.size().y) * s
	var leaks := 0
	for i in layout.size().x:
		for h in [0.3, 1.0, 2.0, 3.5]:
			var a := Vector3((i + 0.5) * s, h, 2.0)
			var b := Vector3(2.0, h, (i + 0.5) * s)
			for ray: Array in [[a, a + Vector3(0, 0, -6)], [a + Vector3(0, 0, far.z - 4), a + Vector3(0, 0, far.z + 2)],
					[b, b + Vector3(-6, 0, 0)], [b + Vector3(far.x - 4, 0, 0), b + Vector3(far.x + 2, 0, 0)]]:
				if _space().intersect_ray(PhysicsRayQueryParameters3D.create(ray[0], ray[1], 1)).is_empty():
					leaks += 1
	assert_eq(leaks, 0, "no ray leaves the grid")


# --- occluders and chunks -----------------------------------------------------------------------------------

func test_every_chunk_has_a_working_occluder() -> void:
	var boxes := 0
	for chunk in _chunks():
		var occ := chunk.get_node("Occluder") as OccluderInstance3D
		var array := occ.occluder as ArrayOccluder3D
		assert_not_null(array, "ArrayOccluder3D")
		assert_eq(array.indices.size() % 36, 0, "whole boxes")
		boxes += array.vertices.size() / 8
	assert_eq(_chunks().size(), 100, "20x20 at 2x2")
	assert_eq(boxes, 401 + 6, "one box per wall and per low ceiling")
	assert_true(world.get_viewport().use_occlusion_culling, "occlusion on")


## Every occluder box of the world in world space (each box is 8 consecutive vertices).
func _occluder_boxes() -> Array[AABB]:
	var boxes: Array[AABB] = []
	for chunk: Node3D in _chunks():
		var v: PackedVector3Array = (chunk.get_node("Occluder").occluder as ArrayOccluder3D).vertices
		for i in range(0, v.size(), 8):
			var box := AABB(chunk.to_global(v[i]), Vector3.ZERO)
			for k in range(1, 8):
				box = box.expand(chunk.to_global(v[i + k]))
			boxes.append(box)
	return boxes


func test_occluder_boxes_sit_inside_the_walls() -> void:
	var boxes := _occluder_boxes()
	assert_eq(boxes.size(), 401 + 6, "all boxes seen")
	assert_eq(Rules.occluder_errors(boxes, layout), PackedStringArray())


func _with_box_moved(boxes: Array[AABB], index: int, by: Vector3) -> Array[AABB]:
	var moved: Array[AABB] = boxes.duplicate()
	var box := moved[index]
	box.position += by
	moved[index] = box
	return moved


func test_occluder_check_fails_on_a_moved_box() -> void:
	var boxes := _occluder_boxes()
	var wall_x := -1  # a wall running along X, first found
	var wall_z := -1
	var ceiling := -1
	for i in boxes.size():
		var thin_z := boxes[i].size.z < 1.0
		if thin_z and wall_x < 0:
			wall_x = i
		elif boxes[i].size.x < 1.0 and wall_z < 0:
			wall_z = i
		elif not thin_z and boxes[i].size.x >= 1.0 and ceiling < 0:
			ceiling = i
	assert_true(wall_x >= 0 and wall_z >= 0 and ceiling >= 0, "one box of each kind")
	var cases := {
		"wall across, z": [wall_x, Vector3(0, 0, 0.1)],
		"wall across, x": [wall_z, Vector3(0.1, 0, 0)],
		"wall along, x": [wall_x, Vector3(0.1, 0, 0)],
		"wall along, z": [wall_z, Vector3(0, 0, 0.1)],
		"wall to another cell line": [wall_x, Vector3(0, 0, 2.0)],
		"wall too high": [wall_x, Vector3(0, 0.1, 0)],
		"ceiling, x": [ceiling, Vector3(0.3, 0, 0)],
		"ceiling, z": [ceiling, Vector3(0, 0, 0.3)],
		"ceiling too low": [ceiling, Vector3(0, -2.0, 0)],
	}
	for what: String in cases:
		var broken := _with_box_moved(boxes, cases[what][0], cases[what][1])
		assert_false(Rules.occluder_errors(broken, layout).is_empty(), what)
	# A correct box on the wrong spot: a whole cell across puts it on some edge, and the layout has open ones.
	var on_open := 0
	for i in boxes.size():
		if boxes[i].size.z < 1.0 and not Rules.occluder_errors(_with_box_moved([boxes[i]] as Array[AABB], 0, Vector3(0, 0, 4.0)), layout).is_empty():
			on_open += 1
	assert_true(on_open > 0, "a wall box on an open edge is reported")


func test_build_is_deterministic() -> void:
	var a := Rules.digest(world)
	var again := await _make_world(factory.make_layout(), Vector3(0, 0, -1000.0))
	var b := Rules.digest(again)
	var c := Rules.digest(other_worlds[0])
	_check_digests(a, b, c)
	again.queue_free()


func _check_digests(a: String, b: String, c: String) -> void:
	assert_eq(a, b, "same seed, same bytes")
	assert_ne(a, c, "different seed differs")


func test_merged_meshes_cast_no_shadow_and_stop_past_the_fog() -> void:
	for chunk in _chunks():
		var mi := chunk.get_node("Mesh") as MeshInstance3D
		assert_eq(mi.cast_shadow, GeometryInstance3D.SHADOW_CASTING_SETTING_OFF, "no shadow pass")
		assert_eq(mi.visibility_range_end, 36.0, "34 shows the background at run ends, 38 is over the triangle budget")
