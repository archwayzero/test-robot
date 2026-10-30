# Module: player
Character controller: stances, walk/run/jump, collision, third-person camera, hero animation

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/player/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `PlayerFactory.create_player() -> PlayerController` (loads internal/player.tscn).
- `PlayerController` (public/player_controller.gd, CharacterBody3D): `enum Stance {STAND, CROUCH, CRAWL}`,
  `get_stance()`, `is_running()`, `is_grounded()`, `spawn_at(position, yaw)`, `restore_stance(stance)` (T027), `get_collision_height()`, `get_camera()`;
  signals `stance_changed(stance)`, `jumped()`, `landed()`; speeds `WALK_SPEED 1.6`, `RUN_SPEED 4.0`,
  `CROUCH_SPEED 1.0`, `CRAWL_SPEED 0.5` m/s, `JUMP_VELOCITY 4.0` m/s.

### Implementation requirements
- Input only via `GameActions` (`Input.get_vector` on move_*; deflection >= `RUN_THRESHOLD` or `run` held = run).
  Movement is camera-relative. Turn the body toward the move direction.
- Collision capsule heights (meters): STAND = hero height (from docs/contracts/crypt-kit.md "Clearances"; 1.75 until
  the conformed hero reports its height), CROUCH = 1.0, CRAWL = 0.5; radius 0.3. Changing to a taller stance is
  refused if a ShapeCast up would hit layer 1 (stay low under low passages). `stance_cycle`: STAND->CROUCH->CRAWL->
  STAND (skipping refused steps). No jump while crawling or under a low ceiling. No running except in STAND.
- Body on layer 2 ("player"), mask 1. Never tunnels through walls at RUN_SPEED (use move_and_slide; physics 60 Hz).
- Camera: third-person, behind and above (SpringArm3D, collision mask 1, length 2.5 m stand / 1.8 crouch / 1.2 crawl),
  never inside walls. Low passages (T030, M1 finding F6: in CROUCH/CRAWL cells the arm collapsed onto the player and
  the passage was not visible): keep the pivot just below the ceiling, pitch the camera down the passage behind the
  player (arm can't rise; it should extend along the passage instead of shrinking to ~0), and when the camera is
  closer than ~0.6 m to the player hide or fade the player mesh so the view ahead stays visible. Acceptance: in the
  M1 stances playthrough the passage ahead is visible and the player covers less than ~1/3 of the frame.
  Orbit with touch drag on the right half of the screen outside buttons, handled ONLY as
  InputEventScreenTouch/ScreenDrag in `_unhandled_input` (never mouse events: emulated mouse events from touches are
  not consumed by touch_controls; on desktop the mouse arrives as touch via emulate_touch_from_mouse).
- Write `PLAYER_YAW` wrapped to [-PI, PI] (`wrapf`). Jumping from CROUCH first stands up (emits stance_changed(STAND)
  before jumped) and is refused under a low ceiling.
- Emits `Core.player_moved(global_position)` when moved; writes `StateKeys.PLAYER_POSITION`, `PLAYER_YAW`,
  `PLAYER_STANCE` on stance change and at most every 0.5 s while moving.
- Visual: capsule placeholder (T004) -> hero rig `res://assets/hero/rig/hero.glb` with an AnimationTree driving
  idle_loop/walk_loop/jog_loop/crouch_idle_loop/crouch_walk_loop/crawl_idle_loop/crawl_loop/jump (T019), as listed in
  docs/contracts/blender-godot-assets.md "Asset: hero". Hookup rules from QA T014
  (docs/qa/reports/hero-2026-10-29-T014.md): start `jump` at frame 0 when `jumped()` fires, crossfade in ~0.1 s
  (its first pose differs from idle by up to 23 cm at the arms); scale locomotion playback by actual speed / clip
  speed (walk 1.6, jog 4.0, crouch walk 1.0, crawl 0.5 m/s) so the blades stay planted at in-between speeds; no
  blend may overshoot the clip heights (crawl top 0.695 under a 0.75 ceiling, crouch walk 1.234 under 1.3); the
  mesh reaches past the 0.3 m capsule (crawl ~0.85 m forward) - acceptable, do not enlarge the capsule; the
  close-camera fade (T030) must judge distance to the body, not the blade tips (crawl puts them near the lens).
- `restore_stance(stance)` (T027): override the public default; tallest fitting stance via the same ShapeCast check
  as the stance cycle; no stance_changed when unchanged; out-of-range ints -> STAND. Tests for each case.
- Tests: speeds per stance (+-5%), heights per stance, stand-up refused under a low ceiling, no jump while crawling,
  wall-push at 8 angles never penetrates, emits player_moved.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
