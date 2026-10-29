# hero motion reference clips (T012)

Generated with `tools/comfy/workflows/ref_to_video.json` (MiniMax H3 reference-to-video, sha256 69012be1...),
864x480 at 24 fps, from **`snapshot_side.png`**: the exported `godot/assets/hero/model/hero.glb` rendered at
azimuth 270 (the character's left side, facing image-left, like `full_body.png`). Each folder has the video,
`meta.json` (exact prompt and seed), `frames/` (12 fps) + `contact_sheet.png`, and `NOTES.md` (key-pose frames, loop
range, artifacts). Frame numbers are 0-based source frames at 24 fps. In-game clips are 30 fps and in place, so retime.

| Clip | Folder | Seed | Tries | Verdict | Best loop / range (24 fps frames) |
|---|---|---|---|---|---|
| idle_loop | `idle_loop/` | 1001 | 1 | usable: legs kept, motion very subtle | 0-122 |
| walk_loop | `walk_loop/` | 1101 | 1 | **good**: digitigrade + blades kept, clear phases; slow cadence (stride 44 f) | 20-108 (2 strides) |
| jog_loop | `jog_loop/` | 1201 | 1 | **good**: digitigrade + blades kept, very regular (stride 16 f) | 2-66 (4 strides) |
| crouch_idle_loop | `crouch_idle_loop/` | 1301 | 1 | usable: starts standing, sinks into the crouch; use the hold | 60-122 (hold) |
| crouch_walk_loop | `crouch_walk_loop/` | 1401 | 1 | **good**: low body, legs kept (stride 46 f) | 24-118 (2 strides) |
| crawl_idle_loop | `crawl_idle_loop/` | 1502 | 2 | usable: steady pose, legs fold correctly; legs overlap, minimal motion | 0-122 |
| crawl_loop | `crawl_loop/` | 1603 | 3 | usable: correct on-all-fours leg fold; cycle irregular | 0-104 (2 alternations of ~52 f = 1 full two-leg cycle); 56-104 = 1 alternation |
| jump | `jump/` | 1703 | 3 | usable for phases/poses; **look drifted** (bronze/gold, closer camera) | one-shot 0-80 (takeoff 0-28, air 28-44, land 44-80) |

The generator **kept the digitigrade legs and three-tine hook feet in all 8 accepted clips**. None of them turned the
legs into human legs. The left/right leg identity is ambiguous in profile silhouettes, so the NOTES label alternating
steps A/B.

## Snapshots
- `snapshot_side.png` (azimuth 270): **used for all clips.** It shows the shin-to-hock slant and the reverse-C blade
  hooks most clearly, and the generator keeps the input camera angle (seen in T038), so a profile input gives the
  profile camera the locomotion clips need.
- `snapshot_front.png` (azimuth 180) and `snapshot_three_quarter.png` (azimuth 225): rendered for comparison, not
  used. From the front the legs read as straight stilts (the bend is hidden). Note: azimuth 0 shows the hero's BACK,
  because the hero faces -Z in Godot (= glTF -Z).

Limits: these are generated motion guides, not ground truth. Proportions, foot placement (treadmill shots have no
ground reference) and timing can drift. Trust only what the contact sheets show.
