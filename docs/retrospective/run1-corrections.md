# Run 1: corrections for the next game

Purpose: everything that had to be guessed, worked around or fixed in run 1, written as concrete changes for the
next game. Part A is for the specs you write. Part B is for the kit (hooks, tools, setup). Part C is filled in as
run 1 proceeds (milestones M1-M3). Run-1 defaults that were used instead: docs/architecture/DECISIONS.md.

Status: started 2026-10-25 at planning (Phase B). Updated at each milestone.

---

## Part A. Spec corrections (docs/specs/*.md)

### A1. Hero height (ASSETS.md)
- **Problem:** the provided Tripo model is 0.98 m tall; the spec gives no height. Corridor, arch, low-passage and
  camera dimensions all depend on it.
- **Run 1:** the modeler picks a plausible adult height (1.65-1.85 m) and records it (D8).
- **Next time:** give the character's real height in meters in the asset row, e.g. `style notes: adult, 1.75 m`.
  If a model generator is used, export at real scale or say "scale to 1.75 m".

### A2. Camera / perspective (MECHANICS.md)
- **Problem:** the template asks for perspective; it was left empty.
- **Run 1:** third-person follow camera with wall collision (D1).
- **Next time:** state it: "third-person, camera behind and slightly above, player can orbit with a drag on the
  right half of the screen" (or first-person / top-down).

### A3. Controls (MECHANICS.md, not RIGGING_ANIMATION.md)
- **Problem:** controls were in the rigging spec, and "right screen button for jumping and switching to crouch and
  crawl" is one button for three actions.
- **Run 1:** two buttons: Jump, and Stance (cycles stand -> crouch -> crawl); run = joystick pushed past 70% (D3).
- **Next time:** a control table in MECHANICS.md: input -> action, e.g. "left joystick: move; push > 70%: run;
  right button A: jump; right button B: cycle stance".

### A4. Jump is an action, so it belongs in MECHANICS.md (D2)
- **Problem:** jump appears only in the rigging animations list.
- **Next time:** every action the player can do is listed in MECHANICS.md; RIGGING_ANIMATION.md only lists clips.

### A5. Idle animations (RIGGING_ANIMATION.md)
- **Problem:** stand, crouch and crawl all need an idle pose; none listed.
- **Run 1:** added `idle_loop`, `crouch_idle_loop`, `crawl_idle_loop` (D4).
- **Next time:** list idles and say which clips loop. Use the clip names from docs/contracts/blender-godot-assets.md.

### A6. Collision is a mechanic, not a rig constraint
- **Problem:** "does not clip through walls, the floor, or the ceiling" is under rigging. Collision is done by the
  character controller in Godot, not by the rig.
- **Next time:** put it in MECHANICS.md ("the player never passes through walls/floor/ceiling; camera never shows
  the inside of a wall").

### A7. Why crouch and crawl exist (MECHANICS.md)
- **Problem:** no place in the game requires them.
- **Run 1:** 4-8 low passages (crouch-only, crawl-only), never the only route (D5).
- **Next time:** say what they are for (low passages, hiding, ...) and whether any area must require them.

### A8. Maze construction and size (ASSETS.md / MECHANICS.md)
- **Problem:** ASSETS.md tells the modeler to draw a base map into `reference/map` and model the whole maze. The
  modeler may not write `reference/` (reference-director's folder), and the mini-map needs the layout as game data.
  Maze size was not given.
- **Run 1:** seeded 20 x 20 grid of 4 m cells in the `maze` module; the modeler builds a modular kit; Godot
  assembles it (D6, D7).
- **Next time:** "Maze: 20 x 20 cells, generated from a fixed seed (same maze for everyone), built from a modular
  kit (floor, wall, pier, arch, vault, low ceilings)". If you want a hand-designed layout, provide it as a text grid
  (e.g. `#` wall, `.` floor) in docs/specs/.

### A9. Lighting (ASSETS.md)
- **Problem:** an underground crypt with no light sources described.
- **Run 1:** wall lamps every ~3 corridor cells, baked lighting if possible, else real-time lights limited to 8 per
  mesh (Mobile renderer) (D9).
- **Next time:** describe light sources (lamps, torches, candles, player lantern?) and mood (how dark).

### A10. Reference images
- **Problem:** `crypt.jpg` (Winchester Cathedral crypt) contains Antony Gormley's statue *Sound II* (copyrighted
  artwork) and floodwater (needs reflections the Mobile renderer does not support).
- **Run 1:** no statue, dry floor (D10).
- **Next time:** pick references that show only what should be built, or annotate: "use the architecture only;
  ignore the statue and the water".

### A11. Cloud save (MECHANICS.md)
- **Problem:** "saved automatically to the cloud whenever player progresses" leaves open: which cloud, what is
  progress, what happens offline. iCloud needs a native iOS plugin, an Apple Developer account with the iCloud
  capability, and can only be built and tested on the Mac/device.
- **Run 1:** local autosave on each new explored cell (max every 10 s) and on app background; `CloudBackend` seam;
  iCloud key-value backend at the Mac stage (D11).
- **Next time:** "Save: iCloud key-value store (Apple ID of the device), on every newly explored cell and when the
  app goes to the background; offline: keep a local save and sync later". Confirm the Apple Developer account and
  iCloud container id before the run.

### A12. Menus, pause, audio, win condition (MECHANICS.md)
- **Problem:** none specified.
- **Run 1:** boot straight into the maze, pause on large map and app background, no audio, no win (D12).
- **Next time:** list the screens (title, pause, settings, credits?) and audio (ambience, footsteps). If you want the
  Maaack menu template, allow its 3 autoloads explicitly (they conflict with the "core is the only autoload" rule).

### A13. Textures for "as realistic as possible" (ASSETS.md)
- **Problem:** realistic stone needs photographic PBR textures; the sandbox cannot download them and procedural
  textures look procedural.
- **Run 1:** procedural Blender materials baked to tileable maps (D13).
- **Next time:** before the run, download 3-4 CC0 PBR sets (e.g. Poly Haven / ambientCG: sandstone ashlar, worn
  floor slabs, plaster) into `blender/textures/<set>/` and list them in ASSETS.md; they are tracked with DVC.

### A14. Character animation quality (RIGGING_ANIMATION.md)
- **Problem:** the Tripo model has no rig. Scripted keyframe animation from AI reference videos will look stiff,
  especially crawl and jump.
- **Run 1:** scripted rig + 8 scripted clips (D14).
- **Next time:** decide between (a) scripted (cheap, stiff) and (b) you rig/animate outside (e.g. Mixamo or
  mocap) and provide the result as `provided:` with clip names from the asset contract; the rigger-animator then
  only conforms and retargets.

### A15. Mechanic ids and template leftovers
- **Problem:** ASSETS.md refers to "M1" but MECHANICS.md has no numbered mechanics; MECHANICS.md still contains the
  template line "(One paragraph: genre, perspective, core loop, target platform.)".
- **Next time:** one heading per mechanic `## M1 Movement`, `## M2 ...`, and delete template prompts.

### A16. Project identity (PLATFORM.md)
- **Problem:** no game name or bundle id. Run 1 uses "Test Robot" (from the repo name). Renaming later moves the
  `user://` save folder.
- **Next time:** give the display name and bundle id (e.g. `com.archwayzero.<game>`) in PLATFORM.md.

### A17. Provided model file name
- **Problem:** README/SETUP use `<id>_tripo.glb`; this run used `hero.glb`. Both work; consistency helps scripts.
- **Next time:** use the README convention, or update the README.

---

## Part B. Kit and environment corrections (human-owned files)

### B1. Locked files and hooks
1. **bash_guard false positives.** Blocked read-only commands: `git config core.hooksPath` ("changing
   core.hooksPath"), and any command that mentions a locked file together with a redirection or `python -c`
   (e.g. `python3 tools/envcheck.py 2>&1 | tail`, importing `tools/xdisplay.py`). Suggest: allow `git config
   --get`/no-value reads; match writes (`>`, `tee`, `sed -i`, `cp`/`mv` targets) instead of mere mentions.
2. **completion_gate fires mid-task.** When the orchestrator ends a turn while a subagent works, the gate reports
   "uncommitted changes on a task branch" and suggests `git add -A`, which would commit files outside the branch's
   scope (e.g. the reference-director's image on the modeler's branch). Suggest: skip while a task is
   `in_progress` in the ledger, and never suggest `git add -A`; list only files inside the current branch scope.
3. **`dvc add` exits 255 in the sandbox.** With `core.autostage = true`, DVC opens `.gitmodules`, which the sandbox
   masks, so every `dvc add` ends with "failed open '.gitmodules' is locked" after doing its work. Suggest: set
   `core.autostage false` in `.dvc/config` (agents stage the pointer explicitly anyway) or stop masking
   `.gitmodules` when the file does not exist.
4. **Branching from `origin/<branch>` fails.** `git switch -c X origin/main` (and `tools/task.py start --base
   origin/main`) tries to write upstream tracking into `.git/config`, which is protected. Run 1 used the commit hash
   as base. Suggest: task.py passes `--no-track`, or setup.sh sets `branch.autoSetupMerge=false`.
5. **`task.py finish` vs `start` disagree on untracked files.** `start` ignores untracked files; `finish` refuses
   if any exist, even unrelated ones (a binary waiting for another task). Suggest: `finish` ignores untracked files
   outside the task's scope.
6. **Task ledger is not versioned.** `.claude/state/ledger.json` is gitignored, so the task list exists only in this
   checkout. Run 1 mirrors it in `docs/plan/run1-tasks.md`. Suggest: keep the ledger under `tasks/` (committed).

### B2. Git, GitHub, tokens
7. **Local `main` had no upstream.** The first commit is made locally and never pushed from the sandbox, so plain
   `git pull` on `main` did nothing ("no tracking information"). Suggest: setup.sh runs
   `git branch --set-upstream-to=origin/main main` after the first merge, or docs say `git pull origin main`.
8. **GitHub repo created with an initial commit** (template .gitignore) gave unrelated histories; run 1 merged it
   into the bootstrap branch. Suggest: SETUP.md says "create the repository empty (no README, no .gitignore)".
9. **Token scopes.** Pushing `.github/workflows/*` needs the `workflow` scope; fine-grained tokens only cover repos
   of their resource owner, so moving the repo to an organization required a new token (resource owner = org).
   Suggest: SETUP.md lists the exact fine-grained permissions (Contents, Workflows, Pull requests: read/write) and
   says to create the repo under the final owner first.
10. **Human edits left uncommitted** (CLAUDE.md, staged binaries) blocked `task.py start` and had to be stashed and
    restored. Suggest: SETUP.md tells the human to ask the orchestrator to commit any edit on an `arch/` branch, and
    to drop binaries without `git add`.

### B3. Sandbox environment
11. **Xvfb could not start** (lock file in `/tmp`); fixed by PR #2, which allows writes to all of `/tmp`. Consider a
    narrower rule if Xvfb can be pointed at another lock directory.
12. **No PDF tools** (`pdftotext`/`pdftoppm`) in the sandbox; reading Apple's Metal Feature Set Tables needed a
    workaround. Suggest: install `poppler-utils` during setup.
13. **The sandbox placeholders** (`.idea`, `.vscode`, `.claude/commands`, ...) are character devices; `git add -A`
    failed on them. Fixed in `.gitignore` in run 1 (no trailing slash). Carry the fix into the kit.

### B4. Engine and third-party findings
14. **gdUnit4 does not list Godot 4.7.2** (v6.2.2: up to 4.7.1; its own suite on 4.7.2: 2 of 1,649 failed). Run 1
    uses an in-repo runner (`godot/addons/test_runner/`). Re-check gdUnit4 v7 for the next game.
15. **`Core` autoload name in `-s` scripts:** the runner and its base class are compiled before autoload names exist;
    they look the autoload up as a node. Scripts loaded later can use `Core`.
16. **Frame counting:** awaiting `process_frame` from code that was itself resumed by `process_frame` can resume in
    the same frame; count `Engine.get_process_frames()` instead (runner and core automation do).
17. **`ProjectSettings.save()` drops values equal to defaults** and the header comment; run 1 re-added the explicit
    renderer/driver/orientation lines.
18. **Mobile renderer limits that shape art direction:** no SSR, VoxelGI, SDFGI, SSIL or volumetric fog; 8 omni +
    8 spot lights per mesh; LightmapGI and reflection probes are supported. Put these in ASSETS.md guidance.
19. **Metal on iOS needs iOS 16.0+**; the iOS simulator only supports the Compatibility renderer (test on device).

### B5. ComfyUI workflow
20. Export the workflow with **exactly one** LoadImage node (run 1 had a second example image that would have been
    fed into every run). The README example key `frames` does not fit workflows that take a duration in seconds;
    run 1 uses `seconds`. Suggest: README lists both patterns.

---

## Part C. Findings during run 1 (appended per milestone)

### Planning (Phase B, 2026-10-25)
- Budgets are estimates where no authoritative source exists (marked in docs/qa/budgets.json); validate on device.

### M1 greybox
(to be filled in)

### M2 art
(to be filled in)

### M3 iOS device build
(to be filled in)
