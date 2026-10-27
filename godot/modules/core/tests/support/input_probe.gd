## Test helper: a Control that records the events its _gui_input receives.
extends Control

var events: Array[InputEvent] = []


func _gui_input(event: InputEvent) -> void:
	events.append(event)


func count(type_name: String) -> int:
	return events.filter(func(e: InputEvent) -> bool: return e.get_class() == type_name).size()
