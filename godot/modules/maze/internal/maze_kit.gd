## The crypt_kit and wall_lamp GLBs turned into what the chunks merge: one template per piece, the piece's collision
## faces, and the materials with the contract's assembler settings. Read once per build, then released.
extends RefCounted

const KIT_PATH := "res://assets/crypt_kit/model/crypt_kit.glb"
const LAMP_PATH := "res://assets/wall_lamp/model/wall_lamp.glb"
const PIECES: Array[StringName] = [
	&"floor", &"wall", &"pier", &"arch", &"vault_bay", &"ceiling_crouch", &"ceiling_crawl"]

var meshes := {}  # piece -> Mesh (surface 0 only: the kit has one surface per piece)
var faces := {}  # piece -> PackedVector3Array of the -colonly trimesh
var materials := {}  # source material name -> StandardMaterial3D with the contract's settings
var lamp_iron: Mesh
var lamp_flame: Mesh
var lamp_iron_xform: Transform3D  # lamp local
var lamp_flame_xform: Transform3D  # lamp local
var lamp_emitter := Vector3.ZERO  # lamp local
var lamp_iron_material: Material
var lamp_flame_material: StandardMaterial3D
var _tinted := {}  # tint -> wall ArrayMesh with COLOR_0 scaled


func _init() -> void:
	var kit := (load(KIT_PATH) as PackedScene).instantiate()
	for piece in PIECES:
		var src := kit.get_node(String(piece)) as MeshInstance3D
		meshes[piece] = src.mesh
		faces[piece] = _collision_faces(src)
		var mat := src.mesh.surface_get_material(0) as StandardMaterial3D
		if not materials.has(mat.resource_name):
			materials[mat.resource_name] = kit_material(mat)
	kit.free()
	var lamp := (load(LAMP_PATH) as PackedScene).instantiate() as Node3D
	var iron := lamp.find_child("wall_lamp_iron", true, false) as MeshInstance3D
	var flame := lamp.find_child("wall_lamp_flame", true, false) as MeshInstance3D
	var emitter := lamp.find_child("light_emitter", true, false) as Node3D
	lamp_iron = iron.mesh
	lamp_flame = flame.mesh
	lamp_iron_xform = _relative(iron, lamp)
	lamp_flame_xform = _relative(flame, lamp)
	lamp_emitter = _relative(emitter, lamp).origin
	lamp_iron_material = iron.mesh.surface_get_material(0)
	lamp_flame_material = (flame.mesh.surface_get_material(0) as StandardMaterial3D).duplicate()
	lamp.free()


## Contract: COLOR_0 is the kit's soiling, linear, and grazing floors need anisotropic filtering.
static func kit_material(src: StandardMaterial3D) -> StandardMaterial3D:
	var m := src.duplicate() as StandardMaterial3D
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = false
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m


func material_of(piece: StringName) -> StandardMaterial3D:
	return materials[(meshes[piece] as Mesh).surface_get_material(0).resource_name]


## The mesh to merge for one plan item: walls come in one variant per tint, baked into COLOR_0 (the kit's albedo).
func mesh_for(item: Dictionary) -> Mesh:
	if item.tint == 1.0:
		return meshes[item.piece]
	if not _tinted.has(item.tint):
		_tinted[item.tint] = _tinted_copy(meshes[item.piece], item.tint)
	return _tinted[item.tint]


static func _tinted_copy(src: Mesh, tint: float) -> ArrayMesh:
	var arrays := src.surface_get_arrays(0)
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	for i in colors.size():
		var c := colors[i]
		colors[i] = Color(c.r * tint, c.g * tint, c.b * tint, c.a)
	arrays[Mesh.ARRAY_COLOR] = colors
	var out := ArrayMesh.new()
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return out


static func _collision_faces(mi: MeshInstance3D) -> PackedVector3Array:
	var shape_node := mi.find_children("*", "CollisionShape3D", true, false)[0] as CollisionShape3D
	return (shape_node.shape as ConcavePolygonShape3D).get_faces()


static func _relative(node: Node3D, root: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n := node
	while n != root:
		t = n.transform * t
		n = n.get_parent() as Node3D
	return t
