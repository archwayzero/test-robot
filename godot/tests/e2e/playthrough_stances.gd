## Gameplay video stances.mp4 (TEST_PLAN.md "Gameplay videos", M1): stand/crouch/crawl cycle, jump standing,
## jump refused while crawling, a CROUCH passage (standing refused inside) and a CRAWL passage (rising refused
## inside). The player is teleported (PlayerController.spawn_at) in front of each passage; captions mark the cuts.
## Owner: qa. Recorded with tools/qa/record.py (see playthrough_base.gd).
extends "res://tests/e2e/playthrough_base.gd"


const STANCE_NAMES := ["STAND", "CROUCH", "CRAWL"]


## {"from": FULL entry cell, "to": low cell, "exit": FULL cell on the far side or the entry}, or {}.
func _passage(kind: MazeLayout.Clearance) -> Dictionary:
	var fallback := {}
	for y in layout().size().y:
		for x in layout().size().x:
			var c := Vector2i(x, y)
			if layout().clearance(c) != kind:
				continue
			for d in DIRS:
				var from := c - dir_offset(d)
				var exit := c + dir_offset(d)
				if layout().has_wall(from, d) or not layout().in_bounds(from) \
						or layout().clearance(from) != MazeLayout.Clearance.FULL:
					continue
				if not layout().has_wall(c, d) and layout().in_bounds(exit) \
						and layout().clearance(exit) == MazeLayout.Clearance.FULL:
					return {"from": from, "to": c, "exit": exit, "dir": d}
				if fallback.is_empty():
					fallback = {"from": from, "to": c, "exit": from, "dir": d}
	return fallback


func _stance_tap(label: String) -> void:
	await tap(GameActions.STANCE_CYCLE)
	step("%s -> %s (height %.2f m)" % [label, STANCE_NAMES[player().get_stance()], player().get_collision_height()])


func _set_stance(target: PlayerController.Stance) -> void:
	for i in 3:
		if player().get_stance() == target:
			return
		await tap(GameActions.STANCE_CYCLE)


func _open_dir_yaw(cell: Vector2i) -> float:
	for d in DIRS:
		if not layout().has_wall(cell, d):
			return yaw_of(Vector3(dir_offset(d).x, 0, dir_offset(d).y))
	return 0.0


func _go_through(kind: MazeLayout.Clearance, stance: PlayerController.Stance, name_: String) -> void:
	var p := _passage(kind)
	if p.is_empty():
		step("no %s passage in the layout" % name_)
		return
	var dir := Vector3(dir_offset(p.dir).x, 0, dir_offset(p.dir).y)
	await _set_stance(PlayerController.Stance.STAND)
	player().spawn_at(layout().cell_to_world(p.from) - dir * 0.8, yaw_of(dir))
	step("cut: in front of the %s passage at %s (standing)" % [name_, p.to])
	await wait_s(1.5)
	step("try to walk in standing")
	await walk_to(layout().cell_to_world(p.to), 0.5, 75)
	release_move()
	await wait_s(0.5)
	await _set_stance(stance)
	step("%s, go in" % STANCE_NAMES[stance])
	await walk_to(layout().cell_to_world(p.to), 1.0, 600)
	release_move()
	release_orbit()
	await wait_s(0.5)
	step("inside %s cell %s: try to rise" % [name_, p.to])
	await wait_s(0.5)
	await _stance_tap("stance tap 1")
	await wait_s(1.2)
	await _stance_tap("stance tap 2")
	await wait_s(1.2)
	if player().get_stance() != stance:
		await _set_stance(stance)
	step("leave the passage")
	await walk_to(layout().cell_to_world(p.exit), 1.0, 600)
	release_move()
	release_orbit()
	await _set_stance(PlayerController.Stance.STAND)
	step("out: %s" % STANCE_NAMES[player().get_stance()])
	await wait_s(1.0)


func play() -> void:
	await wait_s(1.0)
	step("stance cycle in the start cell")
	await wait_s(0.5)
	for i in 3:
		await _stance_tap("stance tap")
		await wait_s(1.3)
	step("jump (standing)")
	await tap(GameActions.JUMP)
	await wait_s(1.3)
	var yaw := _open_dir_yaw(layout().start_cell())
	await turn_camera_to(yaw)
	step("jump while walking")
	var dir := Vector3(0, 0, -1).rotated(Vector3.UP, yaw)
	for i in 30:
		hold_move(dir, 0.5)
		if i == 8:
			Input.action_press(GameActions.JUMP)
		if i == 11:
			Input.action_release(GameActions.JUMP)
		await wait(1)
	release_move()
	await wait_s(0.5)
	await _set_stance(PlayerController.Stance.CRAWL)
	step("crawl, press jump (must be refused)")
	await tap(GameActions.JUMP)
	await wait_s(1.5)
	await _go_through(MazeLayout.Clearance.CROUCH, PlayerController.Stance.CROUCH, "CROUCH")
	await _go_through(MazeLayout.Clearance.CRAWL, PlayerController.Stance.CRAWL, "CRAWL")
