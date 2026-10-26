## Self-test of the runner. Run: godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation
##   --dir res://addons/test_runner/selftest
## Expected: 4 passed, 2 failed (the two `test_expected_failure_*`), exit code 1.
extends TestCase


func before_all() -> void:
	timeout_frames = 30


func test_sync_asserts() -> void:
	assert_true(true)
	assert_eq(1 + 1, 2)
	assert_almost_eq(0.1 + 0.2, 0.3, 0.0001)
	assert_has([1, 2, 3], 2)


func test_coroutine_waits_frames() -> void:
	var start := Engine.get_process_frames()
	await wait_frames(3)
	var delta := Engine.get_process_frames() - start
	assert_true(delta >= 3, "delta=%d" % delta)


func test_core_autoload_present() -> void:
	assert_not_null(core())
	assert_true(core() is CoreAPI)
	assert_true(CoreAPI.is_test_run())


func test_type_strict_eq() -> void:
	assert_ne(1, 1.0, "int vs float are different types")


func test_expected_failure_assert() -> void:
	assert_eq("a", "b")


func test_expected_failure_timeout() -> void:
	await wait_frames(100)
