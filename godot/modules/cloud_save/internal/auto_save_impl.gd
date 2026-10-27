## AutoSave implementation (created by internal/cloud_save_factory_impl.gd).
##
## Save: Core.saves.save_game(SAVE_SLOT); on OK, record the UTC time in our own sidecar (META_PATH) and push our own
## envelope (see make_envelope()) to the backend. The local save never waits for the cloud.
## Throttle: game time (sum of _process deltas, PROCESS_MODE_PAUSABLE so it stops while the tree is paused).
## Restore: the cloud envelope wins only if it is valid and strictly newer than the local sidecar timestamp (or no
## local save exists); otherwise the local slot is loaded.
## This module never reads core's save file; it only uses Core.state / Core.saves.
extends AutoSave

const META_DIR := "user://cloud_save"
const META_PATH := "user://cloud_save/meta.cfg"
const META_KEY := "saved_at_unix"
const ENVELOPE_FORMAT := "cloud_save"
const ENVELOPE_VERSION := 1
## Upper bound for a cloud payload we are willing to parse (iCloud key-value store limits a value to 1 MB).
const MAX_PAYLOAD_BYTES := 1024 * 1024
## Tolerance for float accumulation of frame deltas (300 * 1/30 may sum to 9.99999...).
const _EPSILON := 0.0001
## var_to_str constructors that would instantiate objects/resources; never parsed from cloud data.
const _FORBIDDEN_TOKENS: Array[String] = ["Object(", "Resource(", "SubResource(", "ExtResource("]

var _backend: CloudBackend
var _active := false
var _restoring := false
var _pending := false
## Game seconds since the last save; starts "long ago" so the first trigger saves immediately.
var _since_last_save := INF


func _init() -> void:
	process_mode = Node.PROCESS_MODE_PAUSABLE


func setup(backend: CloudBackend) -> void:
	_backend = backend
	if not _active:
		_active = true
		Core.state_value_changed.connect(_on_state_value_changed)


func _exit_tree() -> void:
	if _active and Core.state_value_changed.is_connected(_on_state_value_changed):
		Core.state_value_changed.disconnect(_on_state_value_changed)
	_active = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_PAUSED or what == NOTIFICATION_WM_CLOSE_REQUEST:
		if _active:
			save_now()


func _process(delta: float) -> void:
	_since_last_save += delta
	if _pending and _active and _since_last_save + _EPSILON >= MIN_INTERVAL_S:
		_save()


func _on_state_value_changed(key: StringName, _value: Variant) -> void:
	if key != StateKeys.EXPLORATION_COUNT or _restoring:
		return
	if _since_last_save + _EPSILON >= MIN_INTERVAL_S:
		_save()
	else:
		_pending = true


func save_now() -> Error:
	return _save()


func _save() -> Error:
	_pending = false
	_since_last_save = 0.0
	var error := Core.saves.save_game(SAVE_SLOT)
	var cloud_error: Error = ERR_SKIP  # local save failed: nothing to mirror
	if error == OK:
		var saved_at := int(Time.get_unix_time_from_system())
		_write_local_saved_at(SAVE_SLOT, saved_at)
		if _backend != null and _backend.is_available():
			cloud_error = _backend.push(SAVE_SLOT, make_envelope(Core.state.snapshot(), saved_at))
		else:
			cloud_error = ERR_UNAVAILABLE
	autosaved.emit(error, cloud_error)
	return error


func restore() -> Error:
	_restoring = true
	var result := _restore()
	_restoring = false
	_pending = false
	return result


func _restore() -> Error:
	var cloud := {}
	if _backend != null and _backend.is_available():
		cloud = parse_envelope(_backend.pull(SAVE_SLOT))
	var has_local := Core.saves.has_save(SAVE_SLOT)
	if cloud.is_empty() and not has_local:
		return ERR_FILE_NOT_FOUND
	var cloud_newer: bool = not cloud.is_empty() and (not has_local or cloud.saved_at_unix > read_local_saved_at(SAVE_SLOT))
	if not cloud_newer:
		var error := Core.saves.load_game(SAVE_SLOT)
		if error == OK or cloud.is_empty():
			return error
		# Local slot unreadable but the cloud has a valid (older) copy: better than nothing.
	Core.state.restore(cloud.snapshot)
	var save_error := Core.saves.save_game(SAVE_SLOT)
	if save_error == OK:
		_write_local_saved_at(SAVE_SLOT, cloud.saved_at_unix)
	return OK


# --- Envelope -------------------------------------------------------------------------------------------

## The cloud payload: var_to_str({"format", "version", "saved_at_unix", "snapshot"}) as UTF-8.
static func make_envelope(snapshot: Dictionary, saved_at_unix: int) -> PackedByteArray:
	return var_to_str({
		"format": ENVELOPE_FORMAT,
		"version": ENVELOPE_VERSION,
		"saved_at_unix": saved_at_unix,
		"snapshot": snapshot,
	}).to_utf8_buffer()


## Returns {"saved_at_unix": int, "snapshot": Dictionary}, or {} if `data` is empty, corrupt or not ours.
static func parse_envelope(data: PackedByteArray) -> Dictionary:
	if data.is_empty() or data.size() > MAX_PAYLOAD_BYTES or data[0] != 0x7B:  # '{'
		return {}
	var text := data.get_string_from_utf8()
	for token in _FORBIDDEN_TOKENS:
		if text.contains(token):
			return {}
	var parsed: Variant = str_to_var(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var env: Dictionary = parsed
	if env.get("format") != ENVELOPE_FORMAT or typeof(env.get("version")) != TYPE_INT \
			or env.version != ENVELOPE_VERSION:
		return {}
	if typeof(env.get("saved_at_unix")) != TYPE_INT or typeof(env.get("snapshot")) != TYPE_DICTIONARY:
		return {}
	var snapshot: Dictionary = env.snapshot
	if typeof(snapshot.get("values")) != TYPE_DICTIONARY:
		return {}
	return {"saved_at_unix": env.saved_at_unix, "snapshot": snapshot}


# --- Local timestamp sidecar ----------------------------------------------------------------------------

## UTC unix time of the last local save made by cloud_save for `slot`, or -1 if unknown.
static func read_local_saved_at(slot: int) -> int:
	var cfg := ConfigFile.new()
	if cfg.load(META_PATH) != OK:
		return -1
	var value: Variant = cfg.get_value(_section(slot), META_KEY, -1)
	return value if typeof(value) == TYPE_INT else -1


static func _write_local_saved_at(slot: int, saved_at_unix: int) -> void:
	DirAccess.make_dir_recursive_absolute(META_DIR)
	var cfg := ConfigFile.new()
	cfg.load(META_PATH)  # missing/corrupt file: start fresh
	cfg.set_value(_section(slot), META_KEY, saved_at_unix)
	var error := cfg.save(META_PATH)
	if error != OK:
		push_warning("cloud_save: cannot write %s (%s)" % [META_PATH, error_string(error)])


static func _section(slot: int) -> String:
	return "slot_%d" % slot
