## Gameplay video walkthrough.mp4 (TEST_PLAN.md "Gameplay videos", M1): ~60 s scripted walk through the maze,
## first walking (50% stick), then running (100% stick), camera turned toward the walking direction with orbit drags.
## Owner: qa. Recorded with tools/qa/record.py (see playthrough_base.gd).
extends "res://tests/e2e/playthrough_base.gd"

const WALK_UNTIL_S := 22.0
const RUN_UNTIL_S := 56.0


## A long route: greedily chains BFS paths to the farthest not-yet-visited FULL cell.
func _tour(min_cells: int) -> Array[Vector2i]:
	var route: Array[Vector2i] = []
	var visited := {}
	var cur := layout().start_cell()
	visited[cur] = true
	for leg in 10:
		var tree := bfs(cur)
		var best := cur
		var best_d := -1
		for c: Vector2i in tree:
			if visited.has(c):
				continue
			if int(tree[c][0]) > best_d:
				best_d = int(tree[c][0])
				best = c
		if best == cur:
			break
		var p := path_to(tree, best)
		for c in p.slice(1):
			route.append(c)
			visited[c] = true
		cur = best
		if route.size() >= min_cells:
			break
	return route


func play() -> void:
	await wait_s(1.5)
	var route := _tour(70)
	step("walk (stick 50%%), %d-cell route" % route.size())
	var running := false
	var t0 := Engine.get_process_frames()
	for c in route:
		var t := float(Engine.get_process_frames() - t0) / FPS + 1.5
		if t >= RUN_UNTIL_S:
			break
		if not running and t >= WALK_UNTIL_S:
			running = true
			step("run (stick 100%)")
		if not await walk_to(layout().cell_to_world(c), 1.0 if running else 0.5, 900, 0.35 if running else 0.2):
			step("stuck before %s" % c)
			break
	release_move()
	release_orbit()
	step("stop (idle)")
	await wait_s(3.0)
