## T017 (qa): a 3x3 MazeLayout for the self-tests: open inside, closed boundary, all FULL, one lamp on each outer side of
## the middle row. Owner: qa.
extends MazeLayout

func size() -> Vector2i:
	return Vector2i(3, 3)


func cell_size_m() -> float:
	return 4.0


func get_seed() -> int:
	return 1


func start_cell() -> Vector2i:
	return Vector2i(1, 1)


func in_bounds(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < 3 and cell.y < 3


func has_wall(cell: Vector2i, dir: Dir) -> bool:
	var o: Vector2i = {Dir.NORTH: Vector2i(0, -1), Dir.EAST: Vector2i(1, 0), Dir.SOUTH: Vector2i(0, 1), Dir.WEST: Vector2i(-1, 0)}[dir]
	return not in_bounds(cell + o)


func clearance(_cell: Vector2i) -> Clearance:
	return Clearance.FULL


func lamp_slots() -> Array[Dictionary]:
	return [{"cell": Vector2i(0, 1), "dir": Dir.WEST}, {"cell": Vector2i(2, 1), "dir": Dir.EAST}]


func world_to_cell(world_position: Vector3) -> Vector2i:
	return Vector2i(floori(world_position.x / 4.0), floori(world_position.z / 4.0))


func cell_to_world(cell: Vector2i) -> Vector3:
	return Vector3((cell.x + 0.5) * 4.0, 0.0, (cell.y + 0.5) * 4.0)
