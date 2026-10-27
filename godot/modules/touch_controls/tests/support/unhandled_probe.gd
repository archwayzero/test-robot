## Test helper: records the screen touch/drag events that reach _unhandled_input (like the player's camera orbit).
extends Node

var events: Array[InputEvent] = []


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch or event is InputEventScreenDrag:
		events.append(event)
