extends Node3D
## Preview only (T011): turns the hero 90 degrees every 0.5 s so a capture contact sheet shows
## back (frame 0, camera behind the character on +Z), right side, front and left side.

func _process(delta: float) -> void:
	rotate_y(delta * PI)
