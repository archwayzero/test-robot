## Test helper: records the pointer events that reach _unhandled_input (stands in for gameplay / camera input).
extends Node

var events: Array[InputEvent] = []


func _init() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch or event is InputEventMouseButton:
		events.append(event)
