## Entry point of the maze module: creates layouts and the 3D world node.
## Owner: orchestrator. Implemented in maze/internal (internal/maze_factory_impl.gd extends this).
@abstract
class_name MazeFactory
extends RefCounted

## The one maze shipped in this game (fixed so every player and every save share it).
const GAME_SEED := 20261025
const GAME_SIZE := Vector2i(20, 20)

const _IMPL_PATH := "res://modules/maze/internal/maze_factory_impl.gd"


## Returns the module's implementation. Call this, never `new()` on internal classes.
static func create() -> MazeFactory:
	return load(_IMPL_PATH).new()


## Generates a layout. Deterministic for (seed, size). Every open cell reachable from start_cell().
@abstract func make_layout(seed_value: int = GAME_SEED, grid_size: Vector2i = GAME_SIZE) -> MazeLayout


## Creates the 3D maze world node (not yet built). Add it to the tree, then call build().
@abstract func make_world() -> MazeWorld
