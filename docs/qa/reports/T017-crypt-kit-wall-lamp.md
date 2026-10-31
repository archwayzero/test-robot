# T017 QA: crypt_kit and wall_lamp, assembled in the seed maze

**Overall: FAIL.** 5 tests fail on 3 known asset defects. None is player-visible enough to block T018; see "Blocks T018".
The accepted look (pass 4), the kept lamps and the lamp's 8.5 were not reopened, and nothing was scored against crypt.jpg.

Build under test: `crypt_kit.glb` md5 fff6162c, `wall_lamp.glb` md5 0c0bbca3, seed 20261025, Godot 4.7.2.
Captures: `capture.py --mode accurate`, Forward Mobile on llvmpipe. `cpu_rendered: true`, `accurate_fell_back_to_opengl: false`, no errors.
All frame numbers below are counts. Nothing here measures device performance.

## Results

| Check | Result | Numbers |
|---|---|---|
| Static budgets (`T017-budgets.md`) | PASS | score 100.0; crypt_kit 4550/21000 tris, 14/14 primitives, 64.0/64 MB upper bound; wall_lamp 880/1000, 2/2, 4.02/16 MB |
| Full test run | **FAIL** | 53 passed, 5 failed, 8 files |
| ASTC headers | PASS | every kit and lamp texture is ASTC 4x4 |
| Collision planes | PASS | floor 0.000, wall face 0.300 from the edge, ceilings 0.750 and 1.300 |
| Stances in low cells, real player | PASS | CROUCH refuses standing, CRAWL refuses crouching; a standing player stops at z=27.698 at the edge z=28.0 |
| Assembly rules | PASS | floor 400, vault_bay 394, wall 401, arch 439, ceiling_crawl 4, ceiling_crouch 2, pier 441, lamps 89 |
| No holes, ray fan | PASS | 0 of 573120 rays escape |
| No holes, rendered on magenta | PASS | 0 void pixels in 12 aimed views; control view 755200 of 755200 |
| Lamps on the wall face | PASS | 89 of 89 |
| Omni lights per mesh | PASS for one piece | worst piece 5, worst 4x4-cell chunk 14, Mobile limit 8 (T018 note) |
| Arch collision winding | **FAIL** | defect A |
| Arch crown by ray | **FAIL** | 4.15, expected 3.9 (defect A) |
| Pier top face | **FAIL** | 0 top triangles (defect B) |
| Room fan first-hit back faces | **FAIL** | 42 of 573120, all pier (defect B) |
| Rubble first-hit back faces | **FAIL** | 75/351100 room, 33/702200 neighbour (defect C) |
| New: camera arm fan under an arch | PASS | 720 sphere casts, 0 end in masonry, closest centre 0.154 m from the soffit |
| New: real camera under an arch | PASS | 24 samples, 0 in masonry, highest camera 2.432 m |
| New: real jump at the arch leg | PASS | capsule top 2.600 m, soffit there 3.295 m |

The 5 failing tests stay failing and were not weakened:
`test_crowns_collision_and_render`, `test_arch_collision_winding`, `test_no_first_hit_backfaces_in_rooms`,
`test_pier_capital_has_a_top_face`, `test_rubble_visible_underside_has_no_first_hit_backfaces`.

## Findings by severity

### A. Arch collision is inside out. Medium, latent. A player cannot see or feel it.
The defect is wider than reported at ec6e651: all 96 arch collision faces are reversed, not only the 24 soffit faces.
By group: 24 soffit, 48 on the two depth faces, 20 top, 4 end faces. Wall, floor and ceiling boxes are all outward. Pier reads 22 of 24 on a rough centroid measure, not examined further.

- Player: not felt. The jump's capsule top is 2.600 m; the soffit is 3.295 m at lateral 1.3 m (measured jump) and 3.16 m at the
  1.4 m limit of a capsule against the wall line (computed). The contract's FULL >= 2.2 holds: the soffit at +-1.35 m is 3.23 m (computed).
- Camera: not seen. The arm is a sphere cast, and sphere casts stop on the reversed faces (720 casts, 0 in masonry; 24 real
  camera samples, 0 in masonry). Going up the crown, the sphere stops at 3.742 on both collision and render meshes.
- Rays: wrong. One-sided rays pass the soffit. 88 of 720 rays went more than 5 cm past the render surface and 86 ended in
  masonry. The game's rays do not reach it today: `player.gd` `_ceiling_above` stops at 1.8 m, and the arm and shoulder rays are
  horizontal below 2.2 m. E7 casts at y=0.4. Any future ray above 2.2 m under an arch will be wrong.
- This also means the existing log line "min free height at +-1.35 m 4.150" is the reversed top face, not a clearance.

Fix (modeler), `blender/models/crypt_kit/build.py:1050`:
```python
collision(ob, tris=[pts[::-1] for pts in tris])
```
Not tried here. Afterwards the crown must read 3.9 by ray.

### B. Pier has no top face. Low, cosmetic.
Visible from reachable cameras only as a thin strip on the 0.075 m capital ledge, and it never shows void.
| View (1280x590, hand-placed camera) | Void pixels | Pixels changed by drawing back faces |
|---|---|---|
| game height 2.43 m, fov 70 | 0 | 46 (0.006%) |
| orbit high, 3.3 m | 0 | 94 (0.012%) |
| orbit mid, 2.8 m | 0 | 168 (0.022%) |
| zoomed along the ledge, fov 25 | 0 | 742 (0.098%) |
| 0.65 m from the ledge, fov 40 | 0 | 1151 (0.152%) |

The strip shows neighbouring stone, so it reads as a ledge in shadow. Fan rate: 42 of 573120.

Fix (modeler), `build.py`, in `build_pier` before line 977:
```python
w = cap - 0.006
b.face("cap_top", [(-w, -w, SPRING), (w, -w, SPRING), (w, w, SPRING), (-w, w, SPRING)], <band_a UVs in the capital course>, False)
```
Adds 2 tris per pier, 882 on this seed. Not tried here.

### C. Flipped triangles at the rubble's edges. Low, cosmetic.
10 flipped edge pairs on `ceiling_crawl`, 3 on `ceiling_crouch`, all with |x| or |z| > 1.7, at y 0.9-1.6.
Only 3 of 6 low cells show them (13,0), (9,7), (8,19), each 25 room rays and 11 neighbour rays.
| View | Void pixels | Pixels changed by drawing back faces |
|---|---|---|
| inside the crawl cell | 0 | 3 |
| mixed edge from FULL | 0 | 38 |
| mixed edge, oblique | 0 | 1 |
| aimed at the flip from the room, fov 25 | 0 | 18 |
| aimed at the flip from FULL, fov 25 | 0 | 222 (0.029%) |
| aimed at the flip, fov 70, room and FULL | 0 | 1 and 16 |

The golden wedges on the crawl ceiling are NOT the flips: they do not change when back faces are drawn. They are ordinary facets
catching lamp light, and the lamps cast no shadow in this scene, so light through rock is a likely cause (not proved).

Fix (modeler), `build.py` around line 1519 in `build_ceiling`: make the winding consistent before `b.to_object(name, mat)`, for example
`bmesh.ops.recalc_face_normals`, and make check_kit assert 0 flipped pairs. If a pair is a true fold from `z_of` stretching the side patch,
that needs the corner vertices moved instead. Not tried here. Then `test_rubble_flipped_edge_pairs_match_the_known_count`, pinned at
3 and 10, must change to 0 (qa).

### D. Draw calls over the 200 budget. A requirement on T018, not an asset defect.
This QA assembler draws one node per piece, nothing merged. See "Counts".

### E. Top course is brighter. Low, look note.
Course 6 (1.66-2.00 m, repeats at 3.66-4.00 m) in the base colour: linear luma 0.350 against 0.266-0.291 for the others.
Rendered on an unlit wall: 0.0428, against 0.0305 below and 0.0329 above. Vertex colour is 1.0 there, so it is not soiling.
check_kit's course test skips this course ("the capital course is plain"): 0.043 spread on 6 courses, 0.291 on all 7, limit 0.12.
MAPS.md asks that it be "neither pale nor dark". It sits at lamp height. No action required under the accepted look; the gap in the check is worth knowing.

### F. Lit hairline at pier and wall. Low, cosmetic.
Confirmed: not z-fighting. It is the 2 mm step (`PIER_PROUD`, build.py:75, deliberate), lit along its edge. It renders as a pale hairline, dashed when under a
pixel wide, at 0.9-3 m. No flicker pattern between frames 3 cm apart at close range or at 16 m. Motion was not filmed.

### G. White cap on the lamp font. Low, T018 setting.
Cause proved: it vanishes with `light_specular = 0`. The emitter sits 3.6 cm above the iron's top (0.25 against 0.214). Seen as a bright band on the font top at 0.5 m; the off-specular run was not repeated at 1.4 m.
T018 should lower the omni's specular rather than change the lamp.

### H. Speckled dark dots under grazing light. Look note, no action.
Cause proved: all from the normal map; they vanish with the normal map off (`crops/speckle.png`). Strongest on the wall right beside the camera under a lamp. The albedo's own fine dark
specks are much weaker. Stone realism, so not a failure.

## Other looks
- Webs: 181,161,143 lit in Mobile against 180,162,136 in the Cycles flat render; 149,127,112 in a typical corridor. Cooler than the walls at low lamp light. Fine.
- Piers, capitals: match the walls, crisp undersides, no artefact.
- ASTC: mip 0 of each texture decoded offline. PSNR against the source: ashlar colour 52.1 dB, floor colour 53.5, ashlar ORM 50.2, floor ORM 48.6, floor normal 49.0, ashlar normal 37.9.
  The ashlar normal is the low one, on high-frequency grain; side by side at 3x no block pattern shows. No artefact found.
- Z-fighting: none seen. Gaps: none.

## vertex_color_is_srgb: use false
Wall luma relative to the 0.88-1.39 m band:
| Height m | 0.08-0.30 | 0.34-0.54 | 0.58-0.84 | 2.60-2.82 | 3.10-3.30 |
|---|---|---|---|---|---|
| Cycles flat render (reference) | 0.639 | 0.757 | 0.836 | 0.961 | 0.928 |
| COLOR_0 alone | 0.693 | 0.781 | 0.916 | 0.993 | 0.922 |
| Godot false | 0.402 | 0.700 | 0.736 | 1.035 | 0.799 |
| Godot true | 0.227 | 0.470 | 0.627 | 0.984 | 0.681 |

`false` is closer in 4 of 5 bands, including all three soiled floor bands; in 2.60-2.82 m, where the soiling is slight, `true` is closer (0.984 against 1.035, reference 0.961).
`true` applies the soiling too strongly: true/false at 0.08-0.30 m measures 0.557, predicted 0.610. The values are linear by design
(`build.py` `grime`). The remaining gap to Cycles is probably lighting (unlit Godot wall against even Cycles light); not proved. `crypt_assembly.gd` still defaults to true, so all `srgb_true_*` figures use it.

## Counts against 300k triangles and 200 draw calls
Full maze: **909,396** tris, 3.03 x 300k (kit 831,076 + 89 lamps 78,320). The contract's 730k is out of date.
vault_bay 378,240, arch 351,200, pier 52,920, wall 37,694, ceilings 7,022, floor 4,000.

Engine counters, CPU renderer, 1280x590, unmerged assembler, hold 3:
| View | Draw calls | Tris | With box occluders: draw calls | Tris |
|---|---|---|---|---|
| corridor centre | 239 | 50,333 | 204 | 44,049 |
| corridor wall-hug | 294 | 59,681 | 259 | 53,397 |
| pier close | 1225 | 203,704 | 168 | 35,850 |
| mixed edge | 925 | 144,360 | 128 | 30,912 |
| long view, wall face | 1831 | 281,880 | 249 | 46,282 |

Typical corridor estimate: about 50-60k tris, under 300k. Rays actually seeing surfaces: 14-19k tris from 41-51 instances. Triangles are not the problem; draw calls are.
Wall-only box occluders are required: draw calls still exceed 200 in 3 of 5 views. Merging or instancing must close that.
The first view after load gets no occluder benefit even after 8 frames (`top_course` reads 1375 in both columns), so it is left out above. Cause unknown; first-frame counts with occluders are not reliable.

## Notes for T018
1. `vertex_color_is_srgb = false`, `vertex_color_use_as_albedo = true`, texture filter 5.
2. Merge or MultiMesh by chunk and add occluders; 1831 raw draw calls against 200.
3. Omni per mesh: a 4x4-cell chunk reaches 14 against a limit of 8, single pieces 5. Pick chunks so no chunk passes 8.
4. Lower `light_specular` on lamp omnis.
5. Lamps here have shadows off, so light may pass through walls. Check it in the real scene.
6. Rays above 2.2 m under arches are wrong until defect A is fixed.

## Blocks T018?
| Defect | Severity | Player sees or feels it | Blocks T018 |
|---|---|---|---|
| A arch collision reversed | Medium, latent | No | No, but fix it with T018: one line, and it removes a trap for any new ray |
| B pier top | Low | Barely, a stone-coloured strip | No |
| C rubble flips | Low | Barely, at most 222 pixels when aimed at | No |
| D draw calls | T018 design | Device cost, unmeasured | It is a T018 requirement |
| E, F, G, H | Low | Yes, small | No |

## Evidence each new check can fail
- `_in_arch_masonry`: `test_self_masonry_check_can_fail` (crown masonry true, opening false, outside depth false).
- Arm fan: same helper, and the same fan with rays landed 86 in masonry on the shipped asset.
- Real camera, jump: no broken-asset self-test. They use the helper above and plain numeric asserts; a run where the jump does not happen fails on `rise > 0.3`.
- Void count: control view 755200/755200 magenta.
- Back-face diff: 0 in the control, non-zero in every aimed view.
- pass-1 checks: self-tests in `crypt_geometry_test.gd`, `crypt_kit_test.gd`.
- Cause checks are before/after pairs: `crops/speckle.png`, `crops/fontcap.png`.

## Images (not committed, under `.captures/t017/`)
Mobile, 2.43 m unless noted: `srgb_true_a/` and `srgb_false/` (corridor centre, wall-hug, grazing, top course, lamp at 1.4 and 0.5 m); `srgb_true_a/f0012-14`, `srgb_false_low/` (low-passage cells);
`srgb_true_b/` (mixed edges, flips, capital, vault, pier); `srgb_true_c/`, `srgb_false_c/` (frontal walls, pier seam); `srgb_true_d/` (wall faces); `hole2/` magenta, `hole3/` back faces drawn;
`exp_base/`, `exp_nonormal/`, `exp_nospec/` cause checks; `crops/` (`speckle`, `fontcap`, `seam`, `seamfar`, `astc_compare`). Reference: `.captures/t015/arcade_flat.png`.

Variant scenes are gone: `crypt_preview.tscn` takes env `T017_PREVIEW`, for example `srgb=0,only=wall_hug+lamp_0_5m,tag=x`.

## Not verified
- Device frame rate, GPU cost, memory: not measurable here. M3.
- ASTC on a real GPU: decoded offline only. The captures themselves most likely used the desktop BPTC import; I did not confirm which file loaded.
- Motion: stills only, so hairline crawl, normal-map shimmer and flicker are unseen. No video made; T017 did not ask for one.
- The pier and rubble views use hand-placed cameras near what the arm can reach, not a driven orbit. Only the 24 arch samples use the real camera.
- Fixes in A, B, C are proposals, none built.
- Other seeds. Lamp energy, range and colour are QA's assumptions, not T018's.
- Physics engine is `DEFAULT`; a move to Jolt would need the sphere-cast evidence in A repeated.
- TEST_PLAN camera points P1-P4 are for the M2 frame-count pass with the real maze.
