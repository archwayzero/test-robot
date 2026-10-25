import json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
STATE = {"prompt": None, "polls": 0}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/system_stats": return self.send(200, {"system": {"comfyui_version": "fake"}, "devices": [{"name": "cuda:0"}]})
        if self.path.startswith("/history/"):
            STATE["polls"] += 1
            if STATE["polls"] < 2: return self.send(200, {})
            return self.send(200, {"p1": {"status": {"status_str": "success", "completed": True},
                "outputs": {"40": {"gifs": [{"filename": "ref_00001.mp4", "subfolder": "", "type": "output"}]},
                            "9": {"images": [{"filename": "tmp.png", "subfolder": "", "type": "temp"}]}}}})
        if self.path.startswith("/view?"): return self.send(200, b"FAKEVIDEO", "video/mp4")
        self.send(404, {})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        if self.path == "/upload/image":
            ok = b'name="image"' in body and b"PNGDATA" in body
            return self.send(200 if ok else 400, {"name": "snap.png", "subfolder": "", "type": "input"})
        if self.path == "/free":
            STATE["freed"]=json.loads(body); open(sys.argv[2]+".free","w").write(body.decode()); return self.send(200, b"", "text/plain")
        if self.path == "/prompt":
            STATE["prompt"] = json.loads(body)["prompt"]
            open(sys.argv[2], "w").write(json.dumps(STATE["prompt"]))
            return self.send(200, {"prompt_id": "p1", "number": 1})
        self.send(404, {})
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
