# Static budget report (2026-10-31T08:04:31+00:00)

Platform: ios (min device: iPhone 12)
Budget status: APPROVED FOR RUN 1 ONLY (human, 2026-10-25: 'create the game to the best of your ability'). Values marked estimate in notes have no authoritative source and must be validated on the device (M3). QA agents may not edit this file.
**Static budget score: 100.0** | **PASS**

Measured from exported .glb files only. Texture memory is an uncompressed upper bound; draw calls are estimated as mesh primitives. Not a measurement of device performance.

| asset | src | tris | draw calls (est) | joints | max tex | tex MB (ub) | anims | result |
|---|---|---|---|---|---|---|---|---|
| crypt_kit | model | 4550 / 21000 ok | 14 / 14 ok | 0 / 0 | 2048 / 2048 ok | 64.0 / 64 ok | 0 | pass |
| hero | rig | 19949 / 20000 ok | 2 / 4 ok | 23 / 64 ok | 2048 / 2048 ok | 60.0 / 64 ok | 8 | pass |
| wall_lamp | model | 880 / 1000 ok | 2 / 2 ok | 0 / 0 | 512 / 2048 ok | 4.02 / 16 ok | 0 | pass |

Scene totals if every asset were on screen at once (worst case):

- triangles: 25379 / 150000 ok
- texture_mem_mb: 128.02 / 512 ok
- draw_calls_est: 18 / 32 ok
