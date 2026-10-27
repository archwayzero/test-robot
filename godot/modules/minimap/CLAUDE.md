# Module: minimap
Top-left fog-of-war mini-map, large map on tap, player marker

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/minimap/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core, maze, exploration.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `MinimapFactory.create() -> Minimap` (loads internal/minimap.tscn).
- `Minimap` (public/minimap.gd, Control): `setup(layout, exploration)`, `open_large_map()`, `close_large_map()`,
  `is_large_map_open()`, `get_small_rect()`; signal `large_map_toggled(open)`; `SMALL_SIZE 200x200`, `MARGIN 16`.

### Implementation requirements
- Small map top-left, centred on the player, showing ~9x9 cells; large map full screen showing the whole maze.
- Unvisited cells: black. Visited cells: floor colour with their walls drawn; low passages tinted. Player marker:
  triangle showing facing (from `StateKeys.PLAYER_YAW` or the player_moved delta).
- Draw with `_draw()` (Godot 2D primitives), redraw only on change. No image files.
- Tap small map -> open; tap large map -> close. Uses `PROCESS_MODE_ALWAYS` (the tree is paused while open).
- Tests: only visited cells are drawn (inspect the cell colour model, not pixels), marker cell = player cell,
  open/close toggles and signals, small rect is top-left within MARGIN.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
