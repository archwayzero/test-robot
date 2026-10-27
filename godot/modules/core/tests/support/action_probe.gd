## Test helper: polls one InputMap action in _process (like game code) and counts pressed / just-pressed frames.
extends Node

var action: StringName
var pressed_frames := 0
var just_pressed := 0


func _process(_delta: float) -> void:
	if Input.is_action_pressed(action):
		pressed_frames += 1
	if Input.is_action_just_pressed(action):
		just_pressed += 1
