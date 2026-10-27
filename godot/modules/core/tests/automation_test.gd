extends TestCase

const ACTION_PROBE := "res://modules/core/tests/support/action_probe.gd"
const INPUT_PROBE := "res://modules/core/tests/support/input_probe.gd"
const PROBE_SCENE := "res://modules/core/tests/support/probe_scene.tscn"

var auto: Automation


func before_each() -> void:
	auto = automation()


func after_each() -> void:
	for a in GameActions.ALL:
		Input.action_release(a)


func test_seed_reproducibility() -> void:
	auto.set_seed(42)
	var a := [core().rng.randi(), core().rng.randi(), core().rng.randf(), randi()]
	auto.set_seed(42)
	var b := [core().rng.randi(), core().rng.randi(), core().rng.randf(), randi()]
	assert_eq(a, b, "same seed, same sequence (Core.rng and global)")
	auto.set_seed(43)
	var c := [core().rng.randi(), core().rng.randi(), core().rng.randf(), randi()]
	assert_ne(a, c, "different seed, different sequence")
	assert_eq(auto.snapshot().seed, 43)


func test_advance_frames_counts_process_frames() -> void:
	var f0 := auto.get_frame()
	var e0 := Engine.get_process_frames()
	await auto.advance_frames(5)
	assert_eq(auto.get_frame() - f0, 5)
	assert_eq(Engine.get_process_frames() - e0, 5)
	await auto.advance_frames(1)
	await auto.advance_frames(1)
	assert_eq(Engine.get_process_frames() - e0, 7, "consecutive awaits are distinct frames")
	await auto.advance_frames(0)
	assert_eq(Engine.get_process_frames() - e0, 7, "0 frames returns at once")


func test_wait_until_true() -> void:
	var target := Engine.get_process_frames() + 3
	var ok: bool = await auto.wait_until(func(): return Engine.get_process_frames() >= target, 30)
	assert_true(ok)
	assert_eq(Engine.get_process_frames(), target, "returns as soon as it holds")
	var e0 := Engine.get_process_frames()
	assert_true(await auto.wait_until(func(): return true, 10))
	assert_eq(Engine.get_process_frames(), e0, "already true -> no frame passes")


func test_wait_until_timeout() -> void:
	var e0 := Engine.get_process_frames()
	var ok: bool = await auto.wait_until(func(): return false, 10)
	assert_false(ok)
	assert_eq(Engine.get_process_frames() - e0, 10)


func test_press_release_action_visible_to_input() -> void:
	auto.press_action(GameActions.MOVE_FORWARD, 0.8)
	assert_true(Input.is_action_pressed(GameActions.MOVE_FORWARD), "same frame")
	assert_almost_eq(Input.get_action_strength(GameActions.MOVE_FORWARD), 0.8, 1e-6)
	var v := Input.get_vector(GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
			GameActions.MOVE_BACK)
	assert_true(v.y < -0.5 and is_zero_approx(v.x), "get_vector sees it: %s" % v)
	await auto.advance_frames(2)
	assert_true(Input.is_action_pressed(GameActions.MOVE_FORWARD), "held across frames")
	auto.release_action(GameActions.MOVE_FORWARD)
	assert_false(Input.is_action_pressed(GameActions.MOVE_FORWARD))
	assert_eq(Input.get_action_strength(GameActions.MOVE_FORWARD), 0.0)


func test_tap_action() -> void:
	var probe = load(ACTION_PROBE).new()
	probe.action = GameActions.JUMP
	add_child(probe)
	# Start from a known point: resumed at the start of a process frame, before nodes' _process.
	await auto.advance_frames(1)
	await auto.tap_action(GameActions.JUMP, 3)
	assert_false(Input.is_action_pressed(GameActions.JUMP), "released after tap")
	await auto.advance_frames(2)
	probe.queue_free()
	assert_eq(probe.pressed_frames, 3, "held for 3 frames")
	assert_eq(probe.just_pressed, 1, "one press")


func test_inject_key_event_maps_to_action() -> void:
	var key := InputEventKey.new()
	key.physical_keycode = KEY_SPACE
	key.pressed = true
	auto.inject_event(key)
	assert_true(Input.is_action_pressed(GameActions.JUMP))
	var up := InputEventKey.new()
	up.physical_keycode = KEY_SPACE
	up.pressed = false
	auto.inject_event(up)
	assert_false(Input.is_action_pressed(GameActions.JUMP))


func test_touch_and_drag_reach_control() -> void:
	assert_eq(get_tree().root.size, Vector2i(1280, 590), "headless root sized like the project viewport")
	var probe = load(INPUT_PROBE).new()
	probe.position = Vector2(900, 300)
	probe.size = Vector2(200, 200)
	add_child(probe)
	await auto.advance_frames(1)
	auto.touch(Vector2(950, 350), true, 0)
	assert_eq(probe.count("InputEventScreenTouch"), 1, "touch down reaches _gui_input")
	var down: InputEventScreenTouch = probe.events.filter(func(e): return e is InputEventScreenTouch)[0]
	assert_true(down.pressed)
	assert_eq(down.position, Vector2(50, 50), "local position")
	auto.touch(Vector2(950, 350), false, 0)
	assert_eq(probe.count("InputEventScreenTouch"), 2, "touch up reaches _gui_input")
	auto.touch(Vector2(10, 10), true, 1)
	auto.touch(Vector2(10, 10), false, 1)
	assert_eq(probe.count("InputEventScreenTouch"), 2, "touch outside the control does not reach it")
	probe.events.clear()
	await auto.drag(Vector2(950, 350), Vector2(1050, 350), 4, 0)
	assert_eq(probe.count("InputEventScreenTouch"), 2, "drag: down + up")
	assert_eq(probe.count("InputEventScreenDrag"), 4, "one drag event per frame")
	var drags: Array = probe.events.filter(func(e): return e is InputEventScreenDrag)
	assert_eq(drags.back().position, Vector2(150, 50), "drag ends at `to`")
	assert_eq(drags[0].relative, Vector2(25, 0))
	probe.queue_free()


func test_snapshot() -> void:
	auto.set_seed(7)
	var snap := auto.snapshot()
	for k in ["phase", "paused", "values", "frame", "seed", "scene"]:
		assert_has(snap, k)
	assert_eq(snap.seed, 7)
	assert_eq(snap.frame, auto.get_frame())
	assert_eq(snap.phase, core().state.get_phase())
	assert_eq(typeof(snap.scene), TYPE_STRING)
	assert_eq(str_to_var(var_to_str(snap)), snap, "plain data")


func test_load_scene_waits_for_ready() -> void:
	await auto.load_scene(PROBE_SCENE)
	var scene := get_tree().current_scene
	assert_not_null(scene)
	if scene != null:
		assert_eq(scene.scene_file_path, PROBE_SCENE)
		assert_true(scene.is_node_ready())
		assert_true(scene.ready_ran, "_ready ran before load_scene returned")
	assert_eq(auto.snapshot().scene, PROBE_SCENE)
	var first := scene
	await auto.load_scene(PROBE_SCENE)
	assert_ne(get_tree().current_scene, first, "reloading gives a fresh instance")
	assert_true(get_tree().current_scene.ready_ran)
	get_tree().unload_current_scene()
	await auto.advance_frames(1)
	assert_eq(auto.snapshot().scene, "")
