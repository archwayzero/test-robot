## On-screen controls (landscape): left virtual joystick, right buttons "Jump" and "Stance".
## Output is ONLY InputMap actions (GameActions): the joystick drives move_* with analog strength (deflection 0..1;
## run when deflection >= GameActions.RUN_THRESHOLD), buttons press jump / stance_cycle. No game API.
## Must not swallow touches outside its widgets (the minimap is tappable). Multi-touch: joystick + button together.
##
## Owner: orchestrator. Implemented in touch_controls/internal; instance it via TouchControlsFactory.
@abstract
class_name TouchControls
extends Control

## Emitted when the controls are shown or hidden.
signal visibility_toggled(visible_now: bool)


## Shows/hides the controls (hidden while the large map is open). Releases all held actions when hidden.
@abstract func set_controls_visible(show: bool) -> void


## Current joystick deflection, Vector2 with length 0..1 (x = right, y = back). Exposed for tests.
@abstract func get_stick_vector() -> Vector2
