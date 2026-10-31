#!/usr/bin/env python3
"""Set VRAM compression on the textures Godot extracted from crypt_kit.glb (contract: "VRAM compression must be enabled").

  python3 blender/models/crypt_kit/import_settings.py

Edits godot/assets/crypt_kit/model/*.png.import in place; run `godot --headless --path godot --import` afterwards. Called by
run_pipeline.py --import. compress/mode: 0 lossless, 1 lossy, 2 VRAM compressed. Mipmaps are on, as for any 3D texture.
"""
import re
from pathlib import Path

MODEL = Path(__file__).resolve().parents[3] / "godot/assets/crypt_kit/model"
SETTINGS = {"compress/mode": "2", "mipmaps/generate": "true", "detect_3d/compress_to": "0"}


def main():
    files = sorted(MODEL.glob("*.png.import"))
    if not files:
        raise SystemExit("no extracted textures: run the Godot import first")
    for f in files:
        s = f.read_text()
        for k, v in SETTINGS.items():
            s, n = re.subn(r"(?m)^%s=.*$" % re.escape(k), "%s=%s" % (k, v), s)
            if n != 1:
                raise SystemExit("%s: no %s" % (f.name, k))
        if "normal" in f.name:
            s = re.sub(r"(?m)^compress/normal_map=.*$", "compress/normal_map=1", s)
        f.write_text(s)
        print("vram", f.name)


main()
