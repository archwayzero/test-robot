extends TestCase

const STATE_IMPL := "res://modules/core/internal/game_state_impl.gd"
const SAVE_IMPL := "res://modules/core/internal/save_service_impl.gd"
const TEST_DIR := "user://core_test_saves"
const CORE_SLOT := 9901  # used once against the real Core.saves (user://saves), cleaned up

var fake: CoreAPI
var saves: SaveService
var saved: Array = []
var loaded: Array = []


func before_each() -> void:
	_wipe(TEST_DIR)
	# An isolated CoreAPI (not in the tree, so its installer never runs): signals and state stay local.
	fake = CoreAPI.new()
	fake.state = load(STATE_IMPL).new(fake)
	saves = load(SAVE_IMPL).new(fake, TEST_DIR)
	saved = []
	loaded = []
	fake.save_finished.connect(func(slot, err): saved.append([slot, err]))
	fake.load_finished.connect(func(slot, err): loaded.append([slot, err]))


func after_each() -> void:
	saves = null
	fake.free()
	_wipe(TEST_DIR)


func after_all() -> void:
	core().saves.delete_save(CORE_SLOT)


func _fill() -> void:
	fake.state.set_phase(&"playing")
	fake.state.set_value(&"player/position", Vector3(1.25, 0, -3))
	fake.state.set_value(&"exploration/visited", "AAEC")
	fake.state.set_value(&"exploration/count", 3)


func _path(slot: int) -> String:
	return TEST_DIR.path_join("slot_%d.save" % slot)


func _write(slot: int, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(TEST_DIR)
	var f := FileAccess.open(_path(slot), FileAccess.WRITE)
	f.store_string(text)
	f.close()


func _wipe(dir: String) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for f in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir.path_join(f))
	DirAccess.remove_absolute(dir)


func test_round_trip() -> void:
	_fill()
	var snap := fake.state.snapshot()
	assert_false(saves.has_save(1))
	assert_eq(saves.save_game(1), OK)
	assert_true(saves.has_save(1))
	assert_eq(saved, [[1, OK]])
	fake.state.restore({"phase": &"boot", "paused": true, "values": {&"player/yaw": 1.0}})
	assert_eq(saves.load_game(1), OK)
	assert_eq(loaded, [[1, OK]])
	assert_eq(fake.state.snapshot(), snap)


func test_load_emits_state_signals() -> void:
	_fill()
	saves.save_game(2)
	fake.state.set_value(&"exploration/count", 4)
	var changes := []
	fake.state_value_changed.connect(func(k, v): changes.append([k, v]))
	saves.load_game(2)
	assert_eq(changes, [[&"exploration/count", 3]])


func test_file_is_self_describing() -> void:
	_fill()
	var before := Time.get_unix_time_from_system()
	saves.save_game(3)
	var data: Variant = str_to_var(FileAccess.get_file_as_string(_path(3)))
	assert_eq(typeof(data), TYPE_DICTIONARY)
	assert_eq(data.header.format, "core_save")
	assert_eq(data.header.version, 1)
	assert_between(data.header.saved_at_unix, before - 1.0, Time.get_unix_time_from_system() + 1.0, "UTC unix time")
	assert_eq(data.state, fake.state.snapshot())


func test_missing_file() -> void:
	_fill()
	var snap := fake.state.snapshot()
	assert_eq(saves.load_game(4), ERR_FILE_NOT_FOUND)
	assert_eq(loaded, [[4, ERR_FILE_NOT_FOUND]])
	assert_eq(fake.state.snapshot(), snap, "state unchanged")


func test_corrupt_files() -> void:
	_fill()
	var snap := fake.state.snapshot()
	var bad := [
		"",
		"this is not a save {{{",
		var_to_str([1, 2, 3]),
		var_to_str({"state": snap}),
		var_to_str({"header": {"format": "core_save", "version": 99, "saved_at_unix": 1.0}, "state": snap}),
		var_to_str({"header": {"format": "other", "version": 1, "saved_at_unix": 1.0}, "state": snap}),
		var_to_str({"header": {"format": "core_save", "version": 1, "saved_at_unix": 1.0}, "state": {"phase": 1}}),
	]
	for i in bad.size():
		_write(5, bad[i])
		assert_eq(saves.load_game(5), ERR_FILE_CORRUPT, "case %d" % i)
		assert_eq(fake.state.snapshot(), snap, "state unchanged, case %d" % i)
	assert_eq(loaded.size(), bad.size())
	assert_eq(loaded[0], [5, ERR_FILE_CORRUPT])


func test_truncated_file() -> void:
	_fill()
	saves.save_game(6)
	var text := FileAccess.get_file_as_string(_path(6))
	_write(6, text.substr(0, text.length() / 2))
	fake.state.set_value(&"exploration/count", 10)
	var snap := fake.state.snapshot()
	assert_eq(saves.load_game(6), ERR_FILE_CORRUPT)
	assert_eq(fake.state.snapshot(), snap)


func test_atomic_write_leaves_no_temp_file() -> void:
	_fill()
	# A stale temp file from an interrupted earlier save must not survive or be mistaken for the save.
	_write(7, "garbage")
	DirAccess.rename_absolute(_path(7), _path(7) + ".tmp")
	assert_eq(saves.save_game(7), OK)
	fake.state.set_value(&"exploration/count", 5)
	assert_eq(saves.save_game(7), OK, "overwrite")
	assert_false(FileAccess.file_exists(_path(7) + ".tmp"), "no temp file left")
	assert_eq(Array(DirAccess.get_files_at(TEST_DIR)), ["slot_7.save"])
	fake.state.set_value(&"exploration/count", 6)
	saves.load_game(7)
	assert_eq(fake.state.get_value(&"exploration/count"), 5, "latest save wins")


func test_delete_and_invalid_slots() -> void:
	saves.save_game(8)
	assert_eq(saves.delete_save(8), OK)
	assert_false(saves.has_save(8))
	assert_eq(saves.delete_save(8), ERR_FILE_NOT_FOUND)
	assert_eq(saves.save_game(-1), ERR_INVALID_PARAMETER)
	assert_eq(saves.load_game(-1), ERR_INVALID_PARAMETER)
	assert_false(saves.has_save(-1))
	assert_eq(saved.back(), [-1, ERR_INVALID_PARAMETER])
	assert_eq(loaded.back(), [-1, ERR_INVALID_PARAMETER])


func test_core_saves_uses_user_saves_dir() -> void:
	var got := []
	var cb := func(slot, err): got.append([slot, err])
	core().save_finished.connect(cb)
	assert_eq(core().saves.save_game(CORE_SLOT), OK)
	core().save_finished.disconnect(cb)
	assert_eq(got, [[CORE_SLOT, OK]])
	assert_true(FileAccess.file_exists("user://saves/slot_%d.save" % CORE_SLOT))
	assert_eq(core().saves.delete_save(CORE_SLOT), OK)
	assert_false(FileAccess.file_exists("user://saves/slot_%d.save" % CORE_SLOT))
