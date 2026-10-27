## MazeFactory implementation (loaded by public/maze_factory.gd at this exact path).
extends MazeFactory

const LayoutImpl := preload("res://modules/maze/internal/maze_layout_impl.gd")
const WorldImpl := preload("res://modules/maze/internal/maze_world_impl.gd")


func make_layout(seed_value: int = GAME_SEED, grid_size: Vector2i = GAME_SIZE) -> MazeLayout:
	return LayoutImpl.new(seed_value, grid_size)


func make_world() -> MazeWorld:
	var world: MazeWorld = WorldImpl.new()
	world.name = "MazeWorld"
	return world
