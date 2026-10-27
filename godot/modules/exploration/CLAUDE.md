# Module: exploration
Visited maze cells (fog-of-war state), stored in GameState

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/exploration/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core, maze.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `ExplorationFactory.create() -> Exploration` (loads internal/exploration_impl.gd).
- `Exploration` (public/exploration.gd, Node): `setup(layout)`, `is_explored(cell)`, `explored_count()`,
  `get_explored_cells()`; signals `cell_explored(cell)`, `restored()`.

### Implementation requirements
- Listen to `Core.player_moved`; convert with `layout.world_to_cell()`; ignore out-of-bounds.
- Persist as `StateKeys.EXPLORATION_VISITED` (Base64 bitset, bit y*width+x) and `EXPLORATION_COUNT` after each new cell.
- On `setup()`: restore if `StateKeys.MAZE_SEED` == layout seed and the bitset exists, else start with only the
  start cell. Re-read on `Core.load_finished(_, OK)` and emit `restored()`.
- Tests: fresh start = 1 cell; moving through A,B,C emits 3 signals once each; revisits emit nothing; bitset round-trip;
  wrong seed discards stored data.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `python3 tools/qa/memguard.py -- godot --headless --fixed-fps 30 --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
