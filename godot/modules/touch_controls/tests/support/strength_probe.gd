## Test helper: samples the move/jump action strengths every process frame and keeps the maxima.
extends Node

var max_strength: Dictionary = {}


func _process(_delta: float) -> void:
	for a in GameActions.ALL:
		max_strength[a] = maxf(max_strength.get(a, 0.0), Input.get_action_strength(a))
