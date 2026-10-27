## In-memory CloudBackend for tests. `available` can be toggled at any time to simulate losing/regaining the cloud.
## Every successful push is recorded in `pushes` ({"slot": int, "data": PackedByteArray}) for assertions.
extends CloudBackend

var available := true
## slot (int) -> PackedByteArray
var store := {}
var pushes: Array[Dictionary] = []


func _init(is_available_now: bool = true) -> void:
	available = is_available_now


func is_available() -> bool:
	return available


func push(slot: int, data: PackedByteArray) -> Error:
	if not available:
		return ERR_UNAVAILABLE
	var copy := data.duplicate()
	store[slot] = copy
	pushes.append({"slot": slot, "data": copy})
	return OK


func pull(slot: int) -> PackedByteArray:
	if not available or not store.has(slot):
		return PackedByteArray()
	return (store[slot] as PackedByteArray).duplicate()
