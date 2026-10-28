## Unit tests for the cloud_save autosave policy, envelope, restore decisions and backends.
## Frames are 1/30 s (runner uses --fixed-fps 30). Uses only Core public API (state/saves) plus this module.
extends TestCase

const AutoSaveImpl := preload("res://modules/cloud_save/internal/auto_save_impl.gd")
const COUNT := StateKeys.EXPLORATION_COUNT
const SLOT := AutoSave.SAVE_SLOT

var factory: CloudSaveFactory
var auto_save: AutoSave
var fake: CloudBackend
var events: Array = []  # [error, cloud_error] per autosaved emission
var _initial_state: Dictionary
## The player's (non-test) sidecar directory. Spelled out only here, to prove test runs never touch it.
const PLAYER_META_DIR := "user://cloud_save/"
var _player_dir_before: Dictionary
## True if this test file created the automation sidecar dir (only then is it removed in after_all).
var _created_meta_dir := false


func before_all() -> void:
	factory = CloudSaveFactory.create()
	_initial_state = Core.state.snapshot()
	_player_dir_before = _listing(PLAYER_META_DIR)
	_created_meta_dir = not DirAccess.dir_exists_absolute(AutoSaveImpl.meta_dir())


func after_all() -> void:
	_cleanup_files()
	if _created_meta_dir and DirAccess.dir_exists_absolute(AutoSaveImpl.meta_dir()) \
			and DirAccess.get_files_at(AutoSaveImpl.meta_dir()).is_empty():
		DirAccess.remove_absolute(AutoSaveImpl.meta_dir())
	Core.state.restore(_initial_state)


## {"exists": bool, "files": {name: mtime}} for a directory, without changing anything.
static func _listing(dir: String) -> Dictionary:
	var files := {}
	var exists := DirAccess.dir_exists_absolute(dir)
	if exists:
		for f in DirAccess.get_files_at(dir):
			files[f] = FileAccess.get_modified_time(dir + f)
	return {"exists": exists, "files": files}


func before_each() -> void:
	_cleanup_files()
	Core.state.restore(_initial_state)
	Core.state.set_value(COUNT, 0)
	events.clear()


func after_each() -> void:
	get_tree().paused = false
	if auto_save != null:
		remove_child(auto_save)
		auto_save.free()
		auto_save = null
	fake = null
	_cleanup_files()


func _cleanup_files() -> void:
	if Core.saves.has_save(SLOT):
		Core.saves.delete_save(SLOT)
	if FileAccess.file_exists(AutoSaveImpl.meta_path()):
		DirAccess.remove_absolute(AutoSaveImpl.meta_path())


func _start(available := true) -> void:
	fake = factory.make_fake_backend(available)
	auto_save = factory.make_auto_save()
	add_child(auto_save)
	auto_save.autosaved.connect(func(e: Error, ce: Error) -> void: events.append([e, ce]))
	auto_save.setup(fake)


func _bump() -> void:
	Core.state.set_value(COUNT, int(Core.state.get_value(COUNT, 0)) + 1)


# --- throttle -------------------------------------------------------------------------------------------

func test_throttle_one_immediate_then_one_after_interval() -> void:
	_start()
	_bump()
	assert_eq(events.size(), 1, "first cell saves immediately")
	await wait_frames(5)
	_bump()
	assert_eq(events.size(), 1, "second cell within 10 s is deferred")
	await wait_frames(280)  # ~9.5 s since the first save
	assert_eq(events.size(), 1, "still within the interval")
	await wait_frames(30)  # ~10.5 s
	assert_eq(events.size(), 2, "pending save done when the interval ended")
	var count_after_two := int(Core.state.get_value(COUNT))
	var env := AutoSaveImpl.parse_envelope(fake.pushes[-1].data)
	assert_eq(int(env.snapshot.values[COUNT]), count_after_two, "deferred save has the latest state")
	await wait_frames(330)  # another 11 s with nothing pending
	assert_eq(events.size(), 2, "no save without a pending trigger")


## Frames (Engine.get_process_frames()) at which `autosaved` fired.
var save_frames: Array[int] = []


func _start_recording_frames() -> void:
	save_frames.clear()
	auto_save.autosaved.connect(func(_e: Error, _ce: Error) -> void: save_frames.append(Engine.get_process_frames()))


## M1 QA F2: the deferred save comes >= 10 s of game time after the first (300 frames at 30 fps), at most a frame later.
## The first save here is triggered from the test coroutine (resumed on process_frame, before AutoSave._process).
func test_throttle_deferred_save_after_full_interval_from_process() -> void:
	_start()
	_start_recording_frames()
	await wait_frames(1)
	_bump()
	await wait_frames(3)
	_bump()  # pending
	await wait_frames(310)
	assert_eq(save_frames.size(), 2, "immediate + deferred save")
	if save_frames.size() == 2:
		var gap := save_frames[1] - save_frames[0]
		assert_between(gap, 300, 301, "deferred save gap %d frames (>= 10 s at 30 fps)" % gap)


## Same, with the first save triggered during the physics step (as exploration does in the game).
func test_throttle_deferred_save_after_full_interval_from_physics() -> void:
	_start()
	_start_recording_frames()
	var bumps := [0]
	var on_physics := func() -> void:
		if bumps[0] < 2:
			bumps[0] += 1
			_bump()  # first: immediate save; second (next physics step): pending
	get_tree().physics_frame.connect(on_physics)
	await wait_frames(320)
	get_tree().physics_frame.disconnect(on_physics)
	assert_eq(bumps[0], 2)
	assert_eq(save_frames.size(), 2, "immediate + deferred save")
	if save_frames.size() == 2:
		var gap := save_frames[1] - save_frames[0]
		assert_between(gap, 300, 301, "deferred save gap %d frames (>= 10 s at 30 fps)" % gap)


## A trigger at 299 frames is still inside the interval; it is saved exactly 300 frames after the first save.
func test_throttle_trigger_just_before_interval_end_is_deferred_one_frame() -> void:
	_start()
	_start_recording_frames()
	await wait_frames(1)
	_bump()
	await wait_frames(299)
	_bump()
	assert_eq(save_frames.size(), 1, "299 frames (9.97 s) is still inside the interval")
	await wait_frames(3)
	assert_eq(save_frames.size(), 2, "pending saved when the interval ended")
	if save_frames.size() == 2:
		assert_eq(save_frames[1] - save_frames[0], 300)


func test_many_triggers_in_interval_give_one_pending_save() -> void:
	_start()
	_bump()
	for i in 5:
		await wait_frames(10)
		_bump()
	assert_eq(events.size(), 1)
	await wait_frames(300)
	assert_eq(events.size(), 2, "at most one pending save")


func test_other_keys_do_not_trigger() -> void:
	_start()
	Core.state.set_value(StateKeys.PLAYER_YAW, 1.25)
	assert_eq(events.size(), 0)
	Core.state.set_value(StateKeys.PLAYER_YAW, null)


func test_no_trigger_before_setup() -> void:
	auto_save = factory.make_auto_save()
	add_child(auto_save)
	auto_save.autosaved.connect(func(e: Error, ce: Error) -> void: events.append([e, ce]))
	_bump()
	auto_save.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
	assert_eq(events.size(), 0)
	assert_false(Core.saves.has_save(SLOT))


func test_save_now_ignores_throttle() -> void:
	_start()
	_bump()
	assert_eq(events.size(), 1)
	assert_eq(auto_save.save_now(), OK)
	assert_eq(events.size(), 2, "save_now saves inside the interval")
	assert_eq(auto_save.save_now(), OK)
	assert_eq(events.size(), 3)


func test_pause_notification_triggers_save() -> void:
	_start()
	_bump()
	_bump()  # pending
	auto_save.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
	assert_eq(events.size(), 2, "background saves immediately")
	await wait_frames(320)
	assert_eq(events.size(), 2, "pending was satisfied by the background save")


func test_throttle_does_not_advance_while_tree_paused() -> void:
	_start()
	_bump()
	_bump()  # pending
	assert_eq(events.size(), 1)
	get_tree().paused = true
	await wait_frames(400)  # ~13 s of wall frames, but no game time for the PAUSABLE autosave
	assert_eq(events.size(), 1, "no save while the tree is paused")
	get_tree().paused = false
	await wait_frames(280)  # ~9.3 s of game time since the first save
	assert_eq(events.size(), 1, "interval counts only unpaused time")
	await wait_frames(30)
	assert_eq(events.size(), 2, "pending saved once 10 s of game time passed")


func test_close_request_triggers_save() -> void:
	_start()
	auto_save.notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	assert_eq(events.size(), 1)
	assert_true(Core.saves.has_save(SLOT))


# --- envelope / backends --------------------------------------------------------------------------------

func test_fake_backend_receives_envelope_of_saved_state() -> void:
	_start()
	Core.state.set_value(StateKeys.PLAYER_POSITION, Vector3(1.5, 0.25, -3.75))
	_bump()
	var expected := Core.state.snapshot()
	assert_eq(events, [[OK, OK]])
	assert_eq(fake.pushes.size(), 1)
	assert_eq(fake.pushes[0].slot, SLOT)
	# Decoded by hand from the documented v3 format (not through parse_envelope()).
	var raw: Variant = JSON.parse_string((fake.pushes[0].data as PackedByteArray).get_string_from_utf8())
	assert_eq(typeof(raw), TYPE_DICTIONARY)
	var keys: Array = raw.keys()
	keys.sort()
	assert_eq(keys, ["format", "saved_at_unix", "snapshot_b64", "version"])
	assert_eq(raw.format, "cloud_save")
	assert_eq(raw.version, 3.0)
	assert_eq(raw.saved_at_unix, floorf(raw.saved_at_unix), "whole-second timestamp")
	assert_almost_eq(raw.saved_at_unix, Time.get_unix_time_from_system(), 5.0)
	assert_eq(bytes_to_var(Marshalls.base64_to_raw(raw.snapshot_b64)), expected,
			"snapshot equals Core.state.snapshot() at save time")
	assert_eq(int(raw.saved_at_unix), AutoSaveImpl.read_local_saved_at(SLOT), "sidecar matches the envelope")
	Core.state.set_value(StateKeys.PLAYER_POSITION, null)


func test_unavailable_backend_saves_locally() -> void:
	_start(false)
	_bump()
	assert_eq(events, [[OK, ERR_UNAVAILABLE]])
	assert_true(Core.saves.has_save(SLOT), "local save exists")
	assert_eq(fake.pushes.size(), 0)
	assert_ne(AutoSaveImpl.read_local_saved_at(SLOT), -1, "sidecar written")


func test_local_only_backend() -> void:
	var b := factory.make_platform_backend()
	assert_false(b.is_available())
	assert_eq(b.push(SLOT, PackedByteArray([1, 2, 3])), ERR_UNAVAILABLE)
	assert_eq(b.pull(SLOT), PackedByteArray())


func test_fake_backend_availability() -> void:
	var b := factory.make_fake_backend(false)
	assert_false(b.is_available())
	assert_eq(b.push(SLOT, PackedByteArray([1])), ERR_UNAVAILABLE)
	b.available = true
	assert_eq(b.push(SLOT, PackedByteArray([1, 2])), OK)
	assert_eq(b.pull(SLOT), PackedByteArray([1, 2]))
	b.available = false
	assert_eq(b.pull(SLOT), PackedByteArray())


# --- restore --------------------------------------------------------------------------------------------

## Saves count=5 locally (and to the fake), then sets count=0 so restore is observable. Returns local timestamp.
func _local_save_of_five() -> int:
	Core.state.set_value(COUNT, 5)
	auto_save.save_now()
	Core.state.set_value(COUNT, 0)
	return AutoSaveImpl.read_local_saved_at(SLOT)


func _cloud_with_count(count: int, saved_at: int) -> void:
	var snap := Core.state.snapshot()
	snap.values[COUNT] = count
	fake.store[SLOT] = AutoSaveImpl.make_envelope(snap, saved_at)


func test_restore_fresh_game() -> void:
	_start()
	assert_eq(auto_save.restore(), ERR_FILE_NOT_FOUND)
	assert_eq(events.size(), 0)


func test_restore_local_only() -> void:
	_start(false)
	_local_save_of_five()
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 5)


func test_restore_cloud_only() -> void:
	_start()
	_cloud_with_count(9, 1000)
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 9)
	assert_true(Core.saves.has_save(SLOT), "cloud state written to the local slot")
	assert_eq(AutoSaveImpl.read_local_saved_at(SLOT), 1000)


func test_restore_cloud_newer_wins_and_is_saved_locally() -> void:
	_start()
	var local_ts := _local_save_of_five()
	assert_ne(local_ts, -1)
	_cloud_with_count(9, local_ts + 100)
	var before := events.size()
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 9, "cloud snapshot restored")
	assert_eq(events.size(), before, "restore does not trigger autosave")
	assert_eq(AutoSaveImpl.read_local_saved_at(SLOT), local_ts + 100, "sidecar takes the cloud time")
	await wait_frames(320)
	assert_eq(events.size(), before, "no pending save left by restore")
	remove_child(auto_save)  # stop the policy so the checks below do not autosave
	Core.state.set_value(COUNT, 0)
	assert_eq(Core.saves.load_game(SLOT), OK)
	assert_eq(Core.state.get_value(COUNT), 9, "local slot now holds the cloud state")
	add_child(auto_save)


func test_restore_local_newer_wins() -> void:
	_start()
	var local_ts := _local_save_of_five()
	_cloud_with_count(9, local_ts - 100)
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 5)


func test_restore_same_time_prefers_local() -> void:
	_start()
	var local_ts := _local_save_of_five()
	_cloud_with_count(9, local_ts)
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 5)


func test_restore_corrupt_cloud_local_wins() -> void:
	_start()
	_local_save_of_five()
	var good_snap := {"phase": &"boot", "paused": false, "values": {COUNT: 9}}
	var corrupt: Array[PackedByteArray] = [
		PackedByteArray([0xFF, 0x00, 0x13, 0x37]),
		"{ not a dictionary".to_utf8_buffer(),
		_json({"format": "other", "version": 2, "saved_at_unix": 9999999999, "snapshot": good_snap}),
		_json({"format": "cloud_save", "version": 1, "saved_at_unix": 9999999999, "snapshot": good_snap}),
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": "soon", "snapshot": good_snap}),
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999, "snapshot": {"values": {}}}),
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999,
				"snapshot": {"phase": &"boot", "paused": "no", "values": {}}}),
		# version-1 (var_to_str) payload of an otherwise valid, newer envelope
		var_to_str({"format": "cloud_save", "version": 1, "saved_at_unix": 9999999999,
				"snapshot": good_snap}).to_utf8_buffer(),
		# plain JSON (not from_native encoded)
		'{"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999, "snapshot": {}}'.to_utf8_buffer(),
		PackedByteArray(),
	]
	for data in corrupt:
		fake.store[SLOT] = data
		Core.state.set_value(COUNT, 0)
		assert_eq(auto_save.restore(), OK)
		assert_eq(Core.state.get_value(COUNT), 5, "local wins over corrupt cloud %s" % data)


func _json(envelope: Dictionary, allow_objects := false) -> PackedByteArray:
	return JSON.stringify(JSON.from_native(envelope, allow_objects)).to_utf8_buffer()


## Instances of the probe script count themselves, so a test can prove no object was created from cloud data.
const ObjectProbe := preload("res://modules/cloud_save/tests/object_probe.gd")


func test_restore_rejects_json_encoded_object() -> void:
	_start()
	_local_save_of_five()
	var probe := ObjectProbe.new()
	var created_before := ObjectProbe.created
	var payloads: Array[PackedByteArray] = [
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999,
				"snapshot": {"phase": &"boot", "paused": false, "values": {COUNT: 9, &"x/evil": probe}}}, true),
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999,
				"snapshot": {"phase": &"boot", "paused": false, "values": {COUNT: 9, &"x/evil": RefCounted.new()}}}, true),
		_json({"format": "cloud_save", "version": 2, "saved_at_unix": 9999999999,
				"snapshot": {"phase": &"boot", "paused": false, "values": {COUNT: 9, &"x/evil": [1, [probe]]}}}, true),
	]
	assert_true(payloads[0].get_string_from_utf8().contains("object_probe.gd"), "encoder really embedded the object")
	for data in payloads:
		assert_true(AutoSaveImpl.parse_envelope(data).is_empty(), "object payload rejected")
		fake.store[SLOT] = data
		Core.state.set_value(COUNT, 0)
		assert_eq(auto_save.restore(), OK)
		assert_eq(Core.state.get_value(COUNT), 5, "local wins over object payload")
		assert_false(Core.state.has_value(&"x/evil"))
	assert_eq(ObjectProbe.created, created_before, "no object created from cloud data")
	probe = null


func test_restore_rejects_var_to_str_object_bypasses() -> void:
	_start()
	_local_save_of_five()
	var head := '{"format": "cloud_save", "version": 1, "saved_at_unix": 9999999999, "snapshot": '
	head += '{"phase": &"boot", "paused": false, "values": {&"x/evil": '
	var bodies: Array[String] = [
		'Object (RefCounted,"script":null)',
		'Object\t(RefCounted,"script":null)',
		'Object;c\n(RefCounted,"script":null)',
		'Object(RefCounted,"script":null)',
		'Resource ("res://modules/cloud_save/tests/auto_save_test.gd")',
	]
	for body in bodies:
		var data := (head + body + ', &"exploration/count": 9}}}').to_utf8_buffer()
		assert_true(AutoSaveImpl.parse_envelope(data).is_empty(), "rejected: %s" % body.c_escape())
		fake.store[SLOT] = data
		Core.state.set_value(COUNT, 0)
		assert_eq(auto_save.restore(), OK)
		assert_eq(Core.state.get_value(COUNT), 5, "local wins over %s" % body.c_escape())
		assert_false(Core.state.has_value(&"x/evil"))


func test_envelope_round_trips_native_types_exactly() -> void:
	var snap := {"phase": &"playing", "paused": true, "values": {
		COUNT: 12,
		StateKeys.PLAYER_POSITION: Vector3(1.5, 0.25, -3.75),
		&"x/name": &"cell_a",
		&"x/text": "s:not a prefix",
		&"x/yaw": 1.25,
		&"x/list": [1, "two", &"three", Vector2i(4, 5), null],
	}}
	var env := AutoSaveImpl.parse_envelope(AutoSaveImpl.make_envelope(snap, 1700000000))
	assert_eq(env.saved_at_unix, 1700000000)
	assert_eq(typeof(env.saved_at_unix), TYPE_INT)
	assert_eq(env.snapshot, snap)
	assert_eq(typeof(env.snapshot.phase), TYPE_STRING_NAME)
	var pos: Variant = env.snapshot.values[StateKeys.PLAYER_POSITION]
	assert_eq(typeof(pos), TYPE_VECTOR3)
	assert_eq(pos, Vector3(1.5, 0.25, -3.75))
	assert_eq(typeof(env.snapshot.values[&"x/name"]), TYPE_STRING_NAME)
	assert_eq(typeof(env.snapshot.values[&"x/text"]), TYPE_STRING)
	assert_eq(typeof(env.snapshot.values[COUNT]), TYPE_INT)
	for key: Variant in env.snapshot.values:
		assert_eq(typeof(key), TYPE_STRING_NAME, "key %s stays StringName" % key)


## Decodes `values` through make_envelope() + parse_envelope(); returns the decoded values, or null if rejected.
func _round_trip_values(values: Dictionary) -> Variant:
	var snap := {"phase": &"playing", "paused": false, "values": values}
	var env := AutoSaveImpl.parse_envelope(AutoSaveImpl.make_envelope(snap, 1700000000))
	return null if env.is_empty() else env.snapshot.values


## Exact float equality that also tells -0.0 from 0.0 (== does not).
static func _same_float(a: Variant, b: Variant) -> bool:
	return typeof(a) == TYPE_FLOAT and typeof(b) == TYPE_FLOAT and a == b and var_to_bytes(a) == var_to_bytes(b)


## M1 QA F1 / T029 review: the reviewer's counterexamples for the decimal (v2) encoding round-trip exactly in v3.
func test_v3_round_trips_review_counterexamples() -> void:
	var values := {&"x/eleventh": 1.0 / 11.0, StateKeys.PLAYER_YAW: -1.5142379999160767,
			StateKeys.PLAYER_POSITION: Vector3(1.0 / 3.0, -2.0 / 3.0, 10.1)}
	var got: Variant = _round_trip_values(values)
	assert_true(got is Dictionary, "envelope parsed")
	if not got is Dictionary:
		return
	assert_eq(got, values)
	assert_true(_same_float(got[&"x/eleventh"], 1.0 / 11.0), "1/11: %s" % var_to_str(got[&"x/eleventh"]))
	assert_true(_same_float(got[StateKeys.PLAYER_YAW], -1.5142379999160767))
	assert_eq(got[StateKeys.PLAYER_POSITION], Vector3(1.0 / 3.0, -2.0 / 3.0, 10.1))


## 10k float32-widened yaws in [-PI, PI], each in its own envelope as the player writes it (fixed seed, local RNG).
func test_v3_round_trips_10k_float32_yaws() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20291
	var wrong := 0
	var first_wrong := ""
	for i in 10000:
		var yaw: float = PackedFloat32Array([rng.randf_range(-PI, PI)])[0]
		var got: Variant = _round_trip_values({StateKeys.PLAYER_YAW: yaw})
		if not (got is Dictionary and _same_float(got.get(StateKeys.PLAYER_YAW), yaw)):
			wrong += 1
			if first_wrong.is_empty():
				first_wrong = "%s -> %s" % [var_to_str(yaw), var_to_str(got)]
	assert_eq(wrong, 0, "yaws not exact (first: %s)" % first_wrong)


## 10k random doubles: 5k from random bit patterns (every exponent, subnormals) and 5k uniform in +-1e6.
func test_v3_round_trips_10k_random_doubles() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20292
	var bits := PackedByteArray()
	bits.resize(8)
	var wrong := 0
	var first_wrong := ""
	var tested := 0
	while tested < 10000:
		var x: float
		if tested < 5000:
			bits.encode_u32(0, rng.randi())
			bits.encode_u32(4, rng.randi())
			x = bits.decode_double(0)
			if not is_finite(x):
				continue
		else:
			x = rng.randf_range(-1e6, 1e6)
		tested += 1
		var got: Variant = _round_trip_values({&"x/d": x, &"x/l": [x]})
		if not (got is Dictionary and _same_float(got.get(&"x/d"), x) and _same_float(got.get(&"x/l")[0], x)):
			wrong += 1
			if first_wrong.is_empty():
				first_wrong = "%s -> %s" % [var_to_str(x), var_to_str(got)]
	assert_eq(wrong, 0, "doubles not exact (first: %s)" % first_wrong)


func test_v3_round_trips_special_floats_and_containers() -> void:
	var values := {
		&"x/nan": NAN,
		&"x/inf": INF,
		&"x/ninf": -INF,
		&"x/neg_zero": -0.0,
		&"x/nan_vec": Vector3(NAN, 1.0 / 3.0, INF),
		&"x/third_vec": Vector3(1.0 / 3.0, -1.0 / 3.0, 0.1),
		&"x/tiny": 5e-324,
		&"x/huge": 1.7976931348623157e308,
		&"x/f64": PackedFloat64Array([1.0 / 3.0, -PI, 1.0 / 11.0]),
		&"x/f32": PackedFloat32Array([1.0 / 3.0, -PI]),
		&"x/i64": PackedInt64Array([-9223372036854775807, 9007199254740993]),
		&"x/i32": PackedInt32Array([-2147483648, 7]),
		&"x/bytes": PackedByteArray([0, 255, 3]),
		&"x/strings": PackedStringArray(["a", "", "ü"]),
		&"x/v3s": PackedVector3Array([Vector3(1.0 / 7.0, 0.1, -0.2)]),
		&"x/typed": [1.0 / 7.0] as Array[float],
		&"x/nested": {"k": {1.0 / 9.0: [2.0 / 3.0, {&"deep": Vector2i(4, 5)}]}},
		&"x/name": &"cell_a",
		&"x/text": "s:not a prefix",
		&"x/big_int": 1234567890123,
		&"x/null": null,
	}
	var got: Variant = _round_trip_values(values)
	assert_true(got is Dictionary, "envelope parsed")
	if not got is Dictionary:
		return
	assert_true(is_nan(got[&"x/nan"]), "NaN stays NaN")
	assert_true(is_inf(got[&"x/inf"]) and got[&"x/inf"] > 0, "+INF")
	assert_true(is_inf(got[&"x/ninf"]) and got[&"x/ninf"] < 0, "-INF")
	assert_true(_same_float(got[&"x/neg_zero"], -0.0) and 1.0 / got[&"x/neg_zero"] < 0, "-0.0 keeps its sign")
	var v: Vector3 = got[&"x/nan_vec"]
	var v_in: Vector3 = values[&"x/nan_vec"]
	assert_true(is_nan(v.x) and v.y == v_in.y and is_inf(v.z) and v.z > 0, "NaN/INF in a vector")
	for key: Variant in values:
		if key in [&"x/nan", &"x/nan_vec"]:
			continue
		assert_eq(typeof(got[key]), typeof(values[key]), "type of %s" % key)
		assert_true(got[key] == values[key], "%s: %s vs %s" % [key, var_to_str(got[key]), var_to_str(values[key])])
	for key: Variant in values:
		assert_eq(var_to_bytes(got[key]), var_to_bytes(values[key]), "%s bit-exact" % key)
	assert_eq((got[&"x/typed"] as Array).get_typed_builtin(), TYPE_FLOAT, "typed array stays typed")
	for key: Variant in got:
		assert_eq(typeof(key), TYPE_STRING_NAME, "key %s stays StringName" % key)


func test_envelope_matches_is_nan_aware_and_refuses_undecodable() -> void:
	var nan_snap := {"phase": &"playing", "paused": false, "values": {StateKeys.PLAYER_POSITION: Vector3(NAN, 0, 0)}}
	assert_true(AutoSaveImpl.envelope_matches(AutoSaveImpl.make_envelope(nan_snap, 1), nan_snap), "NaN round-trips")
	for bad: Variant in [RefCounted.new(), Callable(self, "after_each"), RID()]:
		var snap := {"phase": &"playing", "paused": false, "values": {&"x/bad": bad}}
		assert_false(AutoSaveImpl.envelope_matches(AutoSaveImpl.make_envelope(snap, 1), snap),
				"%s refused" % type_string(typeof(bad)))


## The real autosave path with an awkward float32-widened yaw, then a NaN vector: pushed envelope == state.
func test_autosave_envelope_equals_state_with_awkward_floats() -> void:
	_start()
	Core.state.set_value(StateKeys.PLAYER_YAW, -1.5142379999160767)
	Core.state.set_value(StateKeys.PLAYER_POSITION, Vector3(1.0 / 3.0, 0.1, -7.0 / 3.0))
	_bump()
	var expected := Core.state.snapshot()
	assert_eq(events, [[OK, OK]])
	assert_eq(fake.pushes.size(), 1)
	var env := AutoSaveImpl.parse_envelope(fake.pushes[0].data)
	assert_false(env.is_empty())
	if not env.is_empty():
		assert_eq(env.snapshot, expected, "envelope snapshot == Core.state.snapshot()")
		assert_true(_same_float(env.snapshot.values[StateKeys.PLAYER_YAW], -1.5142379999160767), "yaw bit-exact")
	Core.state.set_value(StateKeys.PLAYER_POSITION, Vector3(NAN, 0.0, 1.0 / 3.0))
	auto_save.save_now()
	assert_eq(events.size(), 2)
	if events.size() == 2:
		assert_eq(events[1], [OK, OK], "NaN vector state is pushed (it round-trips bit-exactly)")
	if fake.pushes.size() == 2:
		var env2 := AutoSaveImpl.parse_envelope(fake.pushes[1].data)
		assert_false(env2.is_empty())
		if not env2.is_empty():
			assert_eq(var_to_bytes(env2.snapshot), var_to_bytes(Core.state.snapshot()), "bit-exact incl. NaN")
	Core.state.set_value(StateKeys.PLAYER_YAW, null)
	Core.state.set_value(StateKeys.PLAYER_POSITION, null)


## A full 20x20 maze state stays far below MAX_PAYLOAD_BYTES and parses back exactly.
func test_envelope_size_for_20x20_maze() -> void:
	var bits := PackedByteArray()
	bits.resize(int(ceil(20 * 20 / 8.0)))
	bits.fill(0xFF)
	var snap := {"phase": &"playing", "paused": false, "values": {
		StateKeys.PLAYER_POSITION: Vector3(1.0 / 3.0, 0.1, -7.0 / 3.0),
		StateKeys.PLAYER_YAW: -1.5142379999160767,
		StateKeys.PLAYER_STANCE: StateKeys.STANCE_CRAWL,
		StateKeys.EXPLORATION_VISITED: Marshalls.raw_to_base64(bits),
		StateKeys.EXPLORATION_COUNT: 400,
		StateKeys.MAZE_SEED: 1234567890123,
	}}
	var data := AutoSaveImpl.make_envelope(snap, 1700000000)
	print("cloud_save: 20x20 maze v3 envelope = %d bytes" % data.size())
	assert_true(data.size() < 4096, "20x20 envelope is %d bytes" % data.size())
	assert_eq(AutoSaveImpl.parse_envelope(data).get("snapshot"), snap)


# --- v2 backward compatibility --------------------------------------------------------------------------

## A v2 envelope exactly as the previous build wrote it (JSON.from_native, default JSON.stringify).
static func _v2_envelope(snapshot: Dictionary, saved_at_unix: int) -> PackedByteArray:
	return JSON.stringify(JSON.from_native({"format": "cloud_save", "version": 2, "saved_at_unix": saved_at_unix,
			"snapshot": snapshot}, false)).to_utf8_buffer()


func test_v2_envelope_still_decodes() -> void:
	var snap := {"phase": &"playing", "paused": true, "values": {
		COUNT: 12,
		StateKeys.PLAYER_POSITION: Vector3(1.5, 0.25, -3.75),
		StateKeys.PLAYER_YAW: 1.25,
		&"x/name": &"cell_a",
		&"x/list": [1, "two", &"three", Vector2i(4, 5), null],
	}}
	var env := AutoSaveImpl.parse_envelope(_v2_envelope(snap, 1700000000))
	assert_false(env.is_empty(), "v2 parsed")
	if env.is_empty():
		return
	assert_eq(env.saved_at_unix, 1700000000)
	assert_eq(typeof(env.saved_at_unix), TYPE_INT)
	assert_eq(env.snapshot, snap)
	assert_eq(typeof(env.snapshot.phase), TYPE_STRING_NAME)


func test_restore_from_newer_v2_cloud() -> void:
	_start()
	var local_ts := _local_save_of_five()
	var snap := Core.state.snapshot()
	snap.values[COUNT] = 9
	fake.store[SLOT] = _v2_envelope(snap, local_ts + 100)
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 9, "v2 cloud snapshot restored")
	assert_eq(AutoSaveImpl.read_local_saved_at(SLOT), local_ts + 100)


# --- v3 security ----------------------------------------------------------------------------------------

## A v3 envelope with arbitrary top-level fields (defaults: a valid, very new envelope of good_snap()).
static func _v3(overrides: Dictionary = {}, remove: Array = []) -> PackedByteArray:
	var env := {"format": "cloud_save", "version": 3, "saved_at_unix": 9999999999,
			"snapshot_b64": Marshalls.raw_to_base64(var_to_bytes(_good_snap()))}
	env.merge(overrides, true)
	for k: String in remove:
		env.erase(k)
	return JSON.stringify(env).to_utf8_buffer()


static func _good_snap() -> Dictionary:
	return {"phase": &"boot", "paused": false, "values": {COUNT: 9}}


static func _v3_bytes(bytes: PackedByteArray) -> PackedByteArray:
	return _v3({"snapshot_b64": Marshalls.raw_to_base64(bytes)})


static func _snap_with(evil: Variant) -> Dictionary:
	return {"phase": &"boot", "paused": false, "values": {COUNT: 9, &"x/evil": evil}}


## Variant header of `type` followed by a huge declared element count / length and nothing else.
static func _huge_header(type: int) -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(8)
	b.encode_u32(0, type)
	b.encode_u32(4, 0x7FFFFFFF)
	return b


func test_v3_valid_helper_payload_is_accepted() -> void:
	var env := AutoSaveImpl.parse_envelope(_v3())
	assert_eq(env.get("snapshot"), _good_snap(), "baseline: the crafted-payload helper makes a valid envelope")
	assert_eq(env.get("saved_at_unix"), 9999999999)


func test_v3_crafted_payloads_rejected_without_objects() -> void:
	_start()
	_local_save_of_five()
	var probe := ObjectProbe.new()
	var good_bytes := var_to_bytes(_good_snap())
	var with_objects := var_to_bytes_with_objects(_snap_with(probe))
	assert_true(_contains(with_objects, "object_probe.gd"),
			"encoder really embedded the object's script")
	var deep: Variant = 1
	for i in 100:
		deep = [deep]
	var oversized := _v3({"snapshot_b64": "A".repeat(AutoSaveImpl.MAX_PAYLOAD_BYTES)})
	var payloads := {
		"full object": _v3_bytes(with_objects),
		"full RefCounted": _v3_bytes(var_to_bytes_with_objects(_snap_with(RefCounted.new()))),
		"object as id": _v3_bytes(var_to_bytes(_snap_with(probe))),
		"object id nested in array": _v3_bytes(var_to_bytes(_snap_with([1, [probe]]))),
		"callable": _v3_bytes(var_to_bytes(_snap_with(Callable(probe, "free")))),
		"signal": _v3_bytes(var_to_bytes(_snap_with(Signal(probe, "x")))),
		"rid": _v3_bytes(var_to_bytes(_snap_with(RID()))),
		"too deep": _v3_bytes(var_to_bytes(_snap_with(deep))),
		"truncated": _v3_bytes(good_bytes.slice(0, good_bytes.size() - 5)),
		"trailing bytes": _v3_bytes(good_bytes + PackedByteArray([0, 0, 0, 0])),
		"huge array": _v3_bytes(_huge_header(TYPE_ARRAY)),
		"huge dictionary": _v3_bytes(_huge_header(TYPE_DICTIONARY)),
		"huge packed bytes": _v3_bytes(_huge_header(TYPE_PACKED_BYTE_ARRAY)),
		"huge string": _v3_bytes(_huge_header(TYPE_STRING)),
		"array top level": _v3_bytes(var_to_bytes([_good_snap()])),
		"string top level": _v3_bytes(var_to_bytes("snapshot")),
		"bad snapshot shape": _v3_bytes(var_to_bytes({"values": {}})),
		"empty base64": _v3({"snapshot_b64": ""}),
		"bad base64": _v3({"snapshot_b64": "!!!!"}),
		"base64 with newline": _v3({"snapshot_b64": Marshalls.raw_to_base64(good_bytes) + "\n"}),
		"base64 wrong length": _v3({"snapshot_b64": Marshalls.raw_to_base64(good_bytes) + "A"}),
		"base64 non-canonical": _v3({"snapshot_b64": "QUJ="}),
		"base64 not a string": _v3({"snapshot_b64": [1, 2]}),
		"oversized payload": oversized,
		"version 4": _v3({"version": 4}),
		"version 2 with v3 shape": _v3({"version": 2}),
		"version string": _v3({"version": "3"}),
		"version fraction": _v3({"version": 3.5}),
		"other format": _v3({"format": "other"}),
		"timestamp string": _v3({"saved_at_unix": "soon"}),
		"timestamp fraction": _v3({"saved_at_unix": 1.5}),
		"timestamp too big": _v3({"saved_at_unix": 1e300}),
		"extra key": _v3({"extra": 1}),
		"missing timestamp": _v3({}, ["saved_at_unix"]),
		"missing version": _v3({}, ["version"]),
		"missing format": _v3({}, ["format"]),
		"top-level array": JSON.stringify([1, 2]).to_utf8_buffer(),
	}
	assert_true(oversized.size() > AutoSaveImpl.MAX_PAYLOAD_BYTES)
	AutoSaveImpl.parse_envelope(_v3())  # warm up lazily created helpers before counting objects
	var probes_before := ObjectProbe.created
	var objects_before := Performance.get_monitor(Performance.OBJECT_COUNT)
	for name: String in payloads:
		assert_true(AutoSaveImpl.parse_envelope(payloads[name]).is_empty(), "rejected: %s" % name)
	assert_eq(Performance.get_monitor(Performance.OBJECT_COUNT), objects_before, "no object left by decoding")
	for name: String in payloads:
		fake.store[SLOT] = payloads[name]
		Core.state.set_value(COUNT, 0)
		assert_eq(auto_save.restore(), OK)
		assert_eq(Core.state.get_value(COUNT), 5, "local wins over %s" % name)
		assert_false(Core.state.has_value(&"x/evil"))
	assert_eq(ObjectProbe.created, probes_before, "no probe object created from cloud data")
	probe = null


static func _contains(bytes: PackedByteArray, text: String) -> bool:
	var needle := text.to_utf8_buffer()
	for i in bytes.size() - needle.size() + 1:
		if bytes.slice(i, i + needle.size()) == needle:
			return true
	return false


func test_restore_cloud_snapshot_rejected_by_core_keeps_local() -> void:
	_start()
	var local_ts := _local_save_of_five()
	# Well-formed envelope, but Core.state.restore() rejects a non-string key and leaves the state unchanged.
	var bad_snap := {"phase": &"boot", "paused": false, "values": {1: 2, COUNT: 9}}
	fake.store[SLOT] = AutoSaveImpl.make_envelope(bad_snap, local_ts + 100)
	assert_false(AutoSaveImpl.parse_envelope(fake.store[SLOT]).is_empty(), "envelope itself is valid")
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 5, "local state loaded")
	assert_eq(AutoSaveImpl.read_local_saved_at(SLOT), local_ts, "sidecar unchanged")
	remove_child(auto_save)  # stop the policy so the checks below do not autosave
	Core.state.set_value(COUNT, 0)
	assert_eq(Core.saves.load_game(SLOT), OK)
	assert_eq(Core.state.get_value(COUNT), 5, "local slot still holds the local save")
	add_child(auto_save)


func test_restore_cloud_snapshot_rejected_by_core_without_local() -> void:
	_start()
	fake.store[SLOT] = AutoSaveImpl.make_envelope({"phase": &"boot", "paused": false, "values": {1: 2}}, 1000)
	assert_eq(auto_save.restore(), ERR_FILE_NOT_FOUND)
	assert_false(Core.saves.has_save(SLOT), "nothing written")
	assert_eq(AutoSaveImpl.read_local_saved_at(SLOT), -1, "no sidecar")


func test_restore_corrupt_cloud_without_local_is_fresh_game() -> void:
	_start()
	fake.store[SLOT] = PackedByteArray([1, 2, 3])
	assert_eq(auto_save.restore(), ERR_FILE_NOT_FOUND)


func test_restore_ignores_cloud_when_unavailable() -> void:
	_start()
	var local_ts := _local_save_of_five()
	_cloud_with_count(9, local_ts + 100)
	fake.available = false
	assert_eq(auto_save.restore(), OK)
	assert_eq(Core.state.get_value(COUNT), 5)


# --- sidecar location (T026) ----------------------------------------------------------------------------

func test_sidecar_lives_under_core_user_data_dir() -> void:
	assert_eq(CoreAPI.user_data_dir(), "user://automation/", "runner is a test run")
	assert_eq(AutoSaveImpl.meta_path(), CoreAPI.user_data_dir() + "cloud_save/meta.cfg")
	_start()
	_bump()
	assert_eq(events.size(), 1)
	assert_true(FileAccess.file_exists("user://automation/cloud_save/meta.cfg"), "sidecar written in test dir")
	assert_ne(AutoSaveImpl.read_local_saved_at(SLOT), -1, "timestamp readable from the test sidecar")
	assert_eq(_listing(PLAYER_META_DIR), _player_dir_before, "player sidecar dir untouched by a save")


## Declared last so it runs after every other test in this file.
func test_player_sidecar_dir_unchanged_by_whole_file() -> void:
	assert_eq(_listing(PLAYER_META_DIR), _player_dir_before, "user://cloud_save/ listing + mtimes unchanged")
