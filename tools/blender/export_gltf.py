"""Headless Blender glTF export.

  blender -b <file.blend> -P tools/blender/export_gltf.py -- --out path/to/asset.glb [--no-anim]

Applies the conventions in docs/contracts/blender-godot-assets.md (GLB, Y-up, modifiers applied).
"""
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[argv.index("--out") + 1] if "--out" in argv else None
if not out:
    sys.exit("usage: -- --out path.glb [--no-anim]")

bpy.ops.export_scene.gltf(
    filepath=out,
    export_format="GLB",
    export_yup=True,
    export_apply=True,
    export_animations="--no-anim" not in argv,
    export_skins=True,
)
print(f"exported {out}")
