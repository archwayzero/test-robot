## The 3D maze: floor, walls, vaults, low passages, lamps, collision, occluders, lighting.
## Built from a MazeLayout using the crypt_kit pieces (godot/assets/crypt_kit), or greybox boxes until they exist.
## All static geometry is on physics layer 1 ("world"); see docs/architecture/ARCHITECTURE.md "Physics layers".
##
## Owner: orchestrator. Implemented in maze/internal.
@abstract
class_name MazeWorld
extends Node3D

## Emitted when build() has finished and collision is ready (the player may be spawned).
signal built()


## Builds the world for `layout`. Must be called after the node is in the tree. Writes StateKeys.MAZE_SEED.
## Idempotent: calling it again rebuilds.
@abstract func build(layout: MazeLayout) -> void


## The layout this world was built from (null before build()).
@abstract func get_layout() -> MazeLayout


## True once built() has been emitted.
@abstract func is_built() -> bool
