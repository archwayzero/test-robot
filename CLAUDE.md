# Game project: Godot (game) + Blender (assets)

You run in WSL2 under Claude Code's sandbox: shell commands can only write inside this project, cannot see
Windows drives, and can only reach GitHub, the project's S3 bucket and ComfyUI (localhost:8188). There is no GPU
inside the sandbox. Enforcement is done by the sandbox and hooks, not by this file:
if a hook blocks you, do not look for a workaround. Report it.

## Structure
- `godot/`            Godot project. Code lives in decoupled modules: `godot/modules/<name>/{public,internal,tests}`.
- `blender/models/`   model generator scripts and .blend files (modeler agent)
- `blender/rigs/`     rig/animation scripts and .blend files (rigger-animator agent)
- `godot/assets/<asset>/{model,rig}/`  exported .glb files consumed by Godot
- `reference/<asset>/<clip>/`  generated motion reference videos + notes (reference-director agent)
- `reference/map/<image>/`  reference map/environment
- `godot/tests/`      end-to-end tests (qa agent); module unit tests live in each module's `tests/`
- `docs/qa/`          TEST_PLAN.md + budgets.json (orchestrator, human-approved), reports/ (qa)
- `docs/`             architecture, workflow, contracts, and the human-written specs in `docs/specs/`
- `docs/module-map.json`  who may write what, binary extensions (locked policy)
- `docs/modules.json`  module list and dependencies (orchestrator, via tools/new_module.py)

## Roles
- `orchestrator` (main session): architect and dispatcher. Never implements internals.
- `modeler`, `reference-director`, `rigger-animator`, `module-dev`, `qa`, `reviewer`: each works only in its own scope.
  `module-dev` is scoped to the module named in its branch `task/module-dev/<module>/<id>-<slug>`.

## Platform
Target and constraints: `docs/specs/PLATFORM.md` (iOS, minimum iPhone 12). Preview on the PC host; the final
build happens last on a Mac with Xcode. Use capture.py to SEE scenes (headless Godot does not render). Never report
sandbox FPS or GPU cost as device performance. Push with `git push origin <branch>` (never `-u`).

## Hard rules
1. One task touches one scope. Need something outside it? Stop and report to the orchestrator.
2. Modules talk only through `public/` interfaces of declared dependencies. Interface changes: orchestrator only.
3. Binary assets (.blend, .glb, .png, audio, ...) go through DVC, never git: `dvc add <file>`, commit the `.dvc` pointer.
4. Order: work on `task/<agent>/<id>-<slug>` (or `arch/<slug>`) -> `dvc add` -> `git add` -> `git commit` -> push branch
   (pre-push runs `dvc push` first) -> human merges PR. Never push to main. Never `--no-verify`.
5. Never change git remotes, DVC remotes/config, or files listed as `locked` in the module map.

## Where to look
- `docs/architecture/ARCHITECTURE.md` module model and dependency rules
- `docs/architecture/WORKFLOW.md` task lifecycle, version-control order, what the hooks enforce
- `docs/contracts/blender-godot-assets.md` asset naming, units, export settings
- Module-specific rules: `godot/modules/<name>/CLAUDE.md`

## Commands
- `python3 tools/task.py list|add|start|finish|done`
- `python3 tools/new_module.py <name> "<desc>" --depends a,b`; module tasks: `tools/task.py add <id> module-dev "<title>" --module <name>`
- `python3 tools/qa/check_budgets.py --report docs/qa/reports/<name>.md`
- `python3 tools/qa/net_data_audit.py` (release: what the game contacts and collects)
- `python3 tools/qa/capture.py --scene res://... [--mode fast|accurate]` then Read `.captures/<scene>/contact_sheet.png`
- `python3 tools/qa/record.py --scene res://... --seconds N --out docs/qa/videos/<milestone>/<name>.mp4` (gameplay video for the human)
- `python3 tools/envcheck.py` (tools, isolation, ComfyUI, render devices); `python3 tools/sandbox_selftest.py` (protections)
- `python3 tools/comfy/comfy_client.py ping|run|frames` (ComfyUI at $COMFY_URL)
- `python3 tools/release/make_mac_package.py --version X` (only on merged main; see PROMPTS.md Prompt 4b)
- Headless Blender: `blender -b <file.blend> -P <script.py> -- <args>`
- Headless Godot: `godot --headless --path godot ...`
