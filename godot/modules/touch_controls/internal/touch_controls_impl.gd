## On-screen controls: dynamic joystick on the left half, Jump and Stance buttons bottom-right.
##
## The root is a full-screen Control with mouse_filter IGNORE, so the GUI never stops at it. Touches are read in
## _input(): a touch that starts the joystick or lands on a button is marked handled (and so are that finger's
## drags and release), which keeps it away from GUI controls and from _unhandled_input (the player's camera orbit).
## Every other touch is left alone and reaches the game normally (minimap taps, camera orbit on the right half).
##
## Output is only Input.action_press / action_release on GameActions. Drawn with _draw(); no image files.
extends TouchControls

const STICK_RADIUS := 90.0
const KNOB_RADIUS := 38.0
## Top-left area reserved for the minimap (SMALL_SIZE 200 + MARGIN 16 on each side). Touches there never start
## the joystick.
const MINIMAP_RESERVED := Vector2(232, 232)
const JUMP_RADIUS := 60.0
const STANCE_RADIUS := 45.0
const MARGIN_RIGHT := 48.0
const MARGIN_BOTTOM := 32.0
const BUTTON_GAP := 28.0
## Buttons accept touches slightly outside their drawn circle (fingers are imprecise).
const HIT_SLOP := 1.1
## Strength components below this are released instead of pressed.
const MIN_STRENGTH := 0.001
const NO_TOUCH := -1

const STANCE_NAMES := ["Stand", "Crouch", "Crawl"]

const COLOR_BASE := Color(1, 1, 1, 0.12)
const COLOR_RING := Color(1, 1, 1, 0.45)
const COLOR_KNOB := Color(1, 1, 1, 0.5)
const COLOR_HINT := Color(1, 1, 1, 0.18)
const COLOR_BUTTON := Color(0.1, 0.1, 0.12, 0.35)
const COLOR_BUTTON_DOWN := Color(1, 1, 1, 0.4)
const COLOR_LABEL := Color(1, 1, 1, 0.85)

var _stick_index := NO_TOUCH
var _stick_center := Vector2.ZERO
var _stick_vector := Vector2.ZERO
var _jump_index := NO_TOUCH
var _stance_index := NO_TOUCH
## Actions this node currently holds down (so release never touches what the keyboard pressed).
var _held: Dictionary = {}
var _stance_text := ""


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	focus_mode = Control.FOCUS_NONE


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = DisplayServer.is_touchscreen_available() \
			or bool(ProjectSettings.get_setting("input_devices/pointing/emulate_touch_from_mouse", false))
	Core.state_value_changed.connect(_on_state_value_changed)
	if Core.state != null:
		_update_stance_text(Core.state.get_value(StateKeys.PLAYER_STANCE, null))
	resized.connect(queue_redraw)


func _exit_tree() -> void:
	_release_all()


func _notification(what: int) -> void:
	if what == NOTIFICATION_VISIBILITY_CHANGED and not is_visible_in_tree():
		_release_all()


# --- public API ---------------------------------------------------------------------------------------------

func set_controls_visible(show: bool) -> void:
	var changed := visible != show
	if not show:
		_release_all()
	visible = show
	if changed:
		visibility_toggled.emit(show)


func get_stick_vector() -> Vector2:
	return _stick_vector


## Test hook: bounding square of the Jump button in viewport coordinates (the space of input events and
## Core.automation.touch()). Derived from the live layout and canvas transform, so it follows offset parents
## (HUD safe area) and viewport resizes. A touch at its centre presses jump.
func get_jump_rect() -> Rect2:
	return _viewport_rect(jump_center(), JUMP_RADIUS)


## Test hook: bounding square of the Stance button in viewport coordinates. Same rules as get_jump_rect().
func get_stance_rect() -> Rect2:
	return _viewport_rect(stance_center(), STANCE_RADIUS)


func _viewport_rect(local_center: Vector2, radius: float) -> Rect2:
	var local := Rect2(local_center - Vector2(radius, radius), Vector2(radius, radius) * 2.0)
	return get_global_transform_with_canvas() * local


# --- layout (local coordinates; the root fills the viewport) ------------------------------------------------

func jump_center() -> Vector2:
	return Vector2(size.x - MARGIN_RIGHT - JUMP_RADIUS, size.y - MARGIN_BOTTOM - JUMP_RADIUS)


func stance_center() -> Vector2:
	var j := jump_center()
	return Vector2(j.x - JUMP_RADIUS - BUTTON_GAP - STANCE_RADIUS, size.y - MARGIN_BOTTOM - STANCE_RADIUS)


## Where the faint joystick hint is drawn while no finger holds the stick.
func stick_rest_center() -> Vector2:
	return Vector2(MARGIN_RIGHT + STICK_RADIUS + 40.0, size.y - MARGIN_BOTTOM - STICK_RADIUS - 40.0)


func is_stick_zone(local: Vector2) -> bool:
	if local.x < 0.0 or local.y < 0.0 or local.x >= size.x * 0.5 or local.y >= size.y:
		return false
	return not (local.x < MINIMAP_RESERVED.x and local.y < MINIMAP_RESERVED.y)


func _on_jump(local: Vector2) -> bool:
	return local.distance_to(jump_center()) <= JUMP_RADIUS * HIT_SLOP


func _on_stance(local: Vector2) -> bool:
	return local.distance_to(stance_center()) <= STANCE_RADIUS * HIT_SLOP


# --- input ----------------------------------------------------------------------------------------------------

func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	if event is InputEventScreenTouch:
		if _handle_touch(event as InputEventScreenTouch):
			get_viewport().set_input_as_handled()
	elif event is InputEventScreenDrag:
		if _handle_drag(event as InputEventScreenDrag):
			get_viewport().set_input_as_handled()


func _to_local(viewport_pos: Vector2) -> Vector2:
	return get_global_transform_with_canvas().affine_inverse() * viewport_pos


## Returns true if the touch belongs to the controls (and must be consumed).
func _handle_touch(t: InputEventScreenTouch) -> bool:
	var local := _to_local(t.position)
	var down := t.pressed and not t.canceled
	if down:
		if t.index == _stick_index or t.index == _jump_index or t.index == _stance_index:
			return true  # repeated press for a finger we already own
		if _on_jump(local):
			if _jump_index == NO_TOUCH:
				_jump_index = t.index
				_press(GameActions.JUMP, 1.0)
				queue_redraw()
			return true
		if _on_stance(local):
			if _stance_index == NO_TOUCH:
				_stance_index = t.index
				_press(GameActions.STANCE_CYCLE, 1.0)
				queue_redraw()
			return true
		if _stick_index == NO_TOUCH and is_stick_zone(local):
			_stick_index = t.index
			_stick_center = local
			_set_stick(Vector2.ZERO)
			return true
		return false
	# release / cancel
	if t.index == _stick_index:
		_stick_index = NO_TOUCH
		_set_stick(Vector2.ZERO)
		return true
	if t.index == _jump_index:
		_jump_index = NO_TOUCH
		_release(GameActions.JUMP)
		queue_redraw()
		return true
	if t.index == _stance_index:
		_stance_index = NO_TOUCH
		_release(GameActions.STANCE_CYCLE)
		queue_redraw()
		return true
	return false


func _handle_drag(d: InputEventScreenDrag) -> bool:
	if d.index == _stick_index:
		var local := _to_local(d.position)
		var offset := local - _stick_center
		if offset.length() > STICK_RADIUS:
			# The base follows the finger so the stick never needs to be "found" again.
			_stick_center = local - offset.normalized() * STICK_RADIUS
			offset = local - _stick_center
		_set_stick(offset / STICK_RADIUS)
		return true
	return d.index == _jump_index or d.index == _stance_index


# --- actions --------------------------------------------------------------------------------------------------

func _set_stick(v: Vector2) -> void:
	_stick_vector = v.limit_length(1.0)
	_apply_axis(GameActions.MOVE_RIGHT, _stick_vector.x)
	_apply_axis(GameActions.MOVE_LEFT, -_stick_vector.x)
	_apply_axis(GameActions.MOVE_BACK, _stick_vector.y)
	_apply_axis(GameActions.MOVE_FORWARD, -_stick_vector.y)
	queue_redraw()


func _apply_axis(action: StringName, strength: float) -> void:
	if strength > MIN_STRENGTH:
		_press(action, minf(strength, 1.0))
	else:
		_release(action)


func _press(action: StringName, strength: float) -> void:
	Input.action_press(action, strength)
	_held[action] = true


func _release(action: StringName) -> void:
	if _held.erase(action):
		Input.action_release(action)


func _release_all() -> void:
	_stick_index = NO_TOUCH
	_jump_index = NO_TOUCH
	_stance_index = NO_TOUCH
	_stick_vector = Vector2.ZERO
	for action in _held.keys():
		Input.action_release(action)
	_held.clear()
	queue_redraw()


# --- stance label ---------------------------------------------------------------------------------------------

func _on_state_value_changed(key: StringName, value: Variant) -> void:
	if key == StateKeys.PLAYER_STANCE:
		_update_stance_text(value)


## PLAYER_STANCE is an int in cycle order stand -> crouch -> crawl (DECISIONS D3). Unknown -> no sub-label.
func _update_stance_text(value: Variant) -> void:
	var text := ""
	if typeof(value) == TYPE_INT and value >= 0 and value < STANCE_NAMES.size():
		text = STANCE_NAMES[value]
	if text != _stance_text:
		_stance_text = text
		queue_redraw()


# --- drawing --------------------------------------------------------------------------------------------------

func _draw() -> void:
	var font := get_theme_default_font()
	if _stick_index != NO_TOUCH:
		draw_circle(_stick_center, STICK_RADIUS, COLOR_BASE)
		draw_arc(_stick_center, STICK_RADIUS, 0.0, TAU, 64, COLOR_RING, 3.0, true)
		draw_circle(_stick_center + _stick_vector * STICK_RADIUS, KNOB_RADIUS, COLOR_KNOB)
	else:
		var rest := stick_rest_center()
		draw_arc(rest, STICK_RADIUS, 0.0, TAU, 64, COLOR_HINT, 2.0, true)
		draw_circle(rest, KNOB_RADIUS * 0.6, COLOR_HINT)

	_draw_button(jump_center(), JUMP_RADIUS, _jump_index != NO_TOUCH, "Jump", "", font, 24)
	_draw_button(stance_center(), STANCE_RADIUS, _stance_index != NO_TOUCH, "Stance", _stance_text, font, 18)


func _draw_button(center: Vector2, radius: float, down: bool, label: String, sub: String, font: Font,
		font_size: int) -> void:
	draw_circle(center, radius, COLOR_BUTTON_DOWN if down else COLOR_BUTTON)
	draw_arc(center, radius, 0.0, TAU, 64, COLOR_RING, 3.0, true)
	if font == null:
		return
	var width := radius * 2.0
	var y := center.y + font_size * 0.35
	if sub != "":
		y -= font_size * 0.45
	draw_string(font, Vector2(center.x - radius, y), label, HORIZONTAL_ALIGNMENT_CENTER, width, font_size,
			COLOR_LABEL)
	if sub != "":
		var sub_size := int(font_size * 0.75)
		draw_string(font, Vector2(center.x - radius, y + sub_size + 4), sub, HORIZONTAL_ALIGNMENT_CENTER, width,
				sub_size, COLOR_LABEL)
