## Fog-of-war mini-map (top-left) and full-screen large map. Root of internal/minimap.tscn.
##
## The root Control spans the whole viewport but only claims input where it draws: _has_point() is the small map
## rectangle while closed and the whole screen while the large map is open, so touches elsewhere fall through to
## the touch controls / camera. Taps that hit the map are accepted (consumed) by the GUI.
##
## Model: `_cell_colors` holds ONLY visited cells (cell -> fill colour); everything not in it is drawn black.
## Redraws are queued only on change: new/restored cells, player cell or facing change, toggle, resize.
extends Minimap

const SMALL_CELLS := 9  # cells across the small map (odd, so the player's cell is in the centre)
const LARGE_PADDING := 24.0

const COLOR_UNVISITED := Color(0.0, 0.0, 0.0)
const COLOR_FLOOR := Color(0.47, 0.43, 0.36)
const COLOR_CROUCH := Color(0.62, 0.45, 0.22)  # low passage (crouch): amber tint
const COLOR_CRAWL := Color(0.58, 0.26, 0.20)  # very low passage (crawl): red tint
const COLOR_WALL := Color(0.93, 0.89, 0.78)
const COLOR_FRAME := Color(0.85, 0.80, 0.65, 0.9)
const COLOR_MARKER := Color(0.25, 0.85, 1.0)
const COLOR_MARKER_OUTLINE := Color(0.0, 0.0, 0.0)
const COLOR_LARGE_BACKDROP := Color(0.02, 0.02, 0.03, 0.96)
const COLOR_HINT := Color(0.85, 0.80, 0.65, 0.8)

## Facing changes smaller than this (radians) do not trigger a redraw.
const YAW_REDRAW_EPSILON := deg_to_rad(3.0)
## Minimum horizontal movement (m) for the player_moved delta to count as a facing.
const DELTA_MIN_M := 0.02

var _layout: MazeLayout
var _exploration: Exploration
var _large_open := false

## Visited cells only: Vector2i -> Color (floor colour, tinted for low passages).
var _cell_colors: Dictionary = {}

var _player_cell := Vector2i.ZERO
var _player_yaw := 0.0  # radians, Godot convention: yaw 0 faces -Z (north / up on the map)
var _drawn_yaw := 0.0
var _last_position: Variant = null  # Vector3 of the previous player_moved, for the delta fallback


func _init() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	mouse_filter = Control.MOUSE_FILTER_STOP


func _enter_tree() -> void:
	_connect_signals()


func _exit_tree() -> void:
	_disconnect_signals()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()


# --- public API ----------------------------------------------------------------------------------------

func setup(layout: MazeLayout, exploration: Exploration) -> void:
	_disconnect_signals()
	_layout = layout
	_exploration = exploration
	_last_position = null
	_player_cell = layout.start_cell() if layout != null else Vector2i.ZERO
	_player_yaw = 0.0
	if Core.state != null:
		var pos: Variant = Core.state.get_value(StateKeys.PLAYER_POSITION)
		if pos is Vector3 and layout != null:
			_player_cell = layout.world_to_cell(pos)
			_last_position = pos
		var yaw: Variant = Core.state.get_value(StateKeys.PLAYER_YAW)
		if yaw is float or yaw is int:
			_player_yaw = float(yaw)
	_drawn_yaw = _player_yaw
	_rebuild_model()
	if is_inside_tree():
		_connect_signals()


func open_large_map() -> void:
	_set_large_open(true)


func close_large_map() -> void:
	_set_large_open(false)


func is_large_map_open() -> bool:
	return _large_open


func get_small_rect() -> Rect2:
	return Rect2(get_global_rect().position + MARGIN, SMALL_SIZE)


# --- internal API (tests) ------------------------------------------------------------------------------

## Copy of the colour model: only visited cells are keys.
func get_cell_color_model() -> Dictionary:
	return _cell_colors.duplicate()


## Cell the player marker is drawn in.
func get_marker_cell() -> Vector2i:
	return _player_cell


## Facing of the marker in radians (yaw 0 = -Z = up on the map).
func get_marker_yaw() -> float:
	return _player_yaw


## Screen-space direction the marker triangle points to (unit vector, y down).
func get_marker_direction() -> Vector2:
	return _yaw_to_dir(_player_yaw)


# --- signals -------------------------------------------------------------------------------------------

func _connect_signals() -> void:
	if not Core.player_moved.is_connected(_on_player_moved):
		Core.player_moved.connect(_on_player_moved)
	if not Core.state_value_changed.is_connected(_on_state_value_changed):
		Core.state_value_changed.connect(_on_state_value_changed)
	if _exploration != null:
		if not _exploration.cell_explored.is_connected(_on_cell_explored):
			_exploration.cell_explored.connect(_on_cell_explored)
		if not _exploration.restored.is_connected(_on_restored):
			_exploration.restored.connect(_on_restored)


func _disconnect_signals() -> void:
	if Core.player_moved.is_connected(_on_player_moved):
		Core.player_moved.disconnect(_on_player_moved)
	if Core.state_value_changed.is_connected(_on_state_value_changed):
		Core.state_value_changed.disconnect(_on_state_value_changed)
	if _exploration != null and is_instance_valid(_exploration):
		if _exploration.cell_explored.is_connected(_on_cell_explored):
			_exploration.cell_explored.disconnect(_on_cell_explored)
		if _exploration.restored.is_connected(_on_restored):
			_exploration.restored.disconnect(_on_restored)


func _on_cell_explored(cell: Vector2i) -> void:
	if _layout == null or not _layout.in_bounds(cell) or _cell_colors.has(cell):
		return
	_cell_colors[cell] = _color_for(cell)
	queue_redraw()


func _on_restored() -> void:
	_rebuild_model()


func _on_player_moved(position: Vector3) -> void:
	if _layout == null:
		return
	var redraw := false
	var cell := _layout.world_to_cell(position)
	if cell != _player_cell:
		_player_cell = cell
		redraw = true
	var state_yaw: Variant = Core.state.get_value(StateKeys.PLAYER_YAW) if Core.state != null else null
	var has_state_yaw := state_yaw is float or state_yaw is int
	if not has_state_yaw and _last_position is Vector3:
		var d: Vector3 = position - (_last_position as Vector3)
		var flat := Vector2(d.x, d.z)
		if flat.length() >= DELTA_MIN_M:
			# Forward is -Z: yaw 0 -> (0, -1); forward = (-sin(yaw), -cos(yaw)).
			_player_yaw = atan2(-flat.x, -flat.y)
			redraw = _yaw_changed() or redraw
	_last_position = position
	if redraw:
		queue_redraw()


func _on_state_value_changed(key: StringName, value: Variant) -> void:
	if key != StateKeys.PLAYER_YAW:
		return
	if value is float or value is int:
		_player_yaw = float(value)
		if _yaw_changed():
			queue_redraw()


func _yaw_changed() -> bool:
	if absf(angle_difference(_drawn_yaw, _player_yaw)) >= YAW_REDRAW_EPSILON:
		_drawn_yaw = _player_yaw
		return true
	return false


# --- model ---------------------------------------------------------------------------------------------

func _rebuild_model() -> void:
	_cell_colors.clear()
	if _layout != null and _exploration != null:
		for cell in _exploration.get_explored_cells():
			if _layout.in_bounds(cell):
				_cell_colors[cell] = _color_for(cell)
	queue_redraw()


func _color_for(cell: Vector2i) -> Color:
	match _layout.clearance(cell):
		MazeLayout.Clearance.CROUCH:
			return COLOR_CROUCH
		MazeLayout.Clearance.CRAWL:
			return COLOR_CRAWL
	return COLOR_FLOOR


# --- toggle and input ----------------------------------------------------------------------------------

func _set_large_open(open: bool) -> void:
	if open == _large_open:
		return
	_large_open = open
	queue_redraw()
	large_map_toggled.emit(open)


func _has_point(point: Vector2) -> bool:
	if _large_open:
		return Rect2(Vector2.ZERO, size).has_point(point)
	return Rect2(MARGIN, SMALL_SIZE).has_point(point)


func _gui_input(event: InputEvent) -> void:
	var pressed := false
	if event is InputEventScreenTouch:
		pressed = (event as InputEventScreenTouch).pressed
	elif event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		pressed = mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT
	elif event is InputEventScreenDrag or event is InputEventMouseMotion:
		accept_event()
		return
	else:
		return
	accept_event()
	# One physical tap arrives twice when touch<->mouse emulation is on; act only on the original event.
	if not pressed or event.device == InputEvent.DEVICE_ID_EMULATION:
		return
	_set_large_open(not _large_open)


# --- drawing -------------------------------------------------------------------------------------------

func _draw() -> void:
	if _large_open:
		_draw_large()
	else:
		_draw_small()


func _draw_small() -> void:
	var area := Rect2(MARGIN, SMALL_SIZE)
	draw_rect(area, COLOR_UNVISITED)
	if _layout != null:
		var cell_px := SMALL_SIZE.x / float(SMALL_CELLS)
		# Player's cell centre sits in the centre of the small map.
		var origin := area.get_center() - (Vector2(_player_cell) + Vector2(0.5, 0.5)) * cell_px
		var half := SMALL_CELLS / 2 + 1
		var cells: Array[Vector2i] = []
		for dy in range(-half, half + 1):
			for dx in range(-half, half + 1):
				var c := _player_cell + Vector2i(dx, dy)
				if _cell_colors.has(c):
					cells.append(c)
		_draw_cells(cells, origin, cell_px, area)
		_draw_marker(area.get_center(), cell_px)
	draw_rect(area, COLOR_FRAME, false, 2.0)


func _draw_large() -> void:
	var full := Rect2(Vector2.ZERO, size)
	draw_rect(full, COLOR_LARGE_BACKDROP)
	if _layout == null:
		return
	var grid := Vector2(_layout.size())
	var avail := size - Vector2(LARGE_PADDING, LARGE_PADDING) * 2.0
	var cell_px := maxf(1.0, minf(avail.x / grid.x, avail.y / grid.y))
	var map_size := grid * cell_px
	var origin := ((size - map_size) * 0.5).floor()
	var area := Rect2(origin, map_size)
	draw_rect(area, COLOR_UNVISITED)
	var cells: Array[Vector2i] = []
	for c in _cell_colors:
		cells.append(c)
	_draw_cells(cells, origin, cell_px, area)
	_draw_marker(origin + (Vector2(_player_cell) + Vector2(0.5, 0.5)) * cell_px, cell_px)
	draw_rect(area.grow(2.0), COLOR_FRAME, false, 2.0)
	var font := get_theme_default_font()
	if font != null:
		var hint := "Tap to close"
		var fs := 16
		var w := font.get_string_size(hint, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		var y := minf(size.y - 6.0, area.end.y + 2.0 + fs)
		draw_string(font, Vector2(size.x - w - LARGE_PADDING, y), hint, HORIZONTAL_ALIGNMENT_LEFT, -1, fs,
				COLOR_HINT)


## Fills the given visited cells and draws their walls, clipped to `clip`.
func _draw_cells(cells: Array[Vector2i], origin: Vector2, cell_px: float, clip: Rect2) -> void:
	for c in cells:
		_clipped_rect(Rect2(origin + Vector2(c) * cell_px, Vector2(cell_px, cell_px)), _cell_colors[c], clip)
	var t := maxf(1.0, cell_px * 0.12)
	for c in cells:
		var p := origin + Vector2(c) * cell_px
		if _layout.has_wall(c, MazeLayout.Dir.NORTH):
			_clipped_rect(Rect2(p.x - t * 0.5, p.y - t * 0.5, cell_px + t, t), COLOR_WALL, clip)
		if _layout.has_wall(c, MazeLayout.Dir.SOUTH):
			_clipped_rect(Rect2(p.x - t * 0.5, p.y + cell_px - t * 0.5, cell_px + t, t), COLOR_WALL, clip)
		if _layout.has_wall(c, MazeLayout.Dir.WEST):
			_clipped_rect(Rect2(p.x - t * 0.5, p.y - t * 0.5, t, cell_px + t), COLOR_WALL, clip)
		if _layout.has_wall(c, MazeLayout.Dir.EAST):
			_clipped_rect(Rect2(p.x + cell_px - t * 0.5, p.y - t * 0.5, t, cell_px + t), COLOR_WALL, clip)


func _clipped_rect(r: Rect2, color: Color, clip: Rect2) -> void:
	var i := r.intersection(clip)
	if i.has_area():
		draw_rect(i, color)


func _draw_marker(center: Vector2, cell_px: float) -> void:
	var fwd := _yaw_to_dir(_player_yaw)
	var side := Vector2(-fwd.y, fwd.x)
	var r := maxf(4.0, cell_px * 0.36)
	var pts := PackedVector2Array([
		center + fwd * r,
		center - fwd * r * 0.6 + side * r * 0.65,
		center - fwd * r * 0.6 - side * r * 0.65,
	])
	draw_colored_polygon(pts, COLOR_MARKER)
	pts.append(pts[0])
	draw_polyline(pts, COLOR_MARKER_OUTLINE, 1.5, true)


static func _yaw_to_dir(yaw: float) -> Vector2:
	# Basis(Y, yaw) * (0, 0, -1) = (-sin(yaw), 0, -cos(yaw)); world X -> screen x, world Z -> screen y.
	return Vector2(-sin(yaw), -cos(yaw))
