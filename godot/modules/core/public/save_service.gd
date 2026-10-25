## Save/load of the GameState snapshot to numbered slots under user://.
##
## Owner: orchestrator. Implemented in core/internal by module-dev. Access it as `Core.saves`.
@abstract
class_name SaveService
extends RefCounted


## Writes Core.state.snapshot() to `slot` (>= 0). Returns OK or an Error and emits Core.save_finished(slot, error).
@abstract func save_game(slot: int) -> Error


## Reads `slot` and calls Core.state.restore(). Returns OK or an Error (ERR_FILE_NOT_FOUND if empty, ERR_FILE_CORRUPT
## if unreadable; the current state is then left unchanged) and emits Core.load_finished(slot, error).
@abstract func load_game(slot: int) -> Error


@abstract func has_save(slot: int) -> bool


@abstract func delete_save(slot: int) -> Error
