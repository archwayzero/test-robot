## Creates the player scene. Owner: orchestrator. Implemented by internal/player.tscn (root script extends
## PlayerController). The visual is the hero rig, godot/assets/hero/rig/hero.glb.
class_name PlayerFactory
extends RefCounted

const _SCENE_PATH := "res://modules/player/internal/player.tscn"


static func create_player() -> PlayerController:
	return (load(_SCENE_PATH) as PackedScene).instantiate() as PlayerController
