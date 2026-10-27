## Test helper (not a test): counts its instances so tests can prove cloud data never instantiated an object.
extends RefCounted

static var created := 0


func _init() -> void:
	created += 1
