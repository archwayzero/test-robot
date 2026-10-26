## Mini-map in the top-left corner: visited cells show the maze layout (walls), unvisited cells are dark; a marker
## shows the player's cell and facing. Tapping it opens the large map (full screen, same rendering, scaled up);
## tapping the large map (or its close button) closes it. While open: game phase StateKeys.PHASE_MAP_OPEN is set
## by `game` in response to large_map_toggled; the minimap itself does not pause anything.
## Drawn with Godot 2D primitives (no image assets). Updates on Exploration.cell_explored and Core.player_moved.
##
## Owner: orchestrator. Implemented in minimap/internal; instance via MinimapFactory.create().
@abstract
class_name Minimap
extends Control

signal large_map_toggled(open: bool)

## Size of the small map in the top-left corner, in viewport pixels at the 1280x590 base resolution.
const SMALL_SIZE := Vector2(200, 200)
const MARGIN := Vector2(16, 16)


@abstract func setup(layout: MazeLayout, exploration: Exploration) -> void


@abstract func open_large_map() -> void


@abstract func close_large_map() -> void


@abstract func is_large_map_open() -> bool


## Screen rectangle of the small map (for tests to tap it).
@abstract func get_small_rect() -> Rect2
