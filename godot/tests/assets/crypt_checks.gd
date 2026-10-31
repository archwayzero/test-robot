## T017 (qa): measuring helpers for the crypt_kit + wall_lamp tests. Owner: qa. Every helper returns a measurement or a list
## of problems, never asserts, so the self-tests can feed it a broken input and show that the same code reports the failure.
## Space-based helpers are called by the tests after physics frames have passed (plain functions, TEST_PLAN rule).
extends RefCounted

const KIT_PATH := "res://assets/crypt_kit/model/crypt_kit.glb"
const LAMP_PATH := "res://assets/wall_lamp/model/wall_lamp.glb"
const KIT_DIR := "res://assets/crypt_kit/model"
const LAMP_DIR := "res://assets/wall_lamp/model"
const KIT_PIECES: Array[String] = ["arch", "ceiling_crawl", "ceiling_crouch", "floor", "pier", "vault_bay", "wall"]
const CTEX_HEADER_BYTES := 0x34


# --- .ctex headers --------------------------------------------------------------------------------------------------

## Parses a GST2 header. {} if it is not one. Layout (4.7.2): magic, version, width, height, flags, mip limit, 3 reserved,
## data_format, u16 w, u16 h, mipmaps, image format.
static func parse_ctex(bytes: PackedByteArray) -> Dictionary:
	if bytes.size() < CTEX_HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "GST2":
		return {}
	return {"data_format": bytes.decode_u32(0x24), "width": bytes.decode_u16(0x28), "height": bytes.decode_u16(0x2A),
			"mipmaps": bytes.decode_u32(0x2C), "format": bytes.decode_u32(0x30)}


## "" if the header says raw ASTC_4x4 with a full mip chain; otherwise what is wrong. data_format 0 = raw GPU image
## (2 = WebP, the stale pre-pass-3 products were RIFF payloads).
static func ctex_problem(h: Dictionary) -> String:
	if h.is_empty():
		return "not a GST2 file"
	if h.data_format != 0:
		return "data_format %d, not raw GPU data" % h.data_format
	if h.format != Image.FORMAT_ASTC_4x4:
		return "image format %d, not ASTC_4x4 (%d)" % [h.format, Image.FORMAT_ASTC_4x4]
	var expected_mips := int(log(maxf(h.width, h.height)) / log(2.0))
	if h.mipmaps < expected_mips:
		return "only %d mipmaps of %d" % [h.mipmaps, expected_mips]
	return ""


## The `path.astc` of a texture's committed .import file, "" if it has none.
static func astc_path(import_file: String) -> String:
	var cfg := ConfigFile.new()
	if cfg.load(import_file) != OK:
		return ""
	return str(cfg.get_value("remap", "path.astc", ""))


## All *.png.import files of a directory.
static func texture_imports(dir: String) -> Array[String]:
	var out: Array[String] = []
	for f in DirAccess.get_files_at(dir):
		if f.ends_with(".png.import"):
			out.append(dir.path_join(f))
	out.sort()
	return out


# --- structure ------------------------------------------------------------------------------------------------------

## Problems of an imported kit root: exact 7 root nodes, each one mesh + StaticBody3D + collision shape, no rendered collision.
static func kit_structure_problems(kit: Node) -> Array[String]:
	var out: Array[String] = []
	var names: Array[String] = []
	for c in kit.get_children():
		names.append(str(c.name))
	names.sort()
	if names != KIT_PIECES:
		out.append("root nodes %s, expected %s" % [names, KIT_PIECES])
	for c in kit.get_children():
		if not c is MeshInstance3D:
			out.append("%s is not a MeshInstance3D" % c.name)
			continue
		var bodies := c.find_children("*", "StaticBody3D", true, false)
		if bodies.size() != 1:
			out.append("%s has %d StaticBody3D" % [c.name, bodies.size()])
		var shapes := c.find_children("*", "CollisionShape3D", true, false)
		if shapes.size() < 1:
			out.append("%s has no CollisionShape3D" % c.name)
		for s in shapes:
			if (s as CollisionShape3D).shape == null:
				out.append("%s has an empty CollisionShape3D" % c.name)
		var rendered := c.find_children("*", "MeshInstance3D", true, false)
		if not rendered.is_empty():
			out.append("%s has %d rendered mesh(es) below it (collision rendered?)" % [c.name, rendered.size()])
		if str(c.name).contains("col") and not str(c.name).begins_with("floor"):
			out.append("%s looks like a collision node" % c.name)
	return out


static func surface_count(root: Node) -> int:
	var n := 0
	for m in root.find_children("*", "MeshInstance3D", true, false):
		n += (m as MeshInstance3D).mesh.get_surface_count()
	return n


## Problems of an imported lamp root.
static func lamp_structure_problems(lamp: Node) -> Array[String]:
	var out: Array[String] = []
	var emitter := lamp.find_child("light_emitter", true, false) as Node3D
	if emitter == null:
		out.append("no light_emitter")
	elif not emitter.position.is_equal_approx(Vector3(0, 0.25, 0.35)):
		out.append("light_emitter at %s" % emitter.position)
	var materials: Array[String] = []
	for m in lamp.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			materials.append(str(mi.mesh.surface_get_material(i).resource_name))
	materials.sort()
	if materials != ["wall_lamp_flame", "wall_lamp_iron"]:
		out.append("surfaces %s, expected flame + iron" % [materials])
	var lights := lamp.find_children("*", "Light3D", true, false)
	if not lights.is_empty():
		out.append("%d lights in the GLB" % lights.size())
	if lamp.find_child("wall_lamp_flame", true, false) == null:
		out.append("no wall_lamp_flame node")
	return out


# --- rays and capsules ----------------------------------------------------------------------------------------------

static func ray(space: PhysicsDirectSpaceState3D, from: Vector3, to: Vector3, mask: int, back_faces := true) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(from, to, mask)
	q.hit_back_faces = back_faces
	return space.intersect_ray(q)


## Hit distance along from->to, or INF.
static func ray_distance(space: PhysicsDirectSpaceState3D, from: Vector3, to: Vector3, mask: int) -> float:
	var hit := ray(space, from, to, mask)
	return from.distance_to(hit.position) if not hit.is_empty() else INF


## True if a capsule with feet at `feet` overlaps anything on `mask`. `lift` clears the floor contact.
static func capsule_blocked(space: PhysicsDirectSpaceState3D, feet: Vector3, height: float, radius: float, mask := 1,
		lift := 0.02) -> bool:
	var shape: Shape3D
	if height < radius * 2.0:
		shape = CylinderShape3D.new()
		shape.radius = radius
		shape.height = height
	else:
		shape = CapsuleShape3D.new()
		shape.radius = radius
		shape.height = height
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.collision_mask = mask
	q.transform = Transform3D(Basis.IDENTITY, feet + Vector3(0, height * 0.5 + lift, 0))
	return not space.intersect_shape(q, 1).is_empty()


## Travel of a sphere moving from `from` to `to` before it touches `mask`, in metres (what a spring arm does).
static func sphere_travel(space: PhysicsDirectSpaceState3D, from: Vector3, to: Vector3, radius: float, mask := 1) -> float:
	var shape := SphereShape3D.new()
	shape.radius = radius
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.collision_mask = mask
	q.transform = Transform3D(Basis.IDENTITY, from)
	q.motion = to - from
	var r := space.cast_motion(q)
	return r[0] * from.distance_to(to)


## Fraction of a ConcavePolygonShape3D's triangles whose front side faces away from the solid, for a solid that is
## convex in the sense of `outward_from(m) -> Vector3` giving the direction from the solid towards the room at m.
## Godot's front face is clockwise: normal = (c - a) x (b - a).
static func faces_pointing_with(faces: PackedVector3Array, outward_from: Callable) -> Dictionary:
	var good := 0
	var bad := 0
	for i in range(0, faces.size(), 3):
		var n := (faces[i + 2] - faces[i]).cross(faces[i + 1] - faces[i]).normalized()
		var m := (faces[i] + faces[i + 1] + faces[i + 2]) / 3.0
		var o: Vector3 = outward_from.call(m)
		if o == Vector3.ZERO:
			continue
		if n.dot(o) > 0.0:
			good += 1
		else:
			bad += 1
	return {"good": good, "bad": bad}


## Fibonacci sphere, `n` unit directions.
static func sphere_dirs(n: int) -> PackedVector3Array:
	var out := PackedVector3Array()
	var golden := PI * (3.0 - sqrt(5.0))
	for i in n:
		var y := 1.0 - 2.0 * (i + 0.5) / n
		var r := sqrt(1.0 - y * y)
		out.append(Vector3(cos(golden * i) * r, y, sin(golden * i) * r))
	return out


## Sees through the rendered geometry? `mask` must select the render-mesh trimeshes. Returns:
## {"rays", "escaped" [from, dir]..., "backface_first" [from, to]...}: escaped = no front face in `reach` metres (the ray
## leaves through a hole); backface_first = the nearest surface along the ray is a back face (culled, so see-through).
static func see_through(space: PhysicsDirectSpaceState3D, eyes: PackedVector3Array, dirs: PackedVector3Array, mask: int,
		reach := 120.0) -> Dictionary:
	var escaped: Array = []
	var back: Array = []
	var rays := 0
	for e in eyes:
		for d in dirs:
			rays += 1
			var to := e + d * reach
			var front := ray(space, e, to, mask, false)
			if front.is_empty():
				escaped.append([e, d])
				continue
			var any := ray(space, e, to, mask, true)
			if not any.is_empty() and e.distance_to(any.position) < e.distance_to(front.position) - 0.001:
				back.append([e, any.position, any.collider, front.collider])
	return {"rays": rays, "escaped": escaped, "backface_first": back}


## Like see_through, but aimed at explicit target points (rays end 2 cm past the target), which guarantees that every
## target is looked at from every eye. Hidden targets are simply occluded by a nearer front face.
static func backface_first_hits(space: PhysicsDirectSpaceState3D, eyes: PackedVector3Array, targets: PackedVector3Array,
		mask: int) -> Dictionary:
	var hits: Array = []
	var rays := 0
	for e in eyes:
		for t in targets:
			var d := (t - e).normalized()
			var to := t + d * 0.02
			rays += 1
			var any := ray(space, e, to, mask, true)
			if any.is_empty():
				continue
			var front := ray(space, e, to, mask, false)
			var nearer: bool = front.is_empty() or e.distance_to(any.position) < e.distance_to(front.position) - 0.001
			if nearer:
				hits.append([e, any.position, any.collider, front.collider if not front.is_empty() else null])
	return {"rays": rays, "hits": hits}


## Summary of backface hits: {"by_piece": {piece: rays}, "points": distinct points at 2 cm in piece-local space,
## "behind": {piece seen through the gap: rays}}. Entries as returned by see_through/backface_first_hits.
static func classify_hits(hits: Array) -> Dictionary:
	var by_piece := {}
	var behind := {}
	var points := {}
	for h: Array in hits:
		var body := h[2] as Node3D
		var piece := str(body.get_meta("piece", "?"))
		by_piece[piece] = int(by_piece.get(piece, 0)) + 1
		var far: Variant = h[3]
		var seen := "nothing" if far == null else str((far as Node).get_meta("piece", "?"))
		behind[seen] = int(behind.get(seen, 0)) + 1
		var local: Vector3 = (body.global_transform.affine_inverse() * (h[1] as Vector3)).snappedf(0.02)
		points[local] = int(points.get(local, 0)) + 1
	return {"by_piece": by_piece, "behind": behind, "points": points}


# --- mesh analysis --------------------------------------------------------------------------------------------------

## Triangle centroids of a mesh (surface 0..n) in mesh space.
static func centroids(mesh: Mesh) -> PackedVector3Array:
	var out := PackedVector3Array()
	var v: PackedVector3Array
	for s in mesh.get_surface_count():
		var a := mesh.surface_get_arrays(s)
		v = a[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
		for i in range(0, idx.size(), 3):
			out.append((v[idx[i]] + v[idx[i + 1]] + v[idx[i + 2]]) / 3.0)
	return out


## Edge pairs of a mesh whose two triangles traverse the edge in the SAME direction (inconsistent winding), welding
## by position at 0.1 mm. Returns {"pairs", "edges": [midpoint...]}.
static func flipped_edge_pairs(mesh: Mesh) -> Dictionary:
	var directed := {}
	for s in mesh.get_surface_count():
		var a := mesh.surface_get_arrays(s)
		var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
		for i in range(0, idx.size(), 3):
			for k in 3:
				var p: Vector3 = v[idx[i + k]]
				var q: Vector3 = v[idx[i + (k + 1) % 3]]
				var key := "%s|%s" % [_weld(p), _weld(q)]
				directed[key] = int(directed.get(key, 0)) + 1
				directed["m" + key] = (p + q) * 0.5
	var pairs := 0
	var where: Array = []
	for key: String in directed:
		if key.begins_with("m"):
			continue
		if int(directed[key]) >= 2:
			pairs += 1
			where.append(directed["m" + key])
	return {"pairs": pairs, "edges": where}


static func _weld(p: Vector3) -> Vector3i:
	return Vector3i((p * 10000.0).round())


## A copy of `mesh` with every triangle whose centroid passes `pick` reversed (self-tests). Single-surface meshes.
static func with_flipped_triangles(mesh: Mesh, pick: Callable) -> ArrayMesh:
	var a := mesh.surface_get_arrays(0)
	var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
	for i in range(0, idx.size(), 3):
		if pick.call((v[idx[i]] + v[idx[i + 1]] + v[idx[i + 2]]) / 3.0):
			var t := idx[i + 1]
			idx[i + 1] = idx[i + 2]
			idx[i + 2] = t
	a[Mesh.ARRAY_INDEX] = idx
	var out := ArrayMesh.new()
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, a)
	return out


## Triangles of `mesh` facing up (Godot winding) at height y.
static func up_faces_at(mesh: Mesh, y: float) -> int:
	var a := mesh.surface_get_arrays(0)
	var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
	var n := 0
	for i in range(0, idx.size(), 3):
		var p := v[idx[i]]
		var q := v[idx[i + 1]]
		var w := v[idx[i + 2]]
		var normal := (w - p).cross(q - p).normalized()
		if normal.y > 0.9 and absf((p.y + q.y + w.y) / 3.0 - y) < 0.01:
			n += 1
	return n


# --- lamps ----------------------------------------------------------------------------------------------------------

## Problems of one assembled lamp entry from crypt_assembly.gd. `mask` = surfaces that count as walls.
static func lamp_problems(space: PhysicsDirectSpaceState3D, entry: Dictionary, mask: int, cell_centre: Vector3) -> Array[String]:
	var out: Array[String] = []
	var lamp: Node3D = entry.node
	var inward: Vector3 = entry.inward
	var label := "lamp %s dir %d" % [entry.slot.cell, entry.slot.dir]
	var emitter := lamp.find_child("light_emitter", true, false) as Node3D
	var flame := lamp.find_child("wall_lamp_flame", true, false) as Node3D
	var e_world: Vector3 = emitter.global_position
	var f_world: Vector3 = flame.global_position
	# Distance out of the wall face, measured against the geometry: ray from the emitter back to the wall.
	var d := ray_distance(space, e_world, e_world - inward * 2.0, mask)
	if absf(d - 0.35) > 0.002:
		out.append("%s: emitter %.4f m from the wall face along -inward, expected 0.35" % [label, d])
	if absf(lamp.global_position.y - cell_centre.y - 2.0) > 0.0001:
		out.append("%s: mounted at y %.3f" % [label, lamp.global_position.y])
	if (lamp.global_basis.z - inward).length() > 0.001:
		out.append("%s: local +Z %s, expected %s" % [label, lamp.basis.z, inward])
	# Flame and emitter must be reachable through open air from the cell centre: nothing between.
	for p: Vector3 in [e_world, f_world, f_world + Vector3(0, 0.09, 0)]:
		var from := Vector3(cell_centre.x, p.y, cell_centre.z)
		if not ray(space, from, p, mask).is_empty():
			out.append("%s: point %s is behind a surface seen from the cell centre" % [label, p])
	var omni := entry.omni as OmniLight3D
	if omni.global_position.distance_to(e_world) > 0.0001:
		out.append("%s: omni %s not at the emitter %s" % [label, omni.global_position, e_world])
	if not is_equal_approx(omni.light_energy, 0.8) or omni.omni_range > 6.0 or omni.shadow_enabled:
		out.append("%s: omni energy %s range %s shadow %s" % [label, omni.light_energy, omni.omni_range, omni.shadow_enabled])
	return out


# --- kit geometry against the contract ------------------------------------------------------------------------------

## Collision planes and heights of `cells` measured by raycast, `origin` = world position of the layout's origin.
## Returns problems; "measured" collects the extreme values for the report.
static func plane_problems(space: PhysicsDirectSpaceState3D, layout: MazeLayout, origin: Vector3, cells: Array[Vector2i],
		mask: int, tol: float, measured: Dictionary) -> Array[String]:
	var out: Array[String] = []
	for cell in cells:
		var c := layout.cell_to_world(cell) + origin
		for ox: float in [-1.4, 0.0, 1.4]:
			for oz: float in [-1.4, 0.0, 1.4]:
				var p := c + Vector3(ox, 0, oz)
				var floor_d := ray_distance(space, p + Vector3(0, 0.5, 0), p - Vector3(0, 0.5, 0), mask)
				_note(measured, "floor_y", 0.5 - floor_d)
				if absf(floor_d - 0.5) > tol:
					out.append("floor at %s: y %.4f" % [p, 0.5 - floor_d])
				var up := ray_distance(space, p + Vector3(0, 0.1, 0), p + Vector3(0, 6, 0), mask) + 0.1
				var ceiling: float = {MazeLayout.Clearance.CROUCH: 1.3, MazeLayout.Clearance.CRAWL: 0.75}.get(
						layout.clearance(cell), -1.0)
				if ceiling > 0.0:
					_note(measured, "ceiling_%s" % ceiling, up)
					if absf(up - ceiling) > tol:
						out.append("ceiling at %s: %.4f, expected %.2f" % [p, up, ceiling])
		for d: int in [0, 1, 2, 3]:
			if not layout.has_wall(cell, d as MazeLayout.Dir):
				continue
			var v := Vector3(dir_x(d), 0, dir_z(d))
			var side := Vector3(v.z, 0, v.x)
			for y: float in [0.1, 1.0, 2.0]:  # above 2.2 a ray from the centre meets the vault web first
				if layout.clearance(cell) != MazeLayout.Clearance.FULL and y > 0.5:
					continue
				for s: float in [-1.2, 0.0, 1.2]:
					var from := c + Vector3(0, y, 0) + side * s
					var dist := ray_distance(space, from, from + v * 3.0, mask)
					_note(measured, "wall_face_from_edge", 2.0 - dist)
					if absf(dist - 1.7) > tol:
						out.append("wall face of %s dir %d at y %.1f s %.1f: %.4f from centre, expected 1.7" % [cell, d, y, s, dist])
	return out


static func dir_x(d: int) -> float:
	return 1.0 if d == 1 else (-1.0 if d == 3 else 0.0)


static func dir_z(d: int) -> float:
	return 1.0 if d == 2 else (-1.0 if d == 0 else 0.0)


static func _note(m: Dictionary, key: String, v: float) -> void:
	var e: Array = m.get(key, [INF, -INF])
	m[key] = [minf(e[0], v), maxf(e[1], v)]


## Contract rules of an assembled set of instances: an arch or wall on every edge, a pier on every corner, floors and
## low ceilings unrotated, strict parity on walls. asm = crypt_assembly.gd after build().
static func rule_problems(asm: RefCounted) -> Array[String]:
	var out: Array[String] = []
	var at := {}
	for i: Dictionary in asm.instances:
		at["%s@%s" % [i.piece, i.at.snappedf(0.01)]] = i
		if i.piece in ["floor", "ceiling_crouch", "ceiling_crawl"] and absf(i.yaw) > 0.0001:
			out.append("%s at %s is rotated" % [i.piece, i.at])
	var layout: MazeLayout = asm.layout
	var s: float = asm.cell_size
	var r: Rect2i = asm.rect
	for y in range(r.position.y, r.end.y):
		for x in range(r.position.x, r.end.x):
			var cell := Vector2i(x, y)
			for d: int in [0, 1, 2, 3]:
				var e: Vector3 = asm.edge_centre(cell, d)
				var key: String = ("wall@%s" if layout.has_wall(cell, d as MazeLayout.Dir) else "arch@%s") % e.snappedf(0.01)
				if not at.has(key):
					out.append("edge %s dir %d: missing %s" % [cell, d, key])
	for y in range(r.position.y, r.end.y + 1):
		for x in range(r.position.x, r.end.x + 1):
			if not at.has("pier@%s" % Vector3(x * s, 0, y * s).snappedf(0.01)):
				out.append("corner (%d, %d): no pier" % [x, y])
	for w: Dictionary in asm.wall_items:
		if bool(w.rotated_180) != (posmod(int(w.along), 2) == 1):
			out.append("wall %s breaks the parity" % w.key)
	return out


## Lamps whose omni range reaches a world AABB: the Mobile renderer's limit is 8 omni per mesh.
static func lights_reaching(lamps: Array[Dictionary], box: AABB) -> int:
	var n := 0
	for l: Dictionary in lamps:
		var o := l.omni as OmniLight3D
		var p := o.global_position
		var nearest := p.clamp(box.position, box.end)
		if nearest.distance_to(p) <= o.omni_range:
			n += 1
	return n
