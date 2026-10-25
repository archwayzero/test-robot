#!/usr/bin/env python3
"""Minimal ComfyUI HTTP client for the reference-director agent (stdlib only).

  comfy_client.py ping
  comfy_client.py run --workflow tools/comfy/workflows/<name>.json --image <png> --out reference/<asset>/<clip>
                      [--set key=value ...] [--timeout 1800]
  comfy_client.py frames --video <file> --out <dir> [--fps 4] [--cols 6]
  comfy_client.py free                  unload models and free GPU memory (lets you use the GPU again)

Server address: env COMFY_URL (default http://localhost:8188; ComfyUI runs on Windows, reached through WSL's
mirrored networking). Inside Claude Code's sandbox each command has a private localhost, so when a direct
connection fails the client goes through the sandbox's network proxy, which must allow `localhost:8188`.
--image and --out must be inside the repository.
Only workflows inside tools/comfy/workflows/ can be run, and only inputs listed in the workflow's
<name>.map.json can be changed. The workflow must be exported in ComfyUI's API format.
Endpoints used: /system_stats, /upload/image, /prompt, /history/<id>, /view, /free (verify against your ComfyUI version).
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("COMFY_URL", "http://localhost:8188").rstrip("/")
WF_DIR = Path(__file__).resolve().parent / "workflows"
REPO = WF_DIR.parents[2]
_opener = None


def _proxy_opener():
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not proxy:
        return None
    # urllib skips the proxy for hosts in NO_PROXY (which lists localhost); the sandbox needs the opposite.
    for k in ("NO_PROXY", "no_proxy"):
        os.environ.pop(k, None)
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def http(method, path, body=None, headers=None, timeout=60):
    global _opener
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    if _opener is not None:
        with _opener.open(req, timeout=timeout) as r:
            return r.read()
    try:
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with direct.open(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError:
        raise
    except OSError:
        _opener = _proxy_opener()
        if _opener is None:
            raise
        req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
        with _opener.open(req, timeout=timeout) as r:
            return r.read()


def inside_repo(p, what):
    rp = Path(p).resolve()
    if REPO.resolve() != rp and REPO.resolve() not in rp.parents:
        sys.exit(f"{what} must be inside the repository: {p}")
    return rp


def get_json(path):
    return json.loads(http("GET", path))


def post_json(path, obj):
    return json.loads(http("POST", path, json.dumps(obj).encode(), {"Content-Type": "application/json"}))


def upload_image(p):
    boundary = uuid.uuid4().hex
    data = Path(p).read_bytes()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{Path(p).name}\"\r\n"
         "Content-Type: application/octet-stream\r\n\r\n").encode() + data + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    resp = http("POST", "/upload/image", b"".join(parts),
                {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    j = json.loads(resp)
    return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]


def coerce(v):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def collect_files(outputs):
    files = []
    for node_out in outputs.values():
        for val in node_out.values():
            if isinstance(val, list):
                files += [x for x in val if isinstance(x, dict) and "filename" in x]
    return files


def cmd_run(a):
    out = inside_repo(a.out, "--out")
    wf_path = Path(a.workflow).resolve()
    if WF_DIR.resolve() not in wf_path.parents:
        sys.exit(f"workflow must be inside {WF_DIR}")
    map_path = wf_path.with_suffix(".map.json")
    if not map_path.exists():
        sys.exit(f"missing input map {map_path} (see tools/comfy/workflows/README.md)")
    wf = json.loads(wf_path.read_text())
    mapping = json.loads(map_path.read_text())
    if not all(isinstance(v, dict) and "class_type" in v for v in wf.values()):
        sys.exit("workflow is not in API format (in ComfyUI: export the workflow as API)")

    def put(key, value):
        if key not in mapping:
            sys.exit(f"'{key}' is not in {map_path.name}; allowed: {sorted(mapping)}")
        node, inp = str(mapping[key]["node"]), mapping[key]["input"]
        if node not in wf or inp not in wf[node].get("inputs", {}):
            sys.exit(f"map entry '{key}' points to missing node/input {node}.{inp}")
        wf[node]["inputs"][inp] = value

    params = {}
    if a.image:
        inside_repo(a.image, "--image")
        put("image", upload_image(a.image))
        params["image"] = Path(a.image).name
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        put(k, coerce(v))
        params[k] = coerce(v)

    resp = post_json("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})
    if "prompt_id" not in resp:
        sys.exit(f"ComfyUI rejected the workflow: {json.dumps(resp)[:800]}")
    pid = resp["prompt_id"]
    print(f"queued {pid}", flush=True)
    deadline = time.time() + a.timeout
    while True:
        hist = get_json(f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                sys.exit(f"ComfyUI reported an error: {json.dumps(status)[:800]}")
            if entry.get("outputs") or status.get("completed"):
                break
        if time.time() > deadline:
            sys.exit(f"timed out after {a.timeout}s waiting for {pid}")
        time.sleep(3)

    out.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in collect_files(entry.get("outputs", {})):
        if f.get("type", "output") != "output":
            continue
        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""),
                                    "type": f.get("type", "output")})
        dest = out / Path(f["filename"]).name
        dest.write_bytes(http("GET", f"/view?{q}", timeout=600))
        saved.append(dest.name)
    if not saved:
        sys.exit("workflow finished but produced no output files")
    meta = {"prompt_id": pid, "workflow": wf_path.name,
            "workflow_sha256": hashlib.sha256(wf_path.read_bytes()).hexdigest(),
            "params": params, "outputs": saved,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


def cmd_frames(a):
    inside_repo(a.out, "--out")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.video, "-vf", f"fps={a.fps}",
                    str(out / "frame_%04d.png")], check=True)
    n = len(list(out.glob("frame_*.png")))
    rows = max(1, -(-n // a.cols))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.video, "-frames:v", "1", "-vf",
                    f"fps={a.fps},scale=320:-1,tile={a.cols}x{rows}", str(out / "contact_sheet.png")], check=True)
    print(f"{n} frames + contact_sheet.png in {out}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("ping")
    sp.add_parser("free")
    r = sp.add_parser("run")
    r.add_argument("--workflow", required=True)
    r.add_argument("--image")
    r.add_argument("--out", required=True)
    r.add_argument("--set", action="append")
    r.add_argument("--timeout", type=int, default=1800)
    f = sp.add_parser("frames")
    f.add_argument("--video", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--fps", type=float, default=4)
    f.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    try:
        if a.cmd == "ping":
            print(json.dumps(get_json("/system_stats"), indent=2)[:1500])
        elif a.cmd == "free":
            http("POST", "/free", json.dumps({"unload_models": True, "free_memory": True}).encode(),
                 {"Content-Type": "application/json"})
            print("requested ComfyUI to unload models and free GPU memory")
        elif a.cmd == "run":
            cmd_run(a)
        else:
            cmd_frames(a)
    except urllib.error.HTTPError as e:
        sys.exit(f"ComfyUI at {BASE} answered with an error: {e}")
    except OSError as e:
        sys.exit(f"cannot reach ComfyUI at {BASE} (directly or through the sandbox proxy): {e}")


if __name__ == "__main__":
    main()
