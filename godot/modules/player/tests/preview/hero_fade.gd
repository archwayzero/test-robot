## T019 scratch: transparency on the hero mesh, held, Mobile renderer.
extends "res://tests/e2e/playthrough_stances.gd"

func play() -> void:
	step("opaque")
	await wait(16)
	for t in [0.5, 0.9]:
		step("fade %.1f" % t)
		for i in 20:
			player().call("_apply_fade", t)
			await wait(1)
	step("end")
	await wait(4)
