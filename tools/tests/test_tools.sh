#!/bin/bash
# Budget checker, ComfyUI client (fake server + proxy fallback), network/data audit, render tools (if available).
S="$KIT_TEST_TMP"; K="$KIT_ROOT"; pass=0; failn=0
ok() { echo "PASS  $1"; pass=$((pass+1)); }; bad() { echo "FAIL  $1"; failn=$((failn+1)); }

# --- budget checker on synthetic GLBs with known counts
B=$S/budget; rm -rf $B; mkdir -p $B; python3 "$K/tools/tests/make_glb.py" $B/assets >/dev/null
cat > $B/budgets.json <<'J'
{"platform":"ios","min_device":"iPhone 12","status":"TEST","weights":{"triangles":1,"draw_calls_est":1,"joints":1,"texture_size":1,"texture_mem_mb":1},
 "defaults":{"max_triangles":2000,"max_draw_calls_est":4,"max_texture_size":1024,"max_texture_mem_mb":8,"max_joints":null},
 "categories":{"character":{"max_triangles":5000,"max_joints":60,"max_texture_size":2048,"max_texture_mem_mb":32}},
 "assets":{"hero":{"category":"character"},"crate":{"max_triangles":300}},"scene_totals":{"max_triangles":10000}}
J
python3 -I "$K/tools/qa/check_budgets.py" --budgets $B/budgets.json --root $B/assets --json $B/out.json >/dev/null; rc=$?
[ "$rc" = 1 ] && ok "budget check fails when over budget" || bad "budget check exit $rc (expected 1)"
python3 - "$B/out.json" <<'PY' && ok "budget metrics exact" || bad "budget metrics"
import json,sys; o=json.load(open(sys.argv[1])); a={r["asset"]:r for r in o["assets"]}
assert a["crate"]["metrics"]["triangles"]==200 and a["hero"]["metrics"]["triangles"]==18000
assert a["hero"]["metrics"]["joints"]==70 and a["hero"]["metrics"]["texture_size"]==2048 and a["tree"]["metrics"]["triangles"]==1800
assert a["hero"]["source"]=="rig" and a["broken"]["errors"]
PY

# --- ComfyUI client against a fake server, direct and through a proxy
C=$S/comfy; rm -rf $C; bash "$K/tools/tests/kit_copy.sh" $C; cd $C
printf '{"6":{"class_type":"CLIPTextEncode","inputs":{"text":"old"}},"12":{"class_type":"LoadImage","inputs":{"image":"x.png"}},"3":{"class_type":"KSampler","inputs":{"seed":0,"steps":20}}}' > tools/comfy/workflows/t.json
printf '{"image":{"node":"12","input":"image"},"prompt":{"node":"6","input":"text"},"seed":{"node":"3","input":"seed"}}' > tools/comfy/workflows/t.map.json
mkdir -p reference/h; printf 'PNGDATA' > reference/h/s.png
python3 "$K/tools/tests/fake_comfy.py" 18188 $S/sent.json & A=$!; python3 "$K/tools/tests/fwdproxy.py" $S/proxy.log & P=$!; sleep 1
COMFY_URL=http://127.0.0.1:18188 python3 -I tools/comfy/comfy_client.py run --workflow tools/comfy/workflows/t.json --image reference/h/s.png --out reference/h/w --set prompt=walk --set seed=7 >/dev/null 2>&1 \
  && python3 -c "import json,sys;p=json.load(open('$S/sent.json'));sys.exit(0 if p['6']['inputs']['text']=='walk' and p['3']['inputs']['seed']==7 and p['3']['inputs']['steps']==20 else 1)" \
  && ok "comfy client patches only mapped inputs" || bad "comfy client direct run"
COMFY_URL=http://127.0.0.1:18188 python3 -I tools/comfy/comfy_client.py run --workflow tools/comfy/workflows/t.json --out reference/x --set steps=99 >/dev/null 2>&1 && bad "unmapped input accepted" || ok "comfy client refuses unmapped inputs"
COMFY_URL=http://127.0.0.1:18188 python3 -I tools/comfy/comfy_client.py run --workflow tools/comfy/workflows/t.json --out /tmp/evil >/dev/null 2>&1 && bad "output outside repo accepted" || ok "comfy client refuses output outside repo"
COMFY_URL=http://localhost:18300 HTTP_PROXY=http://127.0.0.1:18199 NO_PROXY=localhost no_proxy=localhost python3 -I tools/comfy/comfy_client.py ping >/dev/null 2>&1 && ok "comfy client falls back to the sandbox proxy" || bad "proxy fallback"
kill $A $P 2>/dev/null; wait 2>/dev/null

# --- network and data audit finds planted calls
N=$S/net; rm -rf $N; bash "$K/tools/tests/kit_copy.sh" $N; cd $N; mkdir -p godot/modules/s/internal godot/addons/sdk
printf 'extends Node\nfunc f():\n\tvar r = HTTPRequest.new()\n\tvar i = OS.get_unique_id()\n\tOS.execute("ls", [])\n' > godot/modules/s/internal/u.gd
printf 'extends Node\nvar w = WebSocketPeer.new()\n' > godot/addons/sdk/a.gd
out=$(python3 -I tools/qa/net_data_audit.py 2>&1); echo "$out" | grep -q "4 findings" && ok "net/data audit finds planted calls" || { bad "net/data audit"; echo "$out" | tail -2; }

# --- render tools under a read-only /tmp and no network (needs godot, Xvfb, unshare; skipped otherwise)
if command -v godot >/dev/null && command -v Xvfb >/dev/null && unshare --user --map-root-user --mount --net true 2>/dev/null; then
  R=$HOME/.kit-render-test; rm -rf $R; mkdir -p $R/tmpw; bash "$K/tools/tests/kit_copy.sh" $R/p; cd $R/p
  mkdir -p godot/modules/demo/internal
  printf 'config_version=5\n\n[application]\nconfig/name="T"\n\n[rendering]\nrenderer/rendering_method="mobile"\n' > godot/project.godot
  printf 'extends MeshInstance3D\nfunc _process(d):\n\trotate_y(d)\n' > godot/modules/demo/internal/spin.gd
  cat > godot/modules/demo/internal/demo.tscn <<'TS'
[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://modules/demo/internal/spin.gd" id="1"]

[sub_resource type="BoxMesh" id="B"]

[node name="D" type="Node3D"]

[node name="C" type="MeshInstance3D" parent="."]
mesh = SubResource("B")
script = ExtResource("1")

[node name="Cam" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 3)

[node name="L" type="DirectionalLight3D" parent="."]
TS
  cat > $R/run.sh <<RS
python3 "$K/tools/tests/loopback_up.py" >/dev/null
mount -t tmpfs tmpfs /tmp && mount -o remount,ro /tmp
export TMPDIR=$R/tmpw; unset DISPLAY WAYLAND_DISPLAY; cd $R/p
python3 tools/qa/capture.py --scene res://modules/demo/internal/demo.tscn --frames 6 --every 3 --mode fast >/dev/null 2>&1 && echo CAPTURE_OK
python3 tools/qa/record.py --scene res://modules/demo/internal/demo.tscn --seconds 1 --mode fast --out docs/qa/videos/t/d.mp4 >/dev/null 2>&1 && echo RECORD_OK
RS
  res=$(unshare --user --map-root-user --mount --net bash $R/run.sh 2>&1)
  echo "$res" | grep -q CAPTURE_OK && ok "capture works with read-only /tmp and no network" || bad "capture under sandbox-like conditions"
  echo "$res" | grep -q RECORD_OK && ok "record works with read-only /tmp and no network" || bad "record under sandbox-like conditions"
  rm -rf $R
else
  echo "SKIP  render tools (needs godot, Xvfb and unprivileged user namespaces)"
fi
echo "== $pass passed, $failn failed"
