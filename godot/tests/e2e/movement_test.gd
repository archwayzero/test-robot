## M1 movement end-to-end tests: TEST_PLAN.md E1 walk_and_run_speed, E2 stance_cycle, E3 low_passage, E4 jump,
## E5 wall_collision. Owner: qa.
extends "res://tests/e2e/e2e_base.gd"

const SPEED_TOLERANCE := 0.05  # +-5%


func _init() -> void:
	timeout_frames = 4000


## Teleports the player to the start of the longest straight FULL corridor, facing along it (camera behind).
## Returns the corridor's direction as a world vector.
func _go_to_corridor(min_cells: int) -> Vector3:
	var corridor := longest_corridor()
	assert_true(int(corridor.length) >= min_cells, "corridor of %d cells found: %s" % [min_cells, corridor])
	var d: MazeLayout.Dir = corridor.dir
	player().spawn_at(layout().cell_to_world(corridor.cell), dir_yaw(d))
	await automation().advance_frames(5)
	return dir_vector(d)


## Average horizontal speed over `frames` frames (exact 1/FPS frames under --fixed-fps).
func _measure_speed(frames: int) -> float:
	var a := flat(player().global_position)
	await automation().advance_frames(frames)
	var b := flat(player().global_position)
	return a.distance_to(b) / (float(frames) / FPS)


func test_e1_walk_and_run_speed() -> void:
	assert_true(await start_game())
	var forward := await _go_to_corridor(3)
	assert_almost_eq(wrapf(camera_yaw() - player().rotation.y, -PI, PI), 0.0, 0.01, "camera behind the player")
	# 50% forward for 60 frames: measure over the last 40 (acceleration 30 m/s^2 settles within 3 frames).
	automation().press_action(GameActions.MOVE_FORWARD, 0.5)
	await automation().advance_frames(20)
	var walk := await _measure_speed(40)
	assert_false(player().is_running(), "50% deflection walks")
	# 100% forward for 60 frames.
	automation().press_action(GameActions.MOVE_FORWARD, 1.0)
	await automation().advance_frames(20)
	var running_now := player().is_running()
	var run := await _measure_speed(40)
	automation().release_action(GameActions.MOVE_FORWARD)
	assert_true(running_now, "100% deflection runs")
	assert_almost_eq(walk, PlayerController.WALK_SPEED, PlayerController.WALK_SPEED * SPEED_TOLERANCE, "walk speed")
	assert_almost_eq(run, PlayerController.RUN_SPEED, PlayerController.RUN_SPEED * SPEED_TOLERANCE, "run speed")
	print("E1 measured: walk %.3f m/s, run %.3f m/s (forward %s)" % [walk, run, forward])


func test_e2_stance_cycle() -> void:
	assert_true(await start_game())
	assert_eq(layout().clearance(player_cell()), MazeLayout.Clearance.FULL, "start cell is open")
	var changes: Array = []
	player().stance_changed.connect(func(s: PlayerController.Stance) -> void: changes.append(s))
	var stand_h := player().get_collision_height()
	assert_eq(player().get_stance(), PlayerController.Stance.STAND)
	assert_true(stand_h > 1.0, "STAND height %s > 1.0" % stand_h)
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CROUCH)
	assert_almost_eq(player().get_collision_height(), 1.0, 0.001, "CROUCH height")
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL)
	assert_almost_eq(player().get_collision_height(), 0.5, 0.001, "CRAWL height")
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.STAND)
	assert_almost_eq(player().get_collision_height(), stand_h, 0.001, "back to STAND height")
	assert_eq(changes, [PlayerController.Stance.CROUCH, PlayerController.Stance.CRAWL, PlayerController.Stance.STAND])
	assert_eq(Core.state.get_value(StateKeys.PLAYER_STANCE), StateKeys.STANCE_STAND, "stance published")
	# Speeds while moving (full deflection: crouch/crawl never run).
	await _go_to_corridor(2)
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CROUCH)
	automation().press_action(GameActions.MOVE_FORWARD, 1.0)
	await automation().advance_frames(10)
	var crouch := await _measure_speed(40)
	assert_false(player().is_running(), "no running while crouched")
	release_move()
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL)
	automation().press_action(GameActions.MOVE_FORWARD, 1.0)
	await automation().advance_frames(10)
	var crawl := await _measure_speed(40)
	assert_false(player().is_running(), "no running while crawling")
	release_move()
	assert_almost_eq(crouch, PlayerController.CROUCH_SPEED, PlayerController.CROUCH_SPEED * SPEED_TOLERANCE, "crouch")
	assert_almost_eq(crawl, PlayerController.CRAWL_SPEED, PlayerController.CRAWL_SPEED * SPEED_TOLERANCE, "crawl")
	print("E2 measured: stand height %.2f, crouch %.3f m/s, crawl %.3f m/s" % [stand_h, crouch, crawl])


## A FULL cell next to a cell of clearance `kind` with an open edge between them: {"from", "to"} or {}.
func _entry_to(kind: MazeLayout.Clearance) -> Dictionary:
	var l := layout()
	for y in l.size().y:
		for x in l.size().x:
			var c := Vector2i(x, y)
			if l.clearance(c) != kind:
				continue
			for n in open_neighbours(c):
				if l.clearance(n) == MazeLayout.Clearance.FULL:
					return {"from": n, "to": c}
	return {}


func test_e3_low_passage() -> void:
	assert_true(await start_game())
	var stances: Array = []
	player().stance_changed.connect(func(s: PlayerController.Stance) -> void: stances.append(s))

	# --- CROUCH cell: crouch in, go to crawl, then try to stand twice. ---
	var crouch_entry := _entry_to(MazeLayout.Clearance.CROUCH)
	assert_false(crouch_entry.is_empty(), "layout has a CROUCH cell with a FULL neighbour")
	if crouch_entry.is_empty():
		return
	var from: Vector2i = crouch_entry.from
	var to: Vector2i = crouch_entry.to
	player().spawn_at(layout().cell_to_world(from), dir_yaw(dir_between(from, to)))
	await automation().advance_frames(5)
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CROUCH, "crouched before the passage")
	assert_true(await walk_to(layout().cell_to_world(to), 1.0, 300), "crouch-walked into CROUCH cell %s" % to)
	await automation().advance_frames(5)
	assert_eq(player_cell(), to, "inside the CROUCH cell")
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL, "crouch -> crawl in CROUCH cell")
	stances.clear()
	for attempt in 2:
		# From CRAWL the cycle tries STAND first; under a 1.3 m ceiling it must be refused (falls back to CROUCH).
		await tap(GameActions.STANCE_CYCLE)
		assert_ne(player().get_stance(), PlayerController.Stance.STAND, "stand refused in CROUCH cell (try %d)" % attempt)
		assert_true(player().get_collision_height() <= 1.0 + 0.001, "height <= 1.0 in CROUCH cell")
		if player().get_stance() == PlayerController.Stance.CROUCH:
			await tap(GameActions.STANCE_CYCLE)  # back to crawl for the next try
	assert_false(PlayerController.Stance.STAND in stances, "no STAND in CROUCH cell: %s" % [stances])
	# Jump from a crouch stands up first: must be refused here too.
	if player().get_stance() == PlayerController.Stance.CRAWL:
		await tap(GameActions.STANCE_CYCLE)
	var jumps := [0]
	player().jumped.connect(func() -> void: jumps[0] += 1)
	await tap(GameActions.JUMP)
	await automation().advance_frames(10)
	assert_eq(jumps[0], 0, "no jump under the CROUCH ceiling")
	assert_ne(player().get_stance(), PlayerController.Stance.STAND, "still low after jump attempt")

	# --- CRAWL cell: crawl in, then try to rise twice (crouch refused). ---
	var crawl_entry := _entry_to(MazeLayout.Clearance.CRAWL)
	assert_false(crawl_entry.is_empty(), "layout has a CRAWL cell with a FULL neighbour")
	if crawl_entry.is_empty():
		return
	from = crawl_entry.from
	to = crawl_entry.to
	player().spawn_at(layout().cell_to_world(from), dir_yaw(dir_between(from, to)))
	await automation().advance_frames(5)
	# spawn_at keeps the stance; in the open FULL cell cycle to CRAWL (at most 3 taps).
	for i in 3:
		if player().get_stance() == PlayerController.Stance.CRAWL:
			break
		await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL, "crawling before the CRAWL passage")
	assert_true(await walk_to(layout().cell_to_world(to), 1.0, 600), "crawled into CRAWL cell %s" % to)
	await automation().advance_frames(5)
	assert_eq(player_cell(), to, "inside the CRAWL cell")
	stances.clear()
	for attempt in 2:
		await tap(GameActions.STANCE_CYCLE)
		assert_eq(player().get_stance(), PlayerController.Stance.CRAWL, "crouch/stand refused in CRAWL cell (try %d)" % attempt)
		assert_almost_eq(player().get_collision_height(), 0.5, 0.001, "crawl height in CRAWL cell")
	assert_eq(stances, [], "no stance_changed in the CRAWL cell")


func test_e4_jump() -> void:
	assert_true(await start_game())
	var events: Array = []
	player().jumped.connect(func() -> void: events.append(["jumped", automation().get_frame()]))
	player().landed.connect(func() -> void: events.append(["landed", automation().get_frame()]))
	await automation().advance_frames(5)
	assert_true(player().is_grounded(), "grounded before the jump")
	var t0 := automation().get_frame()
	var max_y := player().global_position.y
	automation().press_action(GameActions.JUMP)
	await automation().advance_frames(2)
	automation().release_action(GameActions.JUMP)
	for i in 60:
		await automation().advance_frames(1)
		max_y = maxf(max_y, player().global_position.y)
		if events.size() >= 2:
			break
	var names := events.map(func(e: Array) -> String: return e[0])
	assert_eq(names, ["jumped", "landed"], "jumped then landed")
	if events.size() >= 2:
		assert_true(int(events[1][1]) - t0 <= 60, "landed within 60 frames (%d)" % (int(events[1][1]) - t0))
	assert_true(max_y > 0.3, "rose off the floor (max y %.2f)" % max_y)
	# Crawl, then try to jump.
	await tap(GameActions.STANCE_CYCLE)
	await tap(GameActions.STANCE_CYCLE)
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL)
	events.clear()
	var y0 := player().global_position.y
	await tap(GameActions.JUMP)
	await automation().advance_frames(30)
	assert_eq(events, [], "no jump while crawling")
	assert_almost_eq(player().global_position.y, y0, 0.01, "stayed on the floor")
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL, "still crawling")
	print("E4 measured: max jump height %.2f m" % max_y)


func test_e5_wall_collision() -> void:
	assert_true(await start_game())
	var start := layout().cell_to_world(layout().start_cell())
	var min_dist := INF
	var worst := ""
	for i in 8:
		var angle := i * PI / 4.0
		var dir := Vector3(sin(angle), 0.0, -cos(angle))  # 0 = north (-Z), clockwise seen from above
		player().spawn_at(start, 0.0)
		await automation().advance_frames(2)
		for f in 120:
			hold_move(dir, 1.0)  # full deflection: running, the hardest case for tunnelling
			await automation().advance_frames(1)
			var p := player().global_position
			var d := nearest_wall_distance(p)
			if d < min_dist:
				min_dist = d
				worst = "angle %d deg frame %d pos %s" % [i * 45, f, p]
			if d < 0.29:
				fail("angle %d deg frame %d: %.3f m from a wall plane at %s" % [i * 45, f, d, p])
				break
			if not layout().in_bounds(layout().world_to_cell(p)) or p.y < -0.5:
				fail("angle %d deg frame %d: outside the grid at %s" % [i * 45, f, p])
				break
		release_move()
		await automation().advance_frames(2)
	print("E5 measured: minimum distance to a wall plane %.3f m (%s)" % [min_dist, worst])
