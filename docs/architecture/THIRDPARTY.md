# Third-party code

| Name | Source URL | Pinned commit/tag | Location | Notes |
|---|---|---|---|---|

Nothing is vendored yet.

## Evaluated, not installed (bootstrap, 2026-10-25)
| Name | Source URL | Ref evaluated | Decision | Why |
|---|---|---|---|---|
| Maaack's Godot Game Template | https://github.com/Maaack/Godot-Game-Template | `v1.7.0` (`4daf56910b1e4000fff20ca80722e383bf06a4f3`) | skipped (human, bootstrap) | Its plugins register 3 autoloads (SceneLoader, ProjectMusicController, ProjectUISoundController), which breaks "core is the only autoload"; ships an online `plugin_updater`. Revisit when menus are specified. |
| gdUnit4 | https://github.com/MikeSchulze/gdUnit4 | `v6.2.2` (`0127a55f4543dfc24746f6e5c7ba6f94105d51f2`) | skipped: compatibility with 4.7.2 not confirmed | README/CI list Godot 4.7 and 4.7.1, not 4.7.2. Its own suite, run headless on 4.7.2.stable in a scratch copy: 1649 cases, 2 failed (`GdUnitSceneRunnerTest.test_simulate_scene_interact_with_buttons`, simulated mouse clicks on Buttons; `GdMarkDownReaderTest.test_tobbcode`, self-updater only), 33 skipped. Could not re-run with a display to rule out headless mode (Xvfb is blocked by the sandbox, see final bootstrap report). Also contains .png/.zip files that would need DVC. |
