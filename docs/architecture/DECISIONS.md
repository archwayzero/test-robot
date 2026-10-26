# Decisions for run 1 (approved deviations from and additions to the human specs)

The human specs in docs/specs/ are left as written. Where they are silent, ambiguous, or conflict with the project's
rules, the orchestrator proposed a default (Phase A plan, 2026-10-25) and the human said: build run 1 with the
defaults and record the corrections for the next game (docs/retrospective/run1-corrections.md). Agents follow THIS
file where it differs from docs/specs/.

| # | Topic | Spec says | Run 1 decision |
|---|---|---|---|
| D1 | Camera | (nothing) | Third-person follow camera with wall collision (`player`) |
| D2 | Jump | only in RIGGING_ANIMATION.md | Included (`jump` action, `jump` clip) |
| D3 | Right-hand control | one button for jump + crouch + crawl | Two buttons: **Jump**, and **Stance** (cycles stand -> crouch -> crawl -> stand). Run = joystick deflection >= 70% |
| D4 | Idle animations | not listed | Added `idle_loop`, `crouch_idle_loop`, `crawl_idle_loop` |
| D5 | Purpose of crouch/crawl | (nothing) | 4-8 low-passage cells (crouch-only and crawl-only), never the only route anywhere |
| D6 | Maze construction | modeler draws a base map into reference/map and models the whole maze | Layout = seeded grid in the `maze` module (fixed seed, same maze for everyone); modeler builds a modular kit (docs/contracts/crypt-kit.md); Godot assembles it. Reason: the mini-map needs layout data, `reference/` belongs to reference-director, and assembling in Godot keeps per-mesh light and occlusion limits manageable |
| D7 | Maze size | (nothing) | 20 x 20 cells of 4 m (~80 m square), seed 20261025 |
| D8 | Hero height | model is 0.98 m | Adult; the modeler chooses a plausible height (1.65-1.85 m) and records it |
| D9 | Lighting | (nothing) | Wall lamps (`wall_lamp` asset) about every 3 corridor cells; baked LightmapGI if it can be baked headless, else real-time omni lights (<= 8 per mesh, Mobile renderer limit); no player light |
| D10 | Reference photo content | (image includes a statue and floodwater) | No statue (copyrighted artwork), dry floor (Mobile renderer has no screen-space reflections) |
| D11 | Cloud save | "saved automatically to the cloud whenever player progresses" | Local autosave on each newly explored cell (max every 10 s) and when the app is backgrounded; cloud mirror via a `CloudBackend`; iCloud key-value backend built at the Mac stage (native plugin, needs the Apple Developer entitlement). Sandbox uses local + fake backend |
| D12 | Menus, pause, audio, win condition | (nothing) | Boot straight into the maze; pause while the large map is open and when the app is backgrounded; no audio; no win (no exit, as written) |
| D13 | Textures | "as realistic as can be rendered" | No human-supplied textures in run 1: procedural Blender materials baked to tileable maps (expect a procedural look) |
| D14 | Hero animation | 5 clips | Scripted rig + 8 scripted clips from reference videos (expect stiff motion, especially crawl and jump) |
| D15 | Mechanic ids | not numbered | M1 movement, M2 maze, M3 mini-map, M4 save, M5 controls |
| D16 | Budgets | from platform budgets | docs/qa/budgets.json values as proposed in Phase A, approved for run 1 only; estimates are marked there |
