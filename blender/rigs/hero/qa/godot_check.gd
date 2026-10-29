# Prints what Godot imported from the hero rig GLB (skeleton, animations, loop modes).
#   godot --headless --path godot --script <abs path>/blender/rigs/hero/qa/godot_check.gd
extends SceneTree

func _find(n: Node, cls: String) -> Node:
	if n.is_class(cls):
		return n
	for c in n.get_children():
		var r := _find(c, cls)
		if r:
			return r
	return null

func _init() -> void:
	var ps: PackedScene = load("res://assets/hero/rig/hero.glb")
	if ps == null:
		print("GODOT_CHECK load failed")
		quit(1)
		return
	var root := ps.instantiate()
	var sk: Skeleton3D = _find(root, "Skeleton3D")
	print("GODOT_CHECK skeleton bones=", sk.get_bone_count() if sk else -1)
	if sk:
		var names := []
		for i in sk.get_bone_count():
			names.append(sk.get_bone_name(i))
		print("GODOT_CHECK bones ", names)
	var mi: MeshInstance3D = _find(root, "MeshInstance3D")
	if mi:
		var aabb := mi.get_aabb()
		print("GODOT_CHECK mesh aabb ", aabb.position, " size ", aabb.size, " skin=", mi.skin != null)
	var ap: AnimationPlayer = _find(root, "AnimationPlayer")
	if ap == null:
		print("GODOT_CHECK no AnimationPlayer")
	else:
		for a in ap.get_animation_list():
			var anim := ap.get_animation(a)
			var mode: String = ["none", "linear", "pingpong"][anim.loop_mode]
			print("GODOT_CHECK anim %s length=%.3f loop=%s tracks=%d" % [a, anim.length, mode, anim.get_track_count()])
	root.free()
	quit(0)
