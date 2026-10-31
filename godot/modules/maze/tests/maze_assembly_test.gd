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
	var verts := {}
	for piece in Kit.PIECES:
		verts[piece] = (kit.meshes[piece] as Mesh).surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var by_chunk := {}
	for item in items:
		var key: Vector2i = (item.cell as Vector2i) / 2
		if not by_chunk.has(key):
			by_chunk[key] = []
		by_chunk[key].append(item)
	var tris := 0
	var checked := 0
	var one_broken := false
	for chunk in _chunks():
		var mi := chunk.get_node("Mesh") as MeshInstance3D
		var positions := {}
		for s in mi.mesh.get_surface_count():
			var arrays: Array = mi.mesh.surface_get_arrays(s)
			tris += (arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
			for v: Vector3 in arrays[Mesh.ARRAY_VERTEX]:
				positions[Rules.snap_key(v)] = true
		var key: Vector2i = (chunk.get_meta(&"maze_chunk").position as Vector2i) / 2
		var chunk_items: Array = by_chunk[key]
		assert_eq(Rules.missing_items(chunk_items, positions, verts, (chunk as Node3D).position), PackedStringArray())
		checked += chunk_items.size()
		if not one_broken:
			# Proof: a piece planned elsewhere is reported missing from this chunk.
			var moved: Dictionary = chunk_items[0].duplicate(true)
			moved.xform.origin += Vector3(100, 0, 0)
			assert_eq(Rules.missing_items([moved], positions, verts, (chunk as Node3D).position).size(), 1, "moved piece")
			one_broken = true
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
	assert_eq(Rules.collision_errors(_space(), layout, 0.4), PackedStringArray())
	assert_eq(Rules.collision_errors(_space(), layout, 0.7), PackedStringArray())


func test_collision_check_fails_against_another_layout() -> void:
	assert_true(Rules.collision_errors(_space(), other_worlds[0].get_layout(), 0.4).size() > 100, "seed 42 walls differ")


func test_collision_layer_is_world_only() -> void:
	for chunk in _chunks():
		var body := chunk.get_node("Collision") as StaticBody3D
		assert_eq(body.collision_layer, 1, "layer 1")
		assert_eq(body.collision_mask, 0, "static")
		assert_eq(body.get_child_count(), 1, "one merged shape")


func test_player_passes_at_full_crouch_and_crawl() -> void:
	assert_eq(Rules.passage_errors(_space(), layout), PackedStringArray())


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
			if layout.clearance(c) != MazeLayout.Clearance.FULL and Rules.capsule_blocked(_space(), layout.cell_to_world(c), 1.75):
				blocked += 1
	assert_eq(blocked, 6, "stand capsule blocked in all 6 low cells")
	assert_true(Rules.capsule_blocked(_space(), Vector3(0.4, 0, 2.0), 1.0), "and across a wall face")


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


func test_occluder_boxes_sit_inside_the_walls() -> void:
	var outside := 0
	for chunk: Node3D in _chunks():
		var v: PackedVector3Array = (chunk.get_node("Occluder").occluder as ArrayOccluder3D).vertices
		for p in v:
			var w := chunk.to_global(p)
			var off_x := absf(w.x - roundf(w.x / 4.0) * 4.0)
			var off_z := absf(w.z - roundf(w.z / 4.0) * 4.0)
			if minf(off_x, off_z) > 2.0 or w.y < -0.001 or w.y > 4.151:
				outside += 1
	assert_eq(outside, 0, "occluder corners")


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


func test_no_rendered_shadow_casting_on_merged_meshes() -> void:
	for chunk in _chunks():
		var mi := chunk.get_node("Mesh") as MeshInstance3D
		assert_eq(mi.cast_shadow, GeometryInstance3D.SHADOW_CASTING_SETTING_OFF, "no shadow pass")
