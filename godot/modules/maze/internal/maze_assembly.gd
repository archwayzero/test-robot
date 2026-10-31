## Pure assembly plan: which kit piece goes where, from a MazeLayout, by docs/contracts/crypt-kit.md "Rules for the
## assembler". No nodes and no meshes, so the rules can be checked (and broken on purpose) without building anything.
extends RefCounted

const WALL_TINTS: Array[float] = [0.96, 1.0, 1.04]  # one wall mesh repeats every 4 m; three steps of +-4%
const LAMP_Y := 2.0
const WALL_HALF := 0.3
const DIRS: Array[MazeLayout.Dir] = [
	MazeLayout.Dir.NORTH, MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH, MazeLayout.Dir.WEST]

# Exact quarter-turn bases: no trigonometry, so the same input always gives the same bytes.
const YAW_0 := Basis.IDENTITY
const YAW_90 := Basis(Vector3(0, 0, -1), Vector3(0, 1, 0), Vector3(1, 0, 0))
const YAW_180 := Basis(Vector3(-1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1))
const YAW_270 := Basis(Vector3(0, 0, 1), Vector3(0, 1, 0), Vector3(-1, 0, 0))


static func dir_offset(d: MazeLayout.Dir) -> Vector2i:
	match d:
		MazeLayout.Dir.NORTH:
			return Vector2i(0, -1)
		MazeLayout.Dir.EAST:
			return Vector2i(1, 0)
		MazeLayout.Dir.SOUTH:
			return Vector2i(0, 1)
	return Vector2i(-1, 0)


static func dir_vector(d: MazeLayout.Dir) -> Vector3:
	var o := dir_offset(d)
	return Vector3(o.x, 0.0, o.y)


## Every kit piece of the maze: [{piece: StringName, xform: Transform3D, cell: Vector2i (owning cell), tint: float,
## flipped: bool}]. Corners belong to the cell south-east of them, clamped into the grid at the far boundary.
static func items(layout: MazeLayout) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var sz := layout.size()
	for y in sz.y:
		for x in sz.x:
			_add_cell(out, layout, Vector2i(x, y))
	var s := layout.cell_size_m()
	for y in sz.y + 1:
		for x in sz.x + 1:
			out.append(_item(&"pier", YAW_0, Vector3(x * s, 0, y * s), Vector2i(mini(x, sz.x - 1), mini(y, sz.y - 1))))
	return out


static func _add_cell(out: Array[Dictionary], layout: MazeLayout, cell: Vector2i) -> void:
	var centre := layout.cell_to_world(cell)
	out.append(_item(&"floor", YAW_0, centre, cell))  # never rotated
	match layout.clearance(cell):
		MazeLayout.Clearance.CROUCH:
			out.append(_item(&"ceiling_crouch", YAW_0, centre, cell))  # never rotated
		MazeLayout.Clearance.CRAWL:
			out.append(_item(&"ceiling_crawl", YAW_0, centre, cell))  # never rotated
		_:
			out.append(_item(&"vault_bay", YAW_0, centre, cell))
	# Each edge once: north and west always, south and east only on the far boundary.
	for d in DIRS:
		var far_side := d == MazeLayout.Dir.SOUTH or d == MazeLayout.Dir.EAST
		if far_side and layout.in_bounds(cell + dir_offset(d)):
			continue
		_add_edge(out, layout, cell, d)


static func _add_edge(out: Array[Dictionary], layout: MazeLayout, cell: Vector2i, d: MazeLayout.Dir) -> void:
	var along_x := d == MazeLayout.Dir.NORTH or d == MazeLayout.Dir.SOUTH
	var at := layout.cell_to_world(cell) + dir_vector(d) * layout.cell_size_m() * 0.5
	if not layout.has_wall(cell, d):
		out.append(_item(&"arch", YAW_0 if along_x else YAW_90, at, cell))
		return
	# Strict alternation by world cell parity along the run, never by instance order (contract: 0.570 vs -0.004).
	var flipped := posmod(cell.x if along_x else cell.y, 2) == 1
	var basis: Basis
	if along_x:
		basis = YAW_180 if flipped else YAW_0
	else:
		basis = YAW_270 if flipped else YAW_90
	var item := _item(&"wall", basis, at, cell)
	item.flipped = flipped
	item.tint = wall_tint(cell)
	out.append(item)


static func wall_tint(cell: Vector2i) -> float:
	return WALL_TINTS[posmod(cell.x * 7 + cell.y * 13, WALL_TINTS.size())]


static func _item(piece: StringName, basis: Basis, at: Vector3, cell: Vector2i) -> Dictionary:
	return {"piece": piece, "xform": Transform3D(basis, at), "cell": cell, "tint": 1.0, "flipped": false}


## Mount of a lamp at `slot` {cell, dir}: origin on the wall face at LAMP_Y, local +Z from the wall into the cell.
static func lamp_mount(layout: MazeLayout, slot: Dictionary) -> Transform3D:
	var outward := dir_vector(slot.dir)
	var inward := -outward
	var at := layout.cell_to_world(slot.cell) + outward * (layout.cell_size_m() * 0.5 - WALL_HALF)
	return Transform3D(Basis(Vector3.UP.cross(inward), Vector3.UP, inward), at + Vector3(0, LAMP_Y, 0))
