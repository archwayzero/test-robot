## The main scene (project.godot run/main_scene = MAIN_SCENE). Composition root: creates and wires every module
## through their public factories, in this order:
##   1. phase "loading"; maze layout (MazeFactory.GAME_SEED) + MazeWorld.build()
##   2. Exploration.setup(layout); AutoSave.setup(platform backend); AutoSave.restore()
##   3. Player spawned at the saved position (StateKeys.PLAYER_*) or the layout's start cell
##   4. HUD inside the display safe area (DECISIONS.md D17): TouchControls, then Minimap.setup(layout, exploration)
##      top-left above them (map taps never reach the joystick); TouchControls hidden on desktop unless touch
##      emulation is on
##   5. phase "playing"; large map open -> phase "map_open" + TouchControls hidden + SceneTree paused (minimap and
##      controls run with PROCESS_MODE_ALWAYS); closed -> back to "playing".
## No gameplay logic lives here.
##
## Owner: orchestrator. Implemented by internal/main.tscn (root script extends GameMain).
@abstract
class_name GameMain
extends Node

const MAIN_SCENE := "res://modules/game/internal/main.tscn"

## Emitted when everything is built and the phase is "playing" (end-to-end tests wait for this).
signal ready_to_play()


@abstract func is_ready_to_play() -> bool


## Accessors for end-to-end tests and the qa capture scenes (read-only use).
@abstract func get_player() -> PlayerController


@abstract func get_maze_world() -> MazeWorld


@abstract func get_exploration() -> Exploration


@abstract func get_minimap() -> Minimap


@abstract func get_touch_controls() -> TouchControls


@abstract func get_auto_save() -> AutoSave
