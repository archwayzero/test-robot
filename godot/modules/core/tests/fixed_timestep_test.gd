## Fixed timestep. An exact, wall-clock independent process delta needs the engine argument `--fixed-fps <fps>`
## (no script API can set it), so the official test command starts Godot with it:
##   godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation [--filter core]
## Exact mode is detected from the engine arguments (OS.get_cmdline_args()), never from a measured delta, and this
## file never starts another process.
extends TestCase

const DELTA_PROBE := "res://modules/core/tests/support/delta_probe.gd"
const AUTOMATION_IMPL := "res://modules/core/internal/automation/automation_impl.gd"
const FPS := 30
const TPS := 60
const SETTLE_FRAMES := 5
const MEASURE_FRAMES := 90
const OFFICIAL_COMMAND := ("godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd "
		+ "-- --automation --filter core")

var _saved := {}


func before_each() -> void:
	_saved = {"tps": Engine.physics_ticks_per_second, "max_fps": Engine.max_fps,
			"steps": Engine.max_physics_steps_per_frame}


func after_each() -> void:
	Engine.physics_ticks_per_second = _saved.tps
	Engine.max_fps = _saved.max_fps
	Engine.max_physics_steps_per_frame = _saved.steps


func _engine_exact() -> bool:
	return load(AUTOMATION_IMPL).is_engine_step_exact(FPS)


func test_fixed_timestep_delta() -> void:
	if not _engine_exact():
		fail(("exact fixed timestep needs the engine started with `--fixed-fps %d` (got --fixed-fps=%d). Run: %s")
				% [FPS, load(AUTOMATION_IMPL).engine_fixed_fps(), OFFICIAL_COMMAND])
		return
	var auto := automation()
	auto.set_fixed_timestep(TPS, FPS)
	assert_true(auto.is_fixed_timestep_exact())
	assert_eq(Engine.physics_ticks_per_second, TPS)
	assert_eq(Engine.time_scale, 1.0)
	# Let the new physics rate and the first frames settle before recording.
	await auto.advance_frames(SETTLE_FRAMES)
	var probe: Node = load(DELTA_PROBE).new()
	add_child(probe)
	var p0 := Engine.get_physics_frames()
	await auto.advance_frames(MEASURE_FRAMES)
	var p1 := Engine.get_physics_frames()
	probe.queue_free()
	assert_eq(probe.deltas.size(), MEASURE_FRAMES)
	for d in probe.deltas:
		if d != 1.0 / FPS:
			fail("_process delta %.12f != 1/%d (%s)" % [d, FPS, probe.deltas])
			break
	for n in probe.physics_per_frame:
		if n != TPS / FPS:
			fail("physics steps per frame %d != %d (%s)" % [n, TPS / FPS, probe.physics_per_frame])
			break
	assert_eq(p1 - p0, MEASURE_FRAMES * TPS / FPS, "physics frames")
	assert_eq(get_physics_process_delta_time(), 1.0 / TPS)


func test_fallback_without_fixed_fps() -> void:
	var auto := automation()
	auto.set_fixed_timestep(TPS, FPS)
	assert_eq(Engine.physics_ticks_per_second, TPS)
	assert_true(Engine.max_physics_steps_per_frame >= TPS / FPS)
	if _engine_exact():
		assert_true(auto.is_fixed_timestep_exact(), "exact mode detected")
		assert_eq(Engine.max_fps, 0, "exact mode runs uncapped")
	else:
		assert_false(auto.is_fixed_timestep_exact())
		assert_eq(Engine.max_fps, FPS, "approximate mode paces at fps")
