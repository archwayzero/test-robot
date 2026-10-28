## Wires the core implementation into the Core autoload. Called by CoreAPI._enter_tree(), before any other node's
## _ready(). The automation scripts are loaded by path, and only in test runs (release exports exclude
## res://modules/core/internal/automation/*), so nothing here may preload them.
extends RefCounted

const _GAME_STATE_PATH := "res://modules/core/internal/game_state_impl.gd"
const _SAVE_SERVICE_PATH := "res://modules/core/internal/save_service_impl.gd"
const _AUTOMATION_PATH := "res://modules/core/internal/automation/automation_impl.gd"


static func install(core: CoreAPI) -> void:
	install_with(core, CoreAPI.is_test_run())


## install() with the test-run decision passed in (lets unit tests cover the non-test-run path in-process).
static func install_with(core: CoreAPI, test_run: bool) -> void:
	core.state = load(_GAME_STATE_PATH).new(core)
	core.saves = load(_SAVE_SERVICE_PATH).new(core, CoreAPI.user_data_dir() + "saves")
	core.automation = null
	if test_run:
		var script: Script = load(_AUTOMATION_PATH)
		if script == null:
			push_error("core: test run but automation implementation missing (%s)" % _AUTOMATION_PATH)
			return
		core.automation = script.new(core)
