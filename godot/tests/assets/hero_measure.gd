## CPU skinning + per-clip measurements of the hero rig, as Godot imports it (T014, owner: qa).
## Not a test file (no `_test` suffix). Used by hero_rig_test.gd.
##
## Headless Godot does not skin meshes on the CPU (skinning runs on the GPU / in the RenderingServer), so the skinned
## vertex positions are computed here from what the engine provides: the imported mesh arrays (vertices, bone
## indices, weights), the Skin bind poses and Skeleton3D global bone poses after AnimationPlayer.seek(). This is the
## same linear blend skinning formula the renderer uses:
##   v' = skeleton.global_transform * sum_i w_i * (bone_global_pose(bind_bone_i) * bind_pose_i) * v
extends RefCounted

const GLB := "res://assets/hero/rig/hero.glb"
const FPS := 30.0
## A foot vertex counts as touching the floor below this height (m).
const CONTACT_Y := 0.015
## Hero faces -Z; a planted foot of an in-place clip should slide toward +Z at the game speed.
const FORWARD := Vector3(0, 0, -1)

var root: Node3D
var skeleton: Skeleton3D
var mesh_instance: MeshInstance3D
var player: AnimationPlayer
var verts := PackedVector3Array()
var bones := PackedInt32Array()  # per vertex `stride` bind indices
var weights := PackedFloat32Array()
var stride := 4
var bind_bone := PackedInt32Array()  # bind index -> skeleton bone
var bind_pose: Array[Transform3D] = []
## Vertex indices whose dominant bone is foot_l / foot_r / metatarsal_l / metatarsal_r (the blades).
var foot_verts := {"l": PackedInt32Array(), "r": PackedInt32Array()}


static func find_node(n: Node, cls: String) -> Node:
	if n.is_class(cls):
		return n
	for c in n.get_children():
		var r := find_node(c, cls)
		if r:
			return r
	return null


## Instantiates the GLB under `parent` (must be inside the tree). Returns "" or an error.
func load_into(parent: Node) -> String:
	var ps := load(GLB) as PackedScene
	if ps == null:
		return "could not load " + GLB
	root = ps.instantiate() as Node3D
	parent.add_child(root)
	skeleton = find_node(root, "Skeleton3D") as Skeleton3D
	mesh_instance = find_node(root, "MeshInstance3D") as MeshInstance3D
	player = find_node(root, "AnimationPlayer") as AnimationPlayer
	if skeleton == null or mesh_instance == null or player == null:
		return "missing node (skeleton %s, mesh %s, player %s)" % [skeleton, mesh_instance, player]
	_read_mesh()
	return ""


func free_all() -> void:
	if root:
		root.free()
		root = null


func _read_mesh() -> void:
	var mesh := mesh_instance.mesh
	for s in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(s)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var b: PackedInt32Array = arr[Mesh.ARRAY_BONES]
		var w: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
		stride = b.size() / v.size()
		verts.append_array(v)
		bones.append_array(b)
		weights.append_array(w)
	var skin := mesh_instance.skin
	for i in skin.get_bind_count():
		var bb := skin.get_bind_bone(i)
		if bb < 0:
			bb = skeleton.find_bone(skin.get_bind_name(i))
		bind_bone.append(bb)
		bind_pose.append(skin.get_bind_pose(i))
	var fl := [skeleton.find_bone("foot_l"), skeleton.find_bone("metatarsal_l")]
	var fr := [skeleton.find_bone("foot_r"), skeleton.find_bone("metatarsal_r")]
	for vi in verts.size():
		var best := -1
		var bw := -1.0
		for k in stride:
			var w := weights[vi * stride + k]
			if w > bw:
				bw = w
				best = bind_bone[bones[vi * stride + k]]
		if best in fl:
			foot_verts.l.append(vi)
		elif best in fr:
			foot_verts.r.append(vi)


## Applies clip `clip` at time `t` to the skeleton.
func pose_at(clip: String, t: float) -> void:
	if player.current_animation != clip:
		player.play(clip)
	player.seek(t, true)
	skeleton.force_update_all_bone_transforms()


## Skinned vertex positions (root space) for the current skeleton pose.
func skinned() -> PackedVector3Array:
	var mats: Array[Transform3D] = []
	var to_root := root.global_transform.affine_inverse() * skeleton.global_transform
	for i in bind_bone.size():
		mats.append(to_root * skeleton.get_bone_global_pose(bind_bone[i]) * bind_pose[i])
	var out := PackedVector3Array()
	out.resize(verts.size())
	for vi in verts.size():
		var v := verts[vi]
		var acc := Vector3.ZERO
		var base := vi * stride
		for k in stride:
			var w := weights[base + k]
			if w > 0.0:
				acc += (mats[bones[base + k]] * v) * w
		out[vi] = acc
	return out


## Rest mesh, no skinning (for sanity checks).
func rest_aabb() -> AABB:
	return mesh_instance.get_aabb()


static func aabb_of(p: PackedVector3Array) -> AABB:
	var a := AABB(p[0], Vector3.ZERO)
	for v in p:
		a = a.expand(v)
	return a


## Samples a clip at 30 fps (frames 0..N where N*1/30 = length) and returns a dictionary of measurements:
## length, loop, frames, top (max y over frames), top_frame, min_y, min_frame, reach_fwd/back/side (horizontal
## extents from the origin), seam (max vertex distance pose(length) vs pose(0)), seam_step (max vertex distance
## pose(last frame before length) -> pose(0) for a loop, i.e. the wrap-around step), step_median (median per-frame
## max vertex step), per-foot planted speed along +Z (median, m/s) and lateral drift, and per-frame foot heights.
func measure_clip(clip: String) -> Dictionary:
	var anim := player.get_animation(clip)
	var length := anim.length
	var n := int(round(length * FPS))
	var tops := PackedFloat32Array()
	var mins := PackedFloat32Array()
	var foot_min := {"l": PackedFloat32Array(), "r": PackedFloat32Array()}
	var contact := {"l": [], "r": []}  # per frame: Vector3 centroid of contact verts or null
	var contact_set := {"l": [], "r": []}  # per frame: {vertex index: position} of contact verts
	var reach := {"fwd": 0.0, "back": 0.0, "side": 0.0}
	var frames: Array[PackedVector3Array] = []
	for f in n + 1:
		pose_at(clip, minf(f / FPS, length))
		var p := skinned()
		frames.append(p)
		var a := aabb_of(p)
		tops.append(a.end.y)
		mins.append(a.position.y)
		reach.fwd = maxf(reach.fwd, -a.position.z)
		reach.back = maxf(reach.back, a.end.z)
		reach.side = maxf(reach.side, maxf(-a.position.x, a.end.x))
		for side in ["l", "r"]:
			var lo := INF
			var c := Vector3.ZERO
			var cn := 0
			var cset := {}
			for vi in foot_verts[side]:
				var q := p[vi]
				lo = minf(lo, q.y)
				if q.y < CONTACT_Y:
					c += q
					cn += 1
					cset[vi] = q
			contact_set[side].append(cset)
			foot_min[side].append(lo)
			contact[side].append(c / cn if cn > 0 else null)
	var top := -INF
	var top_f := 0
	var lo_all := INF
	var lo_f := 0
	for f in tops.size():
		if tops[f] > top:
			top = tops[f]
			top_f = f
		if mins[f] < lo_all:
			lo_all = mins[f]
			lo_f = f
	var steps := PackedFloat32Array()
	for f in range(1, frames.size()):
		steps.append(_max_dist(frames[f - 1], frames[f]))
	steps.sort()
	var res := {
		"clip": clip, "length": length, "loop": anim.loop_mode, "frames": n,
		"top": top, "top_frame": top_f, "min_y": lo_all, "min_frame": lo_f,
		"reach_fwd": reach.fwd, "reach_back": reach.back, "reach_side": reach.side,
		"seam": _max_dist(frames[0], frames[n]),
		"seam_step": _max_dist(frames[n - 1], frames[0]) if n > 1 else 0.0,
		"step_median": steps[steps.size() / 2] if steps.size() > 0 else 0.0,
		"step_max": steps[steps.size() - 1] if steps.size() > 0 else 0.0,
		"steps_seq": _step_seq(frames), "foot_min_l": foot_min.l, "foot_min_r": foot_min.r, "tops": tops,
	}
	for side in ["l", "r"]:
		var speeds := PackedFloat32Array()
		var mat_speeds := PackedFloat32Array()
		var drift := 0.0
		var contact_frames := 0
		var cs: Array = contact[side]
		# frame n == frame 0 for loops: use 0..n-1 and wrap
		var count := n if anim.loop_mode != Animation.LOOP_NONE else n + 1
		for f in count:
			if cs[f] != null:
				contact_frames += 1
			var g := (f + 1) % n if anim.loop_mode != Animation.LOOP_NONE else f + 1
			if g >= cs.size() or cs[f] == null or cs[g] == null:
				continue
			# material points: vertices touching the floor in both frames (true slip, not the rolling contact patch)
			var a_set: Dictionary = contact_set[side][f]
			var b_set: Dictionary = contact_set[side][g]
			var dz := 0.0
			var k := 0
			for vi in a_set:
				if b_set.has(vi):
					dz += (b_set[vi] - a_set[vi]).dot(-FORWARD)
					k += 1
			if k > 0:
				mat_speeds.append(dz / k * FPS)
			var d: Vector3 = cs[g] - cs[f]
			speeds.append(d.dot(-FORWARD) * FPS)
			drift = maxf(drift, absf(d.x) * FPS)
		speeds.sort()
		mat_speeds.sort()
		res["vert_speed_" + side] = mat_speeds[mat_speeds.size() / 2] if mat_speeds.size() > 0 else NAN
		res["vert_speed_min_" + side] = mat_speeds[0] if mat_speeds.size() > 0 else NAN
		res["vert_speed_max_" + side] = mat_speeds[mat_speeds.size() - 1] if mat_speeds.size() > 0 else NAN
		res["contact_frames_" + side] = contact_frames
		res["plant_speed_" + side] = speeds[speeds.size() / 2] if speeds.size() > 0 else NAN
		res["plant_speed_min_" + side] = speeds[0] if speeds.size() > 0 else NAN
		res["plant_speed_max_" + side] = speeds[speeds.size() - 1] if speeds.size() > 0 else NAN
		res["lateral_" + side] = drift
	return res


static func _max_dist(a: PackedVector3Array, b: PackedVector3Array) -> float:
	var m := 0.0
	for i in a.size():
		m = maxf(m, a[i].distance_squared_to(b[i]))
	return sqrt(m)


## Max vertex step between consecutive sampled frames (frame f-1 -> f), f = 1..N.
static func _step_seq(frames: Array[PackedVector3Array]) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	for f in range(1, frames.size()):
		out.append(_max_dist(frames[f - 1], frames[f]))
	return out
