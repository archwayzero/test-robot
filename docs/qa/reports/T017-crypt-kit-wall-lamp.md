# T017 QA: crypt_kit and wall_lamp, assembled in the seed maze

**Overall: PASS.** Rerun on the T039 kit. Supersedes the FAIL at 1ee652c: its 3 defects are fixed and proved fixed.
All 59 tests pass and the budget check exits 0. Nothing here blocks T018. What remains is T018 settings and low look notes, listed below.
The accepted look, the kept lamps and the lamp's 8.5 were not reopened, and nothing was scored against crypt.jpg.

Build under test: `crypt_kit.glb` sha256 97ae6f9bcaec05ee (md5 3eb64a50), `wall_lamp.glb` md5 0c0bbca3 (unchanged), seed 20261025, Godot 4.7.2.
Tests on the clean import of this build: `godot/.godot` deleted, imported twice.
Captures: `capture.py --mode accurate`, Forward Mobile on llvmpipe, 1280x590. `cpu_rendered: true`, `accurate_fell_back_to_opengl: false`, no errors in any run.
All frame numbers below are counts. Nothing here measures device performance.

## Results by test group

| Group | Result | Numbers |
|---|---|---|
| Static budgets (`T017-budgets.md`) | PASS | score 100.0; crypt_kit 4552/21000 tris, 14/14 primitives, 64.0/64 MB upper bound; wall_lamp 880/1000, 2/2, 4.02/16 MB |
| Full test run | PASS | 59 passed, 0 failed, 8 files |
| `crypt_geometry_test.gd` | PASS | 28 of 28 |
| `crypt_kit_test.gd` | PASS | 11 of 11 |
| Hero, maze, minimap, movement, save, touch | PASS | 20 of 20 |
| ASTC headers | PASS | all 10 kit and lamp textures: format 35 (ASTC_4x4), data_format 0, full mips |
| Collision planes | PASS | floor 0.000, wall face 0.300 from the edge, ceilings 0.750 and 1.300 |
| Arch collision winding | PASS (was FAIL) | all 96 faces outward; 24 of 24 soffit faces |
| Arch crown by ray | PASS (was FAIL) | collision 3.900, render 3.900, vault 4.148 |
| Rays under an arch | PASS (was printed only) | of 720: 0 end in masonry (was 86), 0 pass the soffit (was 88) |
| Camera and jump under an arch | PASS | 720 sphere casts 0 in masonry; 24 real camera samples 0 in masonry; capsule top 2.600 m, soffit 3.295 m |
| Stances in low cells, real player | PASS | a standing player stops at z=27.698 at the edge z=28.0 |
| Free height under arches | PASS | 3.209 m at +-1.35 m over 427 arches (the 4.150 before was the reversed top face, not a clearance) |
| Pier top face | PASS (was FAIL) | 2 top triangles at y 2.2 |
| Room fan first-hit back faces | PASS (was FAIL) | 0 of 573120 (was 42) |
| Rubble flipped edge pairs | PASS (was pinned) | crouch 0, crawl 0 (was 3 and 10) |
| Rubble first-hit back faces | PASS (was FAIL) | 0/351100 room, 0/702200 neighbour (was 75 and 33) |
| Back-face render diff | PASS | 0-3 pixels in each of 10 views (pier was 46-1151, rubble 1-222) |
| Assembly rules | PASS | floor 400, vault_bay 394, wall 401, arch 439, ceiling_crawl 4, ceiling_crouch 2, pier 441, lamps 89 |
| No holes, ray fan | PASS | 0 of 573120 rays escape |
| No holes, rendered on magenta | PASS | 0 void pixels in 38 views, including every seam, far and lamp view; control view 755200 of 755200 |
| Lamps on the wall face | PASS | 89 of 89 |
| Omni lights per mesh | PASS for one piece | worst piece 5, worst 4x4-cell chunk 14, Mobile limit 8 (T018 note) |

## What changed since 1ee652c

Kit (T039):
- Arch collision wound outward: all 96 faces.
- Pier: top cap added (120 -> 122 tris), first ring moved from 0.35 to 0.32 m (read from the GLB).
- Crouch and crawl ceilings: flipped pairs removed.
- Stone restored, new textures.

Tests:

| Pin or change | Old | New | Why the new value is correct |
|---|---|---|---|
| `test_kit_counted_vs_rendered_primitives` | 4550 | 4552 | The pier's 2 cap triangles. `check_budgets.py` independently reports 4552, and the per-piece print shows pier 122 |
| `test_rubble_flipped_edge_pairs_match_the_known_count`, renamed `test_rubble_has_no_flipped_edge_pairs` | 3 and 10 | 0 and 0 | T039 set out to remove the flips, and the mesh now measures 0 and 0, confirmed by 0 first-hit back faces in the assembled rooms. Any pair's location is in the failure message. `_check_flips_at_boundary` removed: with an expected 0 it could never run |
| `crypt_assembly.gd` `vertex_color_srgb` | true | false | Contract: keep it false |
| `crypt_preview.gd` `vertex_color_srgb` (not in the brief) | true | false | Its own export overrode the assembler default, so the captures would still have used true |

No test hard-coded the old pier ring, the pier's triangle count or any top-course handling, so those needed no change. 4550 was the only stale number.
The full maze figure in this report moves from 909,396 to 910,278 tris (441 piers x 2 = 882).

Added, all stricter than before:
- `test_arch_collision_all_faces_outward`: the first report's "all 96 reversed" claim was only measured with a throwaway script.
- `ray_in_masonry` and `ray_past_soffit` are now asserted in the arm fan. They were printed only.
- `test_assembly_rules` asserts `vertex_color_is_srgb` is false.

## Proof that changed tests can fail

Run in a throwaway copy of the project under `.captures/t017/oldkit/`, deleted afterwards. The kit path was not touched.

Pre-T039 GLB (md5 fff6162c) against the final tests: **50 passed, 9 failed**.
| Test | Result on the old GLB |
|---|---|
| `test_kit_counted_vs_rendered_primitives` | expected 4552, got 4550 |
| `test_rubble_has_no_flipped_edge_pairs` | expected 0, got 3; expected 0, got 10 |
| `test_arch_collision_all_faces_outward` | 96 reversed of 96 |
| `test_camera_arm_fan_stays_out_of_arch_masonry` | 86 in masonry, 88 past the soffit |
| `test_arch_collision_winding` | 24 reversed |
| `test_crowns_collision_and_render` | 4.15, expected 3.9 |
| `test_no_first_hit_backfaces_in_rooms` | 42 |
| `test_pier_capital_has_a_top_face` | 0 top triangles |
| `test_rubble_visible_underside_has_no_first_hit_backfaces` | 75 and 33 |

Mutation `vertex_color_srgb := true` in the same copy: `test_assembly_rules` fails on "contract: vertex colour is linear" (10 failed in total, the 9 above plus this one).
The tests were also run unchanged on the T039 kit first: 56 passed, 2 failed, and those 2 were the pins above. So no other test needed changing.

`test_real_player_camera_under_arch` now counts through the plain helper `_masonry_hit` (TEST_PLAN: no `if` after an await). Temporary mutation, restored: the helper tests a known masonry point instead of the camera. Result: 24 of 24 in masonry, "expected 0, got 24", 58 passed, 1 failed. The restored file passes 59 of 59.

## Defects A, B, C: closed
A (arch collision), B (pier top) and C (rubble flips) are fixed, with the numbers in the table above. The rule from the first report that rays above 2.2 m under arches are wrong no longer applies.

## Open findings

### D. Draw calls. A requirement on T018, not an asset defect.
See "Counts". Raw counts are unchanged; the occluder conclusion is corrected.

### F. Hairline at pier and wall. Low, cosmetic. Worse than first reported, not a T039 regression.
It is the deliberate 2 mm step (`PIER_PROUD`), not z-fighting and not a hole: 0 magenta pixels.
In the 16 m view (`seam_far_16m_a`, fov 12) it reaches pure white, 255,255,255, as dashes along the pier edge. The first report called it pale and did not note the white.
**Cause proved: lamp specular.** Pixels with all channels above 170 in the left 440 columns:
| Build | Pixels |
|---|---|
| 1ee652c | 359 |
| T039 | 339 |
| T039, `light_specular = 0` | 0 (brightest 129) |

The zoomed fov overstates it. At fov 60-70 it is a faint pale line (`wall_frontal_lit`, `lamp_1m`). T018's specular setting should handle it together with G. Lamps here cast no shadows, so light through walls may add to it; not proved.

### G. White cap on the lamp font. Low, T018 setting.
Still there at 0.5 and 1 m, small by 2 m. Gone with `light_specular = 0` (`run2_nospec/f0006.png`), which also makes the iron read darker and more matte.

### H. Speckled dark dots under grazing light. Look note, no action.
Not re-measured. Same appearance at grazing angles.

### I. New note: a stone changes tone at the pier/wall seam. Low, look note.
Where a block crosses the pier/wall line, one half can be noticeably paler than the other (`collinear_pier_seam`, 0.9 m, fov 30). The 1ee652c crop `crops/seam.png` shows the same, so it is not new, but it was not reported. It reads as a vertical cut through a stone at close range, and as slightly mismatched blocks in `wall_frontal_lit`. Likely the different U of the pier and wall faces; not proved. No action required under the accepted look (modeler, if ever revisited).

### Golden wedges on the crawl ceiling
Still visible. Not flips: the back-face diff in those views is 0 and 1 pixels. They are facets catching lamp light, and with no lamp shadows, light through rock remains a likely cause (not proved). Check in T018's real lighting.

### E. Top course brighter: resolved
Mean grey by height on the unlit frontal wall, same view and `srgb` false:
| Height m | 1.30-1.66 | 1.66-2.00 | 2.00-2.40 |
|---|---|---|---|
| 1ee652c | 34.6 | **45.5** | 35.5 |
| T039 | 42.1 | 43.2 | 42.0 |

## What Mobile shows that the Cycles review did not
Crops below compare different views and different light rigs, so they are indicative. QA lamp values are assumptions, not T018's.

| Surface | Cycles flat | Cycles lit | Mobile |
|---|---|---|---|
| Stone, luma (sRGB 0-255) | 111.6 | 135.9 | near lamp 173.3; 1 m below 88.4; unlit 51.0 |
| Stone, R/B | 2.01 | 2.51 | near lamp 1.86; 1 m below 2.12; unlit 1.73 |
| Plaster, R/B | 1.31 | 1.36 | lit 1.30; away from the lamp 1.11 |
| Floor, R/B | 1.43 | 1.72 | under a lamp 1.56; away 1.26 |

1. **Brighter near lamps, by a lot.** Up to 197.5 luma at 0.5 m, against 135.9 in lit Cycles, with 5.8-8.6% of those crops clipped. Cycles clips 0%.
2. **Not warmer by measure.** Near the lamps stone looks like warm cream, but R/B is lower than Cycles (1.73-1.86 against 2.51), because the highlight washes it out. So it reads paler, not more saturated.
3. **Far dimmer away from lamps.** Mobile has real falloff where the Cycles rig is even: 51.0 on an unlit wall. Corridors end in near-black.
4. **Cool ambient, unseen in Cycles.** Away from lamps the plaster turns lilac (R/B 1.11) and the floor violet-grey (1.26). Mobile plaster also reads white near lamps, where Cycles shows cream.
5. **Specular on lamps and edges.** G and F do not appear in the Cycles review.

Against the first Mobile run with `srgb` false, T039 stone is about 9-11% brighter (unlit 46.7 -> 51.0, lit 79.3 -> 88.4). R/B is unchanged (1.73 -> 1.73, 2.18 -> 2.12), so it did not get warmer in Mobile.

## Lamp at 1-4 m
Mounted correctly at every distance, flame legible, no floating and no gap at the wall.
- 1 m: font sheen visible, stone behind is washed pale.
- 2 m: sheen small, hot patch on the wall reads as lamp glow.
- 3-4 m: clean silhouette, warm pool on the wall.
Stills only.

## Far views and seams
`far_corridor_game`, `far_corridor_level`, `far_corridor_zoom`, down the seed's longest run (32 m): no holes, no z-fighting seen, courses and arches stay coherent. The far end goes to black. Gaps: none.
Pier ledge: filled, no void. Its top reads slightly mauve against the stone at very close range (`pier_top_close`); not visible at game distance.

## Counts against 300k triangles and 200 draw calls
Full maze: **910,278** tris, 3.03 x 300k (kit 831,958 + 89 lamps 78,320).
vault_bay 378,240, arch 351,200, pier 53,802, wall 37,694, ceilings 7,022, floor 4,000.

`check_budgets` counts 14 primitives because it includes the 7 colonly meshes. The imported scene renders 7 (measured by test). So 14/14 is at the limit on paper with real headroom: 7 of 14.

Textures: 64.0/64 MB is exactly at the limit, but it is the uncompressed RGBA + mips upper bound (48 MB x 4/3). The ASTC_4x4 import products are 16.0 MiB on disk for the kit and 1.05 MB for the lamp, including mips. Device memory is not measured.

Engine counters, CPU renderer, 1280x590, unmerged assembler. Raw at hold 3. Occluders at hold 16, after 3 warm-up views; hold 16 equals hold 32 in every view, draw calls and tris. Sources: `.captures/t017_review/occ16_counters.json`, `occ32_counters.json` (first 6 rows); `.captures/t017/fix_occ16_counters.json`, `fix_occ32_counters.json` (all 8 rows, and the first 6 match the review to the digit).
| View | Draw calls | Tris | With box occluders: draw calls | Tris |
|---|---|---|---|---|
| corridor centre | 239 | 50,425 | 86 | 22,008 |
| corridor wall-hug | 294 | 59,797 | 97 | 25,378 |
| pier close | 1225 | 204,156 | 20 | 9,774 |
| mixed edge | 925 | 144,714 | 137 | 32,864 |
| long view, wall face | 1831 | 282,568 | 52 | 19,042 |
| far corridor | 1554 | 213,317 | 186 | 34,210 |
| frontal lit wall (new) | 1741 | 273,134 | 61 | 20,464 |
| far corridor, level camera (new) | 1560 | 213,809 | 167 | 29,870 |

**Settled range: 20-186 draw calls.** Every sampled view is under 200. The 3 warm-up views, `lamp_2m`, `lamp_3m`, `lamp_4m`, read 67, 88 and 93.

**Correction (T017 fix pass).** The occluder column at c16c50e was read at hold 8 and was not settled. Its conclusion that the long corridor stays over 200 was wrong: that view settles at 186, and the 236 was a hold 8 reading. The hold 8 numbers themselves were read correctly and the reviewer reproduced them. Against hold 16, 6 of 9 views change at hold 8: first view 494 -> 67, wall face 153 -> 52, far corridor 236 -> 186, pier 46 -> 20, corridor 90 -> 86, mixed edge 135 -> 137.

**Correction to the first report.** Its occluder column (204, 259, 168, 128, 249) was read at hold 3, before occlusion had settled. The first report's "exceed 200 in 3 of 5 views" does not hold: 5 of 5 of those views are under 200 once settled.

Occlusion needs more than 8 frames after a camera cut or load, and is stable by 16 in the sampled views. Occluders do nothing in the very first frames: at hold 3 the first 3 views read raw counts, and at hold 8 the first view still does (494, its raw count). Cause unknown, and it is not known whether the lag follows frames or clock time: these are CPU frames at `--fixed-fps 30`, so the frame count may not carry over to a device.

Limits of this evidence:
- **Coverage.** 11 of 39 views have occluder counts. They include the 4 heaviest raw views. The other 28 are unmeasured, the heaviest being `top_course` at 1375 raw.
- **The spike.** The load case is direct: the first view of a run. The teleport case is weaker, because it comes from camera cuts between preview views. No real teleport or respawn was measured.
- **Resolution.** Settled counts depend on it. A first attempt at the same 11 views ran at `capture.py`'s default `--resolution 960x540` by mistake, and read lower: far corridor 128 against 186, level camera 164 against 167, range 16-164. Hold 16 equalled hold 32 there too. Those numbers are not used above. So 186 is a 1280x590 number, not an iPhone one.

## Notes for T018
1. `vertex_color_is_srgb = false`, `vertex_color_use_as_albedo = true`, texture filter 5.
2. Merge or MultiMesh by chunk and add occluders: 1831 raw draw calls against 200. Box occluders alone settle at 20-186 in the 8 views of "Counts", under 200 in all 11 sampled views of 39, at 1280x590. Merging is still what covers the frames before they settle.
3. New: occluders need more than 8 frames after a load or camera cut, stable by 16 in the sampled views (see "Counts"). Plan for raw counts in those frames. Measure a real teleport in the game: the evidence here is camera cuts in a preview.
4. Omni per mesh: a 4x4-cell chunk reaches 14 against a limit of 8, single pieces 5. Pick chunks so no chunk passes 8.
5. Lower `light_specular` on lamp omnis. New: that handles both the font cap (G) and the white hairlines (F). 0 is proved to remove both; no value between was tried.
6. Lamps here have shadows off, so light may pass through walls. Check it in the real scene, including the crawl ceiling wedges.
7. New: tune the lighting in Mobile, not from the Cycles review. Near lamps it clips and desaturates, and away from them the ambient is cool (lilac plaster, violet floor).
8. Removed: the old note on rays above 2.2 m under arches.

## vertex_color_is_srgb
`false` is now the assembler default and is asserted by a test. The evidence is the 1ee652c table: closer to Cycles in 4 of 5 wall bands. That table was not repeated on T039.

## Not verified
- Device frame rate, GPU cost, memory: not measurable here. M3.
- ASTC on a real GPU: headers only in this run. The PSNR decode from the first run was not repeated on the T039 textures. The captures most likely used the desktop BPTC import; not confirmed.
- Motion: stills only, so hairline crawl, normal-map shimmer and flicker are unseen. The 2-frame flicker comparison at 16 m was not repeated. No video made; not requested.
- F, I and the wedges: causes as marked. H not re-measured.
- Other seeds. Lamp energy, range and colour are QA's assumptions.
- Physics engine is `DEFAULT`; the arch collision is now right for rays too, but Jolt was not tried.
- TEST_PLAN camera points P1-P4 are for the M2 frame-count pass with the real maze.
- The real camera covers only the 24 arch samples; pier and rubble views use hand-placed cameras.

## Images (not committed, under `.captures/t017/`)
`run2_a/`, `run2_b/`, `run2_c/`: all 39 views, hold 3, each with `contact_sheet.png`; view order in `run2_<x>_counters.json`.
`run2_mag1/`, `run2_mag2/`: magenta holes. `run2_cull0/`, `run2_cull1/`: back-face diff. `run2_nospec/`: specular off. `run2_occ/`: occluders, hold 8. `fix_occ16/`, `fix_occ32/`: occluders, 11 views. `fix_wrongres_960x540/`: the 960x540 attempt, not used for the table.
Logs: `run2_tests_final.log`, `run2_tests_oldkit.log`, `run2_tests_mut_srgb.log`, `run2_baseline_tests.log`, `fix_tests_final.log`, `fix_tests_mut_helper.log`.
Older captures in the same folder are the pre-T039 build, kept for comparison. Cycles review: `.captures/t039/pass4/`.
`crypt_preview.tscn` takes env `T017_PREVIEW`, for example `hold=3,only=lamp_1m+lamp_4m,tag=x`.
