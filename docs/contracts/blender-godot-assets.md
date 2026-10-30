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
- Collision: child meshes with Godot import suffixes: `-colonly` (box/trimesh collision only, mesh removed) for
  static environment pieces, `-convcolonly` for convex props. Verified: Godot 4.7 docs, *Node type customization*
  (`-col`, `-convcol`, `-colonly`, `-convcolonly`).

## Rig
- Single armature named `Armature`; root bone `root`; bones snake_case, side suffix `_l` / `_r`.
- Humanoids should match Godot's humanoid skeleton profile bone names so retargeting works (verify).
- Max 4 bone influences per vertex; weights normalized.

## Animation
- Clip names: snake_case `<action>`; looping clips end with `_loop` (e.g. `walk_loop`). Godot 4.7 treats names
  that start or end with `loop`/`cycle` as looping, BUT by default it also strips that suffix (`walk_loop` arrives
  as `walk`; found in T013). Each rig's `.glb.import` therefore sets `use_name_suffixes=false` and an explicit
  `settings/loop_mode` per animation (linear for `_loop` clips, none otherwise), so Godot keeps the exact names.
  Consumers reference the full names.
- 30 fps unless the spec says otherwise; frame ranges documented in docs/specs/RIGGING_ANIMATION.md.
- Root motion only if the spec says so.

## Motion reference
- Snapshot: `tools/blender/render_snapshot.py` from the exported model GLB. Record the azimuth that shows the front here: (verify on first asset).
- Reference clips live in `reference/<asset>/<clip>/`, clip names identical to the animation names above.

## Handoff checks (run by the producing agent before committing)
Tri count, bounding box in meters, bone count, clip list with frame ranges. Report them in the task summary.
Then run `python3 tools/qa/check_budgets.py` and include the asset's row; an asset over budget is not done.

## Asset: hero (run 1)
- Provided original: `blender/models/hero/source/hero.glb` (Tripo, 19,001 tris, 0.98 m tall as delivered, no rig).
- **The provided mesh is upper body only** (found in T011): head/hood, torso, arms, backpack; both legs end in capped
  stumps at mid-thigh. Arms hang down (I-pose). Front faces glTF +Z (needs a 180 deg turn to face -Z).
- **Full-body reference (human-provided):** `reference/hero/full_body.png` (side view; DVC via T037). Lower body:
  armoured, rust-stained thigh plates down to the knee; thin mechanical shins bent backwards (digitigrade, reverse
  knee/hock); feet are reverse-C hooks of three nested curved blade tines: they leave the hock going BACKWARD,
  arch at about hock height (outer tine's rearmost point ~0.85 H behind the hock, H = hock height), sweep down and
  hook FORWARD at ground level, tips landing under or just ahead of the hock; the outer arc is longest and lowest
  (measured in reference/hero/full_body.md).
- **Turnaround (T038):** `reference/hero/turnaround/` (8-angle stills `full_*.png`, `legs_*.png`, NOTES.md). The
  modeler renders the model at the same angles and compares per angle. Only 90 deg is the real source view; the
  others are AI interpretations (listed inventions in NOTES.md are ignored); `full_body.png` wins on conflict.
- Conform (modeler, `blender/models/hero/conform.py` -> `hero_model.blend`):
  - Keep the Tripo upper body's look and topology; generate the lower body from scratch to match the reference
    (thigh plates continuing the existing stumps, hock joint, shins, three-tine blade feet) and attach it as part of
    the same single mesh object (seam closed at the stumps, no gap visible from the game camera).
  - Leg materials match the existing dark rusted metal (reuse the Tripo material/texture where UVs allow, or a
    second PBR material with procedurally baked textures <= 2048 px; at most 2 materials total).
  - Height: head top (hood) at **1.75 m** with the blade tips/contact points at y = 0 (stand capsule stays 1.75).
    Feet at origin, facing -Z in Godot; transforms applied; textures <= 2048 px; standard PBR (drop
    `KHR_materials_volume`, `FB_ngon_encoding`). Total <= the hero triangle budget (docs/qa/budgets.json); reduce
    the upper body only if the legs do not fit.
  - Export `godot/assets/hero/model/hero.glb`.
- **Final model (T011, PR #37):** 19,949 tris, 2 materials, 60/64 MB textures. Each leg is ONE continuous mesh from
  under the hip armour to the blade tips (the earlier "separate rigid piece per bone" idea is revoked; it produced
  disjointed legs). Measured joints (Blender coords, front = +Y, left side; mirror x for right): hip
  (-0.11, 0.0686, 0.8708), knee (-0.1303, 0.0834, 0.4471), hock (-0.1413, 0.0238, 0.336), ankle/tine root
  (-0.1531, -0.048, 0.2233); shin 30 deg back from the thigh. Reviewer-scored 10/10 on structure vs full_body.png.
- Rig notes for the rigger-animator (human decision, T011): rig in the delivered I-pose (no A-pose source will be
  provided). Isolate arm and torso weights at the armpits (no torso deformation when the upper arm moves).
  Optionally re-rest to A/T via the armature. Legs are digitigrade: thigh, shin, an extra metatarsal/hock bone and a
  foot/toe bone per leg so foot contact and stride work; blended weights across knee and hock on the continuous
  leg, blades rigid on the foot; locomotion clips keep the blades planted without sliding.
- **Final rig (T013, PR #41):** 23 joints, I-pose rest (not re-rested), `godot/assets/hero/rig/hero.glb`, built by
  `blender/rigs/hero/rig.py`, checked by `blender/rigs/hero/qa/check_rig.py`. Clip lengths: idle 4.0 s, walk 0.8,
  jog 0.6, crouch_idle 4.0, crouch_walk 0.8 (0.8 m stride; 1.0 m did not fit the 1.25 m top with knees clear),
  crawl_idle 3.0, crawl 1.2, jump 1.267 (takeoff frame 1, touchdown frame 25 = 0.80 s vs 0.816 s physics; start it
  at frame 0 when `jumped()` fires). Tops: stand <= 1.751, crouch <= 1.234, crawl <= 0.695 m. QA in Godot: T014.
- Clips (rigger-animator), 30 fps, in-place (no root motion):
  `idle_loop`, `walk_loop`, `jog_loop`, `crouch_idle_loop`, `crouch_walk_loop`, `crawl_idle_loop`, `crawl_loop`, `jump`.
  Walk cycle stride should match `PlayerController.WALK_SPEED` 1.6 m/s, jog 4.0, crouch walk 1.0, crawl 0.5.

## Asset: crypt_kit (run 1)
See docs/contracts/crypt-kit.md (pieces, dimensions, clearances, materials).
