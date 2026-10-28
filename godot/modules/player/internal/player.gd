## Player implementation (T004): capsule placeholder, stances, walk/run/jump, third-person spring-arm camera.
## Input only through GameActions. See godot/modules/player/CLAUDE.md for the contract.
extends PlayerController

## Collision radius (m). The crawl shape keeps this radius (see _make_body_shape()).
const RADIUS := 0.3
const CROUCH_HEIGHT := 1.0
const CRAWL_HEIGHT := 0.5
## Tolerance on the run threshold (action strengths are 32-bit floats: 0.7 arrives as 0.69999...).
const RUN_EPSILON := 1e-4
## Ground acceleration/deceleration (m/s^2) and in the air.
const GROUND_ACCEL := 30.0
const AIR_ACCEL := 8.0
## Body turn rate toward the move direction (rad/s).
const TURN_SPEED := 12.0
## Minimum time between throttled state writes while moving (s).
const STATE_WRITE_INTERVAL := 0.5
## Position changes below this (m) do not count as movement (floor contact noise).
const MOVE_EPSILON := 1e-4
## Clearance probe: lifted off the floor and slightly thinner than the body, so the floor and touching walls
## never count as "blocked"; only something above (a ceiling) does.
const CLEARANCE_LIFT := 0.05
const CLEARANCE_RADIUS := 0.28
## Camera.
const ARM_LENGTHS := {Stance.STAND: 2.5, Stance.CROUCH: 1.8, Stance.CRAWL: 1.2}
const PIVOT_FRACTION := 0.9
const DEFAULT_PITCH := -0.35
const PITCH_MIN := -1.2
const PITCH_MAX := 0.35
const ORBIT_SENSITIVITY := 0.006
const CAMERA_SMOOTHING := 8.0
## Low passages (T030, M1 finding F6). A ceiling lower than LOW_CEILING_MAX above the feet (below the kit's FULL
## clearance 2.2 m and pier capitals at 1.9-2.2 m, above the CROUCH clearance 1.3 m) moves the pivot to just below
## the ceiling and flattens the pitch so the arm stays long along the passage instead of collapsing onto the player.
const LOW_CEILING_MAX := 1.8
## Pivot/camera centre stays this far below a low ceiling (arm probe radius 0.15 + spring margin 0.1 + slack).
const CEILING_MARGIN := 0.3
## Under a low ceiling the pivot may rise at most this much above the stance pivot (to see over the body).
const LOW_PIVOT_RAISE := 0.15
const LOW_PIVOT_MIN := 0.25
## When the ceiling ends the pitch limit relaxes at this fraction of CAMERA_SMOOTHING (the arm swings back up
## at its full length, so a slower glide keeps the view step per frame small).
const PITCH_RELEASE_RATE := 0.5
## Under a low ceiling the camera sits at head height straight behind the player, so the body would hide the
## passage's vanishing point: shift the view sideways (Camera3D.h_offset, over the right shoulder) by up to this
## much, limited by a sideways ray so the shifted view never enters a wall.
const SHOULDER_OFFSET := 0.5
const SHOULDER_WALL_MARGIN := 0.25
## Ceiling probes start this far above the feet. Hits closer than CEILING_MIN_GAP to the probe start, or on a
## surface not facing down (normal.y > CEILING_NORMAL_MAX_Y: a wall face grazed by the probe), are not ceilings.
const CEILING_PROBE_LIFT := 0.1
const CEILING_MIN_GAP := 0.01
const CEILING_NORMAL_MAX_Y := -0.5
## Arm-path ceiling samples stay this far in front of the first wall behind (never on the wall face itself), or
## reach this far past the end of a clear arm.
const ARM_SAMPLE_WALL_PULL := 0.3
const ARM_SAMPLE_END_EXTRA := 0.2
## Player visual fades out when the camera gets closer to the head than FADE_START (m), hidden at FADE_END.
const FADE_START := 0.8
const FADE_END := 0.5
const FADE_SMOOTHING := 12.0

## Standing collision height (m). 1.75 until the conformed hero reports its height (T019).
@export var stand_height := 1.75

var _stance: Stance = Stance.STAND
var _running := false
var _was_on_floor := true
var _jump_was_pressed := false
var _stance_was_pressed := false
var _last_moved_pos := Vector3.INF
var _last_written_pos := Vector3.INF
var _last_write_physics_frame := -1000000
var _cam_yaw := 0.0
var _cam_pitch := DEFAULT_PITCH
var _arm_length := 2.5
var _pivot_height := 1.5
## Smoothed lower bound on the camera pitch from low ceilings (PITCH_MIN = no constraint).
var _pitch_limit := PITCH_MIN
## Smoothed fade of the player visual: 0 opaque .. 1 hidden.
var _visual_fade := 0.0
## Smoothed sideways view offset (m) under low ceilings (target before the wall clamp in _place_rig()).
var _shoulder := 0.0
## GeometryInstance3D nodes under $Visual (rebuilt when its children change, e.g. the T019 hero swap) and the
## transparency last applied to them (-1 = never / list rebuilt).
var _fade_geoms: Array[GeometryInstance3D] = []
var _fade_geoms_dirty := true
var _applied_fade := -1.0
var _orbit_finger := -1
var _shapes := {}
var _clearance_shapes := {}

@onready var _collision: CollisionShape3D = $CollisionShape3D
@onready var _clearance: ShapeCast3D = $ClearanceCast
@onready var _rig: Node3D = $CameraRig
@onready var _arm: SpringArm3D = $CameraRig/SpringArm3D
@onready var _camera: Camera3D = $CameraRig/SpringArm3D/Camera3D
@onready var _visual: Node3D = $Visual


func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	process_physics_priority = -10  # move before the SpringArm3D casts, so the camera never lags into a wall
	for s in [Stance.STAND, Stance.CROUCH, Stance.CRAWL]:
		_shapes[s] = _make_body_shape(s)
	for s in [Stance.STAND, Stance.CROUCH]:
		var c := CapsuleShape3D.new()
		c.radius = CLEARANCE_RADIUS
		c.height = _height_of(s)
		_clearance_shapes[s] = c
	_clearance.enabled = false
	_clearance.target_position = Vector3.ZERO
	_clearance.collision_mask = 1
	_clearance.exclude_parent = true
	_arm.collision_mask = 1
	if _arm.shape == null:
		var probe := SphereShape3D.new()
		probe.radius = 0.15
		_arm.shape = probe
	_cam_yaw = rotation.y
	_visual.child_entered_tree.connect(_on_visual_children_changed)
	_visual.child_exiting_tree.connect(_on_visual_children_changed)
	_apply_shape()
	_arm_length = ARM_LENGTHS[_stance]
	_pivot_height = _height_of(_stance) * PIVOT_FRACTION
	_update_rig(0.0)
	_camera.make_current()


func _notification(what: int) -> void:
	if what == NOTIFICATION_ENTER_TREE and _camera != null:
		_camera.make_current.call_deferred()


# --- PlayerController ---------------------------------------------------------------------------------

func get_stance() -> Stance:
	return _stance


func is_running() -> bool:
	return _running


func is_grounded() -> bool:
	return is_on_floor()


func spawn_at(spawn_position: Vector3, yaw: float = 0.0) -> void:
	if is_inside_tree():
		global_position = spawn_position
	else:
		position = spawn_position
	rotation = Vector3(0.0, yaw, 0.0)
	velocity = Vector3.ZERO
	_running = false
	_was_on_floor = true
	_cam_yaw = yaw
	_cam_pitch = DEFAULT_PITCH
	if _arm != null:
		_arm_length = ARM_LENGTHS[_stance]
		_pivot_height = _height_of(_stance) * PIVOT_FRACTION
		_update_rig(0.0)
	if is_inside_tree():
		_write_state()


## Load/restore (T027): goes straight to the saved stance if it fits here, otherwise the tallest one that fits
## (STAND > CROUCH > CRAWL; CRAWL always fits). Out-of-range values count as STAND. Valid in the same frame as
## spawn_at() (the clearance probe is forced at the current transform). Emits stance_changed only on a change.
func restore_stance(stance: Stance) -> void:
	var wanted := int(stance)
	if wanted < int(Stance.STAND) or wanted > int(Stance.CRAWL):
		wanted = int(Stance.STAND)
	var target: Stance = Stance.CRAWL
	for s in range(wanted, int(Stance.CRAWL) + 1):
		if s == int(Stance.CRAWL) or not is_inside_tree() or has_clearance_for(s as Stance):
			target = s as Stance
			break
	if not is_node_ready():
		_stance = target  # _ready() applies shape and camera
		return
	var changed := target != _stance
	if changed:
		_stance = target
		_apply_shape()
		# Snap the camera like spawn_at() does (no glide from the previous stance height after a load).
		_arm_length = ARM_LENGTHS[_stance]
		_pivot_height = _height_of(_stance) * PIVOT_FRACTION
		_update_rig(0.0)
	if is_inside_tree():
		_write_state()
	if changed:
		stance_changed.emit(_stance)


func get_collision_height() -> float:
	return _height_of(_stance)


func get_camera() -> Camera3D:
	return _camera


# --- Simulation ---------------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	# Edge detection by polling (robust to physics/process frame ratios).
	var stance_pressed := Input.is_action_pressed(GameActions.STANCE_CYCLE)
	if stance_pressed and not _stance_was_pressed:
		_cycle_stance()
	_stance_was_pressed = stance_pressed
	var jump_pressed := Input.is_action_pressed(GameActions.JUMP)
	var want_jump := jump_pressed and not _jump_was_pressed
	_jump_was_pressed = jump_pressed

	var input := Input.get_vector(GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
			GameActions.MOVE_BACK)
	var deflection := Input.get_vector(GameActions.MOVE_LEFT, GameActions.MOVE_RIGHT, GameActions.MOVE_FORWARD,
			GameActions.MOVE_BACK, 0.0).length()
	var dir := Vector3.ZERO
	if input != Vector2.ZERO:
		var d := input.normalized()
		dir = Vector3(d.x, 0.0, d.y).rotated(Vector3.UP, _cam_yaw)
	_running = (dir != Vector3.ZERO and _stance == Stance.STAND
			and (deflection >= GameActions.RUN_THRESHOLD - RUN_EPSILON or Input.is_action_pressed(GameActions.RUN)))
	var target := dir * _speed()

	var on_floor := is_on_floor()
	var accel := GROUND_ACCEL if on_floor else AIR_ACCEL
	var horizontal := Vector3(velocity.x, 0.0, velocity.z).move_toward(target, accel * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	if not on_floor:
		velocity.y -= _gravity() * delta
	if want_jump and on_floor and _can_jump():
		velocity.y = JUMP_VELOCITY
		jumped.emit()

	if dir != Vector3.ZERO:
		var target_yaw := atan2(-dir.x, -dir.z)
		rotation.y = rotate_toward(rotation.y, target_yaw, TURN_SPEED * delta)

	move_and_slide()

	var now_on_floor := is_on_floor()
	if now_on_floor and not _was_on_floor:
		landed.emit()
	_was_on_floor = now_on_floor

	_update_rig(delta)
	_publish_position()


func _speed() -> float:
	match _stance:
		Stance.CROUCH:
			return CROUCH_SPEED
		Stance.CRAWL:
			return CRAWL_SPEED
	return RUN_SPEED if _running else WALK_SPEED


func _gravity() -> float:
	return float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))


func _can_jump() -> bool:
	if _stance == Stance.CRAWL:
		return false
	if _stance == Stance.CROUCH:
		# Jumping from a crouch stands up first; refused under a ceiling too low to stand.
		return _set_stance(Stance.STAND)
	return true


# --- Stances ------------------------------------------------------------------------------------------

func _height_of(s: Stance) -> float:
	match s:
		Stance.CROUCH:
			return CROUCH_HEIGHT
		Stance.CRAWL:
			return CRAWL_HEIGHT
	return stand_height


## A capsule of radius 0.3 cannot be shorter than 0.6 m (Godot clamps the radius), so the 0.5 m crawl shape
## is a cylinder of the same radius.
func _make_body_shape(s: Stance) -> Shape3D:
	var h := _height_of(s)
	if h < RADIUS * 2.0:
		var cyl := CylinderShape3D.new()
		cyl.radius = RADIUS
		cyl.height = h
		return cyl
	var cap := CapsuleShape3D.new()
	cap.radius = RADIUS
	cap.height = h
	return cap


func _cycle_stance() -> void:
	match _stance:
		Stance.STAND:
			_set_stance(Stance.CROUCH)
		Stance.CROUCH:
			_set_stance(Stance.CRAWL)
		Stance.CRAWL:
			if not _set_stance(Stance.STAND):
				_set_stance(Stance.CROUCH)


## Returns true if the stance is now `target` (changed). Going taller is refused without clearance.
func _set_stance(target: Stance) -> bool:
	if target == _stance:
		return true
	if _height_of(target) > _height_of(_stance) and not has_clearance_for(target):
		return false
	_stance = target
	_apply_shape()
	_write_state()
	stance_changed.emit(_stance)
	return true


## True if the collision shape of `target` fits here (nothing on layer 1 overlaps it, ignoring the floor).
func has_clearance_for(target: Stance) -> bool:
	if not _clearance_shapes.has(target):
		return true
	var shape: Shape3D = _clearance_shapes[target]
	_clearance.shape = shape
	_clearance.position = Vector3(0.0, _height_of(target) * 0.5 + CLEARANCE_LIFT, 0.0)
	_clearance.force_shapecast_update()
	return not _clearance.is_colliding()


func _apply_shape() -> void:
	_collision.shape = _shapes[_stance]
	_collision.position = Vector3(0.0, _height_of(_stance) * 0.5, 0.0)
	_update_visual()


func _update_visual() -> void:
	var h := _height_of(_stance)
	var body := _visual.get_node_or_null("Capsule") as MeshInstance3D
	if body != null:
		var mat := body.material_override
		if h < RADIUS * 2.0:
			var cyl := CylinderMesh.new()
			cyl.top_radius = RADIUS
			cyl.bottom_radius = RADIUS
			cyl.height = h
			body.mesh = cyl
		else:
			var cap := CapsuleMesh.new()
			cap.radius = RADIUS
			cap.height = h
			body.mesh = cap
		body.material_override = mat
		body.position = Vector3(0.0, h * 0.5, 0.0)
	var nose := _visual.get_node_or_null("Nose") as Node3D
	if nose != null:
		nose.position = Vector3(0.0, h * 0.8, -RADIUS)


# --- Camera -------------------------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			if _orbit_finger < 0 and t.position.x >= get_viewport().get_visible_rect().size.x * 0.5:
				_orbit_finger = t.index
		elif t.index == _orbit_finger:
			_orbit_finger = -1
	elif event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		if d.index == _orbit_finger:
			_cam_yaw = wrapf(_cam_yaw - d.relative.x * ORBIT_SENSITIVITY, -PI, PI)
			_cam_pitch = clampf(_cam_pitch - d.relative.y * ORBIT_SENSITIVITY, PITCH_MIN, PITCH_MAX)
			_place_rig()  # orbit applies at once (re-clamping the shoulder shift); smoothed values keep gliding


## Places the camera rig at the player's head. delta = 0 snaps the smoothed values.
func _update_rig(delta: float) -> void:
	var target_len: float = ARM_LENGTHS[_stance]
	var stance_pivot := _height_of(_stance) * PIVOT_FRACTION
	var target_pivot := stance_pivot
	var target_limit := PITCH_MIN
	var target_shoulder := 0.0
	if is_inside_tree():
		var above := _ceiling_above(global_position)
		if above < LOW_CEILING_MAX:
			target_pivot = maxf(minf(stance_pivot + LOW_PIVOT_RAISE, above - CEILING_MARGIN), LOW_PIVOT_MIN)
		# Lowest ceiling over the part of the arm path that is reachable (up to the first wall behind).
		var lowest := above
		var back := Basis(Vector3.UP, _cam_yaw) * Vector3.BACK
		var pivot_world := global_position + Vector3(0.0, _pivot_height, 0.0)
		var reach := _ray_distance(pivot_world, pivot_world + back * target_len, target_len)
		# Clear arm: sample up to just past its end (the camera probe's reach). Arm hitting a wall: samples pulled off
		# that wall (a probe on its face would graze the face, not a ceiling).
		var span := target_len + ARM_SAMPLE_END_EXTRA if reach >= target_len else maxf(reach - ARM_SAMPLE_WALL_PULL, 0.0)
		for f in [0.5, 1.0]:
			lowest = minf(lowest, _ceiling_above(global_position + back * span * f))
		if lowest < LOW_CEILING_MAX:
			var rise := clampf((lowest - CEILING_MARGIN - target_pivot) / target_len, 0.0, 1.0)
			target_limit = -asin(rise)
			target_shoulder = SHOULDER_OFFSET
	if delta > 0.0:
		var k := 1.0 - exp(-CAMERA_SMOOTHING * delta)
		_arm_length = lerpf(_arm_length, target_len, k)
		_pivot_height = lerpf(_pivot_height, target_pivot, k)
		if target_limit > PITCH_MIN:
			_pitch_limit = lerpf(_pitch_limit, target_limit, k)
		elif _pitch_limit > _cam_pitch:
			# Ceiling ended: relax toward the orbit pitch (not PITCH_MIN, which would swing the pitch down at the
			# rate of a 1.2 rad lerp), then release the limit entirely.
			_pitch_limit = lerpf(_pitch_limit, _cam_pitch, 1.0 - exp(-CAMERA_SMOOTHING * PITCH_RELEASE_RATE * delta))
			if _pitch_limit - _cam_pitch < 1e-3:
				_pitch_limit = PITCH_MIN
		else:
			_pitch_limit = PITCH_MIN
		# Smoothed both ways (also when a passage ends); a wall to the side clamps it at once in _place_rig().
		_shoulder = lerpf(_shoulder, target_shoulder, k)
		if target_shoulder == 0.0 and _shoulder < 1e-3:
			_shoulder = 0.0
	else:
		_arm_length = target_len
		_pivot_height = target_pivot
		_pitch_limit = target_limit
		_shoulder = target_shoulder
	_place_rig()
	_update_fade(delta)


func _place_rig() -> void:
	_rig.global_transform = Transform3D(Basis(Vector3.UP, _cam_yaw), global_position + Vector3(0.0, _pivot_height, 0.0))
	_arm.rotation = Vector3(get_camera_pitch(), 0.0, 0.0)
	_arm.spring_length = _arm_length
	if _shoulder > 0.0 and is_inside_tree():
		# Room to the right of the camera at the current yaw (the arm length is at most 1 frame stale). Limiting is
		# immediate so the shifted view never enters a wall; _shoulder keeps the clamped value and regrows smoothly.
		var right := Basis(Vector3.UP, _cam_yaw) * Vector3.RIGHT
		var cam := _camera.global_position
		var probe := SHOULDER_OFFSET + SHOULDER_WALL_MARGIN
		var side := _ray_distance(cam, cam + right * probe, probe)
		_shoulder = minf(_shoulder, clampf(side - SHOULDER_WALL_MARGIN, 0.0, SHOULDER_OFFSET))
	_camera.h_offset = _shoulder


## Height of the lowest layer-1 surface above the feet at `at` (x, z), INF if none below LOW_CEILING_MAX.
## A probe starting inside a wall reports nothing (rays do not hit from inside); a hit at the probe start or on a
## surface not facing down (a wall face the probe grazes) is not a ceiling either.
func _ceiling_above(at: Vector3) -> float:
	var base := Vector3(at.x, global_position.y + CEILING_PROBE_LIFT, at.z)
	var top := Vector3(at.x, global_position.y + LOW_CEILING_MAX, at.z)
	var q := PhysicsRayQueryParameters3D.create(base, top, 1, [get_rid()])
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return INF
	var pos := hit["position"] as Vector3
	if (hit["normal"] as Vector3).y > CEILING_NORMAL_MAX_Y or pos.y - base.y < CEILING_MIN_GAP:
		return INF
	return pos.y - global_position.y


## Distance along from -> to before a layer-1 hit (`full` if clear).
func _ray_distance(from: Vector3, to: Vector3, full: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(from, to, 1, [get_rid()])
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return full
	return from.distance_to(hit["position"])


## Fades (GeometryInstance3D.transparency) and finally hides the player visual when the camera is close to the
## head, so the view ahead stays visible. Generic over whatever meshes live under $Visual (capsule, hero rig).
func _update_fade(delta: float) -> void:
	if delta <= 0.0:
		# Snap (spawn/load): the spring arm has not placed the camera yet, so its position is stale. Start opaque;
		# the next physics frames fade in from the real camera distance.
		_visual_fade = 0.0
	else:
		var head := global_position + Vector3(0.0, _height_of(_stance) * PIVOT_FRACTION, 0.0)
		var d := _camera.global_position.distance_to(head)
		var target := clampf((FADE_START - d) / (FADE_START - FADE_END), 0.0, 1.0)
		_visual_fade = lerpf(_visual_fade, target, 1.0 - exp(-FADE_SMOOTHING * delta))
		if target == 0.0 and _visual_fade < 0.01:
			_visual_fade = 0.0
		elif target == 1.0 and _visual_fade > 0.99:
			_visual_fade = 1.0
	_apply_fade(_visual_fade)
	var show := _visual_fade < 0.99
	if _visual.visible != show:
		_visual.visible = show


## Sets the transparency of the cached GeometryInstance3D list, only when the value (or the list) changed.
func _apply_fade(fade: float) -> void:
	if _fade_geoms_dirty:
		_fade_geoms.clear()
		_collect_geoms(_visual)
		_fade_geoms_dirty = false
		_applied_fade = -1.0
	if fade == _applied_fade:
		return
	_applied_fade = fade
	for g in _fade_geoms:
		if is_instance_valid(g):
			g.transparency = fade


func _collect_geoms(node: Node) -> void:
	if node is GeometryInstance3D:
		_fade_geoms.append(node as GeometryInstance3D)
	for c in node.get_children():
		_collect_geoms(c)


func _on_visual_children_changed(_node: Node) -> void:
	_fade_geoms_dirty = true


## Effective camera pitch: the orbit pitch, raised toward horizontal under low ceilings.
func get_camera_pitch() -> float:
	return maxf(_cam_pitch, _pitch_limit)


## Sideways view offset (Camera3D.h_offset, m): > 0 under low ceilings. Exposed for tests.
func get_camera_shoulder() -> float:
	return _shoulder


## Fade of the player visual (0 opaque .. 1 hidden). Exposed for tests.
func get_visual_fade() -> float:
	return _visual_fade if _visual.visible else 1.0


## Camera yaw (radians); movement input is relative to it. Exposed for tests and the preview.
func get_camera_yaw() -> float:
	return _cam_yaw


## World position of the camera pivot (the player's head).
func get_camera_pivot() -> Vector3:
	return _rig.global_position


# --- Publishing ---------------------------------------------------------------------------------------

func _publish_position() -> void:
	var pos := global_position
	if _last_moved_pos == Vector3.INF or pos.distance_squared_to(_last_moved_pos) > MOVE_EPSILON * MOVE_EPSILON:
		_last_moved_pos = pos
		Core.player_moved.emit(pos)
	if (pos.distance_squared_to(_last_written_pos) > MOVE_EPSILON * MOVE_EPSILON
			and Engine.get_physics_frames() - _last_write_physics_frame >= _write_interval_frames()):
		_write_state()


func _write_interval_frames() -> int:
	return ceili(STATE_WRITE_INTERVAL * Engine.physics_ticks_per_second - 1e-6)


func _write_state() -> void:
	if Core.state == null:
		return
	_last_written_pos = global_position
	_last_write_physics_frame = Engine.get_physics_frames()
	Core.state.set_value(StateKeys.PLAYER_POSITION, global_position)
	Core.state.set_value(StateKeys.PLAYER_YAW, rotation.y)
	Core.state.set_value(StateKeys.PLAYER_STANCE, int(_stance))
