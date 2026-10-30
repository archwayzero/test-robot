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
- **Out-of-memory crash (T002, first attempt).** A core test re-launched Godot (`OS.execute`) to get an exact
  fixed timestep; the child judged "exact" from an early frame's delta (under `--fixed-fps 30` the first deltas are
  0.025 / 0.0333 / 0.0417 s), so it re-launched again, recursively, ~300 MB/s until the OOM killer ended the session.
  Fixes: no process spawning in code/tests (agent rules + review check); `tools/qa/memguard.py` around every heavy
  command; memory rule in WORKFLOW.md. Next game: put memguard and the no-spawn rule in the kit from day one.
- **`--fixed-fps` is stripped from `OS.get_cmdline_args()`** in Godot 4.7.2; core detects it via `/proc/self/cmdline`
  (Linux only). Next game: pass the value as a user argument too (after `--`) so detection is portable.
- **Measured job peaks** on the 28 GB dev machine: capture ~0.5 GB, 20 s recording ~0.3 GB, test suites < 0.1 GB
  (WORKFLOW.md). Godot jobs are cheap; the risk is runaway code, not rendering.
- **The in-house test runner reported crashed tests as PASS** (found by module-dev in T008): a runtime script error
  aborts the test function without a failed assert. Fixed: the runner registers a Godot `Logger` (4.5+) and fails a
  test on any SCRIPT-type error; intentional `push_error` stays allowed. Next game: start with this (or gdUnit4).
- **Security review of cloud data paid off (T008).** `str_to_var` on untrusted data can instantiate objects; a
  substring filter was bypassed with whitespace/comments. Fixed with `JSON.from_native`/`to_native(allow_objects=false)`
  plus a type whitelist and a null-count check. Next game: rule in the kit "never str_to_var untrusted data".
- **A newer but invalid cloud snapshot could overwrite the local save** (T008): Core's `restore()` is void and silently
  ignores invalid data. Fixed by verifying the state after restore. Next game: make `restore()` return an Error.
- **Contract gaps found by reviewers:** stance ints shared across modules without a constant (now `StateKeys.STANCE_*`);
  camera orbit must ignore emulated mouse events; boot order for autosave (`setup` before `restore`).
- **Keyboard always runs in the PC preview:** WASD is full joystick deflection, so walk needs a modifier. Next game:
  specify keyboard controls separately (e.g. Shift = run, default walk).
- **`.claude/agents/` is read-only to shell commands** in the sandbox (like `.claude/skills/`); the orchestrator edits
  them with the file-edit tool, which the scope hook governs.
- **Safe area not specified** (found reviewing T007): a 16 px HUD margin puts the mini-map under the landscape notch
  of iPhone 12. Run 1 lays the HUD inside `DisplayServer.get_display_safe_area()` (D17). Next game: PLATFORM.md
  should state orientation, safe-area handling and which side the notch may be on.
- **Small modules should resync on re-entering the tree** (exploration, minimap reviews): both reconnect signals but
  miss changes made while detached. Harmless with the current boot order; next game: put "resync on enter_tree"
  in the module template.
- **Abstract signature changes cannot land before their implementation:** GDScript rejects an override whose
  signature differs from the `@abstract` parent, which breaks every test that loads core. An arch PR first breaks main;
  committing the public change on the task branch is blocked by the commit hook (orchestrator's paths are outside
  module-dev's scope). Run 1 kept `restore() -> void`. Next game (kit): either let the commit hook accept the
  module's own `public/` from the orchestrator on a task branch, or design `restore() -> Error` from day one.
- **Non-breaking way to grow an interface:** add the method to `public/` as a normal (non-`@abstract`) method whose
  body push_error()s, merge that, then the module task overrides it. Used for `PlayerController.restore_stance()`.
- **Interface gap found by composition (T009):** the player had no way to apply a saved stance, so "same stance after
  reload" (E12) was impossible. Next game: derive the public API from the save/restore test cases up front.
- **M1 QA (T010) found:** float rounding in the cloud JSON envelope (`JSON.stringify` defaults to non-full precision);
  the low-passage camera collapsing onto the player (visible only in videos, not in unit tests); and that the
  recording tool ran without test mode, so playthroughs deleted the real save slot 0. Next game: capture/record
  tools start in test mode from day one, and every test hook QA needs is in the public API before QA starts.
- **Godot 4.7.2 text floats are not exact** (T029 review): `String.to_float`, JSON number parsing and
  `JSON.to_native`'s "f:" strings return a different double for ~12% of values even with 17 digits. Saves that must
  be exact use `var_to_bytes` (cloud envelope v3); `bytes_to_var` without objects is the safe decoder. Next game:
  specify binary save payloads from the start, and keep e2e tests format-agnostic via a public decode hook.
- **Desktop focus-out must not pause previews/recordings;** only mobile pauses on focus loss (D12 in run 1).

- **Godot 4.7.2 VM bug can make tests pass without asserting (N1, found in T032, reproduced by the reviewer):** after
  `await wait_until(<lambda>)` in a coroutine whose lambdas capture locals, an `if` body that declares a local is
  skipped although its condition is true; a probe showed the condition expression evaluating to a
  `GDScriptFunctionState`. T010's E11 gap check sat in such a block, so it never ran (it would have caught F2 earlier).
  Run 1: TEST_PLAN rule "assertions after an await go in a plain helper", a checkpoint guard in the e2e base, audit
  tasks T033-T036, upstream report drafted (docs/retrospective/upstream/). Next game: put the checkpoint guard in the
  test runner itself (every test must reach its end, counted outside the coroutine), and add the rule to the kit.
- **M1 QA re-run (T032): 15/15 e2e, 230/230 overall;** fixes verified by numbers (exact float round-trip, 300-frame
  throttle gap, player 4-7% of the frame in low passages). Two QA rounds per milestone are normal; budget for them.

### M2 art
- **The provided hero was upper body only** (T011): legs ended in capped stumps at mid-thigh; the "0.98 m tall"
  figure in the asset notes was stump-to-head. Found by the modeler's first inspection render. The human supplied a
  full-body reference; the modeler generates digitigrade legs. Next game: check every provided model with front/side/
  below renders and a completeness checklist (head, hands, feet, pose) before planning, and ask for A-pose sources.
- **Modeler worked from a single side view (T011):** two scripted leg passes guessed the unseen angles; the
  orchestrator only used reference-director for motion clips (after modelling), as the plan listed it. The human
  pointed out that the same ComfyUI workflow can produce a turnaround first (T038: 360 deg orbit + 8-angle stills,
  ~20 min). Next game: the asset pipeline starts with a turnaround for every image-based asset, and the modeler
  compares renders per angle (now in ARCHITECTURE.md "Turnaround references").
- **Reference notes need review against the image:** the first T038 notes (and the contract) described the hero's
  feet as "toes forward"; they actually sweep backward and hook forward at the tips. The reviewer caught it by
  measuring on a pixel grid. Next game: describe shapes with direction + measured proportions, not one-word summaries.
- **Scripted Blender limits for organic shapes:** primitives along hand-placed paths give stiff mechanical parts.
  Better scripted routes: curves traced from the reference with bevel/taper, high-poly (remesh/subdivide) baked to
  a low-poly normal map; or generate the part with image-to-3D (Tripo) and conform it.
- **Agent definitions cannot be updated through git inside the sandbox:** `.claude/agents/` is read-only to shell
  commands, so `git switch`/`git pull` fail when a commit changes those files; the human ran the pull. Next game
  (kit): make `.claude/agents/` writable for git in the sandbox, or keep agent rules that change during a run in docs/.
- **"Separate rigid pieces per bone" was an orchestrator mistake (T011 pass 3):** I added it to the brief to make
  rigging easy; it produced disjointed legs, and I reported pass 3 as "a clear improvement" although the reviewer had
  flagged the shin as vertical (a regression). The human caught both. Fixes that worked: one continuous leg mesh,
  landmarks measured on the reference, a 61-row check script run on every rebuild, and the reviewer scoring
  structure out of 10 with the human's rule "not 10/10 -> another pass, don't come back". Passes 4-7: 7.25 -> 8.5 ->
  9.5 -> 10. Next game: never summarise around a failing number; quote it.
- **Usage limits interrupt agents:** the pass-6 modeler stopped mid-work at the API usage limit; it was relaunched
  with a resume brief from the uncommitted state. Fixed in CLAUDE.md "Session continuity" (commit per pass,
  STATUS.md, resume procedure).
- **The modeler's Write hook blocks `.captures/`:** its QA scripts live in `blender/models/hero/qa/` and write
  output into `.captures` from there. Next game (kit): allow scratch writes to `.captures/` for every agent.
- **Reference clips (T012):** a side-view snapshot made the generator keep the camera and the digitigrade legs in
  all 8 clips (front view reads the legs as stilts). Treadmill framing gives no ground reference and left/right legs
  can't be told apart; the jump clip drifted in material. Reviewer-found cycle-length error in crawl notes would have
  halved the crawl speed. Next game: ask for a visible floor line in every locomotion prompt.
- **Rig quality loop (T013):** pass 1 passed every hard limit but scored 5.5-8/10 on fidelity (jump timing not
  matched to the controller's airtime, hovering crawl knees, kneeling-lunge crouch walk). Four passes to >= 8.5 on
  every clip. The check script missed the crouch-walk defect until a knee-clearance rule was added. Next game:
  derive clip timing from the controller constants (jump airtime = 2 v / g) and put contact/clearance rules for
  every clip in the brief from the start.
- **Godot strips `_loop` from clip names on import** (T013): `walk_loop` arrived as `walk`. Fixed per rig with
  `use_name_suffixes=false` + explicit loop modes; the contract had claimed the names were kept.
- **Speed vs reference cadence:** at the game speeds (crouch walk 1.0, crawl 0.5 m/s) the generated references'
  slow cadence would need ~2 m strides; clips step faster than the references. Next game: choose speeds and
  reference cadence together (or generate references with the intended speed in the prompt).
- **Vacuous QA test (T014):** the first loop-seam assertion compared frame 0 with itself (Godot wraps `seek(length)`
  to 0 on looping clips), so it could never fail; the reviewer caught it. Next game: every new QA check ships with a
  self-test that proves it can fail (now in the T014 tests; add to TEST_PLAN.md).
- **Subagents and background shells don't survive a session exit:** only the main conversation can be resumed.
  Everything durable must be in git/DVC/files: CLAUDE.md "Session continuity" + docs/plan/STATUS.md.

### M3 iOS device build
(to be filled in)
