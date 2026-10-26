# 3D assets needed (human-written)

Art style: As realistic as can be rendered without problems on the chosen platform.

Map/environment: A maze. Everywhere you turn you are in an underground crypt, gothic architecture. Groin vaulting is seen between the semicircular arches which rest on square short capitals. Reference image for the crypt can be found at reference/map/crypt.jpg. Modeler should generate a base map to show the general layout of the crypt and save it in reference/map, then build the walls, flooring, and ceiling based on the layout. 

Global constraints (triangle budgets, texture sizes): (from platform budgets)

Source: `generate` (modeler scripts it in Blender) or `provided: <path>` (a model you supply, e.g. from Tripo).
Put provided originals at `blender/models/<id>/source/<file>.glb` and track them with DVC (see README).

| id (snake_case) | name | purpose / used by mechanic | source | style notes | tri budget | needs rig? | priority |
|---|---|---|---|---|---|---|---|
| hero | Main character | player avatar (M1) | provided: blender/models/hero/source/hero.glb | keep look of the Tripo model | (from budgets) | yes | 1 |
