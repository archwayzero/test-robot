#!/bin/bash
# Run the kit's test suites. Linux only (WSL outside the sandbox, or CI). Never modifies the repository:
# every suite works on throwaway copies in a temp folder. dvc, bwrap and socat are stubbed.
#   bash tools/tests/run_all.sh
set -u
export KIT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export KIT_TEST_TMP="$(mktemp -d)"
export KIT_TEST_SHIM="$KIT_TEST_TMP/shim"
mkdir -p "$KIT_TEST_SHIM"
cat > "$KIT_TEST_SHIM/dvc" <<'SH'
#!/bin/sh
case "$1" in
  init) mkdir -p .dvc ;;
  remote) if [ "$2" = "list" ]; then [ -f .dvc/remote ] && cat .dvc/remote; exit 0; elif [ "$2" = "add" ]; then echo "$5 $4" > .dvc/remote; fi ;;
esac
exit 0
SH
for t in bwrap socat; do printf '#!/bin/sh\nexit 0\n' > "$KIT_TEST_SHIM/$t"; done
chmod +x "$KIT_TEST_SHIM"/*
git config --global user.email >/dev/null 2>&1 || git config --global user.email "kit-tests@example.invalid"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "kit-tests"
total_fail=0
for suite in test_guards_git.sh test_release.sh test_tools.sh; do
  echo "### $suite"
  out=$(bash "$KIT_ROOT/tools/tests/$suite" 2>&1); echo "$out" | grep -E "^(FAIL|SKIP)|^==" ; echo "$out" | grep -qE "^FAIL|SETUP FAILED|SETUPFAIL" && total_fail=1
done
rm -rf "$KIT_TEST_TMP"
[ "$total_fail" = 0 ] && echo "ALL SUITES PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
