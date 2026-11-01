## M2 (T020) real-scene end-to-end test: hero, controls, collision and maze working together in GameMain.MAIN_SCENE.
## The route test never teleports: it walks from the start cell through a CROUCH and a CRAWL passage and back out to
## a FULL cell. Owner: qa.
##
## Every condition lives in a plain static function returning "" or a problem text (TEST_PLAN N1), and each has a
## test_self_* feeding it a deliberately broken input (TEST_PLAN "Every new measuring check proves it can fail").
extends "res://tests/e2e/e2e_base.gd"

const MIN_FEET_Y := -0.05
const MAX_FEET_Y := 2.0
const MIN_WALL_DISTANCE := 0.29
## Frames with the stick held and no movement that count as stuck (0.67 s).
const MAX_STALL_FRAMES := 20
const STALL_STEP := 0.001
const SPEED_TOLERANCE := 0.10
## docs/contracts/crypt-kit.md clearances, m.
const CEILING := {MazeLayout.Clearance.CROUCH: 1.3, MazeLayout.Clearance.CRAWL: 0.75}

## Per-frame samples of the current test: {"pos": Vector3, "held": bool, "wall": float}.
var _trace: Array = []
## Median input: stance/run label -> per-frame horizontal speeds (m/s) while held.
var _speeds := {}
var _stances: Array = []
var _jumps := 0
var _lands := 0


func _init() -> void:
	timeout_frames = 9000


func before_each() -> void:
	await super.before_each()
	_trace.clear()
	_speeds.clear()
	_stances.clear()
	_jumps = 0
	_lands = 0


# --- Checks (plain functions, proved by the test_self_* tests) ----------------------------------------------

static func floor_problem(trace: Array) -> String:
	for i in trace.size():
		var y: float = (trace[i].pos as Vector3).y
		if y < MIN_FEET_Y or y > MAX_FEET_Y:
			return "frame %d: feet at y %.3f" % [i, y]
	return ""


static func wall_problem(trace: Array) -> String:
	for i in trace.size():
		if float(trace[i].wall) < MIN_WALL_DISTANCE:
			return "frame %d: %.3f m from a wall at %s" % [i, trace[i].wall, trace[i].pos]
	return ""


## Longest run of consecutive frames with the stick held and no movement.
static func longest_stall(trace: Array) -> int:
	var best := 0
	var run := 0
	for i in range(1, trace.size()):
		var moved := (trace[i].pos as Vector3).distance_to(trace[i - 1].pos) >= STALL_STEP
		if bool(trace[i].held) and not moved:
			run += 1
			best = maxi(best, run)
		else:
			run = 0
	return best


## `changes`: stance_changed values since the attempt; `allowed`: stances the cell may show.
static func refusal_problem(changes: Array, final: int, allowed: Array) -> String:
	if not (final in allowed):
		return "final stance %d not in %s" % [final, allowed]
	for s: int in changes:
		if not (s in allowed):
			return "stance %d appeared under the low ceiling" % s
	return ""


static func fit_problem(height: float, kind: MazeLayout.Clearance) -> String:
	if not CEILING.has(kind):
		return ""
	if height >= float(CEILING[kind]):
		return "height %.2f does not fit under %.2f" % [height, CEILING[kind]]
	return ""


static func median(values: Array) -> float:
	if values.is_empty():
		return 0.0
	var v := values.duplicate()
	v.sort()
	return float(v[v.size() / 2])


static func hero_problem(root: Node) -> String:
	var skeletons := root.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty():
		return "no Skeleton3D under the player (capsule placeholder?)"
	var skinned := 0
	for m: Node in root.find_children("*", "MeshInstance3D", true, false):
		if (m as MeshInstance3D).skin != null:
			skinned += 1
	return "" if skinned > 0 else "no skinned mesh under the player"


## Greybox used untextured materials; the kit merge keeps its textured ones.
static func kit_problem(root: Node) -> String:
	for m: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := (m as MeshInstance3D).mesh
		if mesh == null:
			continue
		for s in mesh.get_surface_count():
			var mat := mesh.surface_get_material(s) as BaseMaterial3D
			if mat != null and mat.albedo_texture != null:
				return ""
	return "no textured mesh in the maze world (greybox?)"


func _report(problem: String, what: String) -> void:
	assert_eq(problem, "", what)


func _check_trace(what: String) -> void:
	_report(floor_problem(_trace), "%s: never through the floor" % what)
	_report(wall_problem(_trace), "%s: never inside a wall" % what)
	var stall := longest_stall(_trace)
	assert_true(stall <= MAX_STALL_FRAMES, "%s: stuck for %d frames" % [what, stall])
	print("M2 measured: %s %d frames, feet y %.3f..%.3f, wall %.3f, stall %d" % [what, _trace.size(),
			_trace.map(func(t: Dictionary) -> float: return t.pos.y).min(),
			_trace.map(func(t: Dictionary) -> float: return t.pos.y).max(),
			_trace.map(func(t: Dictionary) -> float: return t.wall).min(), stall])


## The wall check means nothing unless the route really reached the walls.
func _check_touched_walls() -> void:
	var closest: float = _trace.map(func(t: Dictionary) -> float: return t.wall).min()
	assert_true(closest < 0.35, "the route pressed against a wall (closest %.3f m)" % closest)


func _check_speed(label: String, expected: float) -> void:
	var m := median(_speeds.get(label, []))
	assert_almost_eq(m, expected, expected * SPEED_TOLERANCE, "%s median speed" % label)
	print("M2 measured: %s median %.3f m/s over %d frames" % [label, m, (_speeds.get(label, []) as Array).size()])


func _check_refused(allowed: Array, kind: MazeLayout.Clearance, what: String) -> void:
	_report(refusal_problem(_stances, player().get_stance(), allowed), what)
	_report(fit_problem(player().get_collision_height(), kind), "%s: fits the ceiling" % what)
	print("M2 measured: %s: changes %s, stance %d, height %.2f" % [what, _stances, player().get_stance(),
			player().get_collision_height()])


func _check_jump(max_y: float, y0: float) -> void:
	assert_eq(_jumps, 1, "jumped once")
	assert_eq(_lands, 1, "landed once")
	assert_true(max_y - y0 > 0.3, "rose %.2f m" % (max_y - y0))
	assert_almost_eq(player().global_position.y, y0, 0.02, "back on the floor")
	print("M2 measured: jump rose %.2f m" % (max_y - y0))


func _check_real_assets() -> void:
	_report(hero_problem(player()), "real hero in the main scene")
	_report(kit_problem(main.get_maze_world()), "real kit in the main scene")


func _check_route_end(cells: Array[Vector2i]) -> void:
	assert_eq(layout().clearance(player_cell()), MazeLayout.Clearance.FULL, "back in a FULL cell")
	assert_eq(player().get_stance(), PlayerController.Stance.STAND, "standing again")
	assert_true(player().is_grounded(), "grounded at the end")
	assert_eq(Core.state.get_phase(), StateKeys.PHASE_PLAYING, "still playing")
	var seen := {}
	for c in cells:
		seen[c] = true
	var explored: Array = []
	for c: Variant in main.get_exploration().get_explored_cells():
		explored.append(c)
	for c: Vector2i in seen:
		assert_true(c in explored, "cell %s on the route was explored" % c)
	print("M2 measured: route %d cells, %d explored" % [cells.size(), explored.size()])


func _check_restored(cell: Vector2i, kind: MazeLayout.Clearance, pos: Vector3, expected: int) -> void:
	assert_eq(player_cell(), cell, "restored in the low cell")
	assert_true(player().global_position.distance_to(pos) <= 0.1, "position within 0.1 m")
	assert_eq(player().get_stance(), expected, "fitting stance")
	_report(fit_problem(player().get_collision_height(), kind), "restored stance fits")
	assert_true(player().is_grounded(), "grounded after the restore")
	assert_true(player().global_position.y > MIN_FEET_Y, "not through the floor")
	print("M2 measured: restored in clearance %d: stance %d, height %.2f, y %.3f" % [kind, player().get_stance(),
			player().get_collision_height(), player().global_position.y])


# --- Driving ------------------------------------------------------------------------------------------------

func _on_stance(s: PlayerController.Stance) -> void:
	_stances.append(int(s))


func _on_jumped() -> void:
	_jumps += 1


func _on_landed() -> void:
	_lands += 1


func _connect_player() -> void:
	player().stance_changed.connect(_on_stance)
	player().jumped.connect(_on_jumped)
	player().landed.connect(_on_landed)


func _sample(held: bool) -> void:
	var p := player().global_position
	_trace.append({"pos": p, "held": held, "wall": nearest_wall_distance(p)})


func _speed_label() -> String:
	if player().get_stance() == PlayerController.Stance.CROUCH:
		return "crouch"
	if player().get_stance() == PlayerController.Stance.CRAWL:
		return "crawl"
	return "run" if player().is_running() else "walk"


## walk_to() that samples the trace every frame. Corners are excluded from the speeds by the median.
func _drive(target: Vector3, strength: float, max_frames := 500) -> bool:
	for i in max_frames:
		var diff := flat(target) - flat(player().global_position)
		if diff.length() < 0.2:
			release_move()
			return true
		hold_move(Vector3(diff.x, 0.0, diff.y), strength)
		var before := flat(player().global_position)
		await automation().advance_frames(1)
		_sample(true)
		var label := _speed_label()
		if not _speeds.has(label):
			_speeds[label] = []
		(_speeds[label] as Array).append(before.distance_to(flat(player().global_position)) * FPS)
	release_move()
	return false


func _stance_for(kind: MazeLayout.Clearance) -> PlayerController.Stance:
	if kind == MazeLayout.Clearance.CROUCH:
		return PlayerController.Stance.CROUCH
	if kind == MazeLayout.Clearance.CRAWL:
		return PlayerController.Stance.CRAWL
	return PlayerController.Stance.STAND


func _go_stance(target: PlayerController.Stance) -> void:
	for i in 3:
		if player().get_stance() == target:
			return
		await tap(GameActions.STANCE_CYCLE)
		_sample(false)


## Walks centre to centre, lowering before a lower cell and rising only inside a taller one, as a player would.
func _travel(cells: Array[Vector2i], strength: float) -> bool:
	for c in cells:
		var want := _stance_for(layout().clearance(c))
		if int(want) > int(player().get_stance()):
			await _go_stance(want)
		if not await _drive(layout().cell_to_world(c), strength):
			fail("stuck before cell %s: player %s in cell %s, stance %d" % [c, player().global_position, player_cell(),
					player().get_stance()])
			return false
		if int(want) < int(player().get_stance()):
			await _go_stance(want)
	return true


## Nearest cell (over all clearances) from `from` for which `kind` holds.
func _nearest(from: Vector2i, kind: MazeLayout.Clearance) -> Array[Vector2i]:
	var tree := bfs(from)
	var best := Vector2i(-1, -1)
	var best_d := 1000000
	for c: Vector2i in tree:
		if layout().clearance(c) == kind and c != from and int(tree[c][0]) < best_d:
			best = c
			best_d = int(tree[c][0])
	if best.x < 0:
		fail("no cell of clearance %d" % kind)
		return [from]
	return path_to(tree, best)


func _jump_here() -> void:
	var y0 := player().global_position.y
	var max_y := y0
	_jumps = 0
	_lands = 0
	automation().press_action(GameActions.JUMP)
	await automation().advance_frames(2)
	automation().release_action(GameActions.JUMP)
	for i in 60:
		await automation().advance_frames(1)
		_sample(false)
		max_y = maxf(max_y, player().global_position.y)
		if _lands > 0:
			break
	await automation().advance_frames(3)
	_check_jump(max_y, y0)


## Pushes into every wall of the cell centred on, so the route also touches the collision of the low cells (the
## cell-centre walk alone stays 1.4 m away). Stick-held frames against a wall are expected here: sampled as not held.
func _push_walls(cell: Vector2i) -> void:
	for d in DIRS:
		if not layout().has_wall(cell, d):
			continue
		for i in 100:
			hold_move(dir_vector(d), 1.0)
			await automation().advance_frames(1)
			_sample(false)
		release_move()
		assert_true(await _drive(layout().cell_to_world(cell), 1.0), "back to the centre of %s" % cell)


# --- Tests --------------------------------------------------------------------------------------------------

func test_m2_route_from_start_through_low_passages() -> void:
	assert_true(await start_game())
	_check_real_assets()
	_connect_player()
	var start := layout().start_cell()
	assert_eq(player_cell(), start, "starts in the start cell")
	print("M2 layout: start %s, seed %d, cell %.1f m" % [start, layout().get_seed(), layout().cell_size_m()])

	var to_crouch := _nearest(start, MazeLayout.Clearance.CROUCH)
	var crouch_cell: Vector2i = to_crouch[-1]
	var to_crawl := _nearest(crouch_cell, MazeLayout.Clearance.CRAWL)
	var crawl_cell: Vector2i = to_crawl[-1]
	var out := _nearest(crawl_cell, MazeLayout.Clearance.FULL)
	print("M2 route: crouch path %s, crawl path %s, out %s" % [to_crouch, to_crawl, out])

	# Walk the first leg, then jump, then run the rest.
	assert_true(await _travel(to_crouch.slice(1, 2), 0.5), "walked the first cell")
	await _jump_here()
	assert_true(await _travel(to_crouch.slice(2), 1.0), "reached the CROUCH passage")
	_stances.clear()
	assert_eq(player().get_stance(), PlayerController.Stance.CROUCH, "crouching in the CROUCH cell")
	await tap(GameActions.STANCE_CYCLE)  # to crawl (allowed: going lower)
	await tap(GameActions.STANCE_CYCLE)  # stand refused, falls back to crouch
	_check_refused([PlayerController.Stance.CROUCH, PlayerController.Stance.CRAWL], MazeLayout.Clearance.CROUCH,
			"CROUCH cell, stand refused")
	await _push_walls(crouch_cell)
	var jumps_before := _jumps
	await tap(GameActions.JUMP)
	await automation().advance_frames(10)
	assert_eq(_jumps, jumps_before, "no jump under the CROUCH ceiling")

	assert_true(await _travel(to_crawl.slice(1), 1.0), "reached the CRAWL passage")
	_stances.clear()
	assert_eq(player().get_stance(), PlayerController.Stance.CRAWL, "crawling in the CRAWL cell")
	await tap(GameActions.STANCE_CYCLE)
	await tap(GameActions.STANCE_CYCLE)
	_check_refused([PlayerController.Stance.CRAWL], MazeLayout.Clearance.CRAWL, "CRAWL cell, rise refused")
	await _push_walls(crawl_cell)

	assert_true(await _travel(out.slice(1), 1.0), "left the low passages")
	await automation().advance_frames(10)
	_sample(false)
	var cells: Array[Vector2i] = []
	cells.append_array(to_crouch)
	cells.append_array(to_crawl)
	cells.append_array(out)
	_check_route_end(cells)
	_check_trace("route")
	_check_touched_walls()
	_check_speed("walk", PlayerController.WALK_SPEED)
	_check_speed("run", PlayerController.RUN_SPEED)
	_check_speed("crouch", PlayerController.CROUCH_SPEED)
	_check_speed("crawl", PlayerController.CRAWL_SPEED)
	checkpoint("end")


func _check_boot(frames: int, fades: Array) -> void:
	assert_true(frames <= READY_TIMEOUT, "ready within %d frames (%d)" % [READY_TIMEOUT, frames])
	assert_eq(int(player().get_stance()), int(PlayerController.Stance.STAND), "boots standing")
	assert_true(player().is_grounded(), "boots grounded")
	var faded := 0
	for f: float in fades:
		if f > 0.0:
			faded += 1
	# Measured, not asserted: finding F2 in docs/qa/reports/T020-m2.md (hero fade after boot).
	print("M2 measured: ready after %d frames; hero fade above 0 for %d of the next %d frames (first %.3f)" % [frames,
			faded, fades.size(), fades[0]])


func _record_fades(fades: Array) -> void:
	fades.append(float(player().call("get_visual_fade")))


func test_m2_boot_frames() -> void:
	var f0 := automation().get_frame()
	assert_true(await start_game())
	var frames := automation().get_frame() - f0
	var fades: Array = []
	for i in 16:
		_record_fades(fades)
		await automation().advance_frames(1)
	_check_boot(frames, fades)
	checkpoint("end")


## A FULL cell next to a cell of `kind`: {"from", "to"}, or {}.
func _entry(kind: MazeLayout.Clearance) -> Dictionary:
	for y in layout().size().y:
		for x in layout().size().x:
			var c := Vector2i(x, y)
			if layout().clearance(c) != kind:
				continue
			for n in open_neighbours(c):
				if layout().clearance(n) == MazeLayout.Clearance.FULL:
					return {"from": n, "to": c}
	return {}


## Crawls or crouches into a `kind` cell, saves with stance value `saved` (the real stance when < 0), reloads from
## disk only, checks the stance, then leaves the passage. A saved stance taller than the cell is the case a save
## from an older build, or a cloud save, could hold.
func _save_restore(kind: MazeLayout.Clearance, saved: int, expected: int) -> void:
	assert_true(await start_game())
	var e := _entry(kind)
	assert_false(e.is_empty(), "layout has an entry to clearance %d" % kind)
	var from: Vector2i = e.from
	var to: Vector2i = e.to
	player().spawn_at(layout().cell_to_world(from), dir_yaw(dir_between(from, to)))
	await automation().advance_frames(5)
	await _go_stance(_stance_for(kind))
	assert_true(await _drive(layout().cell_to_world(to), 1.0), "entered the low cell")
	await automation().advance_frames(35)  # let the throttled position write land
	var pos := player().global_position
	if saved >= 0:
		Core.state.set_value(StateKeys.PLAYER_STANCE, saved)
	assert_eq(int(Core.state.get_value(StateKeys.PLAYER_STANCE)), saved if saved >= 0 else int(_stance_for(kind)),
			"stance value going into the save")
	assert_eq(main.get_auto_save().save_now(), OK, "save_now OK")
	await _unload()
	clear_saved_keys()
	assert_true(await start_game())
	await automation().advance_frames(5)
	_check_restored(to, kind, pos, expected)
	# Not stuck: the player leaves the passage and stands up.
	_trace.clear()
	assert_true(await _drive(layout().cell_to_world(from), 1.0), "left the low cell after the restore")
	await _go_stance(PlayerController.Stance.STAND)
	assert_eq(player().get_stance(), PlayerController.Stance.STAND, "stands again in the FULL cell")
	_check_trace("after restore in clearance %d" % kind)
	checkpoint("end")


func test_m2_save_restore_crouch_cell_keeps_crouch() -> void:
	await _save_restore(MazeLayout.Clearance.CROUCH, -1, PlayerController.Stance.CROUCH)


func test_m2_save_restore_crawl_cell_keeps_crawl() -> void:
	await _save_restore(MazeLayout.Clearance.CRAWL, -1, PlayerController.Stance.CRAWL)


func test_m2_saved_stand_in_crouch_cell_becomes_crouch() -> void:
	await _save_restore(MazeLayout.Clearance.CROUCH, PlayerController.Stance.STAND, PlayerController.Stance.CROUCH)


func test_m2_saved_stand_in_crawl_cell_becomes_crawl() -> void:
	await _save_restore(MazeLayout.Clearance.CRAWL, PlayerController.Stance.STAND, PlayerController.Stance.CRAWL)


func test_m2_saved_crouch_in_crawl_cell_becomes_crawl() -> void:
	await _save_restore(MazeLayout.Clearance.CRAWL, PlayerController.Stance.CROUCH, PlayerController.Stance.CRAWL)


# --- Self-tests: one broken input per check ---------------------------------------------------------------------

static func _point(y: float, wall := 1.0, held := false, x := 0.0) -> Dictionary:
	return {"pos": Vector3(x, y, 0.0), "held": held, "wall": wall}


func test_self_floor_check_can_fail() -> void:
	assert_eq(floor_problem([_point(0.0), _point(0.8)]), "", "good trace")
	assert_ne(floor_problem([_point(0.0), _point(-0.5)]), "", "fell through the floor")
	checkpoint("end")


func test_self_wall_check_can_fail() -> void:
	assert_eq(wall_problem([_point(0.0, 0.3)]), "", "good trace")
	assert_ne(wall_problem([_point(0.0, 0.1)]), "", "inside a wall")
	checkpoint("end")


func test_self_stall_check_can_fail() -> void:
	var moving: Array = []
	var stuck: Array = []
	for i in 40:
		moving.append(_point(0.0, 1.0, true, i * 0.01))
		stuck.append(_point(0.0, 1.0, true, 0.0))
	assert_eq(longest_stall(moving), 0, "moving trace")
	assert_true(longest_stall(stuck) > MAX_STALL_FRAMES, "stuck trace")
	checkpoint("end")


func test_self_refusal_check_can_fail() -> void:
	assert_eq(refusal_problem([1, 2], 1, [1, 2]), "", "stayed low")
	assert_ne(refusal_problem([0, 1], 1, [1, 2]), "", "stood up and dropped back")
	assert_ne(refusal_problem([], 0, [1, 2]), "", "ended standing")
	checkpoint("end")


func test_self_fit_check_can_fail() -> void:
	assert_eq(fit_problem(1.0, MazeLayout.Clearance.CROUCH), "", "crouch fits a CROUCH cell")
	assert_ne(fit_problem(1.75, MazeLayout.Clearance.CROUCH), "", "stand does not fit a CROUCH cell")
	assert_ne(fit_problem(1.0, MazeLayout.Clearance.CRAWL), "", "crouch does not fit a CRAWL cell")
	checkpoint("end")


func test_self_hero_check_can_fail() -> void:
	var capsule := Node3D.new()
	var mesh := MeshInstance3D.new()
	mesh.mesh = CapsuleMesh.new()
	capsule.add_child(mesh)
	assert_ne(hero_problem(capsule), "", "a capsule is not the hero")
	capsule.free()
	checkpoint("end")


func test_self_kit_check_can_fail() -> void:
	var grey := Node3D.new()
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	mesh.mesh.surface_set_material(0, StandardMaterial3D.new())
	grey.add_child(mesh)
	assert_ne(kit_problem(grey), "", "an untextured box is not the kit")
	grey.free()
	checkpoint("end")
