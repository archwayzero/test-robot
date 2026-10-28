extends TestCase

const IMPL := "res://modules/core/internal/game_state_impl.gd"

var state: GameState
var events: Array = []


func before_each() -> void:
	state = load(IMPL).new(core())
	events = []
	core().phase_changed.connect(_on_phase)
	core().pause_changed.connect(_on_pause)
	core().state_value_changed.connect(_on_value)


func after_each() -> void:
	core().phase_changed.disconnect(_on_phase)
	core().pause_changed.disconnect(_on_pause)
	core().state_value_changed.disconnect(_on_value)
	state = null


func _on_phase(prev: StringName, cur: StringName) -> void:
	events.append(["phase", prev, cur])


func _on_pause(paused: bool) -> void:
	events.append(["pause", paused])


func _on_value(key: StringName, value: Variant) -> void:
	events.append(["value", key, value])


func test_initial_state() -> void:
	assert_eq(state.get_phase(), GameState.PHASE_BOOT)
	assert_false(state.is_paused())
	assert_false(state.has_value(&"test/a"))
	assert_null(state.get_value(&"test/a"))
	assert_eq(state.get_value(&"test/a", 7), 7, "default returned")
	assert_eq(events, [])


func test_set_phase_emits_once() -> void:
	state.set_phase(StateKeys.PHASE_LOADING)
	assert_eq(state.get_phase(), StateKeys.PHASE_LOADING)
	state.set_phase(StateKeys.PHASE_LOADING)
	state.set_phase(StateKeys.PHASE_PLAYING)
	assert_eq(events, [["phase", &"boot", &"loading"], ["phase", &"loading", &"playing"]])


func test_set_paused_emits_once() -> void:
	state.set_paused(false)
	assert_eq(events, [], "no signal when unchanged")
	state.set_paused(true)
	state.set_paused(true)
	assert_true(state.is_paused())
	state.set_paused(false)
	assert_false(state.is_paused())
	assert_eq(events, [["pause", true], ["pause", false]])


func test_set_value_emits_only_on_change() -> void:
	state.set_value(&"test/pos", Vector3(1, 2, 3))
	state.set_value(&"test/pos", Vector3(1, 2, 3))
	assert_true(state.has_value(&"test/pos"))
	assert_eq(state.get_value(&"test/pos"), Vector3(1, 2, 3))
	state.set_value(&"test/pos", Vector3(1, 2, 4))
	state.set_value(&"test/n", 1)
	state.set_value(&"test/n", 1.0)  # type change counts as a change
	assert_eq(events, [
		["value", &"test/pos", Vector3(1, 2, 3)],
		["value", &"test/pos", Vector3(1, 2, 4)],
		["value", &"test/n", 1],
		["value", &"test/n", 1.0],
	])


func test_container_values_are_copied() -> void:
	var arr := [1, [2, 3]]
	state.set_value(&"test/arr", arr)
	arr[1].append(4)
	assert_eq(state.get_value(&"test/arr"), [1, [2, 3]], "caller's later mutation does not leak in")
	var got: Array = state.get_value(&"test/arr")
	got.append(9)
	assert_eq(state.get_value(&"test/arr"), [1, [2, 3]], "returned value is a copy")
	state.set_value(&"test/arr", [1, [2, 3]])
	assert_eq(events.size(), 1, "equal array is no change")


func test_rejects_non_serializable_and_bad_keys() -> void:
	var n := Node.new()
	state.set_value(&"test/node", n)
	state.set_value(&"test/nested", {"a": [n]})
	state.set_value(&"test/callable", func(): pass)
	state.set_value(&"nonamespace", 1)
	state.set_value(&"Player/x", 1)
	n.free()
	assert_false(state.has_value(&"test/node"))
	assert_false(state.has_value(&"test/nested"))
	assert_false(state.has_value(&"test/callable"))
	assert_false(state.has_value(&"nonamespace"))
	assert_eq(events, [])


func test_snapshot_shape_and_deep_copy() -> void:
	state.set_phase(&"playing")
	state.set_paused(true)
	state.set_value(&"test/dict", {"a": [1, 2]})
	var snap := state.snapshot()
	assert_eq(snap.keys(), ["phase", "paused", "values"])
	assert_eq(snap.phase, &"playing")
	assert_eq(snap.paused, true)
	assert_eq(snap.values, {&"test/dict": {"a": [1, 2]}})
	snap.values[&"test/dict"]["a"].append(3)
	snap.values[&"test/other"] = 5
	assert_eq(state.get_value(&"test/dict"), {"a": [1, 2]}, "snapshot is a deep copy")
	assert_false(state.has_value(&"test/other"))


func test_values_survive_var_to_str() -> void:
	state.set_value(&"test/v3", Vector3(1.5, -2, 3))
	state.set_value(&"test/s", "abc")
	state.set_value(&"test/sn", &"stand")
	state.set_value(&"test/f", 0.1)
	state.set_value(&"test/i", 123456789012)
	state.set_value(&"test/b64", Marshalls.raw_to_base64(PackedByteArray([1, 2, 255])))
	state.set_value(&"test/arr", [Vector2i(1, 2), {"k": true}])
	var snap := state.snapshot()
	var back: Dictionary = str_to_var(var_to_str(snap))
	assert_eq(back, snap)
	for key in snap.values:
		assert_eq(typeof(back.values[key]), typeof(snap.values[key]), String(key))


func test_restore_emits_for_changes_only() -> void:
	state.set_value(&"test/keep", 1)
	state.set_value(&"test/change", 1)
	state.set_value(&"test/remove", 1)
	var before := state.snapshot()
	events.clear()
	state.restore({"phase": &"playing", "paused": true,
			"values": {&"test/keep": 1, &"test/change": 2, &"test/new": "x"}})
	assert_eq(state.get_phase(), &"playing")
	assert_true(state.is_paused())
	assert_eq(state.get_value(&"test/change"), 2)
	assert_eq(state.get_value(&"test/new"), "x")
	assert_false(state.has_value(&"test/remove"))
	assert_has(events, ["phase", &"boot", &"playing"])
	assert_has(events, ["pause", true])
	assert_has(events, ["value", &"test/remove", null])
	assert_has(events, ["value", &"test/change", 2])
	assert_has(events, ["value", &"test/new", "x"])
	assert_eq(events.size(), 5, "nothing for unchanged test/keep: %s" % [events])
	events.clear()
	state.restore(before)
	assert_eq(state.snapshot(), before)
	events.clear()
	state.restore(before)
	assert_eq(events, [], "restoring the same snapshot emits nothing")


func test_restore_rejects_invalid_and_copies_input() -> void:
	state.set_value(&"test/a", 1)
	var before := state.snapshot()
	events.clear()
	state.restore({"phase": &"x"})
	state.restore({"phase": 3, "paused": false, "values": {}})
	state.restore({"phase": &"x", "paused": false, "values": {&"test/a": Node}})
	assert_eq(state.snapshot(), before, "invalid snapshots leave the state unchanged")
	assert_eq(events, [])
	var data := {"phase": "menu", "paused": false, "values": {"test/a": [1]}}
	state.restore(data)
	assert_eq(state.get_phase(), &"menu", "String phase converted")
	assert_eq(typeof(state.get_phase()), TYPE_STRING_NAME)
	assert_true(state.has_value(&"test/a"), "String keys converted")
	data.values["test/a"].append(2)
	assert_eq(state.get_value(&"test/a"), [1], "restore copies its input")


const BAD_KEYS := ["foo", "/x", "Player/x", "a/", "a//b", "a b/c", "", "/", "a/b/", "a/B", "a-b/c", "a/b\n", "a/b c"]
const GOOD_KEYS := ["a/b", "player/position", "maze/seed", "a1/b_2/c3", "test/x/y/z", "_/_"]


func test_set_value_rejects_non_namespaced_keys() -> void:
	for k in BAD_KEYS:
		state.set_value(StringName(k), 1)  # StringName key
		state.set_value(k, 2)  # String key, converted by the typed parameter
		assert_false(state.has_value(StringName(k)), "'%s' rejected" % k)
	assert_eq(state.snapshot().values, {}, "nothing stored")
	assert_eq(events, [], "no signal for rejected keys")


func test_set_value_accepts_multi_segment_keys() -> void:
	for k in GOOD_KEYS:
		state.set_value(k, 1)
		assert_true(state.has_value(StringName(k)), "'%s' accepted" % k)
	assert_eq(events.size(), GOOD_KEYS.size())


func test_restore_rejects_snapshot_with_any_bad_key() -> void:
	state.set_phase(&"menu")
	state.set_value(&"test/a", 1)
	var before := state.snapshot()
	events.clear()
	for k in BAD_KEYS:
		# One bad key among valid ones rejects the whole snapshot, String or StringName key.
		state.restore({"phase": &"playing", "paused": true, "values": {&"test/a": 2, &"test/b": 3, k: 4}})
		state.restore({"phase": &"playing", "paused": true, "values": {&"test/a": 2, StringName(k): 4}})
		assert_eq(state.snapshot(), before, "state unchanged for '%s'" % k)
	assert_eq(events, [], "no signals for rejected snapshots")
	var good := {}
	for k in GOOD_KEYS:
		good[k] = 5
	state.restore({"phase": &"playing", "paused": false, "values": good})
	assert_eq(state.get_phase(), &"playing")
	for k in GOOD_KEYS:
		assert_eq(state.get_value(StringName(k)), 5, "'%s' restored" % k)
	assert_false(state.has_value(&"test/a"))


func test_parse_snapshot_rejects_bad_keys() -> void:
	var impl: Script = load(IMPL)
	assert_eq(impl.parse_snapshot({"phase": &"x", "paused": false, "values": {"foo": 1}}), {})
	assert_eq(impl.parse_snapshot({"phase": &"x", "paused": false, "values": {"a/b": 1, "Player/x": 1}}), {})
	var ok: Dictionary = impl.parse_snapshot({"phase": &"x", "paused": false, "values": {"a/b/c": 1}})
	assert_eq(ok.get("values"), {&"a/b/c": 1})


func test_state_keys_match_key_pattern() -> void:
	var re := RegEx.create_from_string(GameState.KEY_PATTERN)
	var consts: Dictionary = (load("res://modules/core/public/state_keys.gd") as Script).get_script_constant_map()
	var checked := 0
	for name in consts:
		if String(name).begins_with("PHASE_"):
			continue
		var v: Variant = consts[name]
		if not (typeof(v) in [TYPE_STRING, TYPE_STRING_NAME]):
			continue  # STANCE_* values are ints, not keys
		var m := re.search(String(v))
		assert_true(m != null and m.get_string() == String(v), "StateKeys.%s = '%s' matches KEY_PATTERN" % [name, v])
		assert_true(load(IMPL).is_valid_key(v), "StateKeys.%s accepted by set_value" % name)
		checked += 1
	assert_true(checked >= 6, "checked %d StateKeys constants" % checked)
