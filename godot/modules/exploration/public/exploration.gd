## Tracks which maze cells the player has visited (fog-of-war state).
## Listens to Core.player_moved; a cell counts as visited when the player's position is inside it.
## Persists to StateKeys.EXPLORATION_VISITED / EXPLORATION_COUNT and restores from them (after a load).
##
## Owner: orchestrator. Implemented in exploration/internal; create via ExplorationFactory.create().
@abstract
class_name Exploration
extends Node

## Emitted once per newly visited cell (not for already-visited cells).
signal cell_explored(cell: Vector2i)

## Emitted after the visited set was replaced from GameState (e.g. after loading a save).
signal restored()


## Binds to a layout and starts listening. Marks the layout's start cell visited if nothing is stored yet.
## If StateKeys.EXPLORATION_VISITED exists and StateKeys.MAZE_SEED matches the layout, restores from it.
@abstract func setup(layout: MazeLayout) -> void


@abstract func is_explored(cell: Vector2i) -> bool


@abstract func explored_count() -> int


## All visited cells (order unspecified).
@abstract func get_explored_cells() -> Array[Vector2i]
