## AutoSave implementation (created by internal/cloud_save_factory_impl.gd).
##
## Save: Core.saves.save_game(SAVE_SLOT); on OK, record the UTC time in our own sidecar (meta_path()) and push our own
## envelope (see make_envelope()) to the backend. The local save never waits for the cloud.
## Throttle: game time (sum of _process deltas, PROCESS_MODE_PAUSABLE so it stops while the tree is paused). The
## delta of the frame in which a save happened is not counted when that save ran before our _process (physics step,
## signals, other nodes' _process): that frame's time elapsed before the save. So the deferred save fires exactly
## MIN_INTERVAL_S of game time after the previous one (300 frames at 30 fps), not one frame early.
## Restore: the cloud envelope wins only if it is valid and strictly newer than the local sidecar timestamp (or no
## local save exists) and Core actually accepts its snapshot; otherwise the local slot is loaded.
## This module never reads core's save file; it only uses Core.state / Core.saves.
##
## Cloud data is untrusted: the v3 envelope's snapshot is decoded with bytes_to_var() (never with objects); v2
## (JSON.from_native) with JSON.to_native(..., false). Either is rejected if it carries (or tried to carry) objects,
## callables, signals or RIDs, is too deep or too large. Before a push the envelope is decoded again and must equal
## the snapshot (otherwise cloud_error ERR_INVALID_DATA and nothing is pushed).
extends AutoSave

## Sidecar location relative to CoreAPI.user_data_dir() (user:// in play, user://automation/ in test runs).
const META_SUBDIR := "cloud_save/"
const META_FILE := "meta.cfg"
const META_KEY := "saved_at_unix"
const ENVELOPE_FORMAT := "cloud_save"
## Written version: 3 = JSON with a Base64 var_to_bytes() snapshot. Version 2 (JSON.from_native) is still read;
## version 1 (var_to_str text) is not.
const ENVELOPE_VERSION := 3
const ENVELOPE_VERSION_V2 := 2
## Upper bound for a cloud payload we are willing to parse (iCloud key-value store limits a value to 1 MB).
const MAX_PAYLOAD_BYTES := 1024 * 1024
## Upper bound for the decoded v3 snapshot bytes (Base64 of this fits in MAX_PAYLOAD_BYTES).
const MAX_SNAPSHOT_BYTES := (MAX_PAYLOAD_BYTES >> 2) * 3
## Largest whole number a JSON (double) number holds exactly: 2^53.
const _MAX_JSON_INT := 9007199254740992.0
## cloud_error when the envelope would not decode back to the snapshot being saved (e.g. the state holds an
## object): nothing is pushed, the local save stands.
const ERR_ENVELOPE_MISMATCH := ERR_INVALID_DATA
## Deepest container nesting accepted in a cloud payload (raw JSON levels; a snapshot needs far fewer).
const MAX_DEPTH := 64
## Tolerance for float accumulation of frame deltas (300 * 1/30 may sum to 9.99999...). Far below one frame, so
## it can never make a save fire a frame early.
const _EPSILON := 1e-6
## Variant types that must never come out of cloud data.
const _FORBIDDEN_TYPES: Array[int] = [TYPE_OBJECT, TYPE_CALLABLE, TYPE_SIGNAL, TYPE_RID]

var _backend: CloudBackend
var _active := false
var _restoring := false
var _pending := false
## Game seconds since the last save; starts "long ago" so the first trigger saves immediately.
var _since_last_save := INF
## Engine.get_process_frames() at the last save; that frame's delta is not added (see the class doc).
var _last_save_frame := -1


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
	if Engine.get_process_frames() != _last_save_frame:
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
	_last_save_frame = Engine.get_process_frames()
	var error := Core.saves.save_game(SAVE_SLOT)
	var cloud_error: Error = ERR_SKIP  # local save failed: nothing to mirror
	if error == OK:
		var saved_at := int(Time.get_unix_time_from_system())
		_write_local_saved_at(SAVE_SLOT, saved_at)
		if _backend != null and _backend.is_available():
			var snapshot := Core.state.snapshot()
			var data := make_envelope(snapshot, saved_at)
			if envelope_matches(data, snapshot):
				cloud_error = _backend.push(SAVE_SLOT, data)
			else:
				cloud_error = ERR_ENVELOPE_MISMATCH
				push_warning("cloud_save: the envelope does not decode back to the state; not pushed")
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


## Test hook (overrides the public default once declared there): decodes a payload this AutoSave pushed to a
## CloudBackend. Returns {"saved_at_unix": int, "snapshot": Dictionary}, or {} if invalid. Any envelope version
## parse_envelope() reads (v3, v2) is accepted.
func decode_cloud_payload(data: PackedByteArray) -> Dictionary:
	var env := parse_envelope(data)
	if env.is_empty():
		return {}
	return {"saved_at_unix": int(env.saved_at_unix), "snapshot": env.snapshot}


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
	if not _state_matches(cloud.snapshot):
		# Core rejected the snapshot (restore() leaves the state unchanged): keep the local save and sidecar as is.
		push_warning("cloud_save: Core rejected the cloud snapshot; keeping the local save")
		return Core.saves.load_game(SAVE_SLOT) if has_local else ERR_FILE_NOT_FOUND
	var save_error := Core.saves.save_game(SAVE_SLOT)
	if save_error == OK:
		_write_local_saved_at(SAVE_SLOT, cloud.saved_at_unix)
	else:
		push_warning("cloud_save: restored the cloud state but could not save it locally (%s)" % error_string(save_error))
	return OK


## True if Core.state now holds `snapshot` (phase, paused flag and values).
static func _state_matches(snapshot: Dictionary) -> bool:
	var current := Core.state.snapshot()
	return StringName(current.get("phase", &"")) == StringName(snapshot.phase) \
			and current.get("paused") == snapshot.paused \
			and current.get("values") == snapshot.values


# --- Envelope -------------------------------------------------------------------------------------------

## The cloud payload (v3): UTF-8 JSON {"format", "version": 3, "saved_at_unix": int,
## "snapshot_b64": Marshalls.raw_to_base64(var_to_bytes(snapshot))}. The binary Variant encoding keeps every float
## bit-exact (T029: Godot's decimal parser does not round-trip ~12% of doubles even with 17 digits).
static func make_envelope(snapshot: Dictionary, saved_at_unix: int) -> PackedByteArray:
	var envelope := {
		"format": ENVELOPE_FORMAT,
		"version": ENVELOPE_VERSION,
		"saved_at_unix": saved_at_unix,
		"snapshot_b64": Marshalls.raw_to_base64(var_to_bytes(snapshot)),
	}
	return JSON.stringify(envelope).to_utf8_buffer()


## True if `data` decodes (parse_envelope) to exactly `snapshot`: `==`, or identical binary encoding (bit-level, so
## NaN, which is never == itself, still counts as equal when it round-trips). Checked before every push.
static func envelope_matches(data: PackedByteArray, snapshot: Dictionary) -> bool:
	var env := parse_envelope(data)
	if env.is_empty():
		return false
	var decoded: Dictionary = env.snapshot
	return decoded == snapshot or var_to_bytes(decoded) == var_to_bytes(snapshot)


## Returns {"saved_at_unix": int, "snapshot": Dictionary}, or {} if `data` is empty, corrupt, not ours, or carries
## anything that is not plain data. Accepts v3 (written now) and v2 (JSON.from_native, written by older builds).
static func parse_envelope(data: PackedByteArray) -> Dictionary:
	if data.is_empty() or data.size() > MAX_PAYLOAD_BYTES:
		return {}
	var json := JSON.new()
	if json.parse(data.get_string_from_utf8()) != OK:
		return {}
	var raw: Variant = json.data
	var env: Dictionary
	if raw is Dictionary and (raw as Dictionary).has("snapshot_b64"):
		env = _decode_v3(raw)
	else:
		env = _decode_v2(raw)
	if env.is_empty():
		return {}
	var snapshot: Dictionary = env.snapshot
	if not (typeof(snapshot.get("phase")) in [TYPE_STRING_NAME, TYPE_STRING]) \
			or typeof(snapshot.get("paused")) != TYPE_BOOL or typeof(snapshot.get("values")) != TYPE_DICTIONARY:
		return {}
	return env


## v3: plain JSON shape first, then strict Base64, then bytes_to_var (never the *_with_objects variant: a payload
## that encodes a full object fails to decode), then the decoded-type walk. The bytes must also be the canonical
## encoding of what they decode to (no trailing or padding garbage). {} on any failure.
static func _decode_v3(raw: Dictionary) -> Dictionary:
	if raw.size() != 4 or raw.get("format") != ENVELOPE_FORMAT or not _is_json_int(raw.get("version")) \
			or int(raw.version) != ENVELOPE_VERSION or not _is_json_int(raw.get("saved_at_unix")) \
			or typeof(raw.get("snapshot_b64")) != TYPE_STRING:
		return {}
	var b64: String = raw.snapshot_b64
	if b64.is_empty() or b64.length() % 4 != 0 or (b64.length() >> 2) * 3 > MAX_SNAPSHOT_BYTES \
			or _base64_regex().search(b64) == null:
		return {}
	var bytes := Marshalls.base64_to_raw(b64)
	if bytes.is_empty() or bytes.size() > MAX_SNAPSHOT_BYTES or Marshalls.raw_to_base64(bytes) != b64:
		return {}
	var decoded: Variant = bytes_to_var(bytes)
	if typeof(decoded) != TYPE_DICTIONARY or _check_decoded(decoded, 0) < 0:
		return {}
	if var_to_bytes(decoded) != bytes:
		return {}
	return {"saved_at_unix": int(raw.saved_at_unix), "snapshot": decoded}


## A JSON number that is a whole value within the exactly representable integer range (JSON numbers parse as float).
static func _is_json_int(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	return typeof(value) == TYPE_FLOAT and is_finite(value) and value == floorf(value) and absf(value) <= _MAX_JSON_INT


static var _b64_regex: RegEx


static func _base64_regex() -> RegEx:
	if _b64_regex == null:
		_b64_regex = RegEx.create_from_string("^[A-Za-z0-9+/]+={0,2}$")
	return _b64_regex


## v2 (read-only, backward compatibility): JSON.from_native({format, version, saved_at_unix, snapshot}, false).
## Encoded objects ({"type": <class>, "props": [...]}) and unknown types are refused before decoding, because
## to_native(allow_objects = false) would silently turn them into null.
static func _decode_v2(raw: Variant) -> Dictionary:
	var raw_nulls := _check_raw(raw, 0)
	if raw_nulls < 0:
		return {}
	var parsed: Variant = JSON.to_native(raw, false)
	# Every null in the result must come from a JSON null; extra nulls mean part of the payload failed to decode.
	var decoded_nulls := _check_decoded(parsed, 0)
	if decoded_nulls < 0 or decoded_nulls != raw_nulls:
		return {}
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var env: Dictionary = parsed
	if env.size() != 4 or env.get("format") != ENVELOPE_FORMAT or typeof(env.get("version")) != TYPE_INT \
			or env.version != ENVELOPE_VERSION_V2:
		return {}
	if typeof(env.get("saved_at_unix")) != TYPE_INT or typeof(env.get("snapshot")) != TYPE_DICTIONARY:
		return {}
	return {"saved_at_unix": env.saved_at_unix, "snapshot": env.snapshot}


## Walks raw parsed JSON. Returns the number of JSON nulls, or -1 if it is too deep or a typed node names a type
## that is not an allowed built-in (objects, callables, signals, RIDs, class names) or carries object properties.
static func _check_raw(value: Variant, depth: int) -> int:
	if depth > MAX_DEPTH:
		return -1
	match typeof(value):
		TYPE_NIL:
			return 1
		TYPE_ARRAY:
			var nulls := 0
			for item: Variant in value:
				var n := _check_raw(item, depth + 1)
				if n < 0:
					return -1
				nulls += n
			return nulls
		TYPE_DICTIONARY:
			var dict: Dictionary = value
			if dict.has("props") or (dict.has("type") and not _is_allowed_type_name(dict.type)):
				return -1
			var nulls := 0
			for key: Variant in dict:
				var n := _check_raw(dict[key], depth + 1)
				if n < 0:
					return -1
				nulls += n
			return nulls
	return 0


static func _is_allowed_type_name(type_name: Variant) -> bool:
	if typeof(type_name) != TYPE_STRING:
		return false
	for t in TYPE_MAX:
		if t != TYPE_NIL and not (t in _FORBIDDEN_TYPES) and type_string(t) == type_name:
			return true
	return false


## Walks the decoded value. Returns the number of nulls (array items, dictionary keys and values), or -1 if it is
## too deep or contains a forbidden type.
static func _check_decoded(value: Variant, depth: int) -> int:
	if depth > MAX_DEPTH:
		return -1
	var type := typeof(value)
	if type in _FORBIDDEN_TYPES:
		return -1
	match type:
		TYPE_NIL:
			return 1
		TYPE_ARRAY:
			var nulls := 0
			for item: Variant in value:
				var n := _check_decoded(item, depth + 1)
				if n < 0:
					return -1
				nulls += n
			return nulls
		TYPE_DICTIONARY:
			var dict: Dictionary = value
			var nulls := 0
			for key: Variant in dict:
				var nk := _check_decoded(key, depth + 1)
				var nv := _check_decoded(dict[key], depth + 1)
				if nk < 0 or nv < 0:
					return -1
				nulls += nk + nv
			return nulls
	return 0


# --- Local timestamp sidecar ----------------------------------------------------------------------------

## Directory of the sidecar, resolved at call time: CoreAPI.user_data_dir() + "cloud_save/".
static func meta_dir() -> String:
	return CoreAPI.user_data_dir() + META_SUBDIR


## Full sidecar path: CoreAPI.user_data_dir() + "cloud_save/meta.cfg".
static func meta_path() -> String:
	return meta_dir() + META_FILE


## UTC unix time of the last local save made by cloud_save for `slot`, or -1 if unknown.
static func read_local_saved_at(slot: int) -> int:
	var cfg := ConfigFile.new()
	if cfg.load(meta_path()) != OK:
		return -1
	var value: Variant = cfg.get_value(_section(slot), META_KEY, -1)
	return value if typeof(value) == TYPE_INT else -1


static func _write_local_saved_at(slot: int, saved_at_unix: int) -> void:
	var path := meta_path()
	var dir_error := DirAccess.make_dir_recursive_absolute(meta_dir())
	if dir_error != OK:
		push_warning("cloud_save: cannot create %s (%s)" % [meta_dir(), error_string(dir_error)])
	var cfg := ConfigFile.new()
	cfg.load(path)  # missing/corrupt file: start fresh
	cfg.set_value(_section(slot), META_KEY, saved_at_unix)
	var error := cfg.save(path)
	if error != OK:
		push_warning("cloud_save: cannot write %s (%s)" % [path, error_string(error)])


static func _section(slot: int) -> String:
	return "slot_%d" % slot
