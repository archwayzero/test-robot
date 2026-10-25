# Blender -> Godot asset contract

Agents must verify items marked (verify) against the installed Godot and Blender versions and fix this file via the orchestrator.

## Layout
- Source: `blender/models/<asset>/build.py` -> `<asset>_model.blend`; `blender/rigs/<asset>/rig.py` -> `<asset>_rig.blend`
- Exports: `godot/assets/<asset>/model/<asset>.glb` (static), `godot/assets/<asset>/rig/<asset>.glb` (rigged + animations)
- Asset ids: snake_case, identical across folders.

## Provided (external) models
- Original kept unmodified in `blender/models/<asset>/source/` (DVC). The modeler's `conform.py` produces the
  standard `godot/assets/<asset>/model/<asset>.glb`; every later step (reference, rig, QA) uses only that file.
- Any rig or animation inside the original is ignored unless RIGGING_ANIMATION.md says to keep it.
- Check the generator's license terms for commercial use before shipping (human responsibility).

## Units and axes
- 1 Blender unit = 1 meter; origin at the asset's logical pivot (feet for characters); scale applied (1,1,1), rotation applied.
- Export via tools/blender/export_gltf.py (GLB, +Y up, modifiers applied). Forward direction in Godot is -Z.

## Geometry and materials
- Triangle budget per asset: from docs/specs/ASSETS.md. Normals consistent; no n-gons on deforming meshes.
- Materials: Principled BSDF only; textures packed in the GLB unless the spec says otherwise.
- Collision: add child meshes with Godot import suffixes where needed, e.g. `-col`, `-colonly` (verify).

## Rig
- Single armature named `Armature`; root bone `root`; bones snake_case, side suffix `_l` / `_r`.
- Humanoids should match Godot's humanoid skeleton profile bone names so retargeting works (verify).
- Max 4 bone influences per vertex; weights normalized.

## Animation
- Clip names: `<action>` per asset (e.g. `idle`, `walk-loop`). Looping clips end with `-loop` or `_loop` (verify for installed Godot).
- 30 fps unless the spec says otherwise; frame ranges documented in docs/specs/RIGGING_ANIMATION.md.
- Root motion only if the spec says so.

## Motion reference
- Snapshot: `tools/blender/render_snapshot.py` from the exported model GLB. Record the azimuth that shows the front here: (verify on first asset).
- Reference clips live in `reference/<asset>/<clip>/`, clip names identical to the animation names above.

## Handoff checks (run by the producing agent before committing)
Tri count, bounding box in meters, bone count, clip list with frame ranges. Report them in the task summary.
Then run `python3 tools/qa/check_budgets.py` and include the asset's row; an asset over budget is not done.
