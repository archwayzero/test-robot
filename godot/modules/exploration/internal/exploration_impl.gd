## Exploration implementation: visited-cell bitset bound to one MazeLayout, persisted in Core.state.
##
## Storage: StateKeys.EXPLORATION_VISITED = Base64 of ceil(w*h/8) bytes, bit i = y*width+x lives in byte i>>3,
## bit (i & 7) (LSB first). StateKeys.EXPLORATION_COUNT = number of set bits.
## Stored data is accepted only if StateKeys.MAZE_SEED == layout seed and the bitset decodes to exactly the
## expected byte length; otherwise it is discarded and only the start cell counts as visited (and is persisted).
extends Exploration

const _B64_CHARS := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

var _layout: MazeLayout
var _size := Vector2i.ZERO
var _bits := PackedByteArray()
var _count := 0
var _last_cell := Vector2i(-1, -1)
var _has_last_cell := false


func setup(layout: MazeLayout) -> void:
	if layout == null:
		push_error("exploration: setup(null)")
		return
	_layout = layout
	_size = layout.size()
	_reload_from_state()
	_connect_core()


func is_explored(cell: Vector2i) -> bool:
	if _layout == null or not _layout.in_bounds(cell):
		return false
	var i := _index(cell)
	return (_bits[i >> 3] >> (i & 7)) & 1 == 1


func explored_count() -> int:
	return _count


func get_explored_cells() -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	if _layout == null:
		return out
	for y in _size.y:
		for x in _size.x:
			var c := Vector2i(x, y)
			if is_explored(c):
				out.append(c)
	return out


# --- tree / signals ----------------------------------------------------------------------------------------

func _enter_tree() -> void:
	if _layout != null:
		_connect_core()


func _exit_tree() -> void:
	_disconnect_core()


func _connect_core() -> void:
	if not is_inside_tree():
		return  # connected in _enter_tree
	var core := _core()
	if core == null:
		return
	if not core.player_moved.is_connected(_on_player_moved):
		core.player_moved.connect(_on_player_moved)
	if not core.load_finished.is_connected(_on_load_finished):
		core.load_finished.connect(_on_load_finished)


func _disconnect_core() -> void:
	var core := _core()
	if core == null:
		return
	if core.player_moved.is_connected(_on_player_moved):
		core.player_moved.disconnect(_on_player_moved)
	if core.load_finished.is_connected(_on_load_finished):
		core.load_finished.disconnect(_on_load_finished)


func _core() -> CoreAPI:
	# Core is the project's only autoload; referencing it by name is the documented access path.
	return Core


func _on_player_moved(position: Vector3) -> void:
	if _layout == null:
		return
	var cell := _layout.world_to_cell(position)
	if _has_last_cell and cell == _last_cell:
		return
	_last_cell = cell
	_has_last_cell = true
	if not _layout.in_bounds(cell) or is_explored(cell):
		return
	_set_bit(cell)
	_persist()
	cell_explored.emit(cell)


func _on_load_finished(_slot: int, error: Error) -> void:
	if error != OK or _layout == null:
		return
	_reload_from_state()
	restored.emit()


# --- state -------------------------------------------------------------------------------------------------

## Replaces the visited set from Core.state (or resets to the start cell if nothing valid is stored).
func _reload_from_state() -> void:
	_has_last_cell = false
	var decoded := _read_stored_bits()
	if decoded.is_empty():
		_bits = _empty_bits()
		_count = 0
		_set_bit(_layout.start_cell())
		_persist()
		return
	_bits = decoded
	_count = _popcount()
	if int(Core.state.get_value(StateKeys.EXPLORATION_COUNT, -1)) != _count:
		Core.state.set_value(StateKeys.EXPLORATION_COUNT, _count)


## The stored bitset if it belongs to this layout and is well-formed, else an empty array.
func _read_stored_bits() -> PackedByteArray:
	var state := Core.state
	if state == null:
		return PackedByteArray()
	var stored_seed: Variant = state.get_value(StateKeys.MAZE_SEED)
	if not (stored_seed is int) or stored_seed != _layout.get_seed():
		return PackedByteArray()
	var encoded: Variant = state.get_value(StateKeys.EXPLORATION_VISITED)
	if not (encoded is String) or not _is_valid_base64(encoded):
		return PackedByteArray()
	var raw := Marshalls.base64_to_raw(encoded)
	if raw.size() != _byte_len():
		return PackedByteArray()
	# Clear padding bits past w*h so they never count.
	var total := _size.x * _size.y
	if total & 7 != 0:
		raw[raw.size() - 1] &= (1 << (total & 7)) - 1
	return raw


func _persist() -> void:
	var state := Core.state
	if state == null:
		return
	state.set_value(StateKeys.EXPLORATION_VISITED, Marshalls.raw_to_base64(_bits))
	state.set_value(StateKeys.EXPLORATION_COUNT, _count)


# --- bitset helpers ----------------------------------------------------------------------------------------

func _index(cell: Vector2i) -> int:
	return cell.y * _size.x + cell.x


func _byte_len() -> int:
	return (_size.x * _size.y + 7) >> 3


func _empty_bits() -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(_byte_len())
	b.fill(0)
	return b


func _set_bit(cell: Vector2i) -> void:
	if not _layout.in_bounds(cell):
		return
	var i := _index(cell)
	var mask := 1 << (i & 7)
	if _bits[i >> 3] & mask == 0:
		_bits[i >> 3] |= mask
		_count += 1


func _popcount() -> int:
	var n := 0
	for byte in _bits:
		var v := byte
		while v != 0:
			v &= v - 1
			n += 1
	return n


## Strict check so malformed strings are rejected without engine decode errors.
static func _is_valid_base64(s: String) -> bool:
	if s.is_empty() or s.length() % 4 != 0:
		return false
	var pad := 0
	if s.ends_with("=="):
		pad = 2
	elif s.ends_with("="):
		pad = 1
	for i in s.length() - pad:
		if _B64_CHARS.find(s[i]) < 0:
			return false
	return true
