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

## Asset: hero cloak (2026-11-06, decision D18)
Human direction: docs/specs/ASSETS.md and RIGGING_ANIMATION.md "hero cloak". References (human-provided, DVC via
T043): `reference/hero/cloak_front.png`, `reference/hero/cloak_backside.png`. They are a historical draped costume. Take
the cut, fold language and colours from them, not the figure.

**Model (modeler, extends `blender/models/hero/conform.py` -> `hero_model.blend` -> `godot/assets/hero/model/hero.glb`)**
- Two cloth layers, fitted over the hero's I-pose rest:
  - **Mantle**, white. Draped over both shoulders and the upper arms, with the cascading vertical folds and zigzag hems of the
    references. The hem is about knee height at the front and longer at the sides. It sits under the loosened hood at the
    neck. Arms stay free from the elbow down.
  - **Cloak**, gray. Hangs from the shoulders under the mantle, is **open at the front** (the blade legs come through the
    opening), and is **floor length at the back** with a slight train. The hem clears the floor by 2-4 cm in the rest pose.
    A lighter trim band at the hem, as in the references, is optional.
  - Both layers are worn **under the backpack**. The backpack and its straps stay on top and visible.
- **Hood:** loosen the existing hood a little to match the drape of the references: a deeper, softer fall around the face,
  neck and shoulders. Keep its material. The head top (hood) stays <= 1.78 m.
- **Colours:** matte fabric, metallic 0, roughness 0.85-0.95. Mantle albedo is about sRGB (215, 210, 198), off-white
  (pure white blooms under the lamps). Cloak albedo is about sRGB (105, 105, 108). Both layers are double-sided (glTF
  `doubleSided`), because the inside shows when the cloak flares.
- **One** new material for both layers. The colour comes from a UV region of one small texture set, or from the albedo
  multiplied by a texture: <= 1024 px, adding <= 4 MB to the uncompressed texture measure. This gives 3 materials total,
  3/4 draw calls. Keep the hero a single mesh object, so it stays one skinned MeshInstance3D.
- **Triangles:** the whole hero stays <= 20,000 (budgets.json; it is 19,949 now). The cloth needs about 3,000-4,500
  triangles, with enough rows down its length to bend smoothly. Pay for them in this order:
  1. delete body faces that are always hidden under the mantle and cloak (shoulders, upper chest and back under the
     mantle);
  2. use limited-dissolve or planar decimation on the Tripo upper body, away from the face, hood edge and backpack
     silhouette;
  3. then reduce the cloth.
  The legs keep their T011 shape.
- **Self-check:** render front, side, back and three-quarter views next to the references and `full_body.png`. Nothing
  passes through the body in the rest pose, and no hole shows where faces were removed.

**Rig and motion (rigger-animator, extends `blender/rigs/hero/rig.py`)**
- Cloak bones are chains parented to the spine or chest (and the upper arms for the mantle front, if needed). The total
  is **<= 64 joints** (23 now). Use at most 4 weights per vertex. The body skinning stays as T013.
- **Motion is baked from Blender cloth simulation into the cloak bones.** There is no runtime cloth and no shape keys.
  Simulate with body, leg, backpack and floor colliders, then key the bones to follow the simulated cloth, for example
  with damped-track or stretch-to bones on vertex-parented empties, baked with visual keying. Then remove the helpers.
- **The cloth must see the real motion.** The clips are in-place, so during the simulation move the character through
  the world at the clip's speed: walk 1.6, jog 4.0, crouch walk 1.0, crawl 0.5 m/s. For `jump`, use the physics arc:
  up at 4.0 m/s, airborne 0.80 s, touchdown at frame 25. Bake in the character's local space.
- **Per clip (clip names and lengths unchanged):**
  - `idle_loop`, `crouch_idle_loop`, `crawl_idle_loop`: one settled drape per stance, held still.
  - `walk_loop`: gentle sway.
  - `jog_loop`: the cloak **streams behind** and the mantle hems lift and trail.
  - `crouch_walk_loop`, `crawl_loop`: the cloak drapes over the back and drags behind on the floor.
  - `jump`: the cloak **flares**. Hems lift and spread on the way up and in the air, then fall back by the landing. The last
    frame is close to the idle drape.
  - Loops are seamless. Simulate at least 3 cycles, use the last one, and blend its end into its start. Use the T014
    seam check.
- **Limits checked on every frame of every clip:**
  - the cloth never passes through the body, legs or backpack (a few mm is tolerated);
  - it never goes below the floor (more than 1 cm);
  - the tops including the cloth are: crawl <= 0.73 m (0.75 m ceiling), crouch and crouch walk <= 1.28 m (1.3 m ceiling),
    stand <= 1.78 m.
- Re-export `godot/assets/hero/rig/hero.glb`, then rerun `import_settings.py` and `--verify` (ASTC, T042).

**Known limit (accepted for this pass):** the player's AnimationTree crossfades in 0.15 s. Stopping from a run swaps
the streaming cloak to the still drape within that time. Runtime spring bones (`SpringBoneSimulator3D`) or a longer cloak
blend in `player` can come later, if it looks wrong on the phone.

## Asset: crypt_kit (run 1)
See docs/contracts/crypt-kit.md (pieces, dimensions, clearances, materials).
