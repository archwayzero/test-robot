# Platform (human-written; read before bootstrap)

- Target platform: iOS
- Minimum device: iPhone 12
- Orientation: (landscape)
- Target frame rate: 30 fps
- Godot version: pinned at bootstrap. Use the SAME version on the PC (preview) and the Mac (final build).
  **Pinned: Godot 4.7.2.stable.official (build `ed1daf0bf`, tag `4.7.2-stable`).**

## Build stages
1. Development in WSL2 under Claude Code's sandbox (Linux): code, assets, automated tests, static budget checks,
   CPU-rendered screenshots. No GPU inside the sandbox.
2. Preview on the PC host: open `godot/project.godot` in the pinned Godot version and play it.
   Only run reviewed/merged commits: game scripts are code and run with your user's permissions.
3. Final step on a Mac: unzip the package from `dist/` (made by tools/release/make_mac_package.py after you merge
   the release PR), open it in the pinned Godot version, export the Xcode project (iOS export only works on
   macOS), then build, sign and run on the device with Xcode. On-device profiling happens here.

## Renderer
The Mobile renderer is the usual choice for iOS. The orchestrator verifies this for the pinned Godot version
(including whether Apple's native Metal driver is available) and records the decision in docs/architecture/ARCHITECTURE.md.

**Decision (bootstrap, 2026-10-25):** Mobile renderer, set explicitly so PC previews match the device; native Metal
driver on iOS (`driver.ios="metal"`, the 4.7.2 default). Verified against the Godot 4.7 docs and the 4.7.2-stable
ProjectSettings reference; sources in ARCHITECTURE.md, "Engine and renderer". Note: the iOS simulator supports only
the Compatibility renderer, so test on a real device. Native Metal requires iOS 16.0 or newer on the device
(iPhone 12 supports it); set the iOS export minimum OS to 16.0 or later.

## Budgets
Not written here. The orchestrator researches budgets for the minimum device, cites sources in
docs/qa/budgets.json, and the human approves them before asset work starts.
