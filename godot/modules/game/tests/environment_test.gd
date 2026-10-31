## Stable rules of the crypt Environment in main.tscn (T040). Output levels cannot be measured headless, so these
## pin the settings that gave the measured result, and each rule proves it can fail on a broken copy.
extends TestCase

## maze CHUNK_DRAW_DISTANCE (36 m) depends on these: fog must be full before the chunks are cut.
const FOG_BEGIN := 4.0
const FOG_END := 26.0


## The Environment of the main scene, read without booting the game.
func _scene_environment() -> Environment:
	var scene := (load(GameMain.MAIN_SCENE) as PackedScene).instantiate()
	var found: Environment = (scene.get_node("WorldEnvironment") as WorldEnvironment).environment
	scene.free()
	return found


## Names of the rules `env` breaks; empty when it follows all of them.
func _faults(env: Environment) -> Array[String]:
	var faults: Array[String] = []
	if env.ambient_light_color.r < env.ambient_light_color.b:
		faults.append("ambient_cool")
	# Past the chunk cutoff only the background shows. It must take the fog, not its own colour.
	if env.fog_sky_affect != 1.0:
		faults.append("background_not_fogged")
	if not env.fog_enabled:
		faults.append("fog_off")
	if env.fog_depth_begin != FOG_BEGIN or env.fog_depth_end != FOG_END:
		faults.append("fog_range_moved")
	return faults


func test_scene_environment_follows_the_rules() -> void:
	var env := _scene_environment()
	assert_not_null(env)
	assert_eq(_faults(env), [] as Array[String])


func test_cool_ambient_is_reported() -> void:
	var env := _scene_environment().duplicate() as Environment
	env.ambient_light_color = Color(0.42, 0.4, 0.5)
	assert_eq(_faults(env), ["ambient_cool"] as Array[String])


func test_background_without_fog_is_reported() -> void:
	var env := _scene_environment().duplicate() as Environment
	env.fog_sky_affect = 0.5
	assert_eq(_faults(env), ["background_not_fogged"] as Array[String])


func test_fog_off_is_reported() -> void:
	var env := _scene_environment().duplicate() as Environment
	env.fog_enabled = false
	assert_eq(_faults(env), ["fog_off"] as Array[String])


func test_moved_fog_range_is_reported() -> void:
	var env := _scene_environment().duplicate() as Environment
	env.fog_depth_end = 30.0
	assert_eq(_faults(env), ["fog_range_moved"] as Array[String])
	env.fog_depth_end = FOG_END
	env.fog_depth_begin = 5.0
	assert_eq(_faults(env), ["fog_range_moved"] as Array[String])
