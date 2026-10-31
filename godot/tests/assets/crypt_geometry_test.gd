## T017 (qa): the assembled seed maze (crypt_assembly.gd), checks 3, 4, 6 and 7. Contract: docs/contracts/crypt-kit.md.
## Physics queries use the kit's real collision (layer 1) or a trimesh of the render meshes (Assembly.RENDER_LAYER).
## Assertions after an await live in plain _check_* helpers (TEST_PLAN). Self-tests build a broken 3x3 maze far away.
extends "res://tests/e2e/e2e_base.gd"

const Checks := preload("res://tests/assets/crypt_checks.gd")
const Assembly := preload("res://tests/assets/crypt_assembly.gd")
## A 3x3 stub layout, all edges open inside, closed boundary. For self-tests only.
const StubLayout := preload("res://tests/assets/crypt_stub_layout.gd")

const STUB_ORIGIN := Vector3(500, 0, 500)
const COLLISION := 1
const RENDER := Assembly.RENDER_LAYER
const TOL := 0.002

var world: Node3D
var asm: Assembly
var maze: MazeLayout
var pc: PlayerController
var _fan_result := {}


func before_all() -> void:
	super.before_all()
	timeout_frames = 4000
	maze = MazeFactory.create().make_layout()
	world = Node3D.new()
	add_child(world)
	asm = Assembly.new(maze, world)
	asm.with_render_trimesh = true
	asm.build()
	await _settle()


func after_all() -> void:
	world.queue_free()
	await super.after_all()


func after_each() -> void:
	if pc:
		pc.queue_free()
		pc = null
	await super.after_each()


func _settle() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	await wait_frames(1)


func _space() -> PhysicsDirectSpaceState3D:
	return get_tree().root.get_world_3d().direct_space_state


func layout() -> MazeLayout:
	return maze


func player() -> PlayerController:
	return pc


func _all_cells() -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in maze.size().y:
		for x in maze.size().x:
			out.append(Vector2i(x, y))
	return out


func _low_cells() -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for c in _all_cells():
		if maze.clearance(c) != MazeLayout.Clearance.FULL:
			out.append(c)
	return out


func _stub(configure: Callable) -> Array:
	var r := Node3D.new()
	r.position = STUB_ORIGIN
	add_child(r)
	var a := Assembly.new(StubLayout.new(), r)
	a.with_render_trimesh = true
	configure.call(a)
	a.build()
	return [r, a]


# --- check 3: contract geometry -------------------------------------------------------------------------------------

func test_collision_planes_all_cells() -> void:
	var measured := {}
	var problems := Checks.plane_problems(_space(), maze, Vector3.ZERO, _all_cells(), COLLISION, TOL, measured)
	print("T017 collision planes: ", measured)
	assert_eq(problems.size(), 0, str(problems.slice(0, 8)))
	assert_true(measured.has("ceiling_1.3") and measured.has("ceiling_0.75"), "both low ceilings measured")
	checkpoint("end")


func test_self_plane_check_can_fail() -> void:
	var s := _stub(func(_a: Assembly) -> void: pass)
	await _settle()
	_check_plane_self(s)
	s[0].queue_free()
	checkpoint("end")


func _check_plane_self(s: Array) -> void:
	var cells: Array[Vector2i] = [Vector2i(0, 0)]
	var m := {}
	assert_eq(Checks.plane_problems(_space(), s[1].layout, STUB_ORIGIN, cells, COLLISION, TOL, m).size(), 0, "stub is clean")
	var moved := Checks.plane_problems(_space(), s[1].layout, STUB_ORIGIN + Vector3(0.03, 0.03, 0.0), cells, COLLISION, TOL, m)
	assert_true(str(moved).contains("floor at"), "a 3 cm floor error is reported")
	assert_true(str(moved).contains("wall face"), "a 3 cm wall error is reported")


func test_crowns_collision_and_render() -> void:
	_check_crowns()
	checkpoint("end")


func _check_crowns() -> void:
	var cell := Vector2i(10, 10)
	var c := maze.cell_to_world(cell)
	var open_dir := -1
	for d: int in [0, 1, 2, 3]:
		var n := cell + Assembly.dir_offset(d as MazeLayout.Dir)
		if not maze.has_wall(cell, d as MazeLayout.Dir) and maze.clearance(n) == MazeLayout.Clearance.FULL:
			open_dir = d
	assert_true(open_dir >= 0, "start cell has a FULL open edge")
	var e := asm.edge_centre(cell, open_dir as MazeLayout.Dir)
	var results := {}
	for mask: int in [COLLISION, RENDER]:
		var crown := Checks.ray_distance(_space(), c + Vector3(0, 1, 0), c + Vector3(0, 8, 0), mask) + 1.0
		var soffit := Checks.ray_distance(_space(), e + Vector3(0, 1, 0), e + Vector3(0, 8, 0), mask) + 1.0
		results[mask] = [crown, soffit]
	print("T017 crowns: collision vault %.3f arch %.3f; render vault %.3f arch %.3f" % [results[COLLISION][0],
			results[COLLISION][1], results[RENDER][0], results[RENDER][1]])
	assert_almost_eq(results[COLLISION][0], 4.15, 0.02, "vault crown, collision")
	assert_almost_eq(results[COLLISION][1], 3.9, 0.02, "arch soffit crown, collision")
	assert_almost_eq(results[RENDER][0], 4.15, 0.02, "vault crown, render")
	assert_almost_eq(results[RENDER][1], 3.9, 0.02, "arch soffit crown, render")
	assert_true(results[RENDER][0] - results[RENDER][1] > 0.2, "arch ring stands proud of the webs")


## The arch's collision against the room, with the query a spring arm makes: a sphere rising under the crown.
## Radius 0.15 = the camera probe size. Measured against the arch at the start cell's open edge.
func test_arch_soffit_stops_a_camera_probe() -> void:
	_check_probe()
	checkpoint("end")


func _open_edge_of_start() -> Vector3:
	for d: int in [0, 1, 2, 3]:
		var cell := maze.start_cell()
		if not maze.has_wall(cell, d as MazeLayout.Dir) and maze.clearance(cell + Assembly.dir_offset(d as MazeLayout.Dir)) == MazeLayout.Clearance.FULL:
			return asm.edge_centre(cell, d as MazeLayout.Dir)
	return Vector3.ZERO


func _check_probe() -> void:
	var e := _open_edge_of_start()
	var start := e + Vector3(0, 2.5, 0)
	var top := e + Vector3(0, 4.5, 0)
	var travel := Checks.sphere_travel(_space(), start, top, 0.15)
	var reached_y := 2.5 + travel
	var render_travel := Checks.sphere_travel(_space(), start, top, 0.15, RENDER)
	print("T017 sphere r=0.15 under arch crown: stops at y=%.3f on collision, y=%.3f on the render mesh" % [reached_y, 2.5 + render_travel])
	assert_true(reached_y + 0.15 <= 3.95, "camera probe must stop at the 3.9 soffit, its top reached %.3f" % [reached_y + 0.15])


## Defect (a), does it reach a player? The camera's arm is a sphere cast, not a ray (SpringArm3D + player.gd probe radius
## 0.15). Fan from arm pivots under one arch, over the whole orbit pitch range. A sphere must not end in the arch masonry.
## The ray count is printed only: it is what a ray-based consumer would do on the reversed soffit.
func test_camera_arm_fan_stays_out_of_arch_masonry() -> void:
	_check_arm_fan()
	checkpoint("end")


func _arch_at_open_edge() -> Dictionary:
	var e := _open_edge_of_start()
	for inst: Dictionary in asm.instances:
		if inst.piece == "arch" and (inst.at as Vector3).distance_to(e) < 0.01:
			return inst
	return {}


## True if a world point is inside the render masonry of this arch instance: in its 0.6 m depth, beyond the r=1.7 soffit.
func _in_arch_masonry(arch: Dictionary, world: Vector3) -> bool:
	var p := Transform3D(Basis(Vector3.UP, arch.yaw), arch.at).affine_inverse() * world
	var above := p.y - 2.2
	return absf(p.z) <= 0.3 and above >= 0.0 and p.y <= 4.15 and absf(p.x) <= 2.0 and Vector2(p.x, above).length() > 1.7


func _check_arm_fan() -> void:
	var arch := _arch_at_open_edge()
	assert_false(arch.is_empty(), "arch at the start cell's open edge")
	var arch_x := Basis(Vector3.UP, arch.yaw) * Vector3.RIGHT
	var arch_z := Basis(Vector3.UP, arch.yaw) * Vector3.BACK
	var s := _space()
	var arm := 2.5
	var counts := {"casts": 0, "sphere_in_masonry": 0, "ray_in_masonry": 0, "ray_past_soffit": 0}
	var worst := INF
	for lateral: float in [-1.3, -0.65, 0.0, 0.65, 1.3]:
		for through: float in [-0.8, 0.0, 0.8]:
			var pivot: Vector3 = arch.at + arch_x * lateral + arch_z * through + Vector3(0, 1.575, 0)
			for pitch: float in [0.35, 0.8, 1.2]:
				for k in 16:
					var yaw := TAU * k / 16.0
					var dir := Basis(Vector3.UP, yaw) * Vector3(0, sin(pitch), cos(pitch))
					var travel := Checks.sphere_travel(s, pivot, pivot + dir * arm, 0.15)
					var end := pivot + dir * travel
					counts.casts += 1
					if _in_arch_masonry(arch, end):
						counts.sphere_in_masonry += 1
					var p := Transform3D(Basis(Vector3.UP, arch.yaw), arch.at).affine_inverse() * end
					if absf(p.z) <= 0.3 and p.y > 2.2:
						worst = minf(worst, 1.7 - Vector2(p.x, p.y - 2.2).length())
					var ray_d := Checks.ray_distance(s, pivot, pivot + dir * arm, COLLISION)
					var render_d := Checks.ray_distance(s, pivot, pivot + dir * arm, RENDER)
					var ray_end := pivot + dir * minf(ray_d, arm)
					if _in_arch_masonry(arch, ray_end):
						counts.ray_in_masonry += 1
					if ray_d > render_d + 0.05:
						counts.ray_past_soffit += 1
	print("T017 arm fan under arch: %s; sphere centre closest to the soffit %.3f m" % [counts, worst])
	assert_eq(counts.sphere_in_masonry, 0, "camera probe ends inside the arch masonry")


func test_self_masonry_check_can_fail() -> void:
	var arch := {"yaw": 0.0, "at": Vector3(100, 0, 100)}
	assert_true(_in_arch_masonry(arch, Vector3(100, 4.0, 100)), "above the crown is masonry")
	assert_false(_in_arch_masonry(arch, Vector3(100, 3.8, 100)), "below the crown is the opening")
	assert_false(_in_arch_masonry(arch, Vector3(100, 4.0, 100.4)), "outside the depth is not masonry")
	checkpoint("end")


## Real spring arm: the real player stands under the arch at 8 yaws, default pitch.
func test_real_player_camera_under_arch() -> void:
	var arch := _arch_at_open_edge()
	var arch_x := Basis(Vector3.UP, arch.yaw) * Vector3.RIGHT
	pc = PlayerFactory.create_player()
	add_child(pc)
	var inside := 0
	var samples := 0
	var top := 0.0
	for lateral: float in [-1.3, 0.0, 1.3]:
		for k in 8:
			pc.spawn_at(arch.at + arch_x * lateral, TAU * k / 8.0)
			await automation().advance_frames(3)
			var cam := pc.get_camera().global_position
			samples += 1
			top = maxf(top, cam.y)
			if _in_arch_masonry(arch, cam):
				inside += 1
	_check_real_camera(samples, inside, top)
	checkpoint("end")


func _check_real_camera(samples: int, inside: int, top: float) -> void:
	print("T017 real camera under arch: %d samples, %d in masonry, highest camera %.3f" % [samples, inside, top])
	assert_eq(samples, 24, "every sample ran")
	assert_eq(inside, 0, "real camera inside arch masonry")


## Real jump under the arch near its leg, where the soffit is lowest: can the capsule reach the soffit at all?
func test_real_jump_under_arch_leg() -> void:
	var arch := _arch_at_open_edge()
	var arch_x := Basis(Vector3.UP, arch.yaw) * Vector3.RIGHT
	pc = PlayerFactory.create_player()
	add_child(pc)
	var lateral := 1.3
	pc.spawn_at(arch.at + arch_x * lateral, 0.0)
	await automation().advance_frames(5)
	var ground := pc.global_position.y
	await tap(GameActions.JUMP)
	var apex := ground
	for i in 50:
		await automation().advance_frames(1)
		apex = maxf(apex, pc.global_position.y)
	_check_jump(apex - ground, pc.get_collision_height(), lateral)
	checkpoint("end")


func _check_jump(rise: float, height: float, lateral: float) -> void:
	var soffit := 2.2 + sqrt(1.7 * 1.7 - lateral * lateral)
	print("T017 jump at lateral %.2f: rise %.3f, capsule top %.3f, soffit there %.3f" % [lateral, rise, height + rise, soffit])
	assert_true(rise > 0.3, "the jump happened")
	assert_true(height + rise < soffit, "capsule top stays below the soffit")


## Winding of the shipped colonly shapes that face the room. arch: soffit faces (between the pier faces, below y 3.95) must
## face the opening's axis. A one-sided trimesh ignores back faces for rays, so a reversed soffit is not there for them.
func test_arch_collision_winding() -> void:
	var kit: Node = (load(Checks.KIT_PATH) as PackedScene).instantiate()
	var faces := ((kit.get_node("arch").find_children("*", "CollisionShape3D", true, false)[0] as CollisionShape3D).shape
			as ConcavePolygonShape3D).get_faces()
	kit.free()
	var r := Checks.faces_pointing_with(faces, Callable(self, "_soffit_outward"))
	print("T017 arch collision soffit faces: facing the opening %d, facing the masonry %d" % [r.good, r.bad])
	assert_true(r.good + r.bad > 0, "arch collision has soffit faces")
	assert_eq(r.bad, 0, "arch collision soffit faces wound into the masonry")
	checkpoint("end")


func _soffit_outward(m: Vector3) -> Vector3:
	var radial := Vector3(m.x, m.y - 2.2, 0.0)
	if absf(m.z) > 0.29 or radial.length() > 1.75 or m.y < 2.21:
		return Vector3.ZERO
	return -radial.normalized()


func test_self_winding_check_can_fail() -> void:
	var good := PackedVector3Array([Vector3(0, 3.0, 0.1), Vector3(0.1, 3.0, -0.1), Vector3(-0.1, 3.0, -0.1)])
	var n := (good[2] - good[0]).cross(good[1] - good[0])
	if n.y > 0.0:
		good = PackedVector3Array([good[0], good[2], good[1]])
	var reversed := PackedVector3Array([good[0], good[2], good[1]])
	var f := Callable(self, "_soffit_outward")
	assert_eq(Checks.faces_pointing_with(good, f), {"good": 1, "bad": 0}, "down-facing soffit triangle is good")
	assert_eq(Checks.faces_pointing_with(reversed, f), {"good": 0, "bad": 1}, "reversed triangle is reported")
	checkpoint("end")


## Collision shape sizes as the real player reports them, stance by stance. Radius 0.3: player/CLAUDE.md, cross-checked
## against the live CollisionShape3D.
func _player_sizes() -> Dictionary:
	var shape := (pc.find_children("*", "CollisionShape3D", false, false)[0] as CollisionShape3D).shape as CapsuleShape3D
	return {"radius": shape.radius, "stand": pc.get_collision_height()}


func test_capsules_against_low_cells_and_arches() -> void:
	pc = PlayerFactory.create_player()
	add_child(pc)
	pc.spawn_at(maze.cell_to_world(maze.start_cell()), 0.0)
	await automation().advance_frames(2)
	var sizes := _player_sizes()
	await tap(GameActions.STANCE_CYCLE)
	sizes.crouch = pc.get_collision_height()
	await tap(GameActions.STANCE_CYCLE)
	sizes.crawl = pc.get_collision_height()
	pc.queue_free()
	pc = null
	await _settle()
	_check_capsules(sizes)
	checkpoint("end")


func _check_capsules(sz: Dictionary) -> void:
	print("T017 player sizes from PlayerController: ", sz)
	assert_almost_eq(sz.radius, 0.3, 0.001, "player radius as documented")
	assert_true(sz.stand > sz.crouch and sz.crouch > sz.crawl, "stance heights ordered")
	var s := _space()
	var seen := {"crouch": 0, "crawl": 0}
	for cell in _low_cells():
		var crouch_cell := maze.clearance(cell) == MazeLayout.Clearance.CROUCH
		seen["crouch" if crouch_cell else "crawl"] += 1
		var c := maze.cell_to_world(cell)
		for ox: float in [-1.3, 0.0, 1.3]:
			for oz: float in [-1.3, 0.0, 1.3]:
				var p := c + Vector3(ox, 0, oz)
				if crouch_cell:
					assert_true(Checks.capsule_blocked(s, p, sz.stand, sz.radius), "CROUCH cell %s must block a standing capsule at %s" % [cell, p])
					assert_false(Checks.capsule_blocked(s, p, sz.crouch, sz.radius), "CROUCH cell %s must admit a crouching capsule at %s" % [cell, p])
				else:
					assert_true(Checks.capsule_blocked(s, p, sz.crouch, sz.radius), "CRAWL cell %s must block a crouching capsule at %s" % [cell, p])
					assert_false(Checks.capsule_blocked(s, p, sz.crawl, sz.radius), "CRAWL cell %s must admit a crawling capsule at %s" % [cell, p])
	assert_eq(seen, {"crouch": 2, "crawl": 4}, "low cells of the seed")
	# Full stand under every arch between FULL cells, across the clear span between the pier faces.
	var arches := 0
	var min_clear := INF
	for cell in _all_cells():
		for d: int in [1, 2]:
			var n := cell + Assembly.dir_offset(d as MazeLayout.Dir)
			if maze.has_wall(cell, d as MazeLayout.Dir) or not maze.in_bounds(n):
				continue
			if maze.clearance(cell) != MazeLayout.Clearance.FULL or maze.clearance(n) != MazeLayout.Clearance.FULL:
				continue
			arches += 1
			var e := asm.edge_centre(cell, d as MazeLayout.Dir)
			var side := Vector3(Checks.dir_z(d), 0, Checks.dir_x(d))
			for off: float in [-1.35, -0.7, 0.0, 0.7, 1.35]:
				var p := e + side * off
				assert_false(Checks.capsule_blocked(s, p, sz.stand, sz.radius), "arch at %s must admit a standing capsule at offset %.2f" % [e, off])
				min_clear = minf(min_clear, Checks.ray_distance(s, p + Vector3(0, 0.1, 0), p + Vector3(0, 6, 0), COLLISION) + 0.1)
	print("T017 FULL-FULL arches %d, min free height at +-1.35 m %.3f" % [arches, min_clear])
	assert_true(min_clear >= 2.2, "free height under arches >= 2.2")


func test_real_player_is_refused_in_crouch_cell() -> void:
	expect_checkpoint("crouch_refused")
	pc = PlayerFactory.create_player()
	add_child(pc)
	var entry := maze.cell_to_world(Vector2i(1, 6)) + Vector3(0, 0, 1.5)
	pc.spawn_at(entry, 0.0)
	await automation().advance_frames(3)
	await tap(GameActions.STANCE_CYCLE)
	var ok := await walk_to(maze.cell_to_world(Vector2i(1, 7)), 1.0, 300)
	await automation().advance_frames(3)
	var seen: Array[int] = [pc.get_stance()]
	await tap(GameActions.STANCE_CYCLE)  # crouch -> crawl
	seen.append(pc.get_stance())
	await tap(GameActions.STANCE_CYCLE)  # crawl -> stand refused -> crouch
	seen.append(pc.get_stance())
	var y_inside := pc.global_position.y
	_check_crouch_refused(ok, seen, y_inside)
	# Control in the FULL cell behind: the same taps DO reach STAND, so the refusal comes from the kit ceiling.
	pc.spawn_at(maze.cell_to_world(Vector2i(1, 6)), 0.0)
	await automation().advance_frames(3)
	await tap(GameActions.STANCE_CYCLE)  # crouch -> crawl
	await tap(GameActions.STANCE_CYCLE)  # crawl -> stand
	_check_stand_control(pc.get_stance())
	checkpoint("end")


func _check_crouch_refused(walked: bool, seen: Array[int], y: float) -> void:
	assert_true(walked, "crouched player walks through the arch into the CROUCH cell")
	assert_eq(seen[0], PlayerController.Stance.CROUCH, "still crouching inside")
	assert_eq(seen[1], PlayerController.Stance.CRAWL, "crawl possible")
	assert_eq(seen[2], PlayerController.Stance.CROUCH, "stand refused, cycle skips to crouch")
	assert_almost_eq(y, 0.0, 0.05, "player stands on the kit floor")
	checkpoint("crouch_refused")


func _check_stand_control(stance: int) -> void:
	assert_eq(stance, PlayerController.Stance.STAND, "control: stance cycle reaches STAND in a FULL cell")


func test_real_player_is_refused_in_crawl_cell() -> void:
	expect_checkpoint("crawl_refused")
	pc = PlayerFactory.create_player()
	add_child(pc)
	var entry := maze.cell_to_world(Vector2i(8, 7)) + Vector3(1.5, 0, 0)
	pc.spawn_at(entry, 0.0)
	await automation().advance_frames(3)
	await tap(GameActions.STANCE_CYCLE)
	await tap(GameActions.STANCE_CYCLE)
	var ok := await walk_to(maze.cell_to_world(Vector2i(9, 7)), 1.0, 500)
	await automation().advance_frames(3)
	var before := pc.get_stance()
	await tap(GameActions.STANCE_CYCLE)
	await tap(GameActions.STANCE_CYCLE)
	_check_crawl_refused(ok, before, pc.get_stance())
	checkpoint("end")


func _check_crawl_refused(walked: bool, before: int, after: int) -> void:
	assert_true(walked, "crawling player reaches the CRAWL cell centre")
	assert_eq(before, PlayerController.Stance.CRAWL, "crawling inside")
	assert_eq(after, PlayerController.Stance.CRAWL, "crouch and stand refused")
	checkpoint("crawl_refused")


func test_real_player_blocked_from_low_cells_when_too_tall() -> void:
	expect_checkpoint("too_tall")
	pc = PlayerFactory.create_player()
	add_child(pc)
	pc.spawn_at(maze.cell_to_world(Vector2i(1, 6)) + Vector3(0, 0, 1.0), 0.0)
	await automation().advance_frames(3)
	var reached := await walk_to(maze.cell_to_world(Vector2i(1, 7)), 0.5, 200)
	var z_standing := pc.global_position.z
	_check_too_tall(reached, z_standing)
	checkpoint("end")


func _check_too_tall(reached: bool, z: float) -> void:
	assert_false(reached, "a standing player does not reach the CROUCH cell centre")
	var edge_z := 7.0 * maze.cell_size_m()
	print("T017 standing player stopped at z=%.3f, CROUCH cell edge z=%.3f" % [z, edge_z])
	assert_true(z < edge_z, "standing player stays out of the CROUCH cell")
	checkpoint("too_tall")


# --- check 4: assembly ----------------------------------------------------------------------------------------------

func test_assembly_rules() -> void:
	var problems := Checks.rule_problems(asm)
	print("T017 assembly counts ", asm.counts, " materials ", asm.all_materials().size(), " lamps ", asm.lamps.size())
	assert_eq(problems.size(), 0, str(problems.slice(0, 8)))
	assert_eq(asm.counts.pier, 441, "pier on every corner")
	assert_eq(asm.counts.floor, 400, "one floor per cell")
	assert_eq(asm.counts.vault_bay + asm.counts.ceiling_crouch + asm.counts.ceiling_crawl, 400, "one ceiling per cell")
	assert_eq(asm.counts.wall + asm.counts.arch, 840, "every edge of a 20x20 grid holds a wall or an arch")
	for m: StandardMaterial3D in asm.all_materials():
		assert_true(m.vertex_color_use_as_albedo, "vertex colour on")
		assert_eq(m.texture_filter, BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC, "anisotropic filter")
	checkpoint("end")


func test_self_rule_check_can_fail() -> void:
	var r := _stub(func(a: Assembly) -> void:
		a.break_skip_arch_at = Vector2i(1, 1)
		a.break_skip_pier_at = Vector2i(1, 1))
	var problems := str(Checks.rule_problems(r[1]))
	r[0].queue_free()
	assert_true(problems.contains("missing arch"), problems)
	assert_true(problems.contains("no pier"), problems)
	checkpoint("end")


func _fan_eyes(cell: Vector2i, origin := Vector3.ZERO) -> PackedVector3Array:
	var c := maze.cell_to_world(cell) + origin
	var heights: Array[float] = [0.3, 2.43, 3.5]
	if maze.clearance(cell) == MazeLayout.Clearance.CROUCH:
		heights = [0.3, 1.0]
	elif maze.clearance(cell) == MazeLayout.Clearance.CRAWL:
		heights = [0.3, 0.6]
	var out := PackedVector3Array()
	for y in heights:
		for off: Vector3 in [Vector3.ZERO, Vector3(1.3, 0, 1.3), Vector3(-1.3, 0, 1.3), Vector3(1.3, 0, -1.3), Vector3(-1.3, 0, -1.3)]:
			out.append(c + off + Vector3(0, y, 0))
	return out


## Fan from every cell: `escaped` = the ray left the maze. Results kept for the backface test below.
func test_no_holes_every_cell() -> void:
	_check_no_holes()
	checkpoint("end")


func _fan() -> Dictionary:
	if _fan_result.is_empty():
		var eyes := PackedVector3Array()
		for cell in _all_cells():
			eyes.append_array(_fan_eyes(cell))
		_fan_result = Checks.see_through(_space(), eyes, Checks.sphere_dirs(96), RENDER)
	return _fan_result


func _check_no_holes() -> void:
	var r := _fan()
	print("T017 no-holes fan: rays=%d escaped=%d" % [r.rays, r.escaped.size()])
	assert_eq(r.escaped.size(), 0, "rays leaving the maze: %s" % [r.escaped.slice(0, 6)])


## A first hit on a back face is a gap the player sees through (back faces are culled).
func test_no_first_hit_backfaces_in_rooms() -> void:
	_check_room_backfaces()
	checkpoint("end")


func _check_room_backfaces() -> void:
	var r := _fan()
	var c := Checks.classify_hits(r.backface_first)
	print("T017 room fan first-hit back faces: %d of %d rays, by piece %s, seen through to %s, local points %s" % [r.backface_first.size(),
			r.rays, c.by_piece, c.behind, c.points.keys().slice(0, 12)])
	assert_eq(r.backface_first.size(), 0, "first hit is a back face: %s" % [c.by_piece])


func test_pier_capital_has_a_top_face() -> void:
	var kit: Node = (load(Checks.KIT_PATH) as PackedScene).instantiate()
	var top := Checks.up_faces_at((kit.get_node("pier") as MeshInstance3D).mesh, 2.2)
	kit.free()
	print("T017 pier top triangles at y 2.2: %d" % top)
	assert_true(top > 0, "pier mesh has a top face at 2.2 m (overhang 0.075 m past the wall and arch at camera height 2.43)")
	checkpoint("end")


func test_self_top_face_check() -> void:
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	assert_eq(Checks.up_faces_at(box, 0.5), 2, "a box has 2 top triangles (also proves the winding convention)")
	assert_eq(Checks.up_faces_at(box, 0.2), 0, "none at another height")
	var open := Checks.with_flipped_triangles(box, func(c: Vector3) -> bool: return c.y > 0.49)
	assert_eq(Checks.up_faces_at(open, 0.5), 0, "reversed top is not a top")
	checkpoint("end")


func test_self_hole_check_can_fail() -> void:
	var r := _stub(func(a: Assembly) -> void: a.break_skip_arch_at = Vector2i(1, 1))
	await _settle()
	var eyes := PackedVector3Array([STUB_ORIGIN + Vector3(6, 2.43, 6)])
	_check_hole_self(eyes)
	r[0].queue_free()
	checkpoint("end")


func _check_hole_self(eyes: PackedVector3Array) -> void:
	var res := Checks.see_through(_space(), eyes, Checks.sphere_dirs(400), RENDER)
	print("T017 self hole: missing arches -> escaped %d of %d rays" % [res.escaped.size(), res.rays])
	assert_true(res.escaped.size() > 0, "a missing arch must let rays escape")


func test_lamps_on_the_wall_face_and_not_in_a_wall() -> void:
	_check_lamps()
	checkpoint("end")


func _check_lamps() -> void:
	assert_eq(asm.lamps.size(), maze.lamp_slots().size(), "one lamp per slot")
	var problems: Array[String] = []
	for entry in asm.lamps:
		var centre := maze.cell_to_world(entry.slot.cell)
		problems.append_array(Checks.lamp_problems(_space(), entry, COLLISION, centre))
		problems.append_array(Checks.lamp_problems(_space(), entry, RENDER, centre))
	print("T017 lamps checked %d, problems %d" % [asm.lamps.size(), problems.size()])
	assert_eq(problems.size(), 0, str(problems.slice(0, 8)))


func test_self_lamp_check_can_fail() -> void:
	var pushed := _stub(func(a: Assembly) -> void: a.break_lamp_depth = 0.5)
	var flipped := _stub(func(a: Assembly) -> void: a.break_lamp_flip = true)
	flipped[0].position += Vector3(40, 0, 0)
	await _settle()
	_check_lamp_self(pushed[1], STUB_ORIGIN, "behind a surface")
	_check_lamp_self(flipped[1], STUB_ORIGIN + Vector3(40, 0, 0), "local +Z")
	pushed[0].queue_free()
	flipped[0].queue_free()
	checkpoint("end")


func _check_lamp_self(a: Assembly, origin: Vector3, want: String) -> void:
	assert_true(a.lamps.size() > 0, "stub has lamps")
	var all := ""
	for entry in a.lamps:
		all += str(Checks.lamp_problems(_space(), entry, COLLISION, a.layout.cell_to_world(entry.slot.cell) + origin))
	assert_true(all.contains(want), "expected '%s' in %s" % [want, all.left(300)])


func test_lights_per_mesh() -> void:
	var worst := 0
	for i in asm.instances:
		worst = maxi(worst, Checks.lights_reaching(asm.lamps, i.aabb))
	var chunk_worst := 0
	for y in range(0, 20, 4):
		for x in range(0, 20, 4):
			var box := AABB(Vector3(x * 4.0, 0, y * 4.0), Vector3(16, 4.15, 16))
			chunk_worst = maxi(chunk_worst, Checks.lights_reaching(asm.lamps, box))
	print("T017 omni per mesh: worst single piece %d, worst 4x4-cell chunk %d (Mobile limit 8)" % [worst, chunk_worst])
	assert_true(worst <= 8, "per-piece omni count <= 8, got %d" % worst)
	checkpoint("end")


# --- check 6: rubble winding ----------------------------------------------------------------------------------------

func _room_eyes(cell: Vector2i, heights: Array[float]) -> PackedVector3Array:
	var c := maze.cell_to_world(cell)
	var out := PackedVector3Array()
	for y in heights:
		for ox: float in [-1.4, -0.7, 0.0, 0.7, 1.4]:
			for oz: float in [-1.4, -0.7, 0.0, 0.7, 1.4]:
				out.append(c + Vector3(ox, y, oz))
	return out


func _targets(cell: Vector2i, mesh_piece: String, kit: Node, only_visible_side := true) -> PackedVector3Array:
	var c := maze.cell_to_world(cell)
	var out := PackedVector3Array()
	for p in Checks.centroids((kit.get_node(mesh_piece) as MeshInstance3D).mesh):
		if only_visible_side:
			out.append(c + p)
	return out


func test_rubble_visible_underside_has_no_first_hit_backfaces() -> void:
	_check_rubble()
	checkpoint("end")


func _check_rubble() -> void:
	var kit: Node = (load(Checks.KIT_PATH) as PackedScene).instantiate()
	var room_hits: Array = []
	var neighbour_hits: Array = []
	var rays := {"room": 0, "neighbour": 0}
	var per_cell := {}
	for cell in _low_cells():
		var crouch := maze.clearance(cell) == MazeLayout.Clearance.CROUCH
		var piece := "ceiling_crouch" if crouch else "ceiling_crawl"
		var heights: Array[float] = [0.2, 0.65]
		if crouch:
			heights = [0.3, 1.2]
		var t := _targets(cell, piece, kit)
		var inside := Checks.backface_first_hits(_space(), _room_eyes(cell, heights), t, RENDER)
		room_hits.append_array(inside.hits)
		rays.room += inside.rays
		var out := 0
		for n in open_neighbours(cell):  # FULL neighbours, through the mixed-clearance arch
			if maze.clearance(n) != MazeLayout.Clearance.FULL:
				continue
			var from_n := Checks.backface_first_hits(_space(), _room_eyes(n, [0.5, 2.43]), t, RENDER)
			neighbour_hits.append_array(from_n.hits)
			rays.neighbour += from_n.rays
			out += from_n.hits.size()
		per_cell["%s %s" % [cell, piece]] = [inside.hits.size(), out]
	kit.free()
	var c_room := Checks.classify_hits(room_hits)
	var c_n := Checks.classify_hits(neighbour_hits)
	print("T017 rubble first-hit back faces [room, neighbours] per cell: ", per_cell)
	print("T017 rubble room: %d/%d rays %s behind %s points %s" % [room_hits.size(), rays.room, c_room.by_piece, c_room.behind, c_room.points.keys()])
	print("T017 rubble neighbour: %d/%d rays %s behind %s points %s" % [neighbour_hits.size(), rays.neighbour, c_n.by_piece, c_n.behind, c_n.points.keys()])
	assert_eq(room_hits.size(), 0, "first-hit back faces from inside low rooms: %s" % [c_room.by_piece])
	assert_eq(neighbour_hits.size(), 0, "first-hit back faces from FULL neighbours: %s" % [c_n.by_piece])


func test_self_rubble_check_can_fail() -> void:
	# The same helper on a copy of ceiling_crouch with the underside (centre of the room) reversed.
	var kit: Node = (load(Checks.KIT_PATH) as PackedScene).instantiate()
	var src := (kit.get_node("ceiling_crouch") as MeshInstance3D).mesh
	var broken := Checks.with_flipped_triangles(src, func(c: Vector3) -> bool: return c.y < 1.6 and Vector2(c.x, c.z).length() < 1.0)
	var mi := MeshInstance3D.new()
	mi.mesh = broken
	mi.position = STUB_ORIGIN
	var body := StaticBody3D.new()
	body.collision_layer = RENDER
	var shape := CollisionShape3D.new()
	shape.shape = Assembly.render_trimesh(broken)
	body.add_child(shape)
	mi.add_child(body)
	add_child(mi)
	await _settle()
	_check_rubble_self(broken, kit)
	mi.queue_free()
	checkpoint("end")


func _check_rubble_self(broken: Mesh, kit: Node) -> void:
	kit.free()
	var targets := PackedVector3Array()
	for p in Checks.centroids(broken):
		targets.append(p + STUB_ORIGIN)
	var r := Checks.backface_first_hits(_space(), PackedVector3Array([STUB_ORIGIN + Vector3(0, 0.3, 0)]), targets, RENDER)
	print("T017 self rubble: %d first-hit back faces on the broken mesh" % r.hits.size())
	assert_true(r.hits.size() > 0, "reversed underside must be reported")


# --- check 7: counts ------------------------------------------------------------------------------------------------

func test_full_maze_triangles_and_view_estimates() -> void:
	var cam := Camera3D.new()
	cam.fov = 70.0
	cam.near = 0.05
	cam.far = 4000.0
	add_child(cam)
	await _settle()
	_check_counts(cam)
	cam.queue_free()
	checkpoint("end")


## One view: triangles of instances in the frustum (no occlusion), and of instances a 2x1 degree-ish ray grid actually
## hits (first surface per ray, a lower bound of what occlusion culling leaves). LOD0 counts. An estimate, not a frame.
func _view_counts(cam: Camera3D, eye: Vector3, look: Vector3, far: float) -> Dictionary:
	cam.global_position = eye
	cam.look_at(look)
	cam.force_update_transform()
	var frustum: Array[Plane] = cam.get_frustum()
	var tris := 0
	var count := 0
	for i in asm.instances:
		var box: AABB = i.aabb
		if box.get_center().distance_to(eye) - box.size.length() * 0.5 > far:
			continue
		var outside := false
		for pl in frustum:
			var all_out := true
			for k in 8:
				if not pl.is_point_over(box.get_endpoint(k)):
					all_out = false
					break
			if all_out:
				outside = true
				break
		if not outside:
			tris += int(i.tris)
			count += 1
	var seen := {}
	var size := get_viewport().get_visible_rect().size
	for gy in 60:
		for gx in 128:
			var uv := Vector2((gx + 0.5) / 128.0, (gy + 0.5) / 60.0) * size
			var from := cam.project_ray_origin(uv)
			var hit := Checks.ray(_space(), from, from + cam.project_ray_normal(uv) * minf(far, 200.0), RENDER, false)
			if not hit.is_empty():
				seen[hit.collider.get_parent()] = true
	var seen_tris := 0
	for m: MeshInstance3D in seen:
		seen_tris += Assembly.triangle_count(m.mesh)
	return {"frustum_instances": count, "frustum_tris": tris, "seen_instances": seen.size(), "seen_tris": seen_tris}


func _check_counts(cam: Camera3D) -> void:
	var by_piece := {}
	var total := 0
	for i in asm.instances:
		by_piece[i.piece] = int(by_piece.get(i.piece, 0)) + int(i.tris)
		total += int(i.tris)
	var lamp_scene: Node = (load(Checks.LAMP_PATH) as PackedScene).instantiate()
	var lamp_tris := 0
	for m in lamp_scene.find_children("*", "MeshInstance3D", true, false):
		lamp_tris += Assembly.triangle_count((m as MeshInstance3D).mesh)
	lamp_scene.free()
	print("T017 full maze seed %d: kit %d tris %s; lamps %d x %d = %d; total %d" % [maze.get_seed(), total, by_piece,
			asm.lamps.size(), lamp_tris, asm.lamps.size() * lamp_tris, total + asm.lamps.size() * lamp_tris])
	assert_true(total > 700000, "sum sanity")
	var run := _corridor()
	var c0 := maze.cell_to_world(run.cell)
	var v := Assembly.dir_vector(run.dir)
	var side := Vector3(v.z, 0, v.x)
	var views := {
		"corridor_centre": [c0 - v * 1.0 + Vector3(0, 2.43, 0), c0 + v * 4.0 + Vector3(0, 0.9, 0)],
		"corridor_wall_hug": [c0 - v * 1.0 + side * 1.3 + Vector3(0, 2.43, 0), c0 + v * 4.0 + side * 1.3 + Vector3(0, 0.9, 0)],
	}
	var junction := _junction()
	var open_d := Vector3.ZERO
	for d: int in [0, 1, 2, 3]:
		if not maze.has_wall(junction, d as MazeLayout.Dir):
			open_d = Assembly.dir_vector(d as MazeLayout.Dir)
	var j := maze.cell_to_world(junction)
	views["junction_3way"] = [j - open_d * 1.0 + Vector3(0, 2.43, 0), j + open_d * 4.0 + Vector3(0, 0.9, 0)]
	for name: String in views:
		for far: float in [4000.0, 26.0]:
			print("T017 view %s far %.0f (corridor %s dir %d len %d): %s" % [name, far, run.cell, run.dir, run.length,
					_view_counts(cam, views[name][0], views[name][1], far)])


func _junction() -> Vector2i:
	for c in _all_cells():
		if open_neighbours(c).size() == 3 and maze.clearance(c) == MazeLayout.Clearance.FULL:
			return c
	return maze.start_cell()


## Longest straight FULL run in the layout (same definition as e2e_base.longest_corridor()).
func _corridor() -> Dictionary:
	return longest_corridor()
