#!/usr/bin/env python3
"""Set VRAM compression on the textures Godot extracted from crypt_kit.glb (contract: "VRAM compression must be enabled").

  python3 blender/models/crypt_kit/import_settings.py

Edits godot/assets/crypt_kit/model/*.png.import in place; run `godot --headless --path godot --import` afterwards. Called by
run_pipeline.py --import. compress/mode: 0 lossless, 1 lossy, 2 VRAM compressed. high_quality selects ASTC 4x4 (BPTC on desktop); without it Godot writes ETC2, and the contract budgets ASTC. Mipmaps are on, as for any 3D texture.
"""
import re
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[3] / "godot/assets/crypt_kit/model"
SETTINGS = {"compress/mode": "2", "compress/high_quality": "true", "mipmaps/generate": "true", "detect_3d/compress_to": "0"}


def main():
    files = sorted(MODEL.glob("*.png.import"))
    if not files:
        raise SystemExit("no extracted textures: run the Godot import first")
    if "--verify" in sys.argv:
        bad = [f.name for f in files if '"vram_texture": true' not in f.read_text() or "path.astc=" not in f.read_text()]
        print("not ASTC:", bad or "none")
        raise SystemExit(1 if bad else 0)
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
