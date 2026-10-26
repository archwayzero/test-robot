# Module: game
Main scene: composes all modules and owns boot order; no game logic

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/game/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core, maze, player, touch_controls, exploration, minimap, cloud_save.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `GameMain` (public/game_main.gd, Node): `MAIN_SCENE = res://modules/game/internal/main.tscn` (project.godot
  run/main_scene); signal `ready_to_play()`; `is_ready_to_play()`; read-only accessors `get_player()`,
  `get_maze_world()`, `get_exploration()`, `get_minimap()`, `get_touch_controls()`, `get_auto_save()`.

### Implementation requirements
- Exactly the boot order documented in public/game_main.gd. Uses only the public factories of its dependencies.
- Owns WorldEnvironment for now (dark ambient, depth fog, tonemap filmic, glow on) and the phase changes.
- On iOS: `Engine.max_fps = 30` (PLATFORM.md target). Desktop preview: uncapped.
- Tests (end-to-end smoke, headless): main scene reaches `ready_to_play` within 300 frames; player stands in the start
  cell; minimap shows 1 visited cell; opening the large map pauses the tree and sets phase map_open.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
