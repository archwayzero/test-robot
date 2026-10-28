## Shared helpers for the M1 end-to-end tests (TEST_PLAN.md E1-E15). Owner: qa.
## Not a test file itself (the runner only collects *_test.gd). Test files `extends "res://tests/e2e/e2e_base.gd"`.
##
## Every test: Core.automation.set_seed(1), set_fixed_timestep(60, 30), fresh state (no save in slot 0, no
## player/exploration keys), load GameMain.MAIN_SCENE through Core.automation.load_scene(), wait for ready_to_play,
## then drive input through Core.automation only (press/release/tap actions, touch, drag, inject_event).
## Read-only observation uses the public accessors of GameMain and the public APIs of the modules.
## Teleporting (PlayerController.spawn_at) is used only where TEST_PLAN.md does not prescribe a start position.
extends TestCase

const READY_TIMEOUT := 300
const FPS := 30
const PHYSICS_TPS := 60
const MOVE_ACTIONS: Array[StringName] = [GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
		GameActions.MOVE_BACK]
## Crypt-kit contract (docs/contracts/crypt-kit.md): walls 0.6 m thick, centred on the cell edge.
const WALL_THICKNESS := 0.6

var main: GameMain
var _initial_state: Dictionary


func before_all() -> void:
	_initial_state = Core.state.snapshot()


func after_all() -> void:
	await _unload()
	_reset_state()
	Core.state.restore(_initial_state)


func before_each() -> void:
	await _unload()
	_reset_state()
	automation().set_seed(1)
	automation().set_fixed_timestep(PHYSICS_TPS, FPS)


func after_each() -> void:
	_release_all()
	await _unload()
	_reset_state()


func _reset_state() -> void:
	get_tree().paused = false
	Core.state.restore(_initial_state)
	if Core.saves.has_save(AutoSave.SAVE_SLOT):
		Core.saves.delete_save(AutoSave.SAVE_SLOT)
	clear_saved_keys()
	Core.state.set_paused(false)


## Removes every key the game persists, so the next boot is a fresh game (or restores from disk only).
func clear_saved_keys() -> void:
	for key in [StateKeys.PLAYER_POSITION, StateKeys.PLAYER_YAW, StateKeys.PLAYER_STANCE,
			StateKeys.EXPLORATION_VISITED, StateKeys.EXPLORATION_COUNT, StateKeys.MAZE_SEED]:
		Core.state.set_value(key, null)


func _release_all() -> void:
	for a in GameActions.ALL:
		if Input.is_action_pressed(a):
			automation().release_action(a)


func _unload() -> void:
	main = null
	if get_tree().current_scene != null:
		get_tree().unload_current_scene()
		await wait_frames(2)


## Loads the real main scene through the automation API and waits for ready_to_play. Returns success.
func start_game() -> bool:
	await automation().load_scene(GameMain.MAIN_SCENE)
	main = get_tree().current_scene as GameMain
	if main == null:
		fail("current scene is not a GameMain after load_scene(%s)" % GameMain.MAIN_SCENE)
		return false
	var ok := await automation().wait_until(func() -> bool: return main.is_ready_to_play(), READY_TIMEOUT)
	if not ok:
		fail("ready_to_play not reached within %d frames" % READY_TIMEOUT)
	return ok


func player() -> PlayerController:
	return main.get_player()


func layout() -> MazeLayout:
	return main.get_maze_world().get_layout()


func player_cell() -> Vector2i:
	return layout().world_to_cell(player().global_position)


func flat(v: Vector3) -> Vector2:
	return Vector2(v.x, v.z)


# --- Directions ----------------------------------------------------------------------------------------

const DIRS: Array[MazeLayout.Dir] = [MazeLayout.Dir.NORTH, MazeLayout.Dir.EAST, MazeLayout.Dir.SOUTH,
		MazeLayout.Dir.WEST]


static func dir_offset(d: MazeLayout.Dir) -> Vector2i:
	match d:
		MazeLayout.Dir.NORTH:
			return Vector2i(0, -1)
		MazeLayout.Dir.EAST:
			return Vector2i(1, 0)
		MazeLayout.Dir.SOUTH:
			return Vector2i(0, 1)
	return Vector2i(-1, 0)


## World-space unit vector of a direction (NORTH = -Z, EAST = +X).
static func dir_vector(d: MazeLayout.Dir) -> Vector3:
	var o := dir_offset(d)
	return Vector3(o.x, 0.0, o.y)


## Godot yaw (0 faces -Z, +PI/2 faces -X) facing direction `d`.
static func dir_yaw(d: MazeLayout.Dir) -> float:
	var v := dir_vector(d)
	return atan2(-v.x, -v.z)


static func dir_between(a: Vector2i, b: Vector2i) -> MazeLayout.Dir:
	var o := b - a
	for d in DIRS:
		if dir_offset(d) == o:
			return d
	return MazeLayout.Dir.NORTH


## Longest straight run of FULL-clearance cells joined by open edges: {"cell", "dir", "length"} (length = number of
## further cells reachable straight ahead from "cell").
func longest_corridor() -> Dictionary:
	var l := layout()
	var best := {"cell": l.start_cell(), "dir": MazeLayout.Dir.NORTH, "length": 0}
	for y in l.size().y:
		for x in l.size().x:
			var c := Vector2i(x, y)
			if l.clearance(c) != MazeLayout.Clearance.FULL:
				continue
			for d in DIRS:
				var n := 0
				var cur := c
				while not l.has_wall(cur, d):
					var nxt := cur + dir_offset(d)
					if not l.in_bounds(nxt) or l.clearance(nxt) != MazeLayout.Clearance.FULL:
						break
					n += 1
					cur = nxt
				if n > int(best.length):
					best = {"cell": c, "dir": d, "length": n}
	return best


## Open neighbours of `cell` (no wall between, in bounds).
func open_neighbours(cell: Vector2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for d in DIRS:
		var n := cell + dir_offset(d)
		if not layout().has_wall(cell, d) and layout().in_bounds(n):
			out.append(n)
	return out


## BFS distances from `from` over open edges, optionally only through FULL cells. Returns {cell: [dist, parent]}.
func bfs(from: Vector2i, full_only := false) -> Dictionary:
	var seen := {from: [0, from]}
	var queue: Array[Vector2i] = [from]
	while not queue.is_empty():
		var c: Vector2i = queue.pop_front()
		for n in open_neighbours(c):
			if seen.has(n):
				continue
			if full_only and layout().clearance(n) != MazeLayout.Clearance.FULL:
				continue
			seen[n] = [int(seen[c][0]) + 1, c]
			queue.append(n)
	return seen


## Shortest path start..target (inclusive) from a bfs() result.
static func path_to(tree: Dictionary, target: Vector2i) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	var c := target
	while true:
		path.push_front(c)
		var parent: Vector2i = tree[c][1]
		if parent == c:
			break
		c = parent
	return path


# --- Input helpers (all through Core.automation) --------------------------------------------------------

## Yaw of the player's camera, from the public get_camera() (movement input is camera-relative).
func camera_yaw() -> float:
	var fwd := -player().get_camera().global_basis.z
	return atan2(-fwd.x, -fwd.z)


## Holds the move actions so the player moves along world direction `world_dir` with joystick deflection
## `strength` (0..1). Releases components that are ~0.
func hold_move(world_dir: Vector3, strength: float) -> void:
	var local := Vector3(world_dir.x, 0.0, world_dir.z).normalized().rotated(Vector3.UP, -camera_yaw()) * strength
	_set_axis(GameActions.MOVE_RIGHT, GameActions.MOVE_LEFT, local.x)
	_set_axis(GameActions.MOVE_BACK, GameActions.MOVE_FORWARD, local.z)


func _set_axis(positive: StringName, negative: StringName, value: float) -> void:
	if value > 0.001:
		automation().press_action(positive, value)
		if Input.is_action_pressed(negative):
			automation().release_action(negative)
	elif value < -0.001:
		automation().press_action(negative, -value)
		if Input.is_action_pressed(positive):
			automation().release_action(positive)
	else:
		for a in [positive, negative]:
			if Input.is_action_pressed(a):
				automation().release_action(a)


func release_move() -> void:
	for a in MOVE_ACTIONS:
		if Input.is_action_pressed(a):
			automation().release_action(a)


## Walks (re-steering every frame) to the horizontal point `target`. Returns true if reached within `max_frames`.
func walk_to(target: Vector3, strength := 0.5, max_frames := 600, tolerance := 0.12) -> bool:
	var frames := 0
	while frames < max_frames:
		var diff := flat(target) - flat(player().global_position)
		if diff.length() < tolerance:
			release_move()
			return true
		hold_move(Vector3(diff.x, 0.0, diff.y), strength)
		await automation().advance_frames(1)
		frames += 1
	release_move()
	return false


## Walks along `cells` (centre to centre). Returns true if every centre was reached.
func walk_path(cells: Array[Vector2i], strength := 0.5, frames_per_cell := 400) -> bool:
	for c in cells:
		if not await walk_to(layout().cell_to_world(c), strength, frames_per_cell):
			fail("could not reach cell %s (player at %s, cell %s)" % [c, player().global_position, player_cell()])
			return false
	return true


func tap(action: StringName, frames := 2) -> void:
	await automation().tap_action(action, frames)
	await automation().advance_frames(2)


# --- Geometry -------------------------------------------------------------------------------------------

## Horizontal distance from `p` to the nearest wall box (per the crypt-kit contract) in the 3x3 cells around it.
func nearest_wall_distance(p: Vector3) -> float:
	var l := layout()
	var s := l.cell_size_m()
	var cell := l.world_to_cell(p)
	var best := INF
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			var c := cell + Vector2i(dx, dy)
			for d in DIRS:
				if not l.has_wall(c, d):
					continue
				var centre: Vector2
				var half: Vector2
				match d:
					MazeLayout.Dir.NORTH:
						centre = Vector2((c.x + 0.5) * s, c.y * s)
						half = Vector2(s * 0.5, WALL_THICKNESS * 0.5)
					MazeLayout.Dir.SOUTH:
						centre = Vector2((c.x + 0.5) * s, (c.y + 1) * s)
						half = Vector2(s * 0.5, WALL_THICKNESS * 0.5)
					MazeLayout.Dir.WEST:
						centre = Vector2(c.x * s, (c.y + 0.5) * s)
						half = Vector2(WALL_THICKNESS * 0.5, s * 0.5)
					_:
						centre = Vector2((c.x + 1) * s, (c.y + 0.5) * s)
						half = Vector2(WALL_THICKNESS * 0.5, s * 0.5)
				var q := (flat(p) - centre).abs() - half
				best = minf(best, Vector2(maxf(q.x, 0.0), maxf(q.y, 0.0)).length())
	return best
