## GameState implementation. Emits the Core signals (through the CoreAPI passed in) only when something actually
## changed. Stored values are deep copies and must be plain data that survives var_to_str()/str_to_var().
## Does not touch SceneTree.paused (set_paused only records the flag and emits pause_changed).
extends GameState

var _core: CoreAPI
var _phase: StringName = PHASE_BOOT
var _paused := false
var _values: Dictionary = {}

static var _key_regex: RegEx


func _init(core: CoreAPI) -> void:
	_core = core


func get_phase() -> StringName:
	return _phase


func set_phase(phase: StringName) -> void:
	if phase == _phase:
		return
	var previous := _phase
	_phase = phase
	_core.phase_changed.emit(previous, phase)


func is_paused() -> bool:
	return _paused


func set_paused(paused: bool) -> void:
	if paused == _paused:
		return
	_paused = paused
	_core.pause_changed.emit(paused)


func get_value(key: StringName, default: Variant = null) -> Variant:
	if not _values.has(key):
		return default
	return _copy(_values[key])


func set_value(key: StringName, value: Variant) -> void:
	if not is_valid_key(key):
		push_error("GameState: key '%s' rejected, must match %s (<module>/<name>)" % [key, KEY_PATTERN])
		return
	if not is_plain_data(value):
		push_error("GameState: value for '%s' is not plain serializable data: %s" % [key, value])
		return
	if _values.has(key) and same_value(_values[key], value):
		return
	_values[key] = _copy(value)
	_core.state_value_changed.emit(key, _copy(value))


func has_value(key: StringName) -> bool:
	return _values.has(key)


func snapshot() -> Dictionary:
	return {"phase": _phase, "paused": _paused, "values": _values.duplicate(true)}


func restore(data: Dictionary) -> void:
	var parsed := parse_snapshot(data)
	if parsed.is_empty():
		push_error("GameState: restore() got an invalid snapshot; state unchanged")
		return
	var old_phase := _phase
	var old_paused := _paused
	var old_values := _values
	_phase = parsed.phase
	_paused = parsed.paused
	_values = parsed.values
	# Emit only after the whole state is in place, so listeners always read a consistent state.
	if _phase != old_phase:
		_core.phase_changed.emit(old_phase, _phase)
	if _paused != old_paused:
		_core.pause_changed.emit(_paused)
	for key in old_values:
		if not _values.has(key):
			_core.state_value_changed.emit(key, null)
	for key in _values:
		if not old_values.has(key) or not same_value(old_values[key], _values[key]):
			_core.state_value_changed.emit(key, _copy(_values[key]))


## Validates a snapshot()-shaped dictionary. Returns {"phase": StringName, "paused": bool, "values": Dictionary
## (StringName keys, deep copy)} or {} if invalid. Used by restore() and by the save service.
static func parse_snapshot(data: Variant) -> Dictionary:
	if typeof(data) != TYPE_DICTIONARY:
		return {}
	var d: Dictionary = data
	if not (d.has("phase") and d.has("paused") and d.has("values")):
		return {}
	if not (typeof(d.phase) in [TYPE_STRING_NAME, TYPE_STRING]) or typeof(d.paused) != TYPE_BOOL:
		return {}
	if typeof(d.values) != TYPE_DICTIONARY:
		return {}
	var values: Dictionary = {}
	for key in d.values:
		if not (typeof(key) in [TYPE_STRING_NAME, TYPE_STRING]) or not is_plain_data(d.values[key]):
			return {}
		if not is_valid_key(StringName(key)):
			push_error("GameState: snapshot key '%s' does not match %s; whole snapshot rejected" % [key, KEY_PATTERN])
			return {}
		values[StringName(key)] = _copy(d.values[key])
	return {"phase": StringName(d.phase), "paused": d.paused, "values": values}


## True if `key` matches GameState.KEY_PATTERN (`<module>/<name>[/...]`, lower-case, digits, `_`).
static func is_valid_key(key: StringName) -> bool:
	if _key_regex == null:
		_key_regex = RegEx.create_from_string(KEY_PATTERN)
	var s := String(key)
	var m := _key_regex.search(s)
	# Compare the whole match: PCRE's `$` also matches before a trailing newline.
	return m != null and m.get_string() == s


## True if `value` is plain data that survives var_to_str()/str_to_var() unchanged (no Objects, Callables,
## Signals or RIDs, also not nested).
static func is_plain_data(value: Variant) -> bool:
	match typeof(value):
		TYPE_OBJECT, TYPE_CALLABLE, TYPE_SIGNAL, TYPE_RID, TYPE_MAX:
			return false
		TYPE_ARRAY:
			for item in value:
				if not is_plain_data(item):
					return false
		TYPE_DICTIONARY:
			for k in value:
				if not is_plain_data(k) or not is_plain_data(value[k]):
					return false
	return true


## Change detection: different types count as different (e.g. 1 vs 1.0, "a" vs &"a").
static func same_value(a: Variant, b: Variant) -> bool:
	return typeof(a) == typeof(b) and a == b


static func _copy(value: Variant) -> Variant:
	if value is Array or value is Dictionary:
		return value.duplicate(true)
	return value
