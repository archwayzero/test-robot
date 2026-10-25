#!/bin/bash
# Make a pristine copy of the kit (no git history, no DVC state, no game content) for a test to work on.
#   bash tools/tests/kit_copy.sh <destination>
set -e
src="$KIT_ROOT"; dst="$1"; rm -rf "$dst"; mkdir -p "$dst"
tar -C "$src" --exclude=./.git --exclude=./.dvc --exclude=./.captures --exclude=./dist --exclude=./.kit-update \
  --exclude='./godot/modules/*' --exclude='./godot/assets/*' --exclude='./godot/addons/*' --exclude=./godot/project.godot \
  --exclude=./godot/.godot --exclude='./blender/models/*' --exclude='./blender/rigs/*' --exclude='./reference/*' \
  --exclude='./docs/qa/reports/*' --exclude=./docs/qa/videos --exclude='./godot/tests' --exclude='*/__pycache__' \
  --exclude='./tools/comfy/workflows/*.json' -cf - . | tar -C "$dst" -xf -
for d in godot/modules godot/assets godot/addons blender/models blender/rigs reference docs/qa/reports; do
  mkdir -p "$dst/$d" && touch "$dst/$d/.gitkeep"; done
printf '{\n  "modules": {}\n}\n' > "$dst/docs/modules.json"
cp "$src/tools/tests/fixtures/budgets.json" "$dst/docs/qa/budgets.json"
