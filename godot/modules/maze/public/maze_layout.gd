## The maze as a grid of cells. Pure data: no nodes, no rendering. Same seed -> same layout, everywhere.
##
## Cell coordinates: Vector2i(x, y), x = column (world +X), y = row (world +Z). Cell (0,0) is at world origin corner;
## cell centre = Vector3((x + 0.5) * cell_size_m(), 0, (y + 0.5) * cell_size_m()). Floor is at y = 0.
## Walls sit on cell edges. The outer boundary is always closed (there is no exit, by design).
##
## Owner: orchestrator. Implemented in maze/internal. Obtain one with MazeFactory (public/maze_factory.gd).
@abstract
class_name MazeLayout
extends RefCounted

## Ceiling clearance class of a cell (drives which kit piece is used and which stance can pass).
enum Clearance { FULL, CROUCH, CRAWL }

## Edge directions for has_wall().
enum Dir { NORTH, EAST, SOUTH, WEST }  # NORTH = -Z (row - 1), EAST = +X, SOUTH = +Z, WEST = -X


## Grid size in cells (width = x, height = y).
@abstract func size() -> Vector2i


## Edge length of one square cell in meters (see docs/contracts/crypt-kit.md).
@abstract func cell_size_m() -> float


## The seed this layout was generated from.
@abstract func get_seed() -> int


## Cell where a new game starts.
@abstract func start_cell() -> Vector2i


## True if `cell` is inside the grid.
@abstract func in_bounds(cell: Vector2i) -> bool


## True if there is a wall on edge `dir` of `cell`. Out-of-bounds neighbours always count as walls.
@abstract func has_wall(cell: Vector2i, dir: Dir) -> bool


## Clearance of `cell` (FULL for normal corridors; CROUCH / CRAWL for low passages).
@abstract func clearance(cell: Vector2i) -> Clearance


## Cells at which a wall lamp is mounted (with the wall direction it hangs on), as [{"cell": Vector2i, "dir": Dir}].
@abstract func lamp_slots() -> Array[Dictionary]


## World position (floor height) -> cell. May return out-of-bounds cells; check in_bounds().
@abstract func world_to_cell(world_position: Vector3) -> Vector2i


## Cell -> world position of the cell centre at floor height.
@abstract func cell_to_world(cell: Vector2i) -> Vector3
