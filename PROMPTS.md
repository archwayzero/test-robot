# Prompts

Before Prompt 1: fill in docs/specs/PLATFORM.md (target iOS, minimum iPhone 12, orientation, frame rate).
Run Claude Code from the repository root (in WSL2, with the sandbox on; see SETUP.md). Paste Prompt 1 once. After you fill in
`docs/specs/*.md` and merge the bootstrap PR, paste Prompt 2.

---

## Prompt 1: bootstrap (architecture, hooks, DVC, Godot skeleton)

```
You are bootstrapping a Godot + Blender game project in WSL2 under Claude Code's sandbox. This repository already
contains an architecture kit. Read CLAUDE.md, docs/specs/PLATFORM.md, docs/architecture/ARCHITECTURE.md and
docs/architecture/WORKFLOW.md first.

Goal of this session: reach a clean, verified, committed baseline. No gameplay and no art assets yet.

Rules for this session
- Do not install software or change system or network settings without telling me exactly what and why,
  and waiting for my OK.
- Never edit locked files: .claude/hooks/**, .claude/settings.json, tools/githooks/**, tools/scope_lib.py,
  tools/precommit_checks.py, tools/setup.sh, tools/envcheck.py, docs/module-map.json. Add modules only via
  tools/new_module.py (it updates docs/modules.json).
- If a hook blocks a command, report it to me. Do not look for a workaround.

Steps
1. Preflight: report versions of git, python3, dvc, blender, godot (`godot --version`), ffmpeg and
   `claude --version` (hook failure-blocking needs Claude Code 2.1.295 or newer; tell me if older). Check
   network access: `git ls-remote https://github.com/godotengine/godot HEAD`. If anything is missing,
   stop and tell me what to install. Also run `python3 tools/comfy/comfy_client.py ping` and report whether
   ComfyUI is reachable (it runs on Windows on my GPU; only needed later for reference videos). Then run
   `python3 tools/sandbox_selftest.py` and show me the full output. If any line says FAIL, stop and tell me.
2. I already ran `tools/setup.sh` outside the sandbox (SETUP.md part F). Do NOT run it: inside the sandbox it
   cannot write git/DVC config, by design. Instead confirm: `git config core.hooksPath` prints tools/githooks,
   `dvc remote list` shows the storage remote, and `python3 tools/sandbox_selftest.py` passes. Then make the
   first commit (allowed once on an empty repo): `git add -A && git commit -m "chore: bootstrap kit"`, and
   `git switch -c arch/bootstrap`.
3. Create the Godot skeleton: write godot/project.godot (config_version=5, project name, config/features
   matching the installed Godot major.minor). Pick the renderer for the target in PLATFORM.md (the Mobile
   renderer is the usual choice for iOS): verify against the docs for this Godot version, cite the source,
   and record the decision and the exact Godot version in docs/architecture/ARCHITECTURE.md and PLATFORM.md.
   I will use the same Godot version on my PC to play previews and on my Mac for the final Xcode build.
   Verify with `godot --headless --path godot --import`.
4. Optional, ask me first: pull the UI template https://github.com/Maaack/Godot-Game-Template (menus,
   options, pause, credits, scene loader; Godot 4.3+). Verify the URL with `git ls-remote`, pin a release
   tag or commit, install ONLY its addon folder(s) into godot/addons/ following its README, and do not copy
   its example game scenes into modules. Also consider a test framework such as gdUnit4
   (https://github.com/MikeSchulze/gdUnit4) only if you can confirm it supports our Godot version. If you
   cannot confirm compatibility, skip and tell me. Record each in docs/architecture/THIRDPARTY.md
   (name, URL, pinned ref, location).
5. Create the core module: `python3 tools/new_module.py core "Event bus, game state, save/load interfaces"`.
   Write its public/ interface (typed event-bus signals, a minimal GameState interface, and the test
   automation API: input injection, state snapshot, fixed seed and timestep, test runs only) and the interface
   section of godot/modules/core/CLAUDE.md. Register core as the only autoload in project.godot.
6. Verify: tools/task.py runs, Godot imports headless, `python3 tools/qa/check_budgets.py` runs (no assets yet
   is fine), and `python3 tools/sandbox_selftest.py` still passes.
   Commit on arch/bootstrap in small commits.
7. If a git remote `origin` exists, `git push origin arch/bootstrap` (the pre-push hook runs dvc push
   first). If not, tell me. Do not add or change remotes.
8. Final report: what you created, pinned versions, self-test output, anything skipped, and what I do next
   (fill docs/specs/*.md, put my ComfyUI workflow + map in tools/comfy/workflows/, merge the PR, enable
   branch protection on main, run Prompt 2).
```

---

## Prompt 2: plan and build from the specs

```
The architecture is merged to main and docs/specs/MECHANICS.md, ASSETS.md and RIGGING_ANIMATION.md are
filled in. Act as the orchestrator (see .claude/agents/orchestrator.md).

Phase A: plan only, no code
1. Read the three specs and docs/architecture/*.
2. In ONE message propose: the module list (name, responsibility, depends_on) and the dependency graph;
   a public interface sketch per module; the asset list mapped to mechanics; and the task list with
   owning agent and dependencies (asset pipeline: modeler -> reference-director for animated assets ->
   rigger-animator -> qa). Flag spec gaps or conflicts, and any asset that scripted Blender modeling or
   rigging probably cannot deliver at the requested quality.
3. Testing design: draft docs/qa/TEST_PLAN.md (layers, acceptance tests per mechanic, test runner) and
   propose values for docs/qa/budgets.json for the minimum device in PLATFORM.md, each with a cited source
   (Apple/Godot docs or reputable profiling write-ups); mark any value you had to estimate. Separate what
   this sandbox can check (static budgets, headless tests) from what only my PC preview or the Mac/device
   run can check. Then wait for my approval.

Phase B: set up the architecture (after approval)
4. On an arch/<slug> branch: create modules with tools/new_module.py, write each module's public/
   interface and CLAUDE.md, update docs/architecture/ARCHITECTURE.md (module table and dependency
   graph), write the approved TEST_PLAN.md and budgets.json, and add the tasks with tools/task.py.
   Commit, push the branch, and ask me to merge.

Phase C: execute tasks (after I merge)
5. For each task in dependency order, one at a time: `tools/task.py start` -> delegate to the owning
   agent with task id, spec paths, allowed paths and definition of done -> delegate review to `reviewer`
   -> `tools/task.py finish` -> push the task branch -> tell me the branch name for PR review.
   Do not start a task whose dependency is unmerged. At each milestone, run a qa task (budgets + e2e + gameplay
   videos) and tell me where the videos are and what to look for.
6. After each task, summarize: files changed, tests run, DVC artifacts added, open issues.

Stop and ask me if: a hook or scope blocks required work, an interface must change, a spec is
ambiguous, or an asset cannot meet its spec.
```

---

## Prompt 3: add features later

```
I updated docs/specs/<file>.md. Diff it against what is already built, plan ONLY the delta
(new or changed modules, interfaces, assets, tasks), show me the plan, and wait for approval before
creating anything. Follow the same phases as before; never change an existing public interface
without telling me which modules it affects.
```

---

## Prompt 4: release for the Mac (last step)

Godot can only export iOS on a Mac with Xcode, so the sandbox produces a source package: the approved
Godot project plus all DVC assets. You export the Xcode project and build on the Mac.

### 4a: release candidate (needs your PR approval)

```
Prepare a release candidate for the Mac/Xcode build. On an arch/release-<version> branch:
1. Delegate a qa task: full end-to-end suite plus `tools/qa/check_budgets.py`. qa writes
   docs/qa/reports/release-candidate.md whose first line is exactly `RESULT: PASS` or `RESULT: FAIL`,
   followed by the static budget score and findings. If FAIL, stop and report; do not continue.
1b. Delegate a second qa task: the network and data audit (see .claude/agents/qa.md). qa writes
   docs/qa/reports/network-data-audit.md starting with `RESULT: PASS` or `RESULT: FAIL`. If FAIL or it lists
   open questions, stop and show me; do not continue until I decide.
2. Add or update the iOS export preset in godot/export_presets.cfg for the pinned Godot version (verify
   option names against the docs; leave the App Store Team ID and bundle identifier as clearly marked
   placeholders for me to fill in on the Mac).
3. Write docs/IOS_HANDOFF.md: exact Godot version and export templates needed, how to open the package,
   where to fill in Team ID and bundle id, export steps, Xcode build/sign steps, what to profile on the
   iPhone 12 and how to report results back, and known risks from the budget report.
4. Commit, push the branch, and ask me to review and merge the PR. Then stop.
```

### 4b: build the package (after you merge)

```
I merged the release PR and ran `git pull` on main myself. Confirm `git status` is clean on main, then run
`python3 tools/release/make_mac_package.py --version <version>`.
It refuses unless the commit is on main, the tree is clean, budgets are approved and pass, the QA release
report and the network and data audit both say PASS and are newer than the last game change, and all DVC assets
are present. If it refuses,
report the exact reason and stop; do not work around a gate. If it succeeds, tell me the path of the zip in
dist/ and summarize MANIFEST.json (commit, score, file count).
```
