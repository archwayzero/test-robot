## Rule checks shared by the T018 tests. Plain functions that return one message per violation, so the same check runs
## on the real world and on a deliberately broken input (TEST_PLAN: every measuring check proves it can fail).
extends RefCounted

const Assembly := preload("res://modules/maze/internal/maze_assembly.gd")
const OMNI_LIMIT := 8
const WALL_RAY_DISTANCE := 1.7  # cell centre to wall face


static func _edge_key(at: Vector3) -> Vector2i:
	return Vector2i(roundi(at.x * 2.0), roundi(at.z * 2.0))


## Every cell edge holds exactly one wall (where has_wall) or one arch (where open).
static func edge_errors(items: Array, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	var edges := {}
	for item in items:
		if item.piece == &"wall" or item.piece == &"arch":
			var key := _edge_key(item.xform.origin)
			if edges.has(key):
				errors.append("two pieces on edge %s" % key)
			edges[key] = item.piece
	var sz := layout.size()
	for y in sz.y:
		for x in sz.x:
			for d in Assembly.DIRS:
				var c := Vector2i(x, y)
				var key := _edge_key(layout.cell_to_world(c) + Assembly.dir_vector(d) * layout.cell_size_m() * 0.5)
				var want: StringName = &"wall" if layout.has_wall(c, d) else &"arch"
				if edges.get(key, &"") != want:
					errors.append("edge %s dir %d: want %s, got %s" % [c, d, want, edges.get(key, &"none")])
	return errors


## Every grid corner holds exactly one unrotated pier, collinear corners included.
static func pier_errors(items: Array, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	var at := {}
	var s := layout.cell_size_m()
	for item in items:
		if item.piece == &"pier":
			var o: Vector3 = item.xform.origin
			at[Vector2i(roundi(o.x / s), roundi(o.z / s))] = int(at.get(Vector2i(roundi(o.x / s), roundi(o.z / s)), 0)) + 1
	for y in layout.size().y + 1:
		for x in layout.size().x + 1:
			if at.get(Vector2i(x, y), 0) != 1:
				errors.append("corner (%d, %d) has %d piers" % [x, y, at.get(Vector2i(x, y), 0)])
	return errors


## Interior corners where two walls run straight through: the greybox skipped their piers.
static func collinear_corners(layout: MazeLayout) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in range(1, layout.size().y):
		for x in range(1, layout.size().x):
			var c := Vector2i(x, y)
			var nw := c - Vector2i(1, 1)
			var ns := layout.has_wall(c, MazeLayout.Dir.WEST) and layout.has_wall(nw, MazeLayout.Dir.EAST)
			var ew := layout.has_wall(c, MazeLayout.Dir.NORTH) and layout.has_wall(nw, MazeLayout.Dir.SOUTH)
			if ns or ew:
				out.append(c)
	return out


## Floors and low ceilings never rotate; each cell has one floor and the ceiling its clearance asks for.
static func cell_errors(items: Array, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	var by_cell := {}
	for item in items:
		if item.piece in [&"floor", &"vault_bay", &"ceiling_crouch", &"ceiling_crawl"]:
			if item.piece != &"vault_bay" and not item.xform.basis.is_equal_approx(Basis.IDENTITY):
				errors.append("%s rotated in %s" % [item.piece, item.cell])
			var key := "%s %s" % [item.piece, layout.world_to_cell(item.xform.origin)]
			by_cell[key] = int(by_cell.get(key, 0)) + 1
	var ceiling := {
		MazeLayout.Clearance.FULL: &"vault_bay",
		MazeLayout.Clearance.CROUCH: &"ceiling_crouch",
		MazeLayout.Clearance.CRAWL: &"ceiling_crawl",
	}
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			for piece: StringName in [&"floor", ceiling[layout.clearance(c)]]:
				if by_cell.get("%s %s" % [piece, c], 0) != 1:
					errors.append("cell %s needs one %s" % [c, piece])
	return errors


## Walls: rotated 180 degrees exactly on odd world cells along the run, seen in the actual basis.
static func wall_parity_errors(items: Array, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	var s := layout.cell_size_m()
	for item in items:
		if item.piece != &"wall":
			continue
		var o: Vector3 = item.xform.origin
		var x_axis: Vector3 = item.xform.basis.x
		var along_x := absf(x_axis.x) > 0.5
		var along := floori((o.x if along_x else o.z) / s)
		var flipped := (x_axis.x < 0.0) if along_x else (x_axis.z > 0.0)
		if flipped != (posmod(along, 2) == 1):
			errors.append("wall at %s: flipped %s on cell %d" % [o, flipped, along])
	return errors


## Walls in a straight run alternate strictly: neighbours along the run never share a rotation.
static func wall_run_errors(items: Array, s: float) -> PackedStringArray:
	var errors := PackedStringArray()
	var flip := {}  # edge key -> rotated
	var along_x := {}  # edge key -> run direction
	for item in items:
		if item.piece == &"wall":
			var key := _edge_key(item.xform.origin)
			along_x[key] = absf(item.xform.basis.x.x) > 0.5
			flip[key] = item.xform.basis.x.x < 0.0 or item.xform.basis.x.z > 0.0
	var step := roundi(s * 2.0)
	for key: Vector2i in flip:
		var next: Vector2i = key + (Vector2i(step, 0) if along_x[key] else Vector2i(0, step))
		if flip.has(next) and along_x[next] == along_x[key] and flip[next] == flip[key]:
			errors.append("walls %s and %s share a rotation" % [key, next])
	return errors


## Each mesh of the world against the omnis whose AABB touches it, as the engine pairs them. Worst count.
static func max_omnis_per_mesh(root: Node, range_override := -1.0) -> int:
	var omnis: Array[Dictionary] = []
	for omni: OmniLight3D in root.find_children("*", "OmniLight3D", true, false):
		omnis.append({"at": omni.global_position, "r": omni.omni_range if range_override < 0.0 else range_override})
	var worst := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var box: AABB = mi.global_transform * mi.mesh.get_aabb()
		var n := 0
		for l in omnis:
			var half := Vector3.ONE * (l.r as float)
			if box.intersects(AABB((l.at as Vector3) - half, half * 2.0)):
				n += 1
		worst = maxi(worst, n)
	return worst


## Same count for one box, for proving the helper can exceed the limit on a known-bad grouping.
static func omnis_touching(root: Node, box: AABB) -> int:
	var n := 0
	for omni: OmniLight3D in root.find_children("*", "OmniLight3D", true, false):
		var half := Vector3.ONE * omni.omni_range
		if box.intersects(AABB(omni.global_position - half, half * 2.0)):
			n += 1
	return n


## Contract flags on a material of the kit.
static func material_errors(mat: Material) -> PackedStringArray:
	var errors := PackedStringArray()
	var m := mat as StandardMaterial3D
	if m == null:
		return PackedStringArray(["not a StandardMaterial3D: %s" % mat])
	if not m.vertex_color_use_as_albedo:
		errors.append("%s: vertex_color_use_as_albedo off" % m.resource_name)
	if m.vertex_color_is_srgb:
		errors.append("%s: vertex_color_is_srgb on" % m.resource_name)
	if m.texture_filter != BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC:
		errors.append("%s: texture_filter %d" % [m.resource_name, m.texture_filter])
	return errors


## A lamp mount against the contract: wall face, y 2.0, local +Z into the cell, upright.
static func lamp_errors(mount: Transform3D, slot: Dictionary, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	var outward := Assembly.dir_vector(slot.dir)
	var want := layout.cell_to_world(slot.cell) + outward * (layout.cell_size_m() * 0.5 - 0.3) + Vector3(0, 2.0, 0)
	if not mount.origin.is_equal_approx(want):
		errors.append("lamp %s at %s, want %s" % [slot.cell, mount.origin, want])
	if not mount.basis.z.is_equal_approx(-outward):
		errors.append("lamp %s +Z %s, want %s" % [slot.cell, mount.basis.z, -outward])
	if not mount.basis.y.is_equal_approx(Vector3.UP):
		errors.append("lamp %s not upright" % slot.cell)
	if absf(mount.basis.determinant() - 1.0) > 0.001:
		errors.append("lamp %s mirrored or scaled" % slot.cell)
	return errors


## Rays from cell centres over every edge, at `height`: hit exactly where has_wall, at the wall face.
static func collision_errors(space: PhysicsDirectSpaceState3D, layout: MazeLayout, height: float) -> PackedStringArray:
	var errors := PackedStringArray()
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			for d in Assembly.DIRS:
				var from := layout.cell_to_world(c) + Vector3(0, height, 0)
				var to := from + Assembly.dir_vector(d) * layout.cell_size_m()
				var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, to, 1))
				var wall := layout.has_wall(c, d)
				if wall != (not hit.is_empty()):
					errors.append("%s dir %d wall %s hit %s" % [c, d, wall, not hit.is_empty()])
				elif wall and absf(from.distance_to(hit.position) - WALL_RAY_DISTANCE) > 0.01:
					errors.append("%s dir %d face at %.3f" % [c, d, from.distance_to(hit.position)])
	return errors


## True if a capsule of `height` standing on the floor at `at` touches world geometry on layer 1.
static func capsule_blocked(space: PhysicsDirectSpaceState3D, at: Vector3, height: float) -> bool:
	var shape := CapsuleShape3D.new()
	shape.radius = minf(0.28, height * 0.5 - 0.01)
	shape.height = height
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.collision_mask = 1
	q.transform = Transform3D(Basis.IDENTITY, at + Vector3(0, height * 0.5 + 0.03, 0))
	return not space.intersect_shape(q, 1).is_empty()


## Stance heights by the layout's clearance class (player module constants, contract "Clearances").
static func stance_height(cl: MazeLayout.Clearance) -> float:
	match cl:
		MazeLayout.Clearance.CROUCH:
			return 1.0
		MazeLayout.Clearance.CRAWL:
			return 0.5
	return 1.75


## Each open edge, walked in 5 steps from centre to centre by the tallest stance both cells allow.
static func passage_errors(space: PhysicsDirectSpaceState3D, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			for d: MazeLayout.Dir in [MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH]:
				if layout.has_wall(c, d):
					continue
				var n := c + Assembly.dir_offset(d)
				var height := minf(stance_height(layout.clearance(c)), stance_height(layout.clearance(n)))
				var a := layout.cell_to_world(c)
				var b := layout.cell_to_world(n)
				for i in 5:
					if capsule_blocked(space, a.lerp(b, i / 4.0), height):
						errors.append("%s to %s blocked at step %d for height %.2f" % [c, n, i, height])
	return errors


## A low cell must block the next stance up (player stand-up checks rely on it).
static func low_cell_errors(space: PhysicsDirectSpaceState3D, layout: MazeLayout) -> PackedStringArray:
	var errors := PackedStringArray()
	for y in layout.size().y:
		for x in layout.size().x:
			var c := Vector2i(x, y)
			var cl := layout.clearance(c)
			if cl == MazeLayout.Clearance.FULL:
				continue
			var taller := 1.75 if cl == MazeLayout.Clearance.CROUCH else 1.0
			if not capsule_blocked(space, layout.cell_to_world(c), taller):
				errors.append("cell %s clearance %d lets height %.2f through" % [c, cl, taller])
			if capsule_blocked(space, layout.cell_to_world(c), stance_height(cl)):
				errors.append("cell %s clearance %d blocks its own stance" % [c, cl])
	return errors


## Everything the build produced, as bytes: merged meshes, collision, occluders, lamps.
static func digest(root: Node) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var arrays: Array = mi.mesh.surface_get_arrays(i)
			ctx.update((arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).to_byte_array())
			ctx.update((arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).to_byte_array())
	for shape: CollisionShape3D in root.find_children("*", "CollisionShape3D", true, false):
		ctx.update((shape.shape as ConcavePolygonShape3D).get_faces().to_byte_array())
	for occ: OccluderInstance3D in root.find_children("*", "OccluderInstance3D", true, false):
		ctx.update((occ.occluder as ArrayOccluder3D).vertices.to_byte_array())
	for omni: OmniLight3D in root.find_children("*", "OmniLight3D", true, false):
		ctx.update(var_to_bytes((omni.get_parent() as Node3D).transform * omni.position))
	return ctx.finish().hex_encode()


## Plan items that do not appear in the merged geometry of `chunk`: every vertex of the piece must exist there.
static func missing_items(items: Array, positions: Dictionary, kit_mesh_vertices: Dictionary, chunk_origin: Vector3) -> PackedStringArray:
	var errors := PackedStringArray()
	for item in items:
		var xform: Transform3D = item.xform
		xform.origin -= chunk_origin
		var vertices: PackedVector3Array = kit_mesh_vertices[item.piece]
		for i in range(0, vertices.size(), 16):
			if not _near_key(positions, snap_key(xform * vertices[i])):
				errors.append("%s at %s: vertex %s absent" % [item.piece, item.xform.origin, vertices[i]])
				break
	return errors


static func snap_key(p: Vector3) -> Vector3i:
	return Vector3i(roundi(p.x * 200.0), roundi(p.y * 200.0), roundi(p.z * 200.0))


## Merged positions are compressed, so a vertex may round into the neighbouring 5 mm key.
static func _near_key(positions: Dictionary, key: Vector3i) -> bool:
	if positions.has(key):
		return true
	for x in range(-1, 2):
		for y in range(-1, 2):
			for z in range(-1, 2):
				if positions.has(key + Vector3i(x, y, z)):
					return true
	return false
