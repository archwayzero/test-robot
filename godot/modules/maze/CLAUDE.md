# Module: maze
Maze layout grid (seeded, closed) and building the 3D maze from kit pieces, lights, occluders

## Ownership
- `public/`   interface only (signals, typed API stubs, docs). Owned by the orchestrator. Do not edit.
- `internal/` implementation. Owned by `module-dev` on a `task/module-dev/maze/...` branch.
- `tests/`    tests for this module. Same owner.

## Rules
- Reference other modules only as `res://modules/<other>/public/...`, and only modules in depends_on: core.
- Cross-module communication goes through signals/interfaces declared in `public/`, never through node paths.
- Need a public interface change? Stop and report the exact change to the orchestrator.
- Binary assets are never committed to git: `dvc add` them (see docs/architecture/WORKFLOW.md).

## Public interface
- `MazeFactory` (public/maze_factory.gd): `static create()`, `make_layout(seed = GAME_SEED, size = GAME_SIZE) -> MazeLayout`,
  `make_world() -> MazeWorld`. `GAME_SEED = 20261025`, `GAME_SIZE = 20x20`.
- `MazeLayout` (public/maze_layout.gd): grid data. `size()`, `cell_size_m()` (4.0, from docs/contracts/crypt-kit.md),
  `get_seed()`, `start_cell()`, `in_bounds()`, `has_wall(cell, Dir)`, `clearance(cell) -> Clearance {FULL, CROUCH, CRAWL}`,
  `lamp_slots()`, `world_to_cell()`, `cell_to_world()`. Cell (x,y) spans world X [x*s,(x+1)*s], Z [y*s,(y+1)*s].
- `MazeWorld` (public/maze_world.gd, Node3D): `build(layout)`, `get_layout()`, `is_built()`, signal `built()`.

### Implementation requirements
- Layout: perfect maze (recursive backtracker on `RandomNumberGenerator` seeded with the seed, NOT Core.rng) plus
  ~10% extra openings for loops; boundary always closed (no exit). 4-8 low-passage cells (CROUCH and CRAWL, at least
  2 of each), placed only on cells that lie on a loop, so removing them never disconnects the maze (no area is
  reachable only by crouching/crawling). Lamp slots: one wall lamp roughly every 3 cells of corridor.
- Same (seed, size) must give a byte-identical layout on every platform (no float math in generation).
- World: greybox first (T003: boxes with the kit dimensions from docs/contracts/crypt-kit.md, one material), then
  the crypt_kit GLB pieces (T018). Static geometry on physics layer 1 ("world"), collision from the kit's `-col`
  shapes or simple boxes. Merge or instance per 4x4-cell chunk so no mesh is lit by more than 8 omni lights
  (Mobile renderer limit). Add OccluderInstance3D per chunk. Lighting (T018): baked LightmapGI if it can be baked
  headless; otherwise real-time OmniLights at lamp slots (range <= 1.5 cells, no shadows) — report which.
- Writes `StateKeys.MAZE_SEED` in build().
- Tests: determinism (same seed twice, different seed differs), connectivity (all cells reachable from start),
  closed boundary, low passages each have an alternative route, world raycasts match `has_wall` on sample edges.

### Rules that apply to every module
- Global `class_name`s of modules NOT in depends_on are off-limits too (GDScript makes them visible; the reviewer
  rejects their use). Construct other modules only through their public factories.
- Implementations extend the `@abstract` classes in `public/` and live in `internal/` at the paths the factories load.
- Gameplay randomness: `Core.rng` only. No `/root/...` paths. No `preload` of other modules' internals.
- Tests: `tests/*_test.gd`, run with `godot --headless --path godot -s res://addons/test_runner/run.gd -- --automation --filter <module>`
  (format: docs/qa/TEST_PLAN.md "Test runner"). All tests must pass headless before you commit.
- Approved deviations from the human specs for this game: docs/architecture/DECISIONS.md.
