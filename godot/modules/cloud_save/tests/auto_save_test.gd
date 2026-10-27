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


func before_all() -> void:
	factory = CloudSaveFactory.create()
	_initial_state = Core.state.snapshot()


func after_all() -> void:
	_cleanup_files()
	if DirAccess.dir_exists_absolute(AutoSaveImpl.META_DIR):
		DirAccess.remove_absolute(AutoSaveImpl.META_DIR)
	Core.state.restore(_initial_state)


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
	if FileAccess.file_exists(AutoSaveImpl.META_PATH):
		DirAccess.remove_absolute(AutoSaveImpl.META_PATH)


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
	var text: String = (fake.pushes[0].data as PackedByteArray).get_string_from_utf8()
	var raw: Variant = JSON.to_native(JSON.parse_string(text), false)
	assert_eq(typeof(raw), TYPE_DICTIONARY)
	assert_eq(raw.format, "cloud_save")
	assert_eq(raw.version, 2)
	assert_eq(typeof(raw.saved_at_unix), TYPE_INT)
	assert_almost_eq(raw.saved_at_unix, Time.get_unix_time_from_system(), 5.0)
	assert_eq(raw.snapshot, expected, "snapshot equals Core.state.snapshot() at save time")
	assert_eq(raw.saved_at_unix, AutoSaveImpl.read_local_saved_at(SLOT), "sidecar matches the envelope")
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
