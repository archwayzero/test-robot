## T019 scratch: walk, run, jump, crouch, crawl in the real game scene, then both low passages.
extends "res://tests/e2e/playthrough_stances.gd"

func _far_path() -> Array[Vector2i]:
	var tree := bfs(layout().start_cell())
	var best: Vector2i = layout().start_cell()
	for c in tree:
		if int(tree[c][0]) > int(tree[best][0]):
			best = c
	return path_to(tree, best)


func _go(cell: Vector2i, strength: float, frames: int) -> void:
	await walk_to(layout().cell_to_world(cell), strength, frames, 0.3)


func _inside(kind: MazeLayout.Clearance, stance: PlayerController.Stance, seconds: float) -> void:
	var p := _passage(kind)
	var dir := Vector3(dir_offset(p.dir).x, 0, dir_offset(p.dir).y)
	player().spawn_at(layout().cell_to_world(p.to) - dir * 1.2, yaw_of(dir))
	player().restore_stance(stance)
	step("inside %s passage, idle" % STANCE_NAMES[stance])
	await wait_s(1.2)
	step("moving in the passage")
	await walk_to(layout().cell_to_world(p.to) + dir * 1.9, 1.0, int(seconds * FPS), 0.1)
	release_move()
	step("stopped in the passage")
	await wait_s(1.0)


func play() -> void:
	var path := _far_path()
	step("stand idle, %d cells" % path.size())
	await wait_s(1.0)
	step("walk")
	await _go(path[1], 0.5, 66)
	step("run")
	await _go(path[2], 1.0, 45)
	await _go(path[3], 1.0, 30)
	release_move()
	release_orbit()
	step("stop")
	await wait_s(0.6)
	step("jump standing")
	await tap(GameActions.JUMP)
	await wait_s(1.2)
	step("crouch idle")
	await _set_stance(PlayerController.Stance.CROUCH)
	await wait_s(0.8)
	step("crouch walk")
	await _go(path[4], 1.0, 54)
	release_move()
	step("crawl idle")
	await _set_stance(PlayerController.Stance.CRAWL)
	await wait_s(0.9)
	step("crawl")
	await _go(path[5], 1.0, 60)
	release_move()
	release_orbit()
	await _inside(MazeLayout.Clearance.CROUCH, PlayerController.Stance.CROUCH, 2.0)
	await _inside(MazeLayout.Clearance.CRAWL, PlayerController.Stance.CRAWL, 2.0)
	step("end")
