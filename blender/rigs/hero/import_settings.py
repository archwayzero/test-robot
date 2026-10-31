#!/usr/bin/env python3
"""Set VRAM compression on the textures Godot extracted from the rig hero.glb (contract: "VRAM compression must be enabled").

  python3 blender/rigs/hero/import_settings.py            after a re-export whose texture set changed
  python3 blender/rigs/hero/import_settings.py --verify   after `godot --headless --path godot --import`

Same settings as blender/models/crypt_kit/import_settings.py: compress/mode=2 (VRAM compressed), high_quality=true (ASTC 4x4, BPTC
on desktop; without it Godot writes ETC2), mipmaps on. Differences from the kit: the hero has .jpg maps as well as .png, and the two
normal maps are named hero_normal and legs_normal, so "normal" in the name sets compress/normal_map=1 (forced, not detected) and every
other map gets 0. Nothing here touches sRGB: Godot picks it per material slot at render time.

--verify reads the header of each imported .astc.ctex: the .import text only says what was asked for, the header what was made.
It also fails if the .import no longer asks for the settings above.
"""
import re
import struct
import sys
from pathlib import Path

RIG = Path(__file__).resolve().parents[3] / "godot/assets/hero/rig"
ROOT = RIG.parents[3]
ASTC_4X4 = 35       # Image.FORMAT_ASTC_4x4
SETTINGS = {"compress/mode": "2", "compress/high_quality": "true", "mipmaps/generate": "true", "detect_3d/compress_to": "0"}
EXPECTED = 6


def wanted(name):
    return dict(SETTINGS, **{"compress/normal_map": "1" if "normal" in name else "0"})


def verify(files):
    bad = []
    for f in files:
        text = f.read_text()
        drift = [k for k, v in wanted(f.name).items() if not re.search(r"(?m)^%s=%s$" % (re.escape(k), re.escape(v)), text)]
        m = re.search(r'(?m)^path\.astc="res://(.+)"$', text)
        ctex = ROOT / "godot" / m.group(1) if m else None
        if drift or ctex is None or not ctex.exists():
            bad.append(f.name)
            print("%-40s settings drift %s, .astc.ctex %s" % (f.name[:-7], drift, "found" if ctex and ctex.exists() else "missing"))
            continue
        head = ctex.read_bytes()[:52]
        w, h = struct.unpack_from("<2I", head, 8)
        mips, fmt = struct.unpack_from("<2I", head, 44)
        print("%-40s %s %dx%d mips %d format %d %d bytes %s" % (f.name[:-7], head[:4].decode(), w, h, mips, fmt, ctex.stat().st_size,
                                                                 "ASTC_4x4" if fmt == ASTC_4X4 else "NOT ASTC_4x4"))
        if fmt != ASTC_4X4:
            bad.append(f.name)
    print("%d textures, not ASTC_4x4: %s" % (len(files), bad or "none"))
    raise SystemExit(1 if bad else 0)


def main():
    files = sorted(list(RIG.glob("*.png.import")) + list(RIG.glob("*.jpg.import")))
    if len(files) != EXPECTED:
        raise SystemExit("expected %d extracted textures, found %d: run the Godot import first" % (EXPECTED, len(files)))
    if "--verify" in sys.argv:
        verify(files)
    for f in files:
        s = f.read_text()
        for k, v in wanted(f.name).items():
            s, n = re.subn(r"(?m)^%s=.*$" % re.escape(k), "%s=%s" % (k, v), s)
            if n != 1:
                raise SystemExit("%s: no %s" % (f.name, k))
        f.write_text(s)
        print("vram", f.name)


main()
