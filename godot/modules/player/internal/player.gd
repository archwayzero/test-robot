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
			_update_rig(0.0)


## Places the camera rig at the player's head. delta = 0 snaps the smoothed values.
func _update_rig(delta: float) -> void:
	var target_len: float = ARM_LENGTHS[_stance]
	var target_pivot := _height_of(_stance) * PIVOT_FRACTION
	if delta > 0.0:
		var k := 1.0 - exp(-CAMERA_SMOOTHING * delta)
		_arm_length = lerpf(_arm_length, target_len, k)
		_pivot_height = lerpf(_pivot_height, target_pivot, k)
	_rig.global_transform = Transform3D(Basis(Vector3.UP, _cam_yaw), global_position + Vector3(0.0, _pivot_height, 0.0))
	_arm.rotation = Vector3(_cam_pitch, 0.0, 0.0)
	_arm.spring_length = _arm_length


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
