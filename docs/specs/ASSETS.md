# 3D assets needed (human-written)

Art style / reference:
Global constraints (triangle budgets, texture sizes):

Source: `generate` (modeler scripts it in Blender) or `provided: <path>` (a model you supply, e.g. from Tripo).
Put provided originals at `blender/models/<id>/source/<file>.glb` and track them with DVC (see README).

| id (snake_case) | name | purpose / used by mechanic | source | style notes | tri budget | needs rig? | priority |
|---|---|---|---|---|---|---|---|
| example_crate | Wooden crate | M2 pushable object | generate | low poly, flat colors | 300 | no | 1 |
| hero | Main character | player avatar (M1) | provided: blender/models/hero/source/hero_tripo.glb | keep look of the Tripo model | (from budgets) | yes | 1 |
