## T017 (qa): crypt_kit + wall_lamp as Godot imports them (check 2) and the rubble winding of the shipped meshes (check 6,
## mesh side). Contract: docs/contracts/crypt-kit.md. Run after `godot --import` of the committed state: the .ctex
## checks read the import products. All synchronous; every check has a self-test feeding it a broken input.
extends TestCase

const Checks := preload("res://tests/assets/crypt_checks.gd")
const Assembly := preload("res://tests/assets/crypt_assembly.gd")

var kit: Node3D
var lamp: Node3D


func before_all() -> void:
	var kit_scene := load(Checks.KIT_PATH) as PackedScene
	var lamp_scene := load(Checks.LAMP_PATH) as PackedScene
	if kit_scene == null or lamp_scene == null:
		fail("GLB did not load through res://")
		return
	kit = kit_scene.instantiate()
	lamp = lamp_scene.instantiate()


func after_all() -> void:
	if kit:
		kit.free()
	if lamp:
		lamp.free()


func _mesh(piece: String) -> Mesh:
	return (kit.get_node(piece) as MeshInstance3D).mesh


func test_kit_root_nodes_collision_and_nothing_rendered_twice() -> void:
	assert_not_null(kit, "crypt_kit.glb through res://")
	assert_eq(Checks.kit_structure_problems(kit).size(), 0, str(Checks.kit_structure_problems(kit)))


func test_kit_counted_vs_rendered_primitives() -> void:
	var rendered := Checks.surface_count(kit)
	var tris := 0
	var collision_faces := 0
	var per_piece := {}
	for piece in Checks.KIT_PIECES:
		var n := Assembly.triangle_count(_mesh(piece))
		per_piece[piece] = n
		tris += n
		for s in kit.get_node(piece).find_children("*", "CollisionShape3D", true, false):
			collision_faces += (s as CollisionShape3D).shape.get_faces().size() / 3
	print("T017 kit surfaces rendered=%d (tool counts 14 incl. colonly), render tris=%d, collision faces=%d, per piece %s"
			% [rendered, tris, collision_faces, per_piece])
	assert_eq(rendered, 7, "rendered primitives measured from the imported scene")
	assert_eq(tris + collision_faces, 4552, "render + collision triangles equal check_budgets.py's 4552 (pier 120 -> 122, cap top, T039)")


func test_self_structure_check_can_fail() -> void:
	var broken: Node3D = kit.duplicate()
	(broken.get_node("wall/wall") as Node).free()  # no collision
	var extra := MeshInstance3D.new()
	extra.mesh = _mesh("pier")
	broken.get_node("pier").add_child(extra)  # collision rendered
	broken.get_node("arch").name = "arch2"  # wrong name
	var problems := str(Checks.kit_structure_problems(broken))
	broken.free()
	assert_true(problems.contains("root nodes"), problems)
	assert_true(problems.contains("wall has 0 StaticBody3D"), problems)
	assert_true(problems.contains("pier has 1 rendered"), problems)


func test_lamp_structure() -> void:
	assert_not_null(lamp, "wall_lamp.glb through res://")
	assert_eq(Checks.lamp_structure_problems(lamp).size(), 0, str(Checks.lamp_structure_problems(lamp)))


func test_self_lamp_check_can_fail() -> void:
	var broken: Node3D = lamp.duplicate()
	(broken.find_child("light_emitter", true, false) as Node3D).position = Vector3(0, 0.25, -0.35)
	broken.add_child(OmniLight3D.new())
	broken.find_child("wall_lamp_flame", true, false).free()
	var problems := str(Checks.lamp_structure_problems(broken))
	broken.free()
	assert_true(problems.contains("light_emitter at"), problems)
	assert_true(problems.contains("1 lights"), problems)
	assert_true(problems.contains("surfaces"), problems)
	assert_true(problems.contains("no wall_lamp_flame"), problems)


func _check_astc(dir: String, expected: int) -> void:
	var imports := Checks.texture_imports(dir)
	assert_eq(imports.size(), expected, dir + " texture count")
	for f in imports:
		var path := Checks.astc_path(f)
		assert_ne(path, "", f + " has a path.astc")
		var h := Checks.parse_ctex(FileAccess.get_file_as_bytes(path).slice(0, Checks.CTEX_HEADER_BYTES))
		assert_eq(Checks.ctex_problem(h), "", path)
		print("T017 ctex %s: %s" % [path.get_file(), h])


func test_kit_textures_are_astc_4x4() -> void:
	_check_astc(Checks.KIT_DIR, 6)


func test_lamp_textures_are_astc_4x4() -> void:
	_check_astc(Checks.LAMP_DIR, 4)


func test_self_ctex_check_can_fail() -> void:
	var f := Checks.texture_imports(Checks.LAMP_DIR)[0]
	var bptc := Checks.astc_path(f).replace(".astc.ctex", ".bptc.ctex")
	var bytes := FileAccess.get_file_as_bytes(bptc).slice(0, Checks.CTEX_HEADER_BYTES)
	assert_true(Checks.ctex_problem(Checks.parse_ctex(bytes)).contains("not ASTC_4x4"), "BPTC product reported")
	var webp := Checks.parse_ctex(bytes)
	webp.data_format = 2  # what the stale pre-import cache held (RIFF payload)
	assert_true(Checks.ctex_problem(webp).contains("not raw GPU"), "WebP product reported")
	var short := Checks.parse_ctex(FileAccess.get_file_as_bytes(Checks.astc_path(f)).slice(0, Checks.CTEX_HEADER_BYTES))
	short.mipmaps = 1
	assert_true(Checks.ctex_problem(short).contains("mipmaps"), "missing mips reported")
	assert_true(Checks.ctex_problem(Checks.parse_ctex(PackedByteArray([1, 2, 3]))).contains("not a GST2"), "garbage reported")


func test_kit_material_count_and_shipped_defaults() -> void:
	var names := {}
	for piece in Checks.KIT_PIECES:
		var m := _mesh(piece).surface_get_material(0) as StandardMaterial3D
		names[m.resource_name] = true
		# Documents why the assembler must set them: the contract's two warnings, as imported.
		assert_eq(m.texture_filter, BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS, piece + " imports with filter 3")
		assert_false(m.vertex_color_use_as_albedo, piece + " imports with vertex colour off")
	assert_true(names.size() <= 2, "at most 2 kit materials: %s" % [names.keys()])


## Check 6, mesh side. T039 removed the 3 and 10 flipped edge pairs T015 shipped: none may come back.
func test_rubble_has_no_flipped_edge_pairs() -> void:
	var crouch := Checks.flipped_edge_pairs(_mesh("ceiling_crouch"))
	var crawl := Checks.flipped_edge_pairs(_mesh("ceiling_crawl"))
	print("T017 flipped edge pairs crouch=%d %s crawl=%d %s" % [crouch.pairs, crouch.edges, crawl.pairs, crawl.edges])
	assert_eq(crouch.pairs, 0, "ceiling_crouch flipped edge pairs at %s" % [crouch.edges])
	assert_eq(crawl.pairs, 0, "ceiling_crawl flipped edge pairs at %s" % [crawl.edges])


func test_self_flipped_edge_check_can_fail() -> void:
	var clean := Checks.flipped_edge_pairs(_mesh("wall"))
	var broken := Checks.with_flipped_triangles(_mesh("wall"), func(c: Vector3) -> bool: return c.x > 1.0)
	assert_true(Checks.flipped_edge_pairs(broken).pairs > clean.pairs, "flipping triangles raises the count")
