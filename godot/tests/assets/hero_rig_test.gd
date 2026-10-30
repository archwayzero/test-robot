## T014 (qa): the hero rig as Godot imports it. Owner: qa.
## Contract: docs/contracts/blender-godot-assets.md "Asset: hero (run 1)"; clearances docs/contracts/crypt-kit.md;
## consumer: godot/modules/player/CLAUDE.md (T019 AnimationTree by exact clip names, JUMP_VELOCITY 4.0).
## Measurements use CPU skinning of the imported mesh (see hero_measure.gd); every test is synchronous (no await).
extends TestCase

const Measure := preload("res://tests/assets/hero_measure.gd")

const BONE_COUNT := 23
## clip -> [loop mode, length s]. Lengths as delivered in T013 (merged PR #41).
const CLIPS := {
	"idle_loop": [Animation.LOOP_LINEAR, 4.0],
	"walk_loop": [Animation.LOOP_LINEAR, 0.8],
	"jog_loop": [Animation.LOOP_LINEAR, 0.6],
	"crouch_idle_loop": [Animation.LOOP_LINEAR, 4.0],
	"crouch_walk_loop": [Animation.LOOP_LINEAR, 0.8],
	"crawl_idle_loop": [Animation.LOOP_LINEAR, 3.0],
	"crawl_loop": [Animation.LOOP_LINEAR, 1.2],
	"jump": [Animation.LOOP_NONE, 1.2667],
}
## Highest skinned point allowed per clip (m): stand <= 1.85 (hero height 1.65-1.85, FULL clearance 2.2),
## crouch <= 1.25 (CROUCH ceiling 1.3), crawl <= 0.70 (CRAWL ceiling 0.75). Jump: standing jump, the body rises
## physically on top of this, so the clip itself must stay within the standing limit.
const TOP_LIMIT := {
	"idle_loop": 1.85, "walk_loop": 1.85, "jog_loop": 1.85, "jump": 1.85,
	"crouch_idle_loop": 1.25, "crouch_walk_loop": 1.25,
	"crawl_idle_loop": 0.70, "crawl_loop": 0.70,
}
const MIN_Y := -0.01
## Loop seam: pose at `length` must equal the pose at 0 within 5 mm (max vertex distance).
const SEAM_TOL := 0.005
## Physics airtime of a jump: 2 * JUMP_VELOCITY / gravity = 2 * 4.0 / 9.8.
const AIRTIME := 2.0 * 4.0 / 9.8

var m: Measure


func before_all() -> void:
	m = Measure.new()
	var err := m.load_into(self)
	if err != "":
		fail(err)


func after_all() -> void:
	if m:
		m.free_all()


func test_import_structure() -> void:
	assert_not_null(m.skeleton, "Skeleton3D")
	assert_not_null(m.mesh_instance, "skinned MeshInstance3D")
	assert_not_null(m.player, "AnimationPlayer")
	if m.skeleton == null or m.mesh_instance == null or m.player == null:
		return
	assert_eq(m.skeleton.get_bone_count(), BONE_COUNT, "bone count")
	assert_not_null(m.mesh_instance.skin, "mesh has a Skin")
	assert_eq(m.mesh_instance.get_node_or_null(m.mesh_instance.skeleton), m.skeleton, "mesh bound to the skeleton")
	assert_true(m.bones.size() == m.verts.size() * m.stride and m.verts.size() > 0, "mesh has bone/weight arrays")
	assert_true(m.foot_verts.l.size() > 0 and m.foot_verts.r.size() > 0, "blade vertices weighted to both feet")
	var names := Array(m.player.get_animation_list())
	names.sort()
	var expected := CLIPS.keys()
	expected.sort()
	assert_eq(names, expected, "exactly the 8 contract clips")
	for clip: String in CLIPS:
		if not m.player.has_animation(clip):
			continue
		var a := m.player.get_animation(clip)
		assert_eq(a.loop_mode, CLIPS[clip][0], clip + " loop mode")
		assert_almost_eq(a.length, CLIPS[clip][1], 0.01, clip + " length")
	var rest := m.rest_aabb()
	print("HERO_QA rest_aabb pos=%s size=%s verts=%d stride=%d binds=%d foot_verts l=%d r=%d" % [rest.position,
			rest.size, m.verts.size(), m.stride, m.bind_bone.size(), m.foot_verts.l.size(), m.foot_verts.r.size()])
	assert_almost_eq(rest.end.y, 1.75, 0.02, "rest mesh head top at 1.75 m")
	assert_almost_eq(rest.position.y, 0.0, 0.01, "rest mesh feet at y = 0")


func test_clip_heights_floor_and_seams() -> void:
	if m.player == null:
		fail("no rig")
		return
	print("HERO_QA | clip | len s | frames | loop | top m (frame) | limit | min y (frame) | seam mm | wrap step mm | median step mm | max step mm | reach fwd/back/side m |")
	for clip: String in CLIPS:
		if not m.player.has_animation(clip):
			continue
		var r := m.measure_clip(clip)
		print("HERO_QA | %s | %.3f | %d | %s | %.3f (%d) | %.2f | %.4f (%d) | %.1f | %.1f | %.1f | %.1f | %.2f / %.2f / %.2f |" % [
			clip, r.length, r.frames, ["none", "linear", "pingpong"][r.loop], r.top, r.top_frame, TOP_LIMIT[clip],
			r.min_y, r.min_frame, r.seam * 1000.0, r.seam_step * 1000.0, r.step_median * 1000.0, r.step_max * 1000.0,
			r.reach_fwd, r.reach_back, r.reach_side])
		_check_clip(clip, r)


func _check_clip(clip: String, r: Dictionary) -> void:
	assert_true(r.top <= TOP_LIMIT[clip], "%s top %.3f m > %.2f (frame %d)" % [clip, r.top, TOP_LIMIT[clip], r.top_frame])
	assert_true(r.min_y >= MIN_Y, "%s lowest point %.4f m < %.2f (frame %d)" % [clip, r.min_y, MIN_Y, r.min_frame])
	if r.loop != Animation.LOOP_NONE:
		assert_true(r.seam <= SEAM_TOL, "%s loop seam %.1f mm > %.1f mm" % [clip, r.seam * 1000.0, SEAM_TOL * 1000.0])


## Planted blades of in-place locomotion clips should slide backward (+Z) at the game speed.
func test_planted_feet_speed() -> void:
	if m.player == null:
		fail("no rig")
		return
	var speeds := {"walk_loop": 1.6, "jog_loop": 4.0, "crouch_walk_loop": 1.0, "crawl_loop": 0.5,
			"idle_loop": 0.0, "crouch_idle_loop": 0.0, "crawl_idle_loop": 0.0}
	print("HERO_QA | clip | game speed | contact frames L/R | patch speed L (min..max) | patch speed R (min..max) | vertex slip-free speed L (min..max) | R (min..max) | lateral max L/R m/s |")
	for clip: String in speeds:
		var r := m.measure_clip(clip)
		print("HERO_QA | %s | %.2f | %d / %d | %.2f (%.2f..%.2f) | %.2f (%.2f..%.2f) | %.2f (%.2f..%.2f) | %.2f (%.2f..%.2f) | %.2f / %.2f |" % [clip, speeds[clip],
			r.contact_frames_l, r.contact_frames_r, r.plant_speed_l, r.plant_speed_min_l, r.plant_speed_max_l,
			r.plant_speed_r, r.plant_speed_min_r, r.plant_speed_max_r, r.vert_speed_l, r.vert_speed_min_l,
			r.vert_speed_max_l, r.vert_speed_r, r.vert_speed_min_r, r.vert_speed_max_r, r.lateral_l, r.lateral_r])
		var seq := PackedStringArray()
		for st in r.steps_seq:
			seq.append("%.0f" % (st * 1000.0))
		print("HERO_QA steps mm %s: %s" % [clip, " ".join(seq)])
		_check_plant(clip, speeds[clip], r)


## Median speed of floor-touching blade vertices (material points) within 10 % (or 0.05 m/s for idles) of the game
## speed: the blade does not slide on the floor once the body moves at that speed.
func _check_plant(clip: String, speed: float, r: Dictionary) -> void:
	var tol := maxf(0.05, speed * 0.1)
	for side in ["l", "r"]:
		var v: float = r["vert_speed_" + side]
		assert_true(not is_nan(v), "%s: %s blade never touches the floor" % [clip, side])
		assert_true(absf(v - speed) <= tol, "%s: %s planted blade moves at %.2f m/s, game speed %.2f" % [clip, side, v, speed])


## The jump clip starts when jumped() fires (player CLAUDE.md); the blades should be off the floor for about the
## physics airtime and back on the floor (landing) near AIRTIME.
func test_jump_airtime() -> void:
	if m.player == null or not m.player.has_animation("jump"):
		fail("no jump clip")
		return
	var r := m.measure_clip("jump")
	var line := PackedStringArray()
	for f in r.frames + 1:
		line.append("%d:%.3f/%.3f" % [f, r.foot_min_l[f], r.foot_min_r[f]])
	print("HERO_QA jump foot min y per frame (L/R): ", " ".join(line))
	var tops := PackedStringArray()
	for f in r.frames + 1:
		tops.append("%.2f" % r.tops[f])
	print("HERO_QA jump top per frame: ", " ".join(tops))
	m.pose_at("idle_loop", 0.0)
	var idle0 := m.skinned()
	m.pose_at("jump", 0.0)
	var j0 := m.skinned()
	m.pose_at("jump", m.player.get_animation("jump").length)
	var j1 := m.skinned()
	m.pose_at("crouch_idle_loop", 0.0)
	var c0 := m.skinned()
	print("HERO_QA jump vs idle_loop frame 0, max vertex distance: start %.3f m, end %.3f m; jump start vs crouch_idle_loop %.3f m" % [
		Measure._max_dist(idle0, j0), Measure._max_dist(idle0, j1), Measure._max_dist(c0, j0)])
	_check_jump(r)


func _check_jump(r: Dictionary) -> void:
	var first_off := -1
	var last_off := -1
	for f in r.frames + 1:
		var off: bool = r.foot_min_l[f] > Measure.CONTACT_Y and r.foot_min_r[f] > Measure.CONTACT_Y
		if off:
			if first_off < 0:
				first_off = f
			last_off = f
	print("HERO_QA jump blades off floor: first frame %d (%.3f s), last frame %d (%.3f s), clip airtime %.3f s, physics airtime %.3f s" % [
		first_off, first_off / Measure.FPS, last_off, last_off / Measure.FPS,
		(last_off - first_off + 1) / Measure.FPS if first_off >= 0 else 0.0, AIRTIME])
	assert_true(first_off >= 0, "jump: blades never leave the floor")
	if first_off < 0:
		return
	assert_true(first_off / Measure.FPS <= 0.1, "jump: blades leave the floor at %.3f s, > 0.1 s after jumped()" % (first_off / Measure.FPS))
	var touchdown := (last_off + 1) / Measure.FPS
	assert_almost_eq(touchdown, AIRTIME, 0.1, "jump: clip touchdown vs physics landing (s)")
