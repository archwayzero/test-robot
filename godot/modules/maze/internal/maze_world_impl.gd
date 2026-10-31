## MazeWorld from the crypt_kit (T018). The plan comes from maze_assembly.gd; each chunk merges its share of it into
## one mesh, so a chunk costs one draw call per material however many pieces it holds.
extends MazeWorld

const Assembly := preload("res://modules/maze/internal/maze_assembly.gd")
const Kit := preload("res://modules/maze/internal/maze_kit.gd")

## 2x2 cells: with OMNI_RANGE below, no chunk mesh meets more than 8 omni lights (4x4 reached 12-13, 3x3 reached 13).
const CHUNK_CELLS := 2
const WORLD_LAYER := 1
## Boxes inside the masonry: T017 validated 0.5 m thick walls; the low ceilings stay clear of their 0.138 m rubble.
const OCCLUDER_WALL_SIZE := Vector3(4.0, 4.15, 0.5)
const OCCLUDER_CEILING_INSET := 0.2
const OCCLUDER_TOP := 4.15
const CEILING_UNDERSIDE := {&"ceiling_crouch": 1.3, &"ceiling_crawl": 0.75}
## Index list of an 8-corner box, corners numbered by bits x, y, z.
const BOX_TRIS: Array[int] = [0, 2, 1, 1, 2, 3, 4, 5, 6, 5, 7, 6, 0, 1, 4, 1, 5, 4,
		2, 6, 3, 3, 6, 7, 0, 4, 2, 2, 4, 6, 1, 3, 5, 3, 7, 5]

var _layout: MazeLayout
var _built := false
var _generation := 0
var _chunks: Array[Node3D] = []
var _items: Array[Dictionary] = []


func get_layout() -> MazeLayout:
	return _layout


func is_built() -> bool:
	return _built


## The plan the current world was built from (tests only; not part of the public interface).
func assembly_items() -> Array[Dictionary]:
	return _items


func build(layout: MazeLayout) -> void:
	assert(is_inside_tree(), "MazeWorld.build() must be called after the node is in the tree")
	assert(layout != null)
	_generation += 1
	var generation := _generation
	_built = false
	_clear()
	_layout = layout
	Core.state.set_value(StateKeys.MAZE_SEED, layout.get_seed())
	get_viewport().use_occlusion_culling = true  # the project default is off and the chunks rely on it
	var kit := Kit.new()
	_items = Assembly.items(layout)
	var by_chunk := {}
	for item in _items:
		var key: Vector2i = (item.cell as Vector2i) / CHUNK_CELLS
		if not by_chunk.has(key):
			by_chunk[key] = []
		by_chunk[key].append(item)
	var sz := layout.size()
	for cy in range(0, sz.y, CHUNK_CELLS):
		for cx in range(0, sz.x, CHUNK_CELLS):
			_build_chunk(Vector2i(cx, cy), by_chunk.get(Vector2i(cx, cy) / CHUNK_CELLS, []), kit)
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


func _build_chunk(origin: Vector2i, items: Array, kit: Kit) -> void:
	var sz := _layout.size()
	var s := _layout.cell_size_m()
	var end := Vector2i(mini(origin.x + CHUNK_CELLS, sz.x), mini(origin.y + CHUNK_CELLS, sz.y))
	# Chunk-local vertices: compressed positions stay precise and the chunk's origin is its centre.
	var centre := Vector3((origin.x + end.x) * 0.5 * s, 0.0, (origin.y + end.y) * 0.5 * s)
	var chunk := Node3D.new()
	chunk.name = "Chunk_%d_%d" % [origin.x / CHUNK_CELLS, origin.y / CHUNK_CELLS]
	chunk.position = centre
	chunk.set_meta(&"maze_chunk", Rect2i(origin, end - origin))
	var mesh := MeshInstance3D.new()
	mesh.name = "Mesh"
	mesh.mesh = _merge(items, kit, centre)
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	chunk.add_child(mesh)
	chunk.add_child(_collision(items, kit, centre))
	chunk.add_child(_occluder(items, centre))
	add_child(chunk)
	_chunks.append(chunk)


## One surface per material, in the order of first appearance in the plan, which is deterministic.
func _merge(items: Array, kit: Kit, centre: Vector3) -> ArrayMesh:
	var tools := {}  # StandardMaterial3D -> SurfaceTool
	for item in items:
		var mat := kit.material_of(item.piece)
		if not tools.has(mat):
			var st := SurfaceTool.new()
			st.begin(Mesh.PRIMITIVE_TRIANGLES)
			st.set_material(mat)
			tools[mat] = st
		var xform: Transform3D = item.xform
		xform.origin -= centre
		(tools[mat] as SurfaceTool).append_from(kit.mesh_for(item), 0, xform)
	var out := ArrayMesh.new()
	for mat in tools:
		(tools[mat] as SurfaceTool).commit(out, Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES)
	return out


## The kit's -colonly trimeshes merged into one shape per chunk, on layer 1. The faces keep the kit's winding.
func _collision(items: Array, kit: Kit, centre: Vector3) -> StaticBody3D:
	var faces := PackedVector3Array()
	for item in items:
		var xform: Transform3D = item.xform
		xform.origin -= centre
		faces.append_array(xform * (kit.faces[item.piece] as PackedVector3Array))
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(faces)
	var node := CollisionShape3D.new()
	node.shape = shape
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = WORLD_LAYER
	body.collision_mask = 0
	body.add_child(node)
	return body


## One OccluderInstance3D per chunk: a box in each wall and in each solid low ceiling.
func _occluder(items: Array, centre: Vector3) -> OccluderInstance3D:
	var vertices := PackedVector3Array()
	var indices := PackedInt32Array()
	for item in items:
		var xform: Transform3D = item.xform
		xform.origin -= centre
		if item.piece == &"wall":
			var half := OCCLUDER_WALL_SIZE * 0.5
			_add_box(vertices, indices, xform, Vector3(-half.x, 0, -half.z), Vector3(half.x, OCCLUDER_WALL_SIZE.y, half.z))
		elif CEILING_UNDERSIDE.has(item.piece):
			var half := _layout.cell_size_m() * 0.5 - OCCLUDER_CEILING_INSET
			_add_box(vertices, indices, xform, Vector3(-half, CEILING_UNDERSIDE[item.piece], -half),
					Vector3(half, OCCLUDER_TOP, half))
	var occluder := ArrayOccluder3D.new()
	occluder.set_arrays(vertices, indices)
	var node := OccluderInstance3D.new()
	node.name = "Occluder"
	node.occluder = occluder
	return node


static func _add_box(vertices: PackedVector3Array, indices: PackedInt32Array, xform: Transform3D, low: Vector3,
		high: Vector3) -> void:
	var base := vertices.size()
	for i in 8:
		vertices.append(xform * Vector3(high.x if i & 1 else low.x, high.y if i & 2 else low.y, high.z if i & 4 else low.z))
	for i in BOX_TRIS:
		indices.append(base + i)
