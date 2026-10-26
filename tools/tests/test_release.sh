#!/bin/bash
S="$KIT_TEST_TMP"
rm -rf $S/rel $S/relrem $S/origin.git && bash "$KIT_ROOT/tools/tests/kit_copy.sh" $S/rel && cd $S/rel && find . -name __pycache__ -prune -exec rm -rf {} \;
export PATH=$KIT_TEST_SHIM:$PATH CLAUDE_PROJECT_DIR=$S/rel ALLOW_PROTECTED_COMMIT=1 ALLOW_PROTECTED_PUSH=1
sh tools/setup.sh --local-remote $S/relrem >/dev/null 2>&1 || echo SETUPFAIL
git init -q --bare $S/origin.git; git remote add origin $S/origin.git
printf 'config_version=5\n[application]\nconfig/name="My Game"\nconfig/features=PackedStringArray("4.6", "Mobile")\n' > godot/project.godot
python3 "$KIT_ROOT"/tools/tests/make_glb.py godot/assets >/dev/null; rm -rf godot/assets/broken
for f in $(find godot/assets -name '*.glb'); do printf 'outs:\n- md5: x\n  path: %s\n' "$(basename $f)" > $f.dvc; echo "/$(basename $f)" >> $(dirname $f)/.gitignore; done
git add -A && git commit -qm init && git push -q origin main 2>/dev/null
pass=0; failn=0
P() { name="$1"; want="$2"; out=$(python3 tools/release/make_mac_package.py --version 0.1.0 2>&1); rc=$?
  if echo "$out" | grep -q Traceback; then echo "FAIL  $name (crashed)"; echo "$out" | tail -3; failn=$((failn+1)); return; fi
  line=$(echo "$out" | grep -E "NOT PACKAGED|^PACKAGED" | head -1)
  if echo "$line" | grep -q -- "$want"; then echo "PASS  $name -> ${line:0:110}"; pass=$((pass+1)); else echo "FAIL  $name -> got: $line"; failn=$((failn+1)); fi; }
git switch -qc feature; P "not on main" "must run on main"; git switch -q main
echo tmp > stray.txt; P "dirty tree" "not clean"; rm stray.txt
P "placeholder budgets" "placeholders"
python3 - <<'PY'
import json; p="docs/qa/budgets.json"; b=json.load(open(p)); b["status"]="APPROVED v1"; b["sources"]=["test"]
b["defaults"]["max_triangles"]=2000; b["categories"]["character"]["max_triangles"]=5000
b["assets"]={"hero":{"category":"character"}}; json.dump(b,open(p,"w"),indent=2)
PY
git commit -qam budgets; git push -q origin main
P "budget over limit" "static budget check does not pass"
python3 - <<'PY'
import json; p="docs/qa/budgets.json"; b=json.load(open(p)); b["categories"]["character"]["max_triangles"]=20000; json.dump(b,open(p,"w"),indent=2)
PY
git commit -qam budgets2; git push -q origin main
P "no QA report" "missing or does not contain"
printf 'RESULT: FAIL\n' > docs/qa/reports/release-candidate.md; git add -A; git commit -qm qa; git push -q origin main
P "QA report FAIL" "missing or does not contain"
printf 'RESULT: PASS\nscore 90\n' > docs/qa/reports/release-candidate.md; git commit -qam qa2; git push -q origin main
echo "# change" >> godot/project.godot; git commit -qam late; git push -q origin main
P "game changed after QA" "changed after docs/qa/reports/release-candidate.md"
printf 'RESULT: PASS\nscore 91\n' > docs/qa/reports/release-candidate.md; git commit -qam qa3
P "unpushed local main" "differs from origin/main"
git push -q origin main
mv godot/assets/crate/model/crate.glb $S/crate.bak; P "DVC asset missing" "DVC-tracked files missing"; mv $S/crate.bak godot/assets/crate/model/crate.glb
echo "# handoff" > docs/IOS_HANDOFF.md; git add -A; git commit -qm handoff; git push -q origin main
P "no network/data audit" "network-data-audit.md missing"
printf 'RESULT: FAIL
unexplained URL
' > docs/qa/reports/network-data-audit.md; git add -A; git commit -qm audit1; git push -q origin main
P "audit says FAIL" "network-data-audit.md missing or does not contain"
printf 'RESULT: PASS
no network access
' > docs/qa/reports/network-data-audit.md; git commit -qam audit2; git push -q origin main
P "all gates pass" "^PACKAGED"
python3 -c "import zipfile,glob;print('audit in package:', 'docs/qa/reports/network-data-audit.md' in zipfile.ZipFile(sorted(glob.glob('dist/*.zip'))[-1]).namelist())"
rm -rf dist; echo "# later change" >> godot/project.godot; git commit -qam late2; git push -q origin main
printf 'RESULT: PASS
score 92
' > docs/qa/reports/release-candidate.md; git commit -qam qa4; git push -q origin main
P "game changed after audit (QA re-run, audit not)" "changed after docs/qa/reports/network-data-audit.md"
python3 -c "
import zipfile,json,glob,sys
if not glob.glob('dist/*.zip'): sys.exit(0)
z=zipfile.ZipFile(glob.glob('dist/*.zip')[0]); n=z.namelist(); m=json.loads(z.read('MANIFEST.json'))
print('zip:', glob.glob('dist/*.zip')[0], '| glb files:', sum(x.endswith('.glb') for x in n), '| handoff+platform+qa:', all(x in n for x in ('docs/IOS_HANDOFF.md','docs/specs/PLATFORM.md','docs/qa/reports/release-candidate.md')), '| score:', m['static_budget_score'], '| features:', m['godot_features'])"
[ -z "$(git status --porcelain)" ] && echo "PASS  tree still clean after packaging" || echo "FAIL  packaging dirtied tree"
echo "== $pass passed, $failn failed"
