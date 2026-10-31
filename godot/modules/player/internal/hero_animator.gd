## Plays the hero's clips from the controller's real state (T019). Reads the player, never writes to it: no root
## motion, no effect on movement or collision. The tree is built here so the clip list lives in one place:
##
##   clip -> TimeScale (locomotion clips only) -> Transition "locomotion" -> OneShot "jump" (shot = jump) -> output
##
## The Transition always tracks stance and speed, also under a playing jump, so the jump fades out into the right
## clip. Hookup rules: docs/qa/reports/hero-2026-10-29-T014.md section 7.
extends AnimationTree

const IDLE := {
	PlayerController.Stance.STAND: &"idle_loop",
	PlayerController.Stance.CROUCH: &"crouch_idle_loop",
	PlayerController.Stance.CRAWL: &"crawl_idle_loop",
}
## Speed (m/s) each locomotion clip was authored for: playback scale = actual speed / this.
const CLIP_SPEED := {
	&"walk_loop": PlayerController.WALK_SPEED,
	&"jog_loop": PlayerController.RUN_SPEED,
	&"crouch_walk_loop": PlayerController.CROUCH_SPEED,
	&"crawl_loop": PlayerController.CRAWL_SPEED,
}
## Below this actual horizontal speed (m/s) a stance shows its idle clip.
const MOVING_SPEED := 0.05
## STAND switches from walk to jog here: the speed at which both clips run equally far from their authored speed.
const JOG_SPEED := 2.53
const XFADE := 0.15
const JUMP_FADE_IN := 0.1
const JUMP_FADE_OUT := 0.15
## Note on blends, measured with CPU-skinned poses: a crossfade interpolates joints, not heights. Between crouch_idle
## and crouch_walk the top reached 1.237 m and the blades -0.052 m; crawl to crouch reached 1.273 m (over the 1.25 m
## clip limit, 1.3 m ceiling) and crouch to crawl -0.235 m. So a stance change under a low ceiling is a cut, not a blend.
## Clip time of the jump's landing contact (rig contract: frame 25 = 0.80 s). Grounded earlier than this (head hit a
## ceiling, teleport), the air pose must not stay on.
const JUMP_TOUCHDOWN := 0.8
const JUMP_PARAM := &"parameters/jump/"

var _player: PlayerController
var _locomotion: AnimationNodeTransition
var _clip := &""
var _stance := PlayerController.Stance.STAND
var _jumping := false
var _jump_fading := false


## Called by the player in its _ready(). Starts in the clip of the current stance, with no blend.
func setup(player: PlayerController) -> void:
	_player = player
	tree_root = _build_tree()
	active = true
	player.jumped.connect(_on_jumped)
	player.landed.connect(_update_jump)
	snap()


## Pure clip choice for a stance and an actual horizontal speed.
static func clip_for(stance: PlayerController.Stance, speed: float) -> StringName:
	if speed < MOVING_SPEED:
		return IDLE[stance]
	match stance:
		PlayerController.Stance.CROUCH:
			return &"crouch_walk_loop"
		PlayerController.Stance.CRAWL:
			return &"crawl_loop"
	return &"jog_loop" if speed >= JOG_SPEED else &"walk_loop"


## Teleport/load: drops a running jump and shows the current stance's clip at once, with no blend (a blend from a
## taller stance would push the hero through a low ceiling).
func snap() -> void:
	set(JUMP_PARAM + "request", AnimationNodeOneShot.ONE_SHOT_REQUEST_ABORT)
	_jumping = false
	_jump_fading = false
	_update_locomotion(true)
	advance(0.0)


func _process(_delta: float) -> void:
	_update_locomotion()
	_update_jump()


## Horizontal speed the body really moved at (0 against a wall, whatever the input).
func _actual_speed() -> float:
	var v := _player.get_real_velocity()
	return Vector2(v.x, v.z).length()


func _update_locomotion(cut := false) -> void:
	var speed := _actual_speed()
	var stance := _player.get_stance()
	var clip := clip_for(stance, speed)
	if clip != _clip:
		var stance_cut: bool = stance != _stance and _player.call("is_under_low_ceiling")
		_locomotion.xfade_time = 0.0 if cut or stance_cut else XFADE
		_clip = clip
		_stance = stance
		set("parameters/locomotion/transition_request", String(clip))
	if CLIP_SPEED.has(clip):
		set("parameters/scale_%s/scale" % clip, speed / float(CLIP_SPEED[clip]))


func _update_jump() -> void:
	if not _jumping or get(JUMP_PARAM + "request") != AnimationNodeOneShot.ONE_SHOT_REQUEST_NONE:
		return
	if not get(JUMP_PARAM + "active"):
		_jumping = false
		return
	if _jump_fading:
		return
	var grounded := _player.is_grounded()
	if (_player.get_stance() != PlayerController.Stance.STAND
			or (grounded and (_actual_speed() >= MOVING_SPEED or get("parameters/clip_jump/current_position") < JUMP_TOUCHDOWN))):
		set(JUMP_PARAM + "request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FADE_OUT)
		_jump_fading = true


func _on_jumped() -> void:
	set(JUMP_PARAM + "request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)
	_jumping = true
	_jump_fading = false


func _build_tree() -> AnimationNodeBlendTree:
	var tree := AnimationNodeBlendTree.new()
	_locomotion = AnimationNodeTransition.new()
	_locomotion.xfade_time = XFADE
	tree.add_node(&"locomotion", _locomotion)
	var clips: Array[StringName] = []
	clips.assign(IDLE.values())
	clips.append_array(CLIP_SPEED.keys())
	for i in clips.size():
		var clip: StringName = clips[i]
		_locomotion.add_input(String(clip))
		var source := StringName("clip_%s" % clip)
		tree.add_node(source, _clip_node(clip))
		if CLIP_SPEED.has(clip):
			var scaled := StringName("scale_%s" % clip)
			tree.add_node(scaled, AnimationNodeTimeScale.new())
			tree.connect_node(scaled, 0, source)
			source = scaled
		tree.connect_node(&"locomotion", i, source)
	var jump := AnimationNodeOneShot.new()
	jump.fadein_time = JUMP_FADE_IN
	jump.fadeout_time = JUMP_FADE_OUT
	tree.add_node(&"jump", jump)
	tree.add_node(&"clip_jump", _clip_node(&"jump"))
	tree.connect_node(&"jump", 0, &"locomotion")
	tree.connect_node(&"jump", 1, &"clip_jump")
	tree.connect_node(&"output", 0, &"jump")
	return tree


func _clip_node(clip: StringName) -> AnimationNodeAnimation:
	var node := AnimationNodeAnimation.new()
	node.animation = clip
	return node
