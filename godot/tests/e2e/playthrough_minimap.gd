## Gameplay video minimap.mp4 (TEST_PLAN.md "Gameplay videos", M1): fog-of-war reveal on the top-left mini-map
## while walking, then the large map opened by tapping the mini-map and closed by tapping the screen, twice.
## Owner: qa. Recorded with tools/qa/record.py (see playthrough_base.gd).
extends "res://tests/e2e/playthrough_base.gd"


func _route(n: int) -> Array[Vector2i]:
	var tree := bfs(layout().start_cell())
	var best := layout().start_cell()
	for c: Vector2i in tree:
		if int(tree[c][0]) == n:
			best = c
			break
	return path_to(tree, best).slice(1)


func _toggle_map(open: bool) -> void:
	var minimap := main.get_minimap()
	var pos := minimap.get_small_rect().get_center() if open \
			else get_viewport().get_visible_rect().size * 0.5
	step(("tap the mini-map: open large map" if open else "tap screen centre: close large map"))
	await tap_screen(pos)
	step("large map %s (explored %d cells)" % ["OPEN" if minimap.is_large_map_open() else "closed",
			main.get_exploration().explored_count()])


func play() -> void:
	step("fresh game: 1 explored cell")
	await wait_s(2.0)
	var route := _route(8)
	step("walk %d cells, watch the mini-map reveal" % route.size())
	await walk_path(route, 1.0, 0.3)
	step("explored %d cells" % main.get_exploration().explored_count())
	await wait_s(1.0)
	await _toggle_map(true)
	await wait_s(4.0)
	await _toggle_map(false)
	await wait_s(1.0)
	var tree := bfs(player_cell())
	var far := player_cell()
	for c: Vector2i in tree:
		if not main.get_exploration().is_explored(c) and int(tree[c][0]) == 6:
			far = c
			break
	step("walk 6 more cells")
	await walk_path(path_to(tree, far).slice(1), 1.0, 0.3)
	step("explored %d cells" % main.get_exploration().explored_count())
	await wait_s(0.5)
	await _toggle_map(true)
	await wait_s(4.0)
	await _toggle_map(false)
	await wait_s(1.5)
