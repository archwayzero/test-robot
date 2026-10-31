## What Godot actually imported: node paths, emitter position, surfaces, flame emission, texture formats.
##   godot --headless --path godot -s <abs path to this file>
extends SceneTree


func _init() -> void:
	var root: Node3D = load("res://assets/wall_lamp/model/wall_lamp.glb").instantiate()
	_walk(root, "")
	var em: Node3D = root.find_child("light_emitter", true, false)
	print("emitter local ", em.position, " parent ", em.get_parent().name)
	for n in ["wall_lamp_iron", "wall_lamp_flame"]:
		var m: MeshInstance3D = root.find_child(n, true, false)
		print(n, " surfaces ", m.mesh.get_surface_count(), " tris ", m.mesh.get_faces().size() / 3, " pos ", m.position)
		var mat: StandardMaterial3D = m.mesh.surface_get_material(0)
		print("  emission_enabled ", mat.emission_enabled, " energy ", mat.emission_energy_multiplier, " transparency ", mat.transparency,
			" cull ", mat.cull_mode, " metallic ", mat.metallic, " roughness ", mat.roughness)
		for t in [mat.albedo_texture, mat.normal_texture, mat.roughness_texture, mat.metallic_texture, mat.emission_texture]:
			if t:
				print("  ", t.resource_path.get_file(), " ", t.get_width(), "x", t.get_height(), " format ", t.get_format())
	root.free()
	quit()


func _walk(n: Node, indent: String) -> void:
	print(indent, n.name, " (", n.get_class(), ")")
	for c in n.get_children():
		_walk(c, indent + "  ")
