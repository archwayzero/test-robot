## CloudBackend that mirrors nothing: never available, push fails with ERR_UNAVAILABLE, pull is always empty.
## Used on platforms without a cloud (PC preview, sandbox) and as the fallback when the iCloud plugin is absent.
extends CloudBackend


func is_available() -> bool:
	return false


func push(_slot: int, _data: PackedByteArray) -> Error:
	return ERR_UNAVAILABLE


func pull(_slot: int) -> PackedByteArray:
	return PackedByteArray()
