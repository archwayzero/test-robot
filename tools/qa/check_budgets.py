#!/usr/bin/env python3
"""Static performance-budget check for exported assets (no GPU, no Godot needed).

  python3 tools/qa/check_budgets.py [--budgets docs/qa/budgets.json] [--root godot/assets]
                                    [--report docs/qa/reports/budget-<date>.md] [--json out.json]

Reads every godot/assets/<asset>/{model,rig}/*.glb (rig preferred when both exist), measures:
  triangles, vertices, primitives (draw-call estimate), joints, animations,
  largest texture side, texture memory estimate (uncompressed RGBA8 + mips: an upper bound),
and compares them with docs/qa/budgets.json. A limit of null means "not checked".

Score: per check, 1.0 when within budget, falling linearly to 0 at 2x the limit; weighted
average x 100. It is a STATIC BUDGET SCORE, not measured device performance.
Exit code 1 if any check exceeds its limit, 2 on usage/config errors.
"""
import argparse
import datetime
import json
import os
import struct
import sys
from pathlib import Path

CHECKS = ("triangles", "texture_size", "texture_mem_mb", "joints", "draw_calls_est")
LIMIT_KEY = {"triangles": "max_triangles", "texture_size": "max_texture_size",
             "texture_mem_mb": "max_texture_mem_mb", "joints": "max_joints",
             "draw_calls_est": "max_draw_calls_est"}
COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}


def read_glb(path):
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] != b"glTF":
        raise ValueError("not a GLB file")
    _, version, length = struct.unpack_from("<4sII", data, 0)
    if version != 2:
        raise ValueError(f"unsupported glTF version {version}")
    off, js, binchunk = 12, None, b""
    while off + 8 <= min(length, len(data)):
        clen, ctype = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:
            binchunk = chunk
        off += 8 + clen
    if js is None:
        raise ValueError("GLB has no JSON chunk")
    return js, binchunk


def image_size(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            seglen = struct.unpack(">H", b[i + 2:i + 4])[0]
            i += 2 + seglen
    return None


def prim_triangles(gltf, prim):
    mode = prim.get("mode", 4)
    if mode not in (4, 5, 6):
        return 0
    acc_i = prim.get("indices")
    if acc_i is None:
        acc_i = prim.get("attributes", {}).get("POSITION")
    if acc_i is None:
        return 0
    n = gltf["accessors"][acc_i]["count"]
    return n // 3 if mode == 4 else max(0, n - 2)


def measure(path):
    gltf, binchunk = read_glb(path)
    meshes = gltf.get("meshes", [])
    nodes = gltf.get("nodes", [])
    instances = {}
    scene_idx = gltf.get("scene", 0)
    scenes = gltf.get("scenes", [])
    roots = scenes[scene_idx]["nodes"] if scenes else list(range(len(nodes)))
    stack, seen = list(roots), set()
    while stack:
        n = stack.pop()
        if n in seen or n >= len(nodes):
            continue
        seen.add(n)
        node = nodes[n]
        if "mesh" in node:
            instances[node["mesh"]] = instances.get(node["mesh"], 0) + 1
        stack.extend(node.get("children", []))
    if not instances:
        instances = {i: 1 for i in range(len(meshes))}

    tris = verts = prims = 0
    for mi, count in instances.items():
        for prim in meshes[mi].get("primitives", []):
            tris += prim_triangles(gltf, prim) * count
            pos = prim.get("attributes", {}).get("POSITION")
            if pos is not None:
                verts += gltf["accessors"][pos]["count"] * count
            prims += count

    max_side, tex_bytes, tex_unknown = 0, 0, 0
    for img in gltf.get("images", []):
        raw = None
        if "bufferView" in img:
            bv = gltf["bufferViews"][img["bufferView"]]
            start = bv.get("byteOffset", 0)
            raw = binchunk[start:start + bv["byteLength"]]
        elif "uri" in img and not img["uri"].startswith("data:"):
            p = Path(path).parent / img["uri"]
            raw = p.read_bytes() if p.exists() else None
        size = image_size(raw) if raw else None
        if not size:
            tex_unknown += 1
            continue
        w, h = size
        max_side = max(max_side, w, h)
        tex_bytes += int(w * h * 4 * 4 / 3)

    joints = max((len(s.get("joints", [])) for s in gltf.get("skins", [])), default=0)
    anims = [a.get("name", f"anim_{i}") for i, a in enumerate(gltf.get("animations", []))]
    return {"triangles": tris, "vertices": verts, "draw_calls_est": prims, "joints": joints,
            "texture_size": max_side, "texture_mem_mb": round(tex_bytes / (1024 * 1024), 2),
            "textures_unreadable": tex_unknown, "animations": anims}


def check_score(value, limit):
    if limit in (None, 0):
        return None, None
    ratio = value / limit
    return ratio <= 1, (1.0 if ratio <= 1 else max(0.0, 2.0 - ratio))


def limits_for(budgets, asset):
    lim = dict(budgets.get("defaults", {}))
    entry = budgets.get("assets", {}).get(asset, {})
    cat = entry.get("category")
    if cat:
        lim.update(budgets.get("categories", {}).get(cat, {}))
    lim.update({k: v for k, v in entry.items() if k != "category"})
    return lim, cat


def find_assets(root):
    found = {}
    for d in sorted(Path(root).glob("*")):
        if not d.is_dir():
            continue
        for kind in ("rig", "model"):
            glbs = sorted((d / kind).glob("*.glb")) if (d / kind).is_dir() else []
            if glbs:
                found[d.name] = (kind, glbs)
                break
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="docs/qa/budgets.json")
    ap.add_argument("--root", default="godot/assets")
    ap.add_argument("--report")
    ap.add_argument("--json")
    a = ap.parse_args()
    try:
        budgets = json.loads(Path(a.budgets).read_text())
    except (OSError, ValueError) as e:
        print(f"cannot read budgets: {e}", file=sys.stderr)
        sys.exit(2)
    weights = budgets.get("weights", {c: 1 for c in CHECKS})

    results, any_fail, wsum, ssum = [], False, 0.0, 0.0
    totals = {"triangles": 0, "texture_mem_mb": 0.0, "draw_calls_est": 0}
    for asset, (kind, glbs) in find_assets(a.root).items():
        lim, cat = limits_for(budgets, asset)
        m = {"triangles": 0, "vertices": 0, "draw_calls_est": 0, "joints": 0, "texture_size": 0,
             "texture_mem_mb": 0.0, "textures_unreadable": 0, "animations": []}
        errors = []
        for g in glbs:
            try:
                x = measure(g)
            except (OSError, ValueError, KeyError, IndexError, struct.error) as e:
                errors.append(f"{g.name}: {e}")
                continue
            for k in ("triangles", "vertices", "draw_calls_est", "textures_unreadable"):
                m[k] += x[k]
            m["texture_mem_mb"] = round(m["texture_mem_mb"] + x["texture_mem_mb"], 2)
            m["joints"] = max(m["joints"], x["joints"])
            m["texture_size"] = max(m["texture_size"], x["texture_size"])
            m["animations"] += x["animations"]
        checks = {}
        for c in CHECKS:
            if errors and not any(g.name not in " ".join(errors) for g in glbs):
                checks[c] = {"value": None, "limit": lim.get(LIMIT_KEY[c]), "ok": None, "score": None}
                continue
            ok, s = check_score(m[c], lim.get(LIMIT_KEY[c]))
            checks[c] = {"value": m[c], "limit": lim.get(LIMIT_KEY[c]), "ok": ok, "score": s}
            if ok is False:
                any_fail = True
            if s is not None:
                w = float(weights.get(c, 1))
                wsum += w
                ssum += w * s
        if errors:
            any_fail = True
        for k in totals:
            totals[k] += m[k]
        results.append({"asset": asset, "category": cat, "source": kind, "files": [g.name for g in glbs],
                        "metrics": m, "checks": checks, "errors": errors})

    tot_checks = {}
    st = budgets.get("scene_totals", {})
    for c, key in (("triangles", "max_triangles"), ("texture_mem_mb", "max_texture_mem_mb"),
                   ("draw_calls_est", "max_draw_calls_est")):
        ok, s = check_score(totals[c], st.get(key))
        tot_checks[c] = {"value": round(totals[c], 2), "limit": st.get(key), "ok": ok, "score": s}
        if ok is False:
            any_fail = True

    score = round(100 * ssum / wsum, 1) if wsum else None
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "platform": budgets.get("platform"), "min_device": budgets.get("min_device"),
           "budget_status": budgets.get("status"), "static_budget_score": score,
           "passed": not any_fail, "assets": results, "scene_totals_all_assets": tot_checks}

    lines = [f"# Static budget report ({out['generated']})", "",
             f"Platform: {out['platform']} (min device: {out['min_device']})",
             f"Budget status: {out['budget_status']}",
             f"**Static budget score: {score if score is not None else 'n/a (no limits set)'}** "
             f"| **{'PASS' if out['passed'] else 'FAIL'}**", "",
             "Measured from exported .glb files only. Texture memory is an uncompressed upper bound; "
             "draw calls are estimated as mesh primitives. Not a measurement of device performance.", "",
             "| asset | src | tris | draw calls (est) | joints | max tex | tex MB (ub) | anims | result |",
             "|---|---|---|---|---|---|---|---|---|"]

    def cell(c, chk):
        v, l = chk[c]["value"], chk[c]["limit"]
        if v is None:
            return "unreadable"
        mark = "" if chk[c]["ok"] is None else (" ok" if chk[c]["ok"] else " **OVER**")
        return f"{v}" + (f" / {l}" if l is not None else "") + mark

    for r in results:
        ch = r["checks"]
        bad = [c for c in CHECKS if ch[c]["ok"] is False] or (["errors"] if r["errors"] else [])
        lines.append(f"| {r['asset']} | {r['source']} | {cell('triangles', ch)} | {cell('draw_calls_est', ch)} | "
                     f"{cell('joints', ch)} | {cell('texture_size', ch)} | {cell('texture_mem_mb', ch)} | "
                     f"{len(r['metrics']['animations'])} | {'FAIL: ' + ', '.join(bad) if bad else 'pass'} |")
    lines += ["", "Scene totals if every asset were on screen at once (worst case):", ""]
    for c, chk in tot_checks.items():
        lines.append(f"- {c}: {cell(c, tot_checks)}")
    errs = [f"- {r['asset']}: {e}" for r in results for e in r["errors"]]
    if errs:
        lines += ["", "Errors:", *errs]
    unset = [c for c in CHECKS if all(r["checks"][c]["limit"] is None for r in results)] if results else list(CHECKS)
    if unset:
        lines += ["", f"Not checked (no limit set): {', '.join(unset)}"]
    report = "\n".join(lines) + "\n"

    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(report)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2) + "\n")
    print(report)
    sys.exit(0 if out["passed"] else 1)


if __name__ == "__main__":
    main()
