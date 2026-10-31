## T017 (qa): assembles crypt_kit + wall_lamp from a MazeLayout per docs/contracts/crypt-kit.md "Rules for the assembler"
## and "wall_lamp". Owner: qa. This is a QA scene builder, NOT the T018 implementation: one node per piece, nothing merged.
## Only public APIs (MazeLayout) and the committed GLBs. `break_*` options exist so the tests can show their checks fail.
extends RefCounted

const KIT_PATH := "res://assets/crypt_kit/model/crypt_kit.glb"
const LAMP_PATH := "res://assets/wall_lamp/model/wall_lamp.glb"
## Physics layer of the render-mesh trimeshes (what the player SEES); layer 1 stays the kit's collision.
const RENDER_LAYER := 1 << 10
const LAMP_Y := 2.0
const WALL_HALF := 0.3
const OMNI_ENERGY := 0.8
const OMNI_RANGE_CELLS := 1.5
## Same colour as the T016 review scene (wall_lamp_preview.gd).
const OMNI_COLOR := Color(1.0, 0.9, 0.78)
## Per-instance wall tint (contract: one wall mesh repeats every 4 m). QA choice, three steps of +-4%.
const WALL_TINTS: Array[float] = [0.96, 1.0, 1.04]
const DIRS: Array[MazeLayout.Dir] = [MazeLayout.Dir.NORTH, MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH, MazeLayout.Dir.WEST]

var layout: MazeLayout
var root: Node3D
var cell_size := 4.0
## Options.
var vertex_color_srgb := false
var with_lamps := true
var with_render_trimesh := false
var with_occluders := false
var rect := Rect2i()  # cells to assemble; empty = whole layout
var break_skip_arch_at := Vector2i(-1, -1)  # omit the arches around this cell
var break_skip_pier_at := Vector2i(-1, -1)  # omit the pier at this corner
var break_lamp_depth := 0.0  # push lamps this far into the wall
var break_lamp_flip := false  # lamp faces into the wall
## Built data for the tests.
var counts := {}  # piece -> instances
var lamps: Array[Dictionary] = []  # {slot, node, omni, inward (Vector3), wall_point (Vector3)}
var instances: Array[Dictionary] = []  # {piece, aabb (world AABB), cell}
var wall_items: Array[Dictionary] = []  # {key, rotated_180}

var _kit: Node3D
var _lamp_scene: PackedScene
var _materials := {}  # [source material, tint] -> StandardMaterial3D
var _trimesh := {}  # piece -> ConcavePolygonShape3D of the render mesh


func _init(p_layout: MazeLayout, p_root: Node3D) -> void:
	layout = p_layout
	root = p_root
	cell_size = p_layout.cell_size_m()


func build() -> void:
	_kit = (load(KIT_PATH) as PackedScene).instantiate()
	_lamp_scene = load(LAMP_PATH)
	if rect.size == Vector2i.ZERO:
		rect = Rect2i(Vector2i.ZERO, layout.size())
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			_build_cell(Vector2i(x, y))
	for y in range(rect.position.y, rect.end.y + 1):
		for x in range(rect.position.x, rect.end.x + 1):
			if Vector2i(x, y) != break_skip_pier_at:
				_place("pier", Vector3(x * cell_size, 0, y * cell_size), 0.0, Vector2i(x, y))
	if with_lamps:
		for slot in layout.lamp_slots():
			if rect.has_point(slot.cell):
				_build_lamp(slot)
	_kit.free()


static func dir_offset(d: MazeLayout.Dir) -> Vector2i:
	match d:
		MazeLayout.Dir.NORTH:
			return Vector2i(0, -1)
		MazeLayout.Dir.EAST:
			return Vector2i(1, 0)
		MazeLayout.Dir.SOUTH:
			return Vector2i(0, 1)
	return Vector2i(-1, 0)


static func dir_vector(d: MazeLayout.Dir) -> Vector3:
	var o := dir_offset(d)
	return Vector3(o.x, 0.0, o.y)


func edge_centre(cell: Vector2i, d: MazeLayout.Dir) -> Vector3:
	return layout.cell_to_world(cell) + dir_vector(d) * cell_size * 0.5


func _build_cell(cell: Vector2i) -> void:
	var centre := layout.cell_to_world(cell)
	_place("floor", centre, 0.0, cell)  # never rotated
	match layout.clearance(cell):
		MazeLayout.Clearance.CROUCH:
			_place("ceiling_crouch", centre, 0.0, cell)  # never rotated
		MazeLayout.Clearance.CRAWL:
			_place("ceiling_crawl", centre, 0.0, cell)  # never rotated
		_:
			_place("vault_bay", centre, 0.0, cell)
	# Each edge once: north and west always, south/east only on the rectangle's far side.
	for d in DIRS:
		var far_side := d == MazeLayout.Dir.SOUTH or d == MazeLayout.Dir.EAST
		var n := cell + dir_offset(d)
		if far_side and rect.has_point(n):
			continue
		_build_edge(cell, d)


func _build_edge(cell: Vector2i, d: MazeLayout.Dir) -> void:
	var along_x := d == MazeLayout.Dir.NORTH or d == MazeLayout.Dir.SOUTH
	var yaw := 0.0 if along_x else PI * 0.5
	var at := edge_centre(cell, d)
	if layout.has_wall(cell, d):
		# Strict alternation by world cell parity along the run, not by instance order (contract: 0,0,1,1 correlates).
		var along: int = cell.x if along_x else cell.y
		var flipped := posmod(along, 2) == 1
		_place("wall", at, yaw + (PI if flipped else 0.0), cell)
		wall_items.append({"key": "%s:%d" % [cell, d], "rotated_180": flipped, "along": along, "along_x": along_x,
				"line": cell.y if along_x else cell.x})
		if with_occluders:
			_add_occluder(at, yaw)
	elif not (cell == break_skip_arch_at or cell + dir_offset(d) == break_skip_arch_at):
		_place("arch", at, yaw, cell)


## One instance of a kit piece: the mesh plus its collision body, exactly as the GLB imports.
func _place(piece: String, at: Vector3, yaw: float, cell: Vector2i) -> Node3D:
	var src := _kit.get_node(piece) as MeshInstance3D
	var mi := src.duplicate() as MeshInstance3D
	mi.position = at
	mi.rotation.y = yaw
	var tint := 1.0
	if piece == "wall":
		tint = WALL_TINTS[posmod(cell.x * 7 + cell.y * 13, WALL_TINTS.size())]
	for i in mi.mesh.get_surface_count():
		mi.set_surface_override_material(i, _material(mi.mesh.surface_get_material(i), tint))
	root.add_child(mi)
	counts[piece] = int(counts.get(piece, 0)) + 1
	instances.append({"piece": piece, "cell": cell, "at": at, "yaw": yaw, "aabb": mi.transform * mi.mesh.get_aabb(),
			"tris": triangle_count(mi.mesh)})
	if with_render_trimesh:
		_add_render_body(mi, piece)
	return mi


## Kit material with the contract's assembler settings; one shared instance per (source, tint).
func _material(src: Material, tint: float) -> StandardMaterial3D:
	var key := "%s/%s" % [src.resource_name, tint]
	if not _materials.has(key):
		var m := (src as StandardMaterial3D).duplicate() as StandardMaterial3D
		m.vertex_color_use_as_albedo = true
		m.vertex_color_is_srgb = vertex_color_srgb
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		m.albedo_color = Color(tint, tint, tint)
		_materials[key] = m
	return _materials[key]


func all_materials() -> Array:
	return _materials.values()


func _add_render_body(mi: MeshInstance3D, piece: String) -> void:
	if not _trimesh.has(piece):
		_trimesh[piece] = render_trimesh(mi.mesh)
	var body := StaticBody3D.new()
	body.collision_layer = RENDER_LAYER
	body.collision_mask = 0
	body.set_meta("piece", piece)
	var shape := CollisionShape3D.new()
	shape.shape = _trimesh[piece]
	body.add_child(shape)
	mi.add_child(body)


## Trimesh of a render mesh that reports back faces to queries with hit_back_faces (off by default on the shape).
static func render_trimesh(mesh: Mesh) -> ConcavePolygonShape3D:
	var shape := mesh.create_trimesh_shape() as ConcavePolygonShape3D
	shape.backface_collision = true
	return shape


## One box occluder per wall: what T018's per-chunk OccluderInstance3D would give at best.
func _add_occluder(at: Vector3, yaw: float) -> void:
	var occ := OccluderInstance3D.new()
	var box := BoxOccluder3D.new()
	box.size = Vector3(cell_size, 4.15, 0.5)
	occ.occluder = box
	occ.position = at + Vector3(0, 4.15 * 0.5, 0)
	occ.rotation.y = yaw
	root.add_child(occ)


func _build_lamp(slot: Dictionary) -> void:
	var d: MazeLayout.Dir = slot.dir
	var outward := dir_vector(d)  # from the cell towards the wall
	var inward := -outward
	var wall_point := layout.cell_to_world(slot.cell) + outward * (cell_size * 0.5 - WALL_HALF) + Vector3(0, LAMP_Y, 0)
	var lamp := _lamp_scene.instantiate() as Node3D
	var z := outward if break_lamp_flip else inward
	lamp.basis = Basis(Vector3.UP.cross(z).normalized(), Vector3.UP, z)
	lamp.position = wall_point + outward * break_lamp_depth
	root.add_child(lamp)
	var emitter := lamp.find_child("light_emitter", true, false) as Node3D
	var omni := OmniLight3D.new()
	omni.light_energy = OMNI_ENERGY
	omni.light_color = OMNI_COLOR
	omni.omni_range = OMNI_RANGE_CELLS * cell_size
	omni.shadow_enabled = false
	omni.position = lamp.transform * emitter.transform.origin
	root.add_child(omni)
	lamps.append({"slot": slot, "node": lamp, "omni": omni, "inward": inward, "wall_point": wall_point})


static func triangle_count(mesh: Mesh) -> int:
	var n := 0
	for i in mesh.get_surface_count():
		var arrays := mesh.surface_get_arrays(i)
		var idx: Variant = arrays[Mesh.ARRAY_INDEX]
		n += (idx.size() if idx != null else arrays[Mesh.ARRAY_VERTEX].size()) / 3
	return n
