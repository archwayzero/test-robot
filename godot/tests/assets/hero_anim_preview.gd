## T014 (qa) preview of the hero rig clips as Godot plays them. Owner: qa. Not a test (no `_test` suffix).
## Left: orthographic side view from the hero's left (hero faces image-left, like reference/hero/*), with lines at
## the clearance limits. Right: behind-and-above game-like camera. The checker floor scrolls backward at the game
## speed of the clip, so a planted blade should stay fixed on its floor tile (no sliding).
## `clip` = "" cycles through all 8 clips (`cycle_seconds` each); otherwise loops one clip from frame 0.
extends Node3D

const GLB := "res://assets/hero/rig/hero.glb"
const ORDER := ["idle_loop", "walk_loop", "jog_loop", "crouch_idle_loop", "crouch_walk_loop", "crawl_idle_loop",
		"crawl_loop", "jump"]
## Game speed per clip (player CLAUDE.md): the floor scrolls at this speed.
const SPEED := {"idle_loop": 0.0, "walk_loop": 1.6, "jog_loop": 4.0, "crouch_idle_loop": 0.0,
		"crouch_walk_loop": 1.0, "crawl_idle_loop": 0.0, "crawl_loop": 0.5, "jump": 0.0}
## Clearance lines in the side view (m): [limit used by the QA test, ceiling of the kit].
const LINES := {"stand": [1.85, 2.2], "crouch": [1.25, 1.3], "crawl": [0.70, 0.75]}
const TILE := 0.25
## Side camera pitch (deg, looking down) and the depth of the clearance bars behind the hero midline (m). With the
## pitch, a bar BAR_X behind the hero would read BAR_X * tan(pitch) (~6 cm) higher than a hero point at the same
## height, so the bars are lowered by that amount: on screen they line up with the true height at the hero midline
## (x = 0). Points on the near/far side of the body (|x| <= 0.27 m) still read up to ~3 cm lower/higher.
const SIDE_PITCH := 6.0
const BAR_X := 0.6

@export var clip := ""
@export var cycle_seconds := 3.0

var _anim: AnimationPlayer
var _floor_mat: StandardMaterial3D
var _label: Label
var _side_cam: Camera3D
var _game_cam: Camera3D
var _lines: Array[MeshInstance3D] = []
var _current := ""
var _t := 0.0
var _clip_t := 0.0
var _scroll := 0.0
var _hero: Node3D


func _ready() -> void:
	var world := World3D.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.16, 0.17, 0.2)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.55, 0.6)
	env.ambient_light_energy = 0.8
	world.environment = env
	var box := HBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_FULL_RECT)
	box.add_theme_constant_override("separation", 2)
	add_child(box)
	var scene_root := Node3D.new()
	_side_cam = _make_view(box, world, scene_root, true)
	_game_cam = _make_view(box, world, scene_root, false)
	_build_world(scene_root)
	_label = Label.new()
	_label.position = Vector2(12, 8)
	_label.add_theme_font_size_override("font_size", 22)
	_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_label.add_theme_constant_override("outline_size", 6)
	add_child(_label)
	var sub := Label.new()
	sub.text = "side view (ortho) | lines: QA limit (yellow), kit ceiling (red)        game camera (behind, above)"
	sub.position = Vector2(12, 560)
	sub.add_theme_font_size_override("font_size", 14)
	add_child(sub)
	_play(clip if clip != "" else ORDER[0])


func _make_view(box: HBoxContainer, world: World3D, scene_root: Node3D, first: bool) -> Camera3D:
	var c := SubViewportContainer.new()
	c.stretch = true
	c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	c.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(c)
	var vp := SubViewport.new()
	vp.world_3d = world
	vp.own_world_3d = false
	c.add_child(vp)
	if first:
		vp.add_child(scene_root)
	var cam := Camera3D.new()
	vp.add_child(cam)
	cam.current = true
	return cam


func _build_world(r: Node3D) -> void:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -35, 0)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	r.add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, 120, 0)
	fill.light_energy = 0.5
	r.add_child(fill)
	# checker floor, 2x2 tiles per texture repeat
	var img := Image.create(64, 64, false, Image.FORMAT_RGB8)
	for y in 64:
		for x in 64:
			var odd := ((x / 32) + (y / 32)) % 2 == 1
			var line := x % 32 == 0 or y % 32 == 0
			img.set_pixel(x, y, Color(0.12, 0.12, 0.13) if line else (Color(0.55, 0.53, 0.5) if odd else Color(0.38, 0.37, 0.35)))
	_floor_mat = StandardMaterial3D.new()
	_floor_mat.albedo_texture = ImageTexture.create_from_image(img)
	_floor_mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	var plane := PlaneMesh.new()
	# wide floor for the game camera (layer 3) and a 0.8 m strip for the slightly tilted side view (layer 2), so the
	# side view shows a thin band under the blades instead of a wall of tiles
	plane.size = Vector2(20, 20)
	_floor_mat.uv1_scale = Vector3(20.0 / (2 * TILE), 20.0 / (2 * TILE), 1)
	plane.material = _floor_mat
	var floor_mi := MeshInstance3D.new()
	floor_mi.mesh = plane
	floor_mi.layers = 4
	r.add_child(floor_mi)
	var strip := PlaneMesh.new()
	strip.size = Vector2(0.8, 20)
	strip.material = _floor_mat
	var strip_mi := MeshInstance3D.new()
	strip_mi.mesh = strip
	strip_mi.layers = 2
	strip_mi.position.x = 0.0  # x -0.4..0.4: the floor line at the hero midline is the middle of the band
	r.add_child(strip_mi)
	# clearance lines: thin bars across the side view (behind the hero so they never hide it)
	for i in 2:
		var bar := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.01, 0.008, 3.0)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(1, 0.85, 0.1) if i == 0 else Color(1, 0.15, 0.1)
		bm.material = mat
		bar.mesh = bm
		bar.position = Vector3(BAR_X, 0, 0)
		bar.layers = 2  # side view only
		r.add_child(bar)
		_lines.append(bar)
	_hero = (load(GLB) as PackedScene).instantiate() as Node3D
	r.add_child(_hero)
	_anim = _find(_hero, "AnimationPlayer") as AnimationPlayer
	_side_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	_side_cam.size = 2.3
	_side_cam.position = Vector3(-6, 1.0, 0)
	# slight downward tilt so the floor tiles show as a strip under the blades (planting/sliding)
	_side_cam.rotation_degrees = Vector3(-SIDE_PITCH, -90, 0)
	_game_cam.cull_mask = 1 | 4
	_side_cam.cull_mask = 1 | 2


static func _find(n: Node, cls: String) -> Node:
	if n.is_class(cls):
		return n
	for ch in n.get_children():
		var f := _find(ch, cls)
		if f:
			return f
	return null


func _stance(c: String) -> String:
	return "crawl" if c.begins_with("crawl") else ("crouch" if c.begins_with("crouch") else "stand")


func _play(c: String) -> void:
	_current = c
	_clip_t = 0.0
	_anim.play(c)
	_anim.seek(0.0, true)
	var st := _stance(c)
	var bar_drop := BAR_X * tan(deg_to_rad(SIDE_PITCH))
	_lines[0].position.y = LINES[st][0] - bar_drop
	_lines[1].position.y = LINES[st][1] - bar_drop
	# game-like camera: pivot near head/back height, arm behind and above (player CLAUDE.md arm lengths, ~2.2 stand)
	var pivot_h: float = {"stand": 1.45, "crouch": 0.95, "crawl": 0.5}[st]
	var arm: float = {"stand": 2.2, "crouch": 1.8, "crawl": 1.2}[st]
	var pitch := deg_to_rad(22.0)
	_game_cam.position = Vector3(0.35, pivot_h + arm * sin(pitch), arm * cos(pitch))
	_game_cam.look_at(Vector3(0, pivot_h - 0.35, -0.4))
	# view centre height at the hero midline; stand frames -0.2..2.5 m so the 2.2 m FULL ceiling line is visible
	_side_cam.position.y = (1.15 if st == "stand" else 0.62) + 6.0 * tan(deg_to_rad(SIDE_PITCH))
	_side_cam.size = 2.7 if st == "stand" else 1.8


func _process(delta: float) -> void:
	_t += delta
	_clip_t += delta
	if clip == "" and _t >= cycle_seconds:
		_t -= cycle_seconds
		_play(ORDER[(ORDER.find(_current) + 1) % ORDER.size()])
	elif clip != "" and _current == "jump" and _clip_t >= _anim.get_animation("jump").length + 0.5:
		_play("jump")  # replay the one-shot after a short hold
	# floor scrolls toward +Z (backward under a hero facing -Z) at the game speed
	_scroll += SPEED[_current] * delta
	_floor_mat.uv1_offset = Vector3(0, -_scroll / (2 * TILE), 0)
	var a := _anim.get_animation(_current)
	var pos := _anim.current_animation_position
	_label.text = "%s   t=%.2f s  frame %d/%d   floor %.1f m/s   (%s)" % [_current, pos, int(round(pos * 30.0)),
			int(round(a.length * 30.0)), SPEED[_current], "loop" if a.loop_mode != Animation.LOOP_NONE else "one-shot"]
