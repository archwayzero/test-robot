# Architecture

Goal: any task can be done by reading and changing one folder. Structure exists to make that true.

## Module model (Godot)
```
godot/modules/<name>/
  CLAUDE.md   rules + documented public interface   (orchestrator)
  public/     interface only: signals, typed stubs  (orchestrator)
  internal/   implementation, scenes, scripts       (module-dev)
  tests/      module tests                          (module-dev)
```
- A module may reference another module only via `res://modules/<other>/public/...` and only if `<other>`
  is in its `depends_on` (docs/modules.json). The commit hook and CI reject violations.
- Cross-module communication: signals and interfaces declared in `public/`; no hard-coded node paths.
- `core` holds the shared event bus, game state and save/load interfaces. It is the only module allowed to
  be an autoload. Everything else is instanced or injected.
- Dependencies must form a DAG. If A needs B and B needs A, extract an interface into a third module.
- Third-party addons are vendored under `godot/addons/` (orchestrator only) and recorded in
  `docs/architecture/THIRDPARTY.md` with source URL and commit hash.

## Assets
- Blender generator scripts are the source of truth (text, in git). Produced `.blend` and `.glb` files are DVC artifacts.
- `blender/models/<asset>/` (modeler) and `blender/rigs/<asset>/` (rigger-animator); exports land in
  `godot/assets/<asset>/model/` and `.../rig/`. Conventions: docs/contracts/blender-godot-assets.md.
- Godot `.import` files are text: commit them. Regenerate with `godot --headless --path godot --import` after `dvc pull`.

## Testability
`core` exposes an automation API in its `public/` folder (input injection, game-state snapshot, fixed random seed
and timestep), compiled in only for test runs. End-to-end tests drive the game through it and nothing else.

## Motion references
`reference/<asset>/<clip>/` holds a generated video (DVC), frames + contact sheet (DVC), optional keypoints (JSON)
and NOTES.md. Produced by reference-director from a snapshot of the exported model via the ComfyUI workflow in
`tools/comfy/workflows/`. Consumed by rigger-animator and qa. Guidance only, never an acceptance oracle on its own.

## Ownership
| Path | Owner |
|---|---|
| `docs/`, `tools/`, `CLAUDE.md`, `godot/project.godot`, `godot/addons/`, module `public/` + `CLAUDE.md` | orchestrator |
| `godot/modules/<m>/internal`, `tests` | `module-dev` on branch `task/module-dev/<m>/...` |
| `blender/models`, `godot/assets/*/model` | modeler |
| `blender/rigs`, `godot/assets/*/rig` | rigger-animator |
| `reference/` | reference-director |
| `godot/tests/`, `docs/qa/reports/` | qa |
| `docs/qa/TEST_PLAN.md`, `docs/qa/budgets.json` | orchestrator (human approves) |
| `.claude/settings.json`, `.claude/hooks`, `tools/githooks`, `tools/scope_lib.py`, `tools/precommit_checks.py`, `docs/module-map.json`, `tools/setup.sh`, `tools/envcheck.py` | locked (human only) |
| `docs/modules.json` | orchestrator (via tools/new_module.py) |

## Adding a module
1. Orchestrator decides the responsibility and dependencies.
2. `python3 tools/new_module.py <name> "<desc>" --depends a,b`
3. Orchestrator writes `public/` and the interface section of the module CLAUDE.md, commits on `arch/<slug>`, human merges.
4. Only then create implementation tasks: `tools/task.py add <id> module-dev "<title>" --module <name>`.

## Interface change protocol
An implementer needing a different interface stops and reports the exact change. The orchestrator updates `public/`
on an `arch/` branch; after merge, the task resumes.

## Definition of done (any task)
Spec satisfied; tests pass headless; scope respected; binaries in DVC; reviewer PASS; branch pushed; PR open.
