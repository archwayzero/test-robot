## MazeLayout implementation: integer-only, seeded generation (own RandomNumberGenerator, never Core.rng).
##
## Steps (all deterministic for (seed, size)):
##  1. perfect maze by iterative recursive backtracker from the start cell,
##  2. ~10% extra openings (cell count / 10) on remaining interior walls to create loops, never opening a full 2x2
##     room (keeps corridors corridor-like),
##  3. 4-8 low cells (>= 2 CROUCH, >= 2 CRAWL), each with >= 2 open edges, so that removing ALL low cells
##     still leaves every other cell reachable from the start (low passages are never the only route),
##  4. lamp slots: FULL cells at BFS distance % 3 == 0 from the start with no lamp in an edge-adjacent
##     cell, mounted on an existing wall of that cell.
extends MazeLayout

const CELL_SIZE_M := 4.0

# Open-edge bit flags per cell, indexed like MazeLayout.Dir.
const BIT := [1, 2, 4, 8]
const DX := [0, 1, 0, -1]
const DY := [-1, 0, 1, 0]
const OPPOSITE := [2, 3, 0, 1]

var _seed: int
var _size: Vector2i
var _start: Vector2i
var _open: PackedByteArray  # per cell, bit d set = edge d is open
var _clear: PackedByteArray  # per cell, Clearance value
var _lamps: Array[Dictionary] = []

## Generation statistics (informational, not part of the public interface).
var stats := {}


func _init(seed_value: int, grid_size: Vector2i) -> void:
	assert(grid_size.x >= 2 and grid_size.y >= 2, "maze: grid must be at least 2x2")
	_seed = seed_value
	_size = grid_size
	_start = Vector2i(grid_size.x / 2, grid_size.y / 2)
	var n := grid_size.x * grid_size.y
	_open = PackedByteArray()
	_open.resize(n)
	_clear = PackedByteArray()
	_clear.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	_carve(rng)
	stats["loops_added"] = _add_loops(rng)
	_place_low_cells(rng)
	_place_lamps(rng)
	stats["open_cells"] = n
	stats["low_crouch"] = _count_clearance(Clearance.CROUCH)
	stats["low_crawl"] = _count_clearance(Clearance.CRAWL)
	stats["lamp_slots"] = _lamps.size()
	stats["start_cell"] = _start


# --- MazeLayout -----------------------------------------------------------------------------------------

func size() -> Vector2i:
	return _size


func cell_size_m() -> float:
	return CELL_SIZE_M


func get_seed() -> int:
	return _seed


func start_cell() -> Vector2i:
	return _start


func in_bounds(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < _size.x and cell.y < _size.y


func has_wall(cell: Vector2i, dir: Dir) -> bool:
	if not in_bounds(cell):
		return true
	return (_open[_idx(cell)] & BIT[dir]) == 0


func clearance(cell: Vector2i) -> Clearance:
	if not in_bounds(cell):
		return Clearance.FULL
	return _clear[_idx(cell)] as Clearance


func lamp_slots() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for l in _lamps:
		out.append(l.duplicate())
	return out


func world_to_cell(world_position: Vector3) -> Vector2i:
	return Vector2i(floori(world_position.x / CELL_SIZE_M), floori(world_position.z / CELL_SIZE_M))


func cell_to_world(cell: Vector2i) -> Vector3:
	return Vector3((cell.x + 0.5) * CELL_SIZE_M, 0.0, (cell.y + 0.5) * CELL_SIZE_M)


# --- generation -----------------------------------------------------------------------------------------

func _idx(c: Vector2i) -> int:
	return c.y * _size.x + c.x


func _cell(i: int) -> Vector2i:
	return Vector2i(i % _size.x, i / _size.x)


func _open_edge(c: Vector2i, d: int) -> void:
	var nb := Vector2i(c.x + DX[d], c.y + DY[d])
	_open[_idx(c)] |= BIT[d]
	_open[_idx(nb)] |= BIT[OPPOSITE[d]]


func _is_open(c: Vector2i, d: int) -> bool:
	return in_bounds(c) and (_open[_idx(c)] & BIT[d]) != 0


func _carve(rng: RandomNumberGenerator) -> void:
	var visited := PackedByteArray()
	visited.resize(_open.size())
	var stack: Array[Vector2i] = [_start]
	visited[_idx(_start)] = 1
	while not stack.is_empty():
		var c: Vector2i = stack.back()
		var options: Array[int] = []
		for d in 4:
			var nb := Vector2i(c.x + DX[d], c.y + DY[d])
			if in_bounds(nb) and visited[_idx(nb)] == 0:
				options.append(d)
		if options.is_empty():
			stack.pop_back()
			continue
		var d: int = options[rng.randi_range(0, options.size() - 1)]
		var nb := Vector2i(c.x + DX[d], c.y + DY[d])
		_open_edge(c, d)
		visited[_idx(nb)] = 1
		stack.append(nb)


## Would opening edge (c, d) complete a fully open 2x2 block?
func _makes_room(c: Vector2i, d: int) -> bool:
	# The edge is shared by up to two 2x2 blocks; check the other three interior edges of each.
	if d == Dir.EAST:  # vertical edge between c and c+x; blocks above and below
		for oy in [-1, 1]:
			var r := Vector2i(c.x, c.y + oy)
			if not in_bounds(r):
				continue
			var vdir := Dir.NORTH if oy == -1 else Dir.SOUTH
			if _is_open(c, vdir) and _is_open(Vector2i(c.x + 1, c.y), vdir) and _is_open(r, Dir.EAST):
				return true
	else:  # SOUTH: horizontal edge between c and c+y; blocks left and right
		for ox in [-1, 1]:
			var r := Vector2i(c.x + ox, c.y)
			if not in_bounds(r):
				continue
			var hdir := Dir.WEST if ox == -1 else Dir.EAST
			if _is_open(c, hdir) and _is_open(Vector2i(c.x, c.y + 1), hdir) and _is_open(r, Dir.SOUTH):
				return true
	return false


func _add_loops(rng: RandomNumberGenerator) -> int:
	# Candidate interior walls, encoded as cell_index * 4 + dir (EAST or SOUTH only).
	var cands: Array[int] = []
	for y in _size.y:
		for x in _size.x:
			var c := Vector2i(x, y)
			if x < _size.x - 1 and not _is_open(c, Dir.EAST):
				cands.append(_idx(c) * 4 + Dir.EAST)
			if y < _size.y - 1 and not _is_open(c, Dir.SOUTH):
				cands.append(_idx(c) * 4 + Dir.SOUTH)
	_shuffle(cands, rng)
	var want := maxi(1, (_size.x * _size.y) / 10)
	var added := 0
	for e in cands:
		if added >= want:
			break
		var c := _cell(e / 4)
		var d := e % 4
		if _makes_room(c, d):
			continue
		_open_edge(c, d)
		added += 1
	return added


func _shuffle(a: Array[int], rng: RandomNumberGenerator) -> void:
	for i in range(a.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t := a[i]
		a[i] = a[j]
		a[j] = t


func _degree(c: Vector2i) -> int:
	var n := 0
	for d in 4:
		if _is_open(c, d):
			n += 1
	return n


## Number of cells reachable from the start without entering any cell with blocked[i] != 0.
func _reach_count(blocked: PackedByteArray) -> int:
	var seen := PackedByteArray()
	seen.resize(_open.size())
	var queue: Array[int] = [_idx(_start)]
	seen[queue[0]] = 1
	var head := 0
	while head < queue.size():
		var c := _cell(queue[head])
		head += 1
		for d in 4:
			if not _is_open(c, d):
				continue
			var ni := _idx(Vector2i(c.x + DX[d], c.y + DY[d]))
			if seen[ni] == 0 and blocked[ni] == 0:
				seen[ni] = 1
				queue.append(ni)
	return queue.size()


## BFS distance (in cells) from the start to every cell.
func _distances() -> PackedInt32Array:
	var dist := PackedInt32Array()
	dist.resize(_open.size())
	dist.fill(-1)
	var queue: Array[int] = [_idx(_start)]
	dist[queue[0]] = 0
	var head := 0
	while head < queue.size():
		var ci := queue[head]
		var c := _cell(ci)
		head += 1
		for d in 4:
			if not _is_open(c, d):
				continue
			var ni := _idx(Vector2i(c.x + DX[d], c.y + DY[d]))
			if dist[ni] < 0:
				dist[ni] = dist[ci] + 1
				queue.append(ni)
	return dist


func _place_low_cells(rng: RandomNumberGenerator) -> void:
	var n := _open.size()
	var want := rng.randi_range(4, 8)
	# Straight 2-way passages first (they read as a low passage), then any cell with >= 2 openings.
	var straight: Array[int] = []
	var other: Array[int] = []
	for i in n:
		var c := _cell(i)
		if c == _start or _degree(c) < 2:
			continue
		var ns := _is_open(c, Dir.NORTH) and _is_open(c, Dir.SOUTH)
		var ew := _is_open(c, Dir.EAST) and _is_open(c, Dir.WEST)
		if _degree(c) == 2 and (ns or ew):
			straight.append(i)
		else:
			other.append(i)
	_shuffle(straight, rng)
	_shuffle(other, rng)
	var cands := straight + other
	var blocked := PackedByteArray()
	blocked.resize(n)
	var chosen: Array[int] = []
	for i in cands:
		if chosen.size() >= want:
			break
		var c := _cell(i)
		# Keep low cells apart (no two in neighbouring cells, including diagonals) and away from the start.
		var near := false
		for j in chosen:
			var o := _cell(j)
			if absi(o.x - c.x) <= 1 and absi(o.y - c.y) <= 1:
				near = true
				break
		if near or (absi(c.x - _start.x) <= 1 and absi(c.y - _start.y) <= 1):
			continue
		blocked[i] = 1
		if _reach_count(blocked) == n - chosen.size() - 1:
			chosen.append(i)
		else:
			blocked[i] = 0
	# First two CROUCH, next two CRAWL, the rest alternate by the RNG.
	for k in chosen.size():
		var cl := Clearance.CROUCH
		if k == 2 or k == 3:
			cl = Clearance.CRAWL
		elif k >= 4:
			cl = Clearance.CROUCH if rng.randi_range(0, 1) == 0 else Clearance.CRAWL
		_clear[chosen[k]] = cl


func _place_lamps(rng: RandomNumberGenerator) -> void:
	var dist := _distances()
	# Visit cells in (distance, index) order so placement follows the corridors outward from the start.
	var order: Array[int] = []
	for i in _open.size():
		order.append(i)
	order.sort_custom(func(a: int, b: int) -> bool:
		return dist[a] < dist[b] or (dist[a] == dist[b] and a < b))
	var lamp_at := PackedByteArray()
	lamp_at.resize(_open.size())
	for i in order:
		if dist[i] % 3 != 0 or _clear[i] != Clearance.FULL:
			continue
		var c := _cell(i)
		var near := false
		for d in 4:
			var o := Vector2i(c.x + DX[d], c.y + DY[d])
			if in_bounds(o) and lamp_at[_idx(o)] != 0:
				near = true
		if near:
			continue
		var walls: Array[int] = []
		for d in 4:
			if not _is_open(c, d):
				walls.append(d)
		if walls.is_empty():
			continue
		lamp_at[i] = 1
		_lamps.append({"cell": c, "dir": walls[rng.randi_range(0, walls.size() - 1)]})


func _count_clearance(cl: int) -> int:
	var n := 0
	for v in _clear:
		if v == cl:
			n += 1
	return n
