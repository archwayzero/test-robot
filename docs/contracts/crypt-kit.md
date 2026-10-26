# crypt_kit contract (run 1)

Owner: orchestrator. Consumers: modeler (builds the pieces), `maze` module (assembles them), `player` (clearances),
qa (budgets). Look reference: `reference/map/crypt.jpg` (Winchester Cathedral crypt): groin-vaulted bays,
semicircular transverse arches on short square piers with simple block capitals, warm sandstone ashlar, plastered
vault webs, worn flagstone floor. Do NOT model the statue in the photo (copyrighted artwork) and no standing water.

## Grid
- One maze cell = **4.0 m x 4.0 m**. `MazeLayout.cell_size_m() == 4.0`.
- Walls sit **on cell edges**, centred on the edge line, **0.6 m thick** (0.3 m into each cell). Clear corridor
  width = 3.4 m.
- Piers (0.6 x 0.6 m) stand on every cell **corner** that touches at least one wall or arch.
- Units: meters, +Y up in Godot, floor at y = 0.

## Heights (from floor)
| Element | Height |
|---|---|
| Pier shaft | 0.0 - 1.9 |
| Capital (block, slightly wider: 0.75 x 0.75) | 1.9 - 2.2 |
| Springing line (arches and vault start) | 2.2 |
| Transverse arch / vault crown (semicircle, radius 1.7) | 3.9 |
| Wall top (meets vault) | 3.9 |

## Clearances (player collision, must match `player` module)
| Clearance | Free height | Who fits | Kit piece |
|---|---|---|---|
| FULL | >= 2.2 (under arches) | stand (hero height, 1.65-1.85) | `vault_bay` |
| CROUCH | 1.3 | crouch (1.0), crawl | `ceiling_crouch` |
| CRAWL | 0.75 | crawl (0.5) only | `ceiling_crawl` |
Stand-up checks in `player` rely on these: a CROUCH cell must block a standing capsule, a CRAWL cell a crouching one.

## Pieces (one GLB: `godot/assets/crypt_kit/model/crypt_kit.glb`, one root node per piece, names exact)
| Node name | Origin | Description |
|---|---|---|
| `floor` | cell centre, y=0 | 4 x 4 m flagstones, top at y=0, 0.2 m thick |
| `wall` | edge centre, y=0 | 4.0 m long (between pier faces 3.4 m + overlap), 0.6 thick, 0-3.9 m, ashlar |
| `pier` | corner, y=0 | 0.6 x 0.6 shaft + capital, 0-2.2 m |
| `arch` | edge centre, y=0 | transverse semicircular arch spanning an OPEN edge between two piers, 2.2-3.9 m, 0.6 deep |
| `vault_bay` | cell centre, y=0 | groin vault covering one cell (two intersecting barrel vaults, springing 2.2, crown 3.9) |
| `ceiling_crouch` | cell centre, y=0 | low collapsed/rubble ceiling insert, underside at 1.3 m, fills to 3.9 m |
| `ceiling_crawl` | cell centre, y=0 | lower insert, underside at 0.75 m, fills to 3.9 m |
Each piece has a `-colonly` child (boxes / simple trimesh) for collision. Vault and arch collision may be coarse;
floor and walls must be exact planes at y=0 and at the wall faces.

## Materials and textures
- At most 2 materials for the whole kit: `stone_ashlar` (walls, piers, arches, low ceilings) and `stone_floor`
  (floor; vault webs may use either). Principled BSDF, procedural in Blender, **baked** to texture maps
  (base colour, normal, ORM) at 1024 or 2048 px, tileable. Texture budget: docs/qa/budgets.json `crypt_kit`.
- A second UV channel (UV2, non-overlapping) on every piece for lightmaps.

## wall_lamp (separate asset `godot/assets/wall_lamp/model/wall_lamp.glb`)
Wrought-iron bracket with an oil lamp/candle, origin at the wall mounting point, light emitter at local
(0, 0.25, 0.35). <= 1,000 triangles, 1 material + emissive flame. The `maze` module places it at `lamp_slots()` at
y = 2.0 and adds the light source; the GLB contains no lights.
