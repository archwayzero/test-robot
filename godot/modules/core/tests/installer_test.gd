extends TestCase

const INSTALLER := "res://modules/core/internal/core_installer.gd"


func test_core_autoload_is_wired() -> void:
	var c := core()
	assert_not_null(c.state, "Core.state")
	assert_true(c.state is GameState, "Core.state is a GameState")
	assert_not_null(c.saves, "Core.saves")
	assert_true(c.saves is SaveService, "Core.saves is a SaveService")
	assert_true(CoreAPI.is_test_run(), "runner is a test run")
	assert_not_null(c.automation, "Core.automation in a test run")
	assert_true(c.automation is Automation, "Core.automation is an Automation")
	assert_eq(c.saves.slot_path(0), "user://automation/saves/slot_0.save", "test run saves under user://automation/")


func test_installer_uses_user_data_dir_for_saves() -> void:
	var fresh := CoreAPI.new()
	load(INSTALLER).install(fresh)
	assert_eq(fresh.saves.slot_path(3), CoreAPI.user_data_dir() + "saves/slot_3.save")
	fresh.free()


func test_install_on_fresh_core() -> void:
	var fresh := CoreAPI.new()
	load(INSTALLER).install(fresh)
	assert_true(fresh.state is GameState)
	assert_true(fresh.saves is SaveService)
	assert_true(fresh.automation is Automation, "test run -> automation set")
	assert_eq(fresh.state.get_phase(), GameState.PHASE_BOOT)
	assert_false(fresh.state.is_paused())
	# Services talk to the core they were given, not to the autoload.
	var got := []
	fresh.phase_changed.connect(func(a, b): got.append([a, b]))
	fresh.state.set_phase(&"menu")
	assert_eq(got, [[&"boot", &"menu"]])
	assert_eq(core().state.get_phase(), GameState.PHASE_BOOT, "autoload state untouched")
	fresh.free()


func test_no_automation_outside_test_runs() -> void:
	# Same installer, test-run decision forced to false (in-process; tests never start other processes).
	var fresh := CoreAPI.new()
	load(INSTALLER).install_with(fresh, false)
	assert_true(fresh.state is GameState)
	assert_true(fresh.saves is SaveService)
	assert_null(fresh.automation, "not a test run -> automation stays null")
	fresh.free()


func test_automation_never_preloaded() -> void:
	# Release exports exclude internal/automation/*, so no core script may preload it (load by path only).
	var files: PackedStringArray = []
	_collect_gd("res://modules/core/public", files)
	_collect_gd("res://modules/core/internal", files)
	assert_true(files.size() >= 4, "found core scripts: %s" % files)
	var re := RegEx.create_from_string("preload\\s*\\([^)]*automation/")
	for f in files:
		var text := FileAccess.get_file_as_string(f)
		assert_null(re.search(text), "%s preloads the automation implementation" % f)


func _collect_gd(dir: String, out: PackedStringArray) -> void:
	for f in DirAccess.get_files_at(dir):
		if f.ends_with(".gd"):
			out.append(dir.path_join(f))
	for d in DirAccess.get_directories_at(dir):
		_collect_gd(dir.path_join(d), out)
