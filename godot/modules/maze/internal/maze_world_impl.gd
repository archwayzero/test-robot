## MazeWorld from the crypt_kit (T018). The plan comes from maze_assembly.gd; each chunk merges its share of it into
## one mesh, so a chunk costs one draw call per material however many pieces it holds.
extends MazeWorld

const Assembly := preload("res://modules/maze/internal/maze_assembly.gd")
const Kit := preload("res://modules/maze/internal/maze_kit.gd")

## 2x2 cells: with OMNI_RANGE below, no chunk mesh meets more than 8 omni lights (4x4 reached 12-13, 3x3 reached 13).
const CHUNK_CELLS := 2
const WORLD_LAYER := 1

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
