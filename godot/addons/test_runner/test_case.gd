## Base class for all tests (module unit tests and qa end-to-end tests). Owner: orchestrator.
##
## A test file is `*_test.gd` and `extends TestCase`. Every method named `test_*` is a test; it may be a coroutine
## (use `await`). Optional hooks: before_all(), after_all(), before_each(), after_each() (may also await).
## The test node is added to the SceneTree root, so `get_tree()` works. Each test has a frame budget
## (`timeout_frames`, default 1800); a test that does not finish in time fails.
class_name TestCase
extends Node

## Override per file if tests need longer (frames, not seconds; the runner does not use wall-clock time).
var timeout_frames := 1800

var _failures: PackedStringArray = []


## The Core autoload, looked up as a node: TestCase and the runner are compiled (under `-s`) before the autoload's
## global name exists. Test files and game scripts loaded later may use `Core` directly (verified on 4.7.2).
func core() -> CoreAPI:
	return get_tree().root.get_node("Core") as CoreAPI


## Core.automation (non-null once core is implemented, because the runner requires `-- --automation`).
func automation() -> Automation:
	return core().automation


## Lets `n` engine process frames pass (works with or without Core.automation). Counts Engine.get_process_frames()
## rather than signal emissions: awaiting process_frame from code that was itself resumed by process_frame can
## resume in the same frame.
func wait_frames(n: int) -> void:
	var target := Engine.get_process_frames() + n
	while Engine.get_process_frames() < target:
		await get_tree().process_frame


func fail(message: String) -> void:
	_failures.append(message)


func assert_true(value: bool, message := "") -> void:
	if not value:
		fail("expected true. " + message)


func assert_false(value: bool, message := "") -> void:
	if value:
		fail("expected false. " + message)


func assert_eq(actual: Variant, expected: Variant, message := "") -> void:
	if typeof(actual) != typeof(expected) or actual != expected:
		fail("expected %s, got %s. %s" % [var_to_str(expected), var_to_str(actual), message])


func assert_ne(actual: Variant, unexpected: Variant, message := "") -> void:
	if typeof(actual) == typeof(unexpected) and actual == unexpected:
		fail("expected anything but %s. %s" % [var_to_str(unexpected), message])


func assert_almost_eq(actual: float, expected: float, tolerance: float, message := "") -> void:
	if absf(actual - expected) > tolerance:
		fail("expected %s +- %s, got %s. %s" % [expected, tolerance, actual, message])


func assert_between(actual: float, low: float, high: float, message := "") -> void:
	if actual < low or actual > high:
		fail("expected %s in [%s, %s]. %s" % [actual, low, high, message])


func assert_null(value: Variant, message := "") -> void:
	if value != null:
		fail("expected null, got %s. %s" % [value, message])


func assert_not_null(value: Variant, message := "") -> void:
	if value == null:
		fail("expected non-null. " + message)


func assert_has(container: Variant, item: Variant, message := "") -> void:
	if not (item in container):
		fail("expected %s to contain %s. %s" % [container, item, message])


# --- used by the runner ---
func _take_failures() -> PackedStringArray:
	var f := _failures
	_failures = []
	return f
