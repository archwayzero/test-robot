## CPU skinning of the hero inside a live player (headless Godot exposes no skinned vertices). Same linear blend
## formula as the renderer: v' = sum_i w_i * (bone_global_pose(bind_bone_i) * bind_pose_i) * v.
## Not a test file. The hero's Skeleton3D sits at the Visual origin with identity transforms.
extends RefCounted

var skeleton: Skeleton3D
var mesh_instance: MeshInstance3D
var _verts := PackedVector3Array()
var _bones := PackedInt32Array()
var _weights := PackedFloat32Array()
var _stride := 4
var _bind_bone := PackedInt32Array()
var _bind_pose: Array[Transform3D] = []


func _init(player: Node3D) -> void:
	skeleton = player.get_node("Visual/Hero/Armature/Skeleton3D") as Skeleton3D
	mesh_instance = player.get_node("Visual/Hero/Armature/Skeleton3D/hero") as MeshInstance3D
	var mesh := mesh_instance.mesh
	for s in mesh.get_surface_count():
		var arrays := mesh.surface_get_arrays(s)
		var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var b: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		_stride = b.size() / v.size()
		_verts.append_array(v)
		_bones.append_array(b)
		_weights.append_array(arrays[Mesh.ARRAY_WEIGHTS] as PackedFloat32Array)
	var skin := mesh_instance.skin
	for i in skin.get_bind_count():
		var bone := skin.get_bind_bone(i)
		_bind_bone.append(bone if bone >= 0 else skeleton.find_bone(skin.get_bind_name(i)))
		_bind_pose.append(skin.get_bind_pose(i))


## World positions of all vertices in the current pose.
func world_vertices() -> PackedVector3Array:
	skeleton.force_update_all_bone_transforms()
	var to_world := skeleton.global_transform
	var mats: Array[Transform3D] = []
	for i in _bind_bone.size():
		mats.append(to_world * skeleton.get_bone_global_pose(_bind_bone[i]) * _bind_pose[i])
	var out := PackedVector3Array()
	out.resize(_verts.size())
	for vi in _verts.size():
		var acc := Vector3.ZERO
		var base := vi * _stride
		for k in _stride:
			var w := _weights[base + k]
			if w > 0.0:
				acc += (mats[_bones[base + k]] * _verts[vi]) * w
		out[vi] = acc
	return out


## {top, bottom} world y of the current pose.
func heights() -> Dictionary:
	var top := -INF
	var bottom := INF
	for v in world_vertices():
		top = maxf(top, v.y)
		bottom = minf(bottom, v.y)
	return {"top": top, "bottom": bottom}


## Smallest distance from `point` to any vertex of the current pose.
func nearest_vertex_distance(point: Vector3) -> float:
	var best := INF
	for v in world_vertices():
		best = minf(best, point.distance_squared_to(v))
	return sqrt(best)


func bone_world(bone: String) -> Vector3:
	skeleton.force_update_all_bone_transforms()
	return skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone(bone)).origin
