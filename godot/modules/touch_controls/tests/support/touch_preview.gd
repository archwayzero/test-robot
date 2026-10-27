## Visual check scene (tests only, not shipped): the touch controls over a plain background, with the joystick
## held and deflected up-right and the Stance button held, injected as screen touches (no automation needed).
extends Control

var _controls  # TouchControls (internal impl: stance_center() is not on the public type)
var _frame := 0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.22, 0.24, 0.28)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var minimap := ColorRect.new()  # stand-in for the minimap's reserved area
	minimap.color = Color(0.1, 0.3, 0.2, 0.6)
	minimap.position = Vector2(16, 16)
	minimap.size = Vector2(200, 200)
	add_child(minimap)
	_controls = TouchControlsFactory.create()
	add_child(_controls)
	_controls.set_controls_visible(true)


func _process(_delta: float) -> void:
	_frame += 1
	var h: float = _controls.size.y
	var start := Vector2(220, h - 170)
	if _frame == 5:
		_touch(start, true, 0)
		_touch(_controls.stance_center() as Vector2, true, 1)
	elif _frame >= 6 and _frame <= 20:
		var t := float(_frame - 5) / 15.0
		var drag := InputEventScreenDrag.new()
		drag.index = 0
		drag.position = _to_window(start + Vector2(45, -60) * t)
		Input.parse_input_event(drag)


func _touch(pos: Vector2, pressed: bool, index: int) -> void:
	var e := InputEventScreenTouch.new()
	e.index = index
	e.position = _to_window(pos)
	e.pressed = pressed
	Input.parse_input_event(e)


## Injected events go through the window's stretch transform, so convert viewport (canvas) positions back.
func _to_window(viewport_pos: Vector2) -> Vector2:
	return get_viewport().get_final_transform() * viewport_pos
