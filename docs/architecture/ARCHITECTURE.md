# Architecture

Goal: any task can be done by reading and changing one folder. Structure exists to make that true.

## Engine and renderer
Decided at bootstrap (2026-10-25). Use this exact engine everywhere: WSL2 sandbox, PC preview, Mac final build.

- **Engine:** Godot **4.7.2.stable.official**, build `ed1daf0bf`, tag `4.7.2-stable`
  (commit `ed1daf0bf001b61586d9930840f2f1394092c079`, checked with `git ls-remote`). The binary's
  `godot --version` and the tag match.
- **Renderer:** **Mobile** (`rendering/renderer/rendering_method="mobile"`, also `.mobile="mobile"`). Set explicitly,
  not left to the per-platform default, so PC previews use the same renderer as the device.
- **iOS driver:** native **Metal** (`rendering/rendering_device/driver.ios="metal"`, the 4.7.2 default; the
  alternative is Vulkan via MoltenVK).
- **Orientation:** landscape (`display/window/handheld/orientation=0`), per docs/specs/PLATFORM.md.

Rationale and sources (all at the 4.7 branch / 4.7.2-stable tag):
1. ProjectSettings reference, `doc/classes/ProjectSettings.xml` @ `4.7.2-stable`:
   https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ProjectSettings.xml
   `rendering_method` options: "mobile (Mobile): Modern renderer designed for mobile devices"; `rendering_method.mobile`
   defaults to `"mobile"`; `driver.ios` default `"metal"` ("Metal from native drivers") or `"vulkan"` (MoltenVK).
2. Overview of renderers, godot-docs `4.7`, `tutorials/rendering/renderers.rst`:
   https://github.com/godotengine/godot-docs/blob/4.7/tutorials/rendering/renderers.rst
   Mobile is "used by default on mobile platforms"; choose it when "developing for newer mobile devices".
3. System requirements, godot-docs `4.7`, `about/system_requirements.rst`:
   https://github.com/godotengine/godot-docs/blob/4.7/about/system_requirements.rst
   Exported projects: Mobile renderer needs "Metal 3 support (iOS/iPadOS)"; minimum OS is **iOS 16.0 for
   Forward+/Mobile with Metal** (iOS 15.0 with Vulkan). The recommended spec cites "Apple A14 (iPhone 12)" for the
   Mobile renderer, which is our minimum device.
4. Exporting for iOS, godot-docs `4.7`, `tutorials/export/exporting_for_ios.rst`:
   https://github.com/godotengine/godot-docs/blob/4.7/tutorials/export/exporting_for_ios.rst
   "The iOS simulator only supports the Compatibility renderer." Test on a real device (or natively on an Apple
   Silicon Mac), not in the simulator.

Consequences: the iOS export's minimum OS must be at least 16.0 (set when the export preset is created on the Mac).
Headless Godot in the sandbox does not render; renderer behaviour is checked in PC previews and on device.

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

## Modules (run 1)
Source of truth for dependencies: docs/modules.json. Interfaces: each module's `public/` and CLAUDE.md.
Run-1 decisions that differ from the specs: docs/architecture/DECISIONS.md.

```
core ─┬─> maze ──────┬─> exploration ──> minimap ─┐
      ├─> player     │                            │
      ├─> touch_controls                          ├─> game (main scene, composition root)
      ├─> cloud_save ─────────────────────────────┤
      └───────────── (all of the above) ──────────┘
```

| Module | Responsibility | depends_on | Public entry point |
|---|---|---|---|
| `core` | Event bus, GameState, SaveService, Automation (test runs), shared action names and state keys | none | `Core` autoload (`CoreAPI`), `GameActions`, `StateKeys` |
| `maze` | Seeded grid layout; builds the 3D maze from crypt_kit pieces, lamps, collision, occluders, lighting | core | `MazeFactory.create()` -> `MazeLayout`, `MazeWorld` |
| `player` | Character controller, stances, jump, collision, camera, hero animation | core | `PlayerFactory.create_player()` -> `PlayerController` |
| `touch_controls` | On-screen joystick + Jump/Stance buttons -> InputMap actions | core | `TouchControlsFactory.create()` -> `TouchControls` |
| `exploration` | Visited cells (fog of war), persisted in GameState | core, maze | `ExplorationFactory.create()` -> `Exploration` |
| `minimap` | Top-left mini-map and full-screen map | core, maze, exploration | `MinimapFactory.create()` -> `Minimap` |
| `cloud_save` | Autosave policy + cloud backend seam (iCloud at M3) | core | `CloudSaveFactory.create()` -> `AutoSave`, `CloudBackend` |
| `game` | Main scene; composes modules, boot order, phases, environment | all | `GameMain.MAIN_SCENE` |

Patterns:
- **Factories.** Each module's public folder has a factory with a static `create...()` that loads the
  implementation from the module's own `internal/` by path. Other modules never name internal classes.
- **Input through actions.** Producers (touch_controls, keyboard, `Core.automation`) press `GameActions`; only
  `player` reads them. This is what lets tests and controls drive the player without depending on it.
- **State through GameState keys** (`StateKeys`, one writer per key), so `cloud_save` persists everything without
  knowing other modules.
- **`class_name` visibility.** GDScript makes every `class_name` global. Using a class from a module that is not
  in `depends_on` is a contract violation even though it compiles; reviewers reject it.

Physics layers (project.godot `layer_names/3d_physics`): 1 `world` (maze static geometry), 2 `player`.

Main scene: `res://modules/game/internal/main.tscn` (set in project.godot; exists once T009 is merged).

## Assets
- Blender generator scripts are the source of truth (text, in git). Produced `.blend` and `.glb` files are DVC artifacts.
- `blender/models/<asset>/` (modeler) and `blender/rigs/<asset>/` (rigger-animator); exports land in
  `godot/assets/<asset>/model/` and `.../rig/`. Conventions: docs/contracts/blender-godot-assets.md.
- Godot `.import` files are text: commit them. Regenerate with `godot --headless --path godot --import` after `dvc pull`.

## Testability
`core` exposes an automation API in its `public/` folder (input injection, game-state snapshot, fixed random seed
and timestep), compiled in only for test runs. End-to-end tests drive the game through it and nothing else.
Tests run with the in-repo runner `godot/addons/test_runner/` (commands and format: docs/qa/TEST_PLAN.md).

## Motion references
`reference/<asset>/<clip>/` holds a generated video (DVC), frames + contact sheet (DVC), optional keypoints (JSON)
and NOTES.md. Produced by reference-director from a snapshot of the exported model via the ComfyUI workflow in
`tools/comfy/workflows/`. Consumed by rigger-animator and qa. Guidance only, never an acceptance oracle on its own.

## Turnaround references (before modelling)
For any asset modelled from an image (or with generated parts), reference-director first produces a turnaround in
`reference/<asset>/turnaround/` from the source image: orbit video(s), stills at 0/45/.../315 deg, contact sheet and
NOTES.md (angle mapping, per-angle observations, listed AI inventions). The modeler renders its model at the same
angles and compares side by side before reporting. Asset pipeline order: reference-director (turnaround) -> modeler
-> reference-director (motion clips, animated assets) -> rigger-animator -> qa. Found in run 1 (T011/T038).

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
