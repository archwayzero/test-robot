## Owner: orchestrator. Implemented by internal/minimap.tscn (root script extends Minimap).
class_name MinimapFactory
extends RefCounted

const _SCENE_PATH := "res://modules/minimap/internal/minimap.tscn"


static func create() -> Minimap:
	return (load(_SCENE_PATH) as PackedScene).instantiate() as Minimap
