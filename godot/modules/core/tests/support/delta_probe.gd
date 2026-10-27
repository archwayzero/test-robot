## Test helper: records every _process delta and counts physics steps per process frame.
extends Node

var deltas: Array[float] = []
var physics_per_frame: Array[int] = []
var _physics_since_process := 0
var _started := false


func _process(delta: float) -> void:
	if _started:
		physics_per_frame.append(_physics_since_process)
	_started = true
	_physics_since_process = 0
	deltas.append(delta)


func _physics_process(_delta: float) -> void:
	_physics_since_process += 1
