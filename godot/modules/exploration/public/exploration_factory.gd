## Owner: orchestrator. Implemented by internal/exploration_impl.gd (extends Exploration).
class_name ExplorationFactory
extends RefCounted

const _IMPL_PATH := "res://modules/exploration/internal/exploration_impl.gd"


static func create() -> Exploration:
	return load(_IMPL_PATH).new()
