## MazeWorld implementation, greybox stage (T003): primitive boxes with the crypt_kit dimensions
## (docs/contracts/crypt-kit.md), two plain materials, box collision on physics layer 1 ("world").
## Geometry is grouped per 4x4-cell chunk (one Node3D per chunk with a merged stone/floor mesh, a merged ceiling
## mesh and one StaticBody3D) so each mesh stays small enough for the 8-omni-lights-per-mesh limit later (T018).
extends MazeWorld

const CHUNK_CELLS := 4
const WALL_THICKNESS := 0.6
const WALL_HEIGHT := 3.9
const PIER_SIZE := 0.6
const PIER_HEIGHT := 2.2
const FLOOR_THICKNESS := 0.2
const CEILING_THICKNESS := 0.2
const CROUCH_UNDERSIDE := 1.3
const CRAWL_UNDERSIDE := 0.75
const WORLD_LAYER := 1

const STONE_COLOR := Color(0.62, 0.55, 0.45)
const FLOOR_COLOR := Color(0.33, 0.31, 0.29)

enum Kind { STONE, FLOOR, CEILING }

var _layout: MazeLayout
var _built := false
var _generation := 0
var _chunks: Array[Node3D] = []
var _stone_mat: StandardMaterial3D
var _floor_mat: StandardMaterial3D
var _box_meshes := {}  # Vector3 size -> BoxMesh
var _box_shapes := {}  # Vector3 size -> BoxShape3D


func _init() -> void:
	_stone_mat = StandardMaterial3D.new()
	_stone_mat.albedo_color = STONE_COLOR
	_stone_mat.roughness = 0.9
	_floor_mat = StandardMaterial3D.new()
	_floor_mat.albedo_color = FLOOR_COLOR
	_floor_mat.roughness = 0.95


func get_layout() -> MazeLayout:
	return _layout


func is_built() -> bool:
	return _built


func build(layout: MazeLayout) -> void:
	assert(is_inside_tree(), "MazeWorld.build() must be called after the node is in the tree")
	assert(layout != null)
	_generation += 1
	var generation := _generation
	_built = false
	_clear()
	_layout = layout
	Core.state.set_value(StateKeys.MAZE_SEED, layout.get_seed())
	var sz := layout.size()
	for cy in range(0, sz.y, CHUNK_CELLS):
		for cx in range(0, sz.x, CHUNK_CELLS):
			_build_chunk(Vector2i(cx, cy))
	# Let the physics server register the new bodies before announcing that collision is ready.
	await get_tree().physics_frame
	await get_tree().physics_frame
	if generation != _generation or not is_inside_tree():
		return  # superseded by a newer build() call
	_built = true
	built.emit()


func _clear() -> void:
	for chunk in _chunks:
		if is_instance_valid(chunk):
			remove_child(chunk)
			chunk.queue_free()
	_chunks.clear()


# --- chunk assembly -------------------------------------------------------------------------------------

func _build_chunk(origin: Vector2i) -> void:
	var sz := _layout.size()
	var s := _layout.cell_size_m()
	var end := Vector2i(mini(origin.x + CHUNK_CELLS, sz.x), mini(origin.y + CHUNK_CELLS, sz.y))
	var boxes: Array = []  # [Kind, size: Vector3, centre: Vector3]

	# Floor slab: top exactly at y = 0.
	var fw := (end.x - origin.x) * s
	var fd := (end.y - origin.y) * s
	boxes.append([Kind.FLOOR, Vector3(fw, FLOOR_THICKNESS, fd),
			Vector3(origin.x * s + fw * 0.5, -FLOOR_THICKNESS * 0.5, origin.y * s + fd * 0.5)])

	for y in range(origin.y, end.y):
		for x in range(origin.x, end.x):
			var c := Vector2i(x, y)
			# Walls: each cell owns its NORTH and WEST edges; the last column/row also own the outer EAST/SOUTH.
			if _layout.has_wall(c, MazeLayout.Dir.NORTH):
				boxes.append(_wall_h(x, y, s))
			if _layout.has_wall(c, MazeLayout.Dir.WEST):
				boxes.append(_wall_v(x, y, s))
			if x == sz.x - 1 and _layout.has_wall(c, MazeLayout.Dir.EAST):
				boxes.append(_wall_v(x + 1, y, s))
			if y == sz.y - 1 and _layout.has_wall(c, MazeLayout.Dir.SOUTH):
				boxes.append(_wall_h(x, y + 1, s))
			# Ceiling: flat slab at the vault crown for FULL, low inserts (underside -> 3.9) otherwise.
			var centre := _layout.cell_to_world(c)
			match _layout.clearance(c):
				MazeLayout.Clearance.CROUCH:
					boxes.append(_insert(centre, CROUCH_UNDERSIDE, s))
				MazeLayout.Clearance.CRAWL:
					boxes.append(_insert(centre, CRAWL_UNDERSIDE, s))
				_:
					boxes.append([Kind.CEILING, Vector3(s, CEILING_THICKNESS, s),
							Vector3(centre.x, WALL_HEIGHT + CEILING_THICKNESS * 0.5, centre.z)])

	# Piers on corners owned by this chunk (corner (px, py) belongs to the chunk containing cell (px, py),
	# clamped so the outer corners belong to the last chunk). Skipped where two collinear walls already enclose it.
	var px_end := end.x + (1 if end.x == sz.x else 0)
	var py_end := end.y + (1 if end.y == sz.y else 0)
	for py in range(origin.y, py_end):
		for px in range(origin.x, px_end):
			var up := _vertical_wall(px, py - 1)
			var down := _vertical_wall(px, py)
			var left := _horizontal_wall(px - 1, py)
			var right := _horizontal_wall(px, py)
			if (up and down) or (left and right):
				continue
			boxes.append([Kind.STONE, Vector3(PIER_SIZE, PIER_HEIGHT, PIER_SIZE),
					Vector3(px * s, PIER_HEIGHT * 0.5, py * s)])

	var chunk := Node3D.new()
	chunk.name = "Chunk_%d_%d" % [origin.x / CHUNK_CELLS, origin.y / CHUNK_CELLS]
	chunk.set_meta(&"maze_chunk", Rect2i(origin, end - origin))
	var mesh := MeshInstance3D.new()
	mesh.name = "Mesh"
	mesh.mesh = _merge(boxes, [Kind.STONE, Kind.FLOOR])
	chunk.add_child(mesh)
	var ceiling := MeshInstance3D.new()
	ceiling.name = "Ceiling"
	ceiling.mesh = _merge(boxes, [Kind.CEILING])
	chunk.add_child(ceiling)
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = WORLD_LAYER
	body.collision_mask = 0
	for b in boxes:
		var shape := CollisionShape3D.new()
		shape.shape = _box_shape(b[1])
		shape.position = b[2]
		body.add_child(shape)
	chunk.add_child(body)
	add_child(chunk)
	_chunks.append(chunk)


## Wall on the horizontal edge line z = y * s, spanning cell column x.
func _wall_h(x: int, y: int, s: float) -> Array:
	return [Kind.STONE, Vector3(s, WALL_HEIGHT, WALL_THICKNESS), Vector3((x + 0.5) * s, WALL_HEIGHT * 0.5, y * s)]


## Wall on the vertical edge line x = x * s, spanning cell row y.
func _wall_v(x: int, y: int, s: float) -> Array:
	return [Kind.STONE, Vector3(WALL_THICKNESS, WALL_HEIGHT, s), Vector3(x * s, WALL_HEIGHT * 0.5, (y + 0.5) * s)]


func _insert(centre: Vector3, underside: float, s: float) -> Array:
	var h := WALL_HEIGHT - underside
	return [Kind.STONE, Vector3(s, h, s), Vector3(centre.x, underside + h * 0.5, centre.z)]


## Wall on vertical grid line x = px between rows cy and cy+1's top (false if that edge does not exist).
func _vertical_wall(px: int, cy: int) -> bool:
	var sz := _layout.size()
	if cy < 0 or cy >= sz.y or px < 0 or px > sz.x:
		return false
	if px == sz.x:
		return true
	return _layout.has_wall(Vector2i(px, cy), MazeLayout.Dir.WEST)


## Wall on horizontal grid line z = py along column cx (false if that edge does not exist).
func _horizontal_wall(cx: int, py: int) -> bool:
	var sz := _layout.size()
	if cx < 0 or cx >= sz.x or py < 0 or py > sz.y:
		return false
	if py == sz.y:
		return true
	return _layout.has_wall(Vector2i(cx, py), MazeLayout.Dir.NORTH)


func _merge(boxes: Array, kinds: Array) -> ArrayMesh:
	var out := ArrayMesh.new()
	for kind in kinds:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var any := false
		for b in boxes:
			if b[0] != kind:
				continue
			st.append_from(_box_mesh(b[1]), 0, Transform3D(Basis.IDENTITY, b[2]))
			any = true
		if not any:
			continue
		st.set_material(_floor_mat if kind == Kind.FLOOR else _stone_mat)
		st.commit(out)
	return out


func _box_mesh(size: Vector3) -> BoxMesh:
	if not _box_meshes.has(size):
		var m := BoxMesh.new()
		m.size = size
		_box_meshes[size] = m
	return _box_meshes[size]


func _box_shape(size: Vector3) -> BoxShape3D:
	if not _box_shapes.has(size):
		var b := BoxShape3D.new()
		b.size = size
		_box_shapes[size] = b
	return _box_shapes[size]
