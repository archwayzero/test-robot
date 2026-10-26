import sys, urllib.request, http.server
TARGET = "http://127.0.0.1:18188"
class P(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _go(self):
        url = self.path  # absolute URI when used as a proxy
        assert url.startswith("http://localhost:18300"), url
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n) if n else None
        req = urllib.request.Request(TARGET + url[len("http://localhost:18300"):], data=body, method=self.command,
                                     headers={k: v for k, v in self.headers.items() if k.lower() in ("content-type",)})
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(req) as r: data = r.read(); code = r.status
        open(sys.argv[1], "a").write(self.command + " " + url + "\n")
        self.send_response(code); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    do_GET = do_POST = _go
http.server.HTTPServer(("127.0.0.1", 18199), P).serve_forever()
