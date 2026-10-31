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
## Lamps: real-time omnis, no shadows. LightmapGI has no bake call outside the editor and headless has no RenderingDevice.
const OMNI_RANGE := 5.0  # 1.25 cells: 6 m (1.5 cells) gave 9-11 omnis on a 2x2 chunk
const OMNI_ENERGY := 0.8
const OMNI_COLOR := Color(1.0, 0.93, 0.84)  # near neutral: the albedo is already warm
const OMNI_SPECULAR := 0.0  # 0.03, 0.1 and 0.3 keep pure white pier hairlines at 16 m; 0 removes them
const FLAME_EMISSION := 1.0
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
		_group(by_chunk, item.cell, item)
	var lamps_by_chunk := {}
	for slot in layout.lamp_slots():
		_group(lamps_by_chunk, slot.cell, slot)
	kit.lamp_flame_material.emission_energy_multiplier = FLAME_EMISSION
	var sz := layout.size()
	for cy in range(0, sz.y, CHUNK_CELLS):
		for cx in range(0, sz.x, CHUNK_CELLS):
			var key := Vector2i(cx, cy) / CHUNK_CELLS
			_build_chunk(Vector2i(cx, cy), by_chunk.get(key, []), lamps_by_chunk.get(key, []), kit)
	# Let the physics server register the new bodies before announcing that collision is ready.
	await get_tree().physics_frame
	await get_tree().physics_frame
	if generation != _generation or not is_inside_tree():
		return  # superseded by a newer build() call
	_built = true
	built.emit()


static func _group(groups: Dictionary, cell: Vector2i, value: Dictionary) -> void:
	var key := cell / CHUNK_CELLS
	if not groups.has(key):
		groups[key] = []
	groups[key].append(value)


func _clear() -> void:
	for chunk in _chunks:
		if is_instance_valid(chunk):
			remove_child(chunk)
			chunk.queue_free()
	_chunks.clear()


func _build_chunk(origin: Vector2i, items: Array, slots: Array, kit: Kit) -> void:
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
	mesh.mesh = _merge(items, slots, kit, centre)
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	chunk.add_child(mesh)
	chunk.add_child(_collision(items, kit, centre))
	chunk.add_child(_occluder(items, centre))
	for slot in slots:
		chunk.add_child(_lamp(slot, kit, centre))
	add_child(chunk)
	_chunks.append(chunk)


## One surface per material, in the order of first appearance in the plan, which is deterministic.
func _merge(items: Array, slots: Array, kit: Kit, centre: Vector3) -> ArrayMesh:
	var tools := {}  # Material -> SurfaceTool
	for item in items:
		var xform: Transform3D = item.xform
		xform.origin -= centre
		_append(tools, kit.material_of(item.piece), kit.mesh_for(item), xform)
	for slot in slots:
		var mount := Assembly.lamp_mount(_layout, slot)
		mount.origin -= centre
		_append(tools, kit.lamp_iron_material, kit.lamp_iron, mount * kit.lamp_iron_xform)
		_append(tools, kit.lamp_flame_material, kit.lamp_flame, mount * kit.lamp_flame_xform)
	var out := ArrayMesh.new()
	for mat in tools:
		(tools[mat] as SurfaceTool).commit(out, Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES)
	return out


static func _append(tools: Dictionary, mat: Material, mesh: Mesh, xform: Transform3D) -> void:
	if not tools.has(mat):
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		st.set_material(mat)
		tools[mat] = st
	(tools[mat] as SurfaceTool).append_from(mesh, 0, xform)


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


## The lamp's meshes are merged into the chunk (flame material shared, so dim it through FLAME_EMISSION). This node is
## the mount, on the wall face with local +Z into the cell; it has no collision. The omni stands at the kit's emitter.
func _lamp(slot: Dictionary, kit: Kit, centre: Vector3) -> Node3D:
	var mount := Node3D.new()
	mount.name = "Lamp_%d_%d" % [slot.cell.x, slot.cell.y]
	mount.transform = Assembly.lamp_mount(_layout, slot)
	mount.position -= centre
	mount.set_meta(&"maze_lamp", slot)
	var omni := OmniLight3D.new()
	omni.name = "Light"
	omni.position = kit.lamp_emitter
	omni.omni_range = OMNI_RANGE
	omni.light_energy = OMNI_ENERGY
	omni.light_color = OMNI_COLOR
	omni.light_specular = OMNI_SPECULAR
	omni.shadow_enabled = false
	mount.add_child(omni)
	return mount
