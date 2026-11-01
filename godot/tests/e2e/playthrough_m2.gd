## Gameplay video M2/m2_real_scene.mp4 (T020): the real main scene with the hero and the kit. Walk, jump and run from
## the start cell, then a CROUCH passage and a CRAWL passage, in and out. Captions mark the cuts (teleports that keep
## the video short; m2_real_scene_test.gd walks the full route without them). Owner: qa.
## CPU rendering takes longer than one job may run, so the video is four recordings of one scene file each
## (playthrough_m2_<part>.tscn), each a fresh boot of the main scene, joined with ffmpeg.
extends "res://tests/e2e/playthrough_base.gd"

const NAMES := ["STAND", "CROUCH", "CRAWL"]

## "open", "crouch", "crawl_in" or "crawl_out".
@export var part := "open"
## Where this recording starts in the joined video, for the caption clock.
@export var offset_s := 0.0


func video_time() -> String:
	var t := offset_s + float(Engine.get_process_frames() - _start_frame) / FPS
	return "%02d:%04.1f" % [int(t / 60.0), fmod(t, 60.0)]


## {"to": low cell, "dir": direction in, "out": unit vector from the low cell to its way out}, or {}.
func _passage(kind: MazeLayout.Clearance) -> Dictionary:
	var fallback := {}
	for y in layout().size().y:
		for x in layout().size().x:
			var c := Vector2i(x, y)
			if layout().clearance(c) != kind:
				continue
			for d in DIRS:
				var from := c - dir_offset(d)
				if not layout().in_bounds(from) or layout().has_wall(from, d) \
						or layout().clearance(from) != MazeLayout.Clearance.FULL:
					continue
				var v := Vector3(dir_offset(d).x, 0, dir_offset(d).y)
				var exit := c + dir_offset(d)
				if not layout().has_wall(c, d) and layout().in_bounds(exit) \
						and layout().clearance(exit) == MazeLayout.Clearance.FULL:
					return {"to": c, "dir": v, "out": v}
				if fallback.is_empty():
					fallback = {"to": c, "dir": v, "out": -v}
	return fallback


func _stance(target: PlayerController.Stance) -> void:
	for i in 3:
		if player().get_stance() == target:
			return
		await tap(GameActions.STANCE_CYCLE)


func _enter(p: Dictionary, stance: PlayerController.Stance, name_: String) -> void:
	var centre := layout().cell_to_world(p.to)
	await _stance(stance)
	player().spawn_at(centre - p.dir * (layout().cell_size_m() - 1.6), yaw_of(p.dir))
	step("%s passage ahead, %s" % [name_, NAMES[stance]])
	await wait(10)
	await walk_to(centre, 1.0, 400)
	release_move()
	release_orbit()
	step("inside %s cell: try to rise" % name_)
	await tap(GameActions.STANCE_CYCLE)
	await wait_s(0.6)
	await tap(GameActions.STANCE_CYCLE)
	await wait_s(0.6)
	step("stance now %s (height %.2f m)" % [NAMES[player().get_stance()], player().get_collision_height()])


func _leave(p: Dictionary, stance: PlayerController.Stance) -> void:
	await _stance(stance)
	step("leave the passage")
	await walk_to(layout().cell_to_world(p.to) + p.out * 2.6, 1.0, 400)
	release_move()
	release_orbit()
	await _stance(PlayerController.Stance.STAND)
	step("out: %s" % NAMES[player().get_stance()])
	await wait_s(0.6)


func _opening() -> void:
	var start := layout().start_cell()
	var tree := bfs(start)
	var far := start
	for c: Vector2i in tree:
		if int(tree[c][0]) == 4:
			far = c
			break
	var route := path_to(tree, far)
	await wait_s(0.5)
	step("walk")
	await walk_path(route.slice(1, 2), 0.5)
	step("jump")
	await tap(GameActions.JUMP)
	await wait_s(0.9)
	step("run")
	await walk_path(route.slice(2), 1.0)


func play() -> void:
	match part:
		"open":
			await _opening()
		"crouch":
			var p := _passage(MazeLayout.Clearance.CROUCH)
			await _enter(p, PlayerController.Stance.CROUCH, "CROUCH")
			await _leave(p, PlayerController.Stance.CROUCH)
		"crawl_in":
			await _enter(_passage(MazeLayout.Clearance.CRAWL), PlayerController.Stance.CRAWL, "CRAWL")
		"crawl_out":
			var q := _passage(MazeLayout.Clearance.CRAWL)
			await _stance(PlayerController.Stance.CRAWL)
			player().spawn_at(layout().cell_to_world(q.to), yaw_of(q.out))
			await wait(10)
			await _leave(q, PlayerController.Stance.CRAWL)
