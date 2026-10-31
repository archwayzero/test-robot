# crypt_kit replacement maps

How to replace the generated stone maps with hand-made or scanned ones. The kit's geometry and UVs do not change. All numbers
below are also in `atlas.json`, which `build.py` writes; if the two ever differ, `atlas.json` is right.

Scope: `stone_ashlar` (the 2048 atlas) and `stone_floor`. The plaster band stays. The usual route is to replace band A and the
floor only (files in the first table), which leaves the voussoir and plaster bands generated.

## Files

Put any subset in one folder. A missing file means the generated map is used. An unknown file name or a wrong size stops the
build, so a typo cannot fall back silently.

| File | Size (w x h) | Replaces | Colour space |
|---|---|---|---|
| `ashlar_band_a_color.png` | 2048 x 1024 | band A of the atlas colour | sRGB |
| `ashlar_band_a_normal.png` | 2048 x 1024 | band A of the atlas normal | linear (Non-Color) |
| `ashlar_band_a_orm.png` | 2048 x 1024 | band A of the atlas ORM, halved with it | linear (Non-Color) |
| `stone_floor_color.png` | 1024 x 1024 | floor colour | sRGB |
| `stone_floor_normal.png` | 1024 x 1024 | floor normal | linear (Non-Color) |
| `stone_floor_orm.png` | 1024 x 1024 | floor ORM | linear (Non-Color) |
| `stones.json` | | optional, see "Stones" | |

Whole-atlas files are also accepted, and they replace the voussoir and plaster bands too, so only use them to change those:
`stone_ashlar_color.png` and `stone_ashlar_normal.png` (2048 x 2048), `stone_ashlar_orm.png` (1024 x 1024). They need the
bands of the next section at the exact rows, including the wrapped padding of band A. A whole file wins over a band file.

Format: 8-bit PNG, RGB. Alpha is ignored. Do not enlarge the maps: at these sizes the kit is at the budget's 64.0 of 64 MB
(uncompressed upper bound; ASTC 4x4 on device).

## Conventions

- Row 0 is the top of the image. V grows upwards in Blender; the exporter handles the glTF flip.
- Normal: tangent space, glTF / OpenGL, green up (+Y towards the top of the image). X = R, Y = G, Z = B, all 0.5 + 0.5 n. Godot
  imports normals with `compress/normal_map=1`, so only R and G survive; Z is rebuilt.
- ORM: R = ambient occlusion (1 = open), G = roughness (1 = rough), B = metallic (always 0). Occlusion and roughness share
  this one image. Roughness of the generated stone is about 0.86 on the ashlar and 0.70 on the floor.
- Colour carries no baked light direction. Crevice darkening in colour is fine, up to about 10 % (the generated map adds that much
  from its occlusion; a replacement band A is used as delivered). Height soiling is added by COLOR_0 and must not be painted in.
- Keep the colour near the generated mean: sRGB (177, 148, 100) for band A, (146, 133, 112) for the floor, or the review
  exposure and the ring-to-web balance no longer hold.

## Atlas layout (2048 x 2048, rows from the top)

| Band | Rows | Content | Tiles |
|---|---|---|---|
| padding | 0-11 | band A wrapped, written by the build | |
| A | 12-1035 | ashlar, 4 m x 2 m | U and V |
| padding | 1036-1047 | band A wrapped, written by the build | |
| B | 1048-1427 | voussoir strip, arch soffit and ring | no |
| C | 1428-2047 | plaster, vault webs | no |

In the ORM these rows are halved.

## Band A: ashlar tile

- Tile: 4.0 m wide by 2.0 m high, 512 px/m, tiling in both directions. U runs along the wall, V up it. Left and right edges must
  join; top and bottom must join on a bed joint.
- Texel density on walls and piers: 512 px/m, 1:1, no stretch.
- Seven courses, bottom to top. Heights are fixed because the wall's UV splits follow them:

| Course | Height m | From z m | To z m | Band-file row of the top joint | Atlas row of the top joint |
|---|---|---|---|---|---|
| 0 | 0.32 | 0.00 | 0.32 | 860.16 | 872.16 |
| 1 | 0.24 | 0.32 | 0.56 | 737.28 | 749.28 |
| 2 | 0.30 | 0.56 | 0.86 | 583.68 | 595.68 |
| 3 | 0.22 | 0.86 | 1.08 | 471.04 | 483.04 |
| 4 | 0.33 | 1.08 | 1.41 | 302.08 | 314.08 |
| 5 | 0.25 | 1.41 | 1.66 | 174.08 | 186.08 |
| 6 | 0.34 | 1.66 | 2.00 | 0 | 12 |

The bottom of course 0 is the last row of the band (band-file row 1023, atlas row 1035).

- **Bed joints** must be straight, level lines centred on those rows, within 2 mm (1 px), for the whole 4 m. Each wall face is split
  along every bed joint, and each course slides on its own by the U offsets in `atlas.json` (`wall_course_u_offsets`, tile widths,
  per face and 2 m span). A bed joint that wanders breaks at each split. Only course heights are assumed, never stone positions.
- **Head joints** may fall anywhere; stagger them. Courses slide, so
  a straight joint across two courses can appear by chance on a wall; to see where, apply `wall_course_u_offsets`. The generated
  map keeps them at least 5 cm apart; a replacement is not checked for this.
- **Stone size**: 0.35-1.0 m long, course height tall. Mortar 1.0-1.5 cm wide (generated: 1.25 cm), and about the same tone along
  every bed joint, because the two sides of a split come from different stones.
- **Top course**: stones spanning 0.35-1.20 m and 1.55-2.40 m along U must be plain: the capitals map onto them, and no joint may
  cross them. They also need to be neither pale nor dark landmarks.
- **No course stripes**: every course must have about the same mean tone (check_kit: all seven courses, linear luma, brightest minus darkest under 12 % of the
  mean). Each course slides on its own, so a darker course is the one thing that lines up from wall to wall.
- A pale or dark landmark stone repeats every 8 m at worst along a wall, and every 4 m without the assembler's alternation.

## Stones: `stones.json`

Each low-ceiling rubble block maps inside one stone, so that no joint crosses a block. The stones come from the generated map
unless the folder has `stones.json`: a list of `[u0, u1, z0, z1]` in metres in band A, u1 may pass 4.0 (wraps). `atlas.json`
records the generated list as `band_a_stones_m`. Without the file a replacement map still builds, but joints will cross rubble
blocks where its stones differ. The rock's shape does not change with this list, only its UV.

## Floor

Full tile: 4.0 m x 4.0 m, 256 px/m, 1024 x 1024, tiling in U and V. The floor piece is never rotated, so any orientation works. Keep
straight joints under 1.5 m (generated: 1.2 m), and put no joint along the tile edge, or every cell border shows.

## Rebuilding

```
python3 blender/models/crypt_kit/run_pipeline.py --import --maps <folder>
```

This builds with the maps, exports, runs check_kit, deletes `godot/.godot`, imports twice and verifies ASTC 4x4 from the `.ctex`
headers. A trial that must not touch the kit:

```
blender -b --factory-startup -P blender/models/crypt_kit/build.py -- --maps <folder> --out-dir .captures/<name>
```

`python3 blender/models/crypt_kit/qa/test_replacement_maps.py` runs this path end to end on trivial maps, under `.captures/t015/`.
check_kit tests seams, course splits, stripes and lags on the result. The head joint check applies only to generated stones.
Then commit the changed binaries through DVC as usual. Keep the source maps out of git.
