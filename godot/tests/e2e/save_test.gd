## M4 save end-to-end tests: TEST_PLAN.md E11 autosave_throttle, E12 save_restore, E13 cloud_unavailable. Owner: qa.
##
## The game boots with the platform backend (LocalOnly in the sandbox). E11/E13 give the running AutoSave an
## in-memory fake backend through the public API: AutoSave.setup(CloudSaveFactory.make_fake_backend(available)).
## Saves go to user://automation/ in test runs (CoreAPI.user_data_dir()).
extends "res://tests/e2e/e2e_base.gd"


func _init() -> void:
	timeout_frames = 3000


## Shortest FULL-clearance route of `n` new cells from the start cell (start included).
func _route(n: int) -> Array[Vector2i]:
	var start := layout().start_cell()
	var tree := bfs(start, true)
	for c: Vector2i in tree:
		if int(tree[c][0]) == n:
			return path_to(tree, c)
	return [start]


## Decodes cloud_save's envelope (format documented in godot/modules/cloud_save/CLAUDE.md:
## JSON.stringify(JSON.from_native({format, version, saved_at_unix, snapshot}, false))). {} if not decodable.
static func _decode_envelope(data: PackedByteArray) -> Dictionary:
	if data.is_empty():
		return {}
	var raw: Variant = JSON.parse_string(data.get_string_from_utf8())
	if raw == null:
		return {}
	var env: Variant = JSON.to_native(raw, false)
	return env if env is Dictionary else {}


func test_e11_autosave_throttle() -> void:
	assert_true(await start_game())
	var backend := CloudSaveFactory.create().make_fake_backend(true)
	var auto_save := main.get_auto_save()
	auto_save.setup(backend)
	var saves: Array = []  # [frame, error, cloud_error, state snapshot at save time, envelope]
	auto_save.autosaved.connect(func(error: Error, cloud_error: Error) -> void:
		saves.append([automation().get_frame(), error, cloud_error, Core.state.snapshot(),
				_decode_envelope(backend.pull(AutoSave.SAVE_SLOT))]))
	var explored_frames: Array = []
	main.get_exploration().cell_explored.connect(func(_c: Vector2i) -> void:
		explored_frames.append(automation().get_frame()))
	var route := _route(2)
	assert_eq(route.size(), 3, "2-cell route %s" % [route])
	var t0 := automation().get_frame()
	assert_true(await walk_path(route.slice(1)), "walked %s" % [route])
	assert_eq(explored_frames.size(), 2, "2 new cells explored")
	if explored_frames.size() < 2 or saves.is_empty():
		fail("no autosave after exploring (saves %s)" % [saves.size()])
		return
	assert_true(int(explored_frames[1]) - t0 < 10 * FPS, "both cells within 10 s (%d frames)" % (int(explored_frames[1]) - t0))
	var first_save: int = saves[0][0]
	assert_eq(first_save, int(explored_frames[0]), "first save immediately when the first new cell is explored")
	assert_eq(saves.size(), 1, "second cell inside the interval: no immediate save")
	# Wait until 12 s of game time after the first save.
	await automation().wait_until(func() -> bool: return automation().get_frame() >= first_save + 12 * FPS, 13 * FPS)
	assert_eq(saves.size(), 2, "exactly 2 saves: immediately + 1 after the interval")
	if saves.size() >= 2:
		var gap := int(saves[1][0]) - first_save
		assert_between(gap, 10 * FPS - 1, 10 * FPS + 2, "second save when the 10 s interval ends (gap %d frames)" % gap)
	for s: Array in saves:
		assert_eq(s[1], OK, "local save OK")
		assert_eq(s[2], OK, "cloud push OK")
		var env: Dictionary = s[4]
		assert_eq(env.get("format"), "cloud_save", "envelope format")
		assert_eq(env.get("version"), 2, "envelope version")
		assert_true(env.get("saved_at_unix") is int, "envelope timestamp")
		var snap: Variant = env.get("snapshot")
		var state: Dictionary = s[3]
		assert_true(snap is Dictionary, "envelope has a snapshot")
		if snap is Dictionary:
			assert_eq(StringName(snap.get("phase", "")), StringName(state.phase), "snapshot phase")
			assert_eq(snap.get("paused"), state.paused, "snapshot paused")
			assert_eq(snap.get("values"), state.values, "snapshot values equal Core.state at save time")
			_report_value_diffs(snap.get("values", {}), state.values)
	if saves.size() >= 2:
		var values: Dictionary = (saves[1][4] as Dictionary).get("snapshot", {}).get("values", {})
		assert_eq(values.get(StateKeys.EXPLORATION_COUNT), 3, "latest envelope has 3 explored cells")
	assert_true(Core.saves.has_save(AutoSave.SAVE_SLOT), "local save exists")
	print("E11 measured: explored at %s, saves at %s" % [explored_frames, saves.map(func(s: Array) -> int: return s[0])])


func test_e12_save_restore() -> void:
	assert_true(await start_game())
	var route := _route(2)
	assert_true(await walk_path(route.slice(1)), "walked %s" % [route])
	# Off-centre, crouched: a non-trivial position and stance.
	assert_true(await walk_to(layout().cell_to_world(route[2]) + Vector3(0.6, 0, 0.4), 0.5, 120, 0.05))
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CROUCH)
	await automation().advance_frames(30)  # let the throttled position write land (<= 0.5 s)
	var explored := _plain_sorted(main.get_exploration().get_explored_cells())
	var pos := player().global_position
	var stance := player().get_stance()
	assert_eq(main.get_auto_save().save_now(), OK, "save_now OK")
	# Reload: unload, wipe the in-memory keys (so only the save on disk can bring them back), load the main scene.
	await _unload()
	clear_saved_keys()
	assert_true(await start_game())
	await automation().advance_frames(5)
	assert_eq(_plain_sorted(main.get_exploration().get_explored_cells()), explored, "same explored set")
	var d := player().global_position.distance_to(pos)
	assert_true(d <= 0.1, "position within 0.1 m (%.3f m; saved %s, now %s)" % [d, pos, player().global_position])
	assert_eq(player().get_stance(), stance, "same stance")
	print("E12 measured: explored %s, position error %.4f m, stance %d" % [explored, d, player().get_stance()])


## Prints which keys differ between the envelope and the state, and by how much (diagnostic for the report).
func _report_value_diffs(got: Dictionary, expected: Dictionary) -> void:
	for k: Variant in expected:
		var a: Variant = got.get(k)
		var b: Variant = expected[k]
		if typeof(a) != typeof(b) or a != b:
			var delta := ""
			if a is float and b is float:
				delta = " (|diff| %s)" % String.num_scientific(absf(a - b))
			print("E11 envelope differs at %s: envelope %s vs state %s%s" % [k, var_to_str(a), var_to_str(b), delta])


static func _plain_sorted(cells: Variant) -> Array:
	var out: Array = []
	for c: Variant in cells:
		out.append(c)
	out.sort()
	return out


## Visible CanvasItems (HUD and popups) under `node`, as paths.
static func _visible_canvas_items(node: Node, out: PackedStringArray) -> PackedStringArray:
	for child in node.get_children():
		if child is CanvasItem and (child as CanvasItem).is_visible_in_tree():
			out.append(str(child.get_path()))
		elif child is Window and (child as Window).visible:
			out.append(str(child.get_path()))
		_visible_canvas_items(child, out)
	return out


func test_e13_cloud_unavailable() -> void:
	assert_true(await start_game())
	main.get_auto_save().setup(CloudSaveFactory.create().make_fake_backend(false))
	var results: Array = []
	main.get_auto_save().autosaved.connect(func(error: Error, cloud_error: Error) -> void:
		results.append([error, cloud_error]))
	var before := _visible_canvas_items(get_tree().root, PackedStringArray())
	var route := _route(1)
	assert_true(await walk_path(route.slice(1)), "walked %s" % [route])
	await automation().advance_frames(10)
	assert_eq(results.size(), 1, "one autosave")
	if results.size() >= 1:
		assert_eq(results[0][0], OK, "local save OK")
		assert_eq(results[0][1], ERR_UNAVAILABLE, "cloud_error == ERR_UNAVAILABLE")
	assert_true(Core.saves.has_save(AutoSave.SAVE_SLOT), "local save on disk")
	var after := _visible_canvas_items(get_tree().root, PackedStringArray())
	var added := []
	for p in after:
		if not (p in before):
			added.append(p)
	assert_eq(added, [], "no new visible UI (no error shown)")
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_PLAYING, "still playing")
	assert_false(get_tree().paused, "not paused")
