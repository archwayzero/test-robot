# Static budget report (2026-10-31T14:14:13+00:00)

Platform: ios (min device: iPhone 12)
Budget status: APPROVED FOR RUN 1 ONLY (human, 2026-10-25: 'create the game to the best of your ability'). Values marked estimate in notes have no authoritative source and must be validated on the device (M3). QA agents may not edit this file.
**Static budget score: 100.0** | **PASS**

Measured from exported .glb files only. Texture memory is an uncompressed upper bound; draw calls are estimated as mesh primitives. Not a measurement of device performance.

| asset | src | tris | draw calls (est) | joints | max tex | tex MB (ub) | anims | result |
|---|---|---|---|---|---|---|---|---|
| crypt_kit | model | 4552 / 21000 ok | 14 / 14 ok | 0 / 0 | 2048 / 2048 ok | 64.0 / 64 ok | 0 | pass |
| hero | rig | 19949 / 20000 ok | 2 / 4 ok | 23 / 64 ok | 2048 / 2048 ok | 60.0 / 64 ok | 8 | pass |
| wall_lamp | model | 880 / 1000 ok | 2 / 2 ok | 0 / 0 | 512 / 2048 ok | 4.02 / 16 ok | 0 | pass |

Scene totals if every asset were on screen at once (worst case):

- triangles: 25381 / 150000 ok
- texture_mem_mb: 128.02 / 512 ok
- draw_calls_est: 18 / 32 ok

## QA notes (T017 rerun on the T039 kit, supersedes the 2026-10-31T08:04 report at 1ee652c)
Verdict: PASS, score 100.0, check exits 0. Change since 1ee652c: crypt_kit 4550 -> 4552 tris (pier cap top); scene total 25379 -> 25381.
- crypt_kit draw calls 14/14: the tool counts collision primitives too. 7 are rendered (measured in `test_kit_counted_vs_rendered_primitives`).
- crypt_kit 64.0/64 MB: exactly at the limit, but an uncompressed RGBA + mips upper bound. ASTC_4x4 products on disk: 16.0 MiB (lamp 1.01 MiB, 1,054,384 bytes).
- The limits are approved for run 1 only, and these are static figures, not device measurements.
