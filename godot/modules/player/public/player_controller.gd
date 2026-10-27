## The player character: movement, stances, jump, collision, third-person camera, hero animation.
## Reads input ONLY through GameActions (InputMap); never from touch_controls directly.
## Emits Core.player_moved(position) and writes StateKeys.PLAYER_* (throttled).
## Collides with physics layer 1 ("world"); the player body is on layer 2 ("player").
##
## Owner: orchestrator. Implemented in player/internal; instance it via PlayerFactory.create_player().
@abstract
class_name PlayerController
extends CharacterBody3D

## Values are fixed and equal StateKeys.STANCE_STAND/CROUCH/CRAWL (0/1/2); do not reorder.
enum Stance { STAND = 0, CROUCH = 1, CRAWL = 2 }

## Emitted after the stance changed (including when a stand-up is refused it is NOT emitted).
signal stance_changed(stance: Stance)

## Emitted when a jump starts.
signal jumped()

## Emitted when the player lands after being airborne.
signal landed()

## Movement tuning (m/s). Tests assert against these, so they are part of the interface.
const WALK_SPEED := 1.6
const RUN_SPEED := 4.0
const CROUCH_SPEED := 1.0
const CRAWL_SPEED := 0.5
const JUMP_VELOCITY := 4.0


@abstract func get_stance() -> Stance


## True while moving at run speed (only possible in STAND).
@abstract func is_running() -> bool


## True while on the floor.
@abstract func is_grounded() -> bool


## Teleports the player (feet at `position`, facing `yaw` radians) and resets velocity. Used for spawn and load.
@abstract func spawn_at(position: Vector3, yaw: float = 0.0) -> void


## Height of the current collision shape in meters (stand > crouch > crawl). Exposed for tests.
@abstract func get_collision_height() -> float


## The camera following the player (current camera while the player is in the tree).
@abstract func get_camera() -> Camera3D
