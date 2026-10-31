#!/usr/bin/env python3
"""Set VRAM compression on the textures Godot extracted from crypt_kit.glb (contract: "VRAM compression must be enabled").

  python3 blender/models/crypt_kit/import_settings.py

Edits godot/assets/crypt_kit/model/*.png.import in place; run `godot --headless --path godot --import` afterwards. Called by
run_pipeline.py --import. compress/mode: 0 lossless, 1 lossy, 2 VRAM compressed. high_quality selects ASTC 4x4 (BPTC on desktop);
without it Godot writes ETC2, and the contract budgets ASTC. Mipmaps are on, as for any 3D texture.

--verify reads the header of each imported .astc.ctex: the .import text only says what was asked for, the header what was made.
"""
import re
import struct
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[3] / "godot/assets/crypt_kit/model"
ROOT = MODEL.parents[3]
ASTC_4X4 = 35       # Image.FORMAT_ASTC_4x4
SETTINGS = {"compress/mode": "2", "compress/high_quality": "true", "mipmaps/generate": "true", "detect_3d/compress_to": "0"}


def main():
    files = sorted(MODEL.glob("*.png.import"))
    if not files:
        raise SystemExit("no extracted textures: run the Godot import first")
    if "--verify" in sys.argv:
        bad = []
        for f in files:
            m = re.search(r'(?m)^path\.astc="res://(.+)"$', f.read_text())
            ctex = ROOT / "godot" / m.group(1) if m else None
            if ctex is None or not ctex.exists():
                bad.append(f.name)
                print("%-46s no .astc.ctex" % f.name[:-7])
                continue
            head = ctex.read_bytes()[:52]
            w, h = struct.unpack_from("<2I", head, 8)
            mips, fmt = struct.unpack_from("<2I", head, 44)
            print("%-46s %s %dx%d mips %d format %d %s" % (f.name[:-7], head[:4].decode(), w, h, mips, fmt,
                                                            "ASTC_4x4" if fmt == ASTC_4X4 else "NOT ASTC_4x4"))
            if fmt != ASTC_4X4:
                bad.append(f.name)
        print("%d textures, not ASTC_4x4: %s" % (len(files), bad or "none"))
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
