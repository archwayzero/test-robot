## SaveService implementation: one text file per slot, `<dir>/slot_<n>.save` (default dir user://saves).
##
## File format (self-describing, text): var_to_str() of
##   {"header": {"format": "core_save", "version": 1, "saved_at_unix": float (UTC unix time, seconds)},
##    "state": Core.state.snapshot()}
## Writes are atomic: the data goes to `slot_<n>.save.tmp` first, which is then renamed over the real file.
## A missing file -> ERR_FILE_NOT_FOUND; unreadable/invalid/newer-version file -> ERR_FILE_CORRUPT; in both cases
## the state is left unchanged.
extends SaveService

const FORMAT := "core_save"
const VERSION := 1
const DEFAULT_DIR := "user://saves"
const _GameStateImpl := preload("res://modules/core/internal/game_state_impl.gd")

var _core: CoreAPI
var _dir: String


func _init(core: CoreAPI, dir: String = DEFAULT_DIR) -> void:
	_core = core
	_dir = dir


func save_game(slot: int) -> Error:
	var err := _save(slot)
	_core.save_finished.emit(slot, err)
	return err


func load_game(slot: int) -> Error:
	var err := _load(slot)
	_core.load_finished.emit(slot, err)
	return err


func has_save(slot: int) -> bool:
	return slot >= 0 and FileAccess.file_exists(slot_path(slot))


func delete_save(slot: int) -> Error:
	if slot < 0:
		return ERR_INVALID_PARAMETER
	var tmp := slot_path(slot) + ".tmp"
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp)
	if not FileAccess.file_exists(slot_path(slot)):
		return ERR_FILE_NOT_FOUND
	return DirAccess.remove_absolute(slot_path(slot))


## Path of a slot's file (internal; useful to tests and tools inside core).
func slot_path(slot: int) -> String:
	return _dir.path_join("slot_%d.save" % slot)


## Reads only the header of a slot ({} if missing or invalid). Internal; lets core compare save times.
func read_header(slot: int) -> Dictionary:
	var data := _read(slot)
	return data.header if data.has("header") else {}


func _save(slot: int) -> Error:
	if slot < 0:
		return ERR_INVALID_PARAMETER
	if _core.state == null:
		return ERR_UNCONFIGURED
	var err := DirAccess.make_dir_recursive_absolute(_dir)
	if err != OK:
		return err
	var payload := {
		"header": {"format": FORMAT, "version": VERSION, "saved_at_unix": Time.get_unix_time_from_system()},
		"state": _core.state.snapshot(),
	}
	var final_path := slot_path(slot)
	var tmp_path := final_path + ".tmp"
	var f := FileAccess.open(tmp_path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(var_to_str(payload))
	f.flush()
	err = f.get_error()
	f.close()
	if err != OK:
		DirAccess.remove_absolute(tmp_path)
		return err
	err = DirAccess.rename_absolute(tmp_path, final_path)
	if err != OK:
		DirAccess.remove_absolute(tmp_path)
	return err


func _load(slot: int) -> Error:
	if slot < 0:
		return ERR_INVALID_PARAMETER
	if _core.state == null:
		return ERR_UNCONFIGURED
	if not FileAccess.file_exists(slot_path(slot)):
		return ERR_FILE_NOT_FOUND
	var data := _read(slot)
	if data.is_empty():
		return ERR_FILE_CORRUPT
	_core.state.restore(data.state)
	return OK


## Returns {"header": Dictionary, "state": Dictionary} for a valid file, {} otherwise.
func _read(slot: int) -> Dictionary:
	var f := FileAccess.open(slot_path(slot), FileAccess.READ)
	if f == null:
		return {}
	var text := f.get_as_text()
	f.close()
	if text.strip_edges().is_empty():
		return {}
	var parsed: Variant = str_to_var(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var d: Dictionary = parsed
	if typeof(d.get("header")) != TYPE_DICTIONARY or typeof(d.get("state")) != TYPE_DICTIONARY:
		return {}
	var header: Dictionary = d.header
	if header.get("format") != FORMAT or typeof(header.get("version")) != TYPE_INT:
		return {}
	if header.version < 1 or header.version > VERSION:
		return {}
	if not (typeof(header.get("saved_at_unix")) in [TYPE_FLOAT, TYPE_INT]):
		return {}
	var state := _GameStateImpl.parse_snapshot(d.state)
	if state.is_empty():
		return {}
	return {"header": header, "state": state}
