## Headless test runner. Owner: orchestrator. Usage (from the repo root):
##   python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd \
##       -- --automation [--filter <text>] [--dir <res://dir>]
##       [--report <path.md>]
## Discovers `*_test.gd` under res://modules/*/tests/ and res://tests/ (recursively), or only under --dir.
## --filter keeps files whose res:// path contains <text> (e.g. a module name). Exit code: 0 all passed,
## 1 failures, 2 nothing found or bad arguments. Prints one line per test and a summary.
extends SceneTree

var _passed := 0
var _failed := 0
var _lines: PackedStringArray = []
var _catcher := ScriptErrorCatcher.new()


## Records runtime SCRIPT errors (e.g. "Invalid call", null access). A script error aborts the running function
## without failing an assert, so without this a crashed test would be reported as PASS. Errors from push_error()
## (type ERROR) are not counted: tests use them on purpose to check that bad input is rejected.
class ScriptErrorCatcher extends Logger:
	var _mutex := Mutex.new()
	var _errors: PackedStringArray = []

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
		if error_type != ERROR_TYPE_SCRIPT:
			return
		_mutex.lock()
		_errors.append("script error: %s %s (%s:%d in %s)" % [code, rationale, file, line, function])
		_mutex.unlock()

	func _log_message(_message: String, _error: bool) -> void:
		pass

	func take() -> PackedStringArray:
		_mutex.lock()
		var e := _errors
		_errors = []
		_mutex.unlock()
		return e


func _initialize() -> void:
	OS.add_logger(_catcher)
	_run.call_deferred()


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if not CoreAPI.is_test_run():
		printerr("test_runner: start with `-- --automation` in a debug build")
		quit(2)
		return
	var filter := _arg(args, "--filter")
	var dir := _arg(args, "--dir")
	var report := _arg(args, "--report")
	var files: PackedStringArray = []
	if dir != "":
		_collect(dir, files)
	else:
		for m in DirAccess.get_directories_at("res://modules"):
			_collect("res://modules/%s/tests" % m, files)
		_collect("res://tests", files)
	if filter != "":
		files = PackedStringArray(Array(files).filter(func(f): return filter in f))
	files.sort()
	if files.is_empty():
		printerr("test_runner: no *_test.gd files found (filter=%s dir=%s)" % [filter, dir])
		quit(2)
		return
	for f in files:
		await _run_file(f)
	var summary := "%d passed, %d failed, %d files" % [_passed, _failed, files.size()]
	print(("PASSED: " if _failed == 0 else "FAILED: ") + summary)
	if report != "":
		_write_report(report, summary)
	quit(0 if _failed == 0 else 1)


func _run_file(path: String) -> void:
	var script := load(path) as GDScript
	if script == null or not script.can_instantiate():
		_record(path, "<load>", ["script failed to load or parse"])
		return
	var instance: Object = script.new()
	if not (instance is TestCase):
		_record(path, "<load>", ["does not extend TestCase (or TestCase failed to compile)"])
		if instance is Node:
			instance.free()
		return
	var test := instance as TestCase
	root.add_child(test)
	var names: PackedStringArray = []
	for m in script.get_script_method_list():
		if m.name.begins_with("test_") and not (m.name in names):
			names.append(m.name)
	if names.is_empty():
		_record(path, "<discover>", ["no test_* methods"])
	_catcher.take()
	if test.has_method("before_all"):
		await _call_with_timeout(test, "before_all")
	var setup_errors := _catcher.take()
	if not setup_errors.is_empty():
		_record(path, "<before_all>", setup_errors)
	for n in names:
		if test.has_method("before_each"):
			await _call_with_timeout(test, "before_each")
		var timed_out := not await _call_with_timeout(test, n)
		if test.has_method("after_each"):
			await _call_with_timeout(test, "after_each")
		var failures := test._take_failures()
		failures.append_array(_catcher.take())
		if timed_out:
			failures.append("timed out after %d frames" % test.timeout_frames)
		_record(path, n, failures)
	if test.has_method("after_all"):
		await _call_with_timeout(test, "after_all")
	var teardown_errors := _catcher.take()
	if not teardown_errors.is_empty():
		_record(path, "<after_all>", teardown_errors)
	test.queue_free()
	await process_frame


## Calls `method` (possibly a coroutine); returns false if it did not finish within the test's frame budget.
func _call_with_timeout(test: TestCase, method: String) -> bool:
	var state := {"done": false}
	var runner := func() -> void:
		await test.call(method)
		state.done = true
	runner.call()
	var frames := 0
	while not state.done and frames < test.timeout_frames:
		await process_frame
		frames += 1
	return state.done


func _record(path: String, test_name: String, failures: PackedStringArray) -> void:
	var id := "%s::%s" % [path, test_name]
	if failures.is_empty():
		_passed += 1
		_lines.append("PASS " + id)
		print("PASS ", id)
	else:
		_failed += 1
		_lines.append("FAIL %s\n    %s" % [id, "\n    ".join(failures)])
		print("FAIL ", id)
		for f in failures:
			print("    ", f)


func _collect(dir: String, out: PackedStringArray) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for f in DirAccess.get_files_at(dir):
		if f.ends_with("_test.gd"):
			out.append(dir.path_join(f))
	for d in DirAccess.get_directories_at(dir):
		_collect(dir.path_join(d), out)


func _arg(args: PackedStringArray, name: String) -> String:
	var i := args.find(name)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else ""


func _write_report(path: String, summary: String) -> void:
	var fa := FileAccess.open(path, FileAccess.WRITE)
	if fa == null:
		printerr("test_runner: cannot write report ", path)
		return
	fa.store_string("# Test run\n\n%s\n\n```\n%s\n```\n" % [summary, "\n".join(_lines)])
