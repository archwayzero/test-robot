## Owner: orchestrator. Implemented by internal/touch_controls.tscn (root script extends TouchControls).
class_name TouchControlsFactory
extends RefCounted

const _SCENE_PATH := "res://modules/touch_controls/internal/touch_controls.tscn"


static func create() -> TouchControls:
	return (load(_SCENE_PATH) as PackedScene).instantiate() as TouchControls
