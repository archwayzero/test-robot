# Module: touch_controls
On-screen joystick and buttons that emit the standard input actions

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/touch_controls/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `TouchControlsFactory.create() -> TouchControls` (loads internal/touch_controls.tscn).
- `TouchControls` (public/touch_controls.gd, Control): `set_controls_visible(show)`, `get_stick_vector() -> Vector2`,
  test hooks `get_jump_rect()`, `get_stance_rect()` (T031: override the public defaults; viewport coordinates),
  signal `visibility_toggled(visible_now)`.

### Implementation requirements
- Landscape layout at the 1280x590 base resolution, anchored so it scales (stretch mode canvas_items, aspect expand):
  joystick bottom-left (radius 90 px, appears where the left-half touch starts), buttons bottom-right: Jump (large),
  Stance (smaller, shows current stance icon text). Drawn with Godot 2D nodes/StyleBoxes only (no image files).
- Output only `Input.action_press(action, strength)` / `action_release` on GameActions. Multi-touch (joystick and a
  button at once). Touches outside the widgets are NOT consumed (`mouse_filter = IGNORE` on the full-screen root).
- Hidden when `set_controls_visible(false)`; hiding releases all actions. Shown on touch devices; on desktop only if
  `input_devices/pointing/emulate_touch_from_mouse` is on (PC preview).
- Tests: drag joystick 50% -> move strength ~0.5 and no run; 100% -> strength ~1 (>= RUN_THRESHOLD); release -> 0;
  tap Jump -> `jump` pressed then released; simultaneous stick + button.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
