## Autosave policy: saves Core.state to SAVE_SLOT via Core.saves, then mirrors the saved file to the CloudBackend.
## Triggers: a change of StateKeys.EXPLORATION_COUNT (new cell explored), throttled to at most one save per
## MIN_INTERVAL_S of game time (a pending trigger is saved when the interval ends); and immediately when the app goes
## to the background (NOTIFICATION_APPLICATION_PAUSED) or closes (NOTIFICATION_WM_CLOSE_REQUEST). The local save never
## depends on the cloud.
## On startup, restore() picks the newer of local and cloud (by the saved timestamp) and loads it.
##
## Owner: orchestrator. Implemented in cloud_save/internal; create via CloudSaveFactory.
@abstract
class_name AutoSave
extends Node

## Emitted after each autosave attempt. `error` is the local save result; `cloud_error` the cloud push result
## (ERR_UNAVAILABLE when the backend is unavailable, ERR_SKIP when the local save failed and nothing was pushed).
signal autosaved(error: Error, cloud_error: Error)

const SAVE_SLOT := 0
const MIN_INTERVAL_S := 10.0


## Starts the policy with `backend`. The game calls it once, after the maze and exploration are set up. Calling it
## again replaces the backend (end-to-end tests swap in CloudSaveFactory.make_fake_backend()); the throttle state is kept.
@abstract func setup(backend: CloudBackend) -> void


## Loads the newest available save into Core.state. Returns OK, or ERR_FILE_NOT_FOUND for a fresh game.
@abstract func restore() -> Error


## Saves now, ignoring the throttle (used on app background and by tests).
@abstract func save_now() -> Error
