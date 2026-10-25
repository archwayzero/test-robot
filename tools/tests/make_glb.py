import json, struct, sys, zlib
def png(w, h):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    c = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + c(b"IHDR", ihdr) + c(b"IEND", b"")
def glb(path, tris, instances=1, tex=None, joints=0, anims=0, prims=1):
    binbuf = b""; bvs = []; accs = []; images = []
    nverts = tris * 3
    meshes = [{"primitives": []}]
    for p in range(prims):
        accs.append({"count": nverts, "componentType": 5126, "type": "VEC3"})
        accs.append({"count": nverts, "componentType": 5125, "type": "SCALAR"})
        meshes[0]["primitives"].append({"attributes": {"POSITION": len(accs)-2}, "indices": len(accs)-1})
    if tex:
        data = png(*tex); bvs.append({"buffer": 0, "byteOffset": len(binbuf), "byteLength": len(data)})
        binbuf += data; images.append({"bufferView": len(bvs)-1, "mimeType": "image/png"})
    nodes = [{"mesh": 0} for _ in range(instances)]
    js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(instances))}],
          "nodes": nodes, "meshes": meshes, "accessors": accs, "bufferViews": bvs,
          "buffers": [{"byteLength": len(binbuf)}]}
    if images: js["images"] = images
    if joints: js["skins"] = [{"joints": list(range(joints))}]
    if anims: js["animations"] = [{"name": f"clip{i}", "channels": [], "samplers": []} for i in range(anims)]
    j = json.dumps(js).encode(); j += b" " * (-len(j) % 4); binbuf += b"\0" * (-len(binbuf) % 4)
    body = struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(binbuf), 0x004E4942) + binbuf
    open(path, "wb").write(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
if __name__ == "__main__":
    import os
    root = sys.argv[1]
    def mk(asset, kind, **kw):
        os.makedirs(f"{root}/{asset}/{kind}", exist_ok=True); glb(f"{root}/{asset}/{kind}/{asset}.glb", **kw)
    mk("crate", "model", tris=200, tex=(512, 512))
    mk("hero", "model", tris=1000)
    mk("hero", "rig", tris=6000, tex=(2048, 2048), joints=70, anims=3, prims=3)
    mk("tree", "model", tris=900, instances=2)
    os.makedirs(f"{root}/broken/model", exist_ok=True); open(f"{root}/broken/model/broken.glb", "wb").write(b"nope")
