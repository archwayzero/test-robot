# hero / crawl_idle_loop: motion reference (T012)

**Verdict: usable with caveats (accepted try 2 of 2).** It shows a steady hands-and-knees pose with the
digitigrade legs folded correctly: the knee pod is on the floor, and the shin and three-tine blades trail behind with
the blade tips on the ground. The motion is minimal (a small head and torso sway), so use it mainly for the pose.

| | |
|---|---|
| Video | `crawl_idle_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | **1502** (accepted) / 2 of 3 (rejected: 1501, prompt in `rejected_s1501.meta.json`) |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. Retime to 30 fps in-game.

## Prompt (action part; the design/background paragraph is in meta.json)
"The character in <Picture 1> is down on all fours on the floor, on hands and knees, body low and roughly
horizontal, head up looking forward, staying in place in one steady pose. ... Same dim lighting and same plain flat
uniform grey background as <Picture 1>, no pattern, no spots ... The rounded knee joints rest on the floor, the thin
backward-bending shins and the curved blade-tine feet trail behind the knees with the blade tips resting on the
ground, the hands are flat on the floor under the shoulders. Subtle continuous idle loop ... does not stand up, move
forward or change pose. ..."

## Tries
1. **Seed 1501: rejected.** The pose and legs were good (knees on the floor, shins and blades trailing). But the
   background turned into a bright wall with olive spots, the colours shifted to bright orange, and at ~frame 46 the pose
   changed: one leg goes from extended back to tucked under the hip.
2. **Seed 1502: accepted.** Plain grey background with a soft vignette spotlight. The pose stays the same for the whole
   clip.

## Key poses (one held pose)
- The camera is closer than in the standing clips: the crawling body fills about 2/3 of the frame width.
- Hands: flat on the floor ahead of the shoulders, arms nearly straight and slightly angled forward.
- The torso is roughly horizontal and slightly higher at the hips. The backpack sits on top, and the head hangs low and
  forward (the hood hangs down; the face looks down and forward rather than "head up").
- Legs: the thigh plate is near vertical from the hip down to the knee pod resting on the floor. The thin shin runs
  back from the knee along/just above the floor, and the three blade tines arch up and back and come down with their
  tips on the floor behind. The near and far legs overlap almost perfectly, so effectively one leg is visible.
- Motion: a slight head bob and a small torso rise/fall (breathing-like), a few px. There is no weight rocking between
  hands and knees. Lowest/highest torso points are not distinct enough to name frames.
- **Loop:** the whole clip, **0-122**. Start and end are nearly identical.

## Known artifacts
- The look is more stylised and better lit than the input. The orange face markings on the hood/face are stronger
  (they exist on the model but are exaggerated here).
- Only one leg is visible (depth overlap). Infer the far leg by symmetry.
- The head is lower than asked ("head up" was not followed).
- A generated motion guide, not ground truth.
