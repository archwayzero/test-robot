## T019 scratch: short accurate-mode stills, each state held >= 16 frames, in the real game scene.
extends "res://tests/e2e/playthrough_stances.gd"

const HOLD := 20

func _spawn(kind: MazeLayout.Clearance, stance: PlayerController.Stance) -> void:
	var p := _passage(kind)
	var dir := Vector3(dir_offset(p.dir).x, 0, dir_offset(p.dir).y)
	player().spawn_at(layout().cell_to_world(p.to) - dir * 1.0, yaw_of(dir))
	player().restore_stance(stance)
	step("idle in low passage")
	await wait(HOLD)
	step("moving in low passage")
	hold_move(dir, 1.0)
	await wait(HOLD)
	release_move()


func play() -> void:
	var dir := Vector3(0, 0, -1).rotated(Vector3.UP, player().get_camera_yaw())
	step("idle")
	await wait(HOLD)
	step("walk")
	hold_move(dir, 0.5)
	await wait(HOLD)
	step("run")
	hold_move(dir, 1.0)
	await wait(HOLD)
	release_move()
	await _set_stance(PlayerController.Stance.CROUCH)
	step("crouch idle")
	await wait(HOLD)
	step("crouch walk")
	hold_move(dir, 1.0)
	await wait(HOLD)
	release_move()
	await _set_stance(PlayerController.Stance.CRAWL)
	step("crawl idle")
	await wait(HOLD)
	step("crawl")
	hold_move(dir, 1.0)
	await wait(HOLD)
	release_move()
	await _set_stance(PlayerController.Stance.STAND)
	step("fade 0.5 on the hero materials")
	var mesh := player().get_node("Visual/Hero/Armature/Skeleton3D/hero") as GeometryInstance3D
	mesh.transparency = 0.5
	await wait(HOLD)
	mesh.transparency = 0.0
	await _spawn(MazeLayout.Clearance.CROUCH, PlayerController.Stance.CROUCH)
	await _spawn(MazeLayout.Clearance.CRAWL, PlayerController.Stance.CRAWL)
	step("end")
