# hero / jog_loop: motion reference (T012)

**Verdict: good (accepted on try 1).** Identity is kept, and the **digitigrade legs and blade feet are kept** in
every frame. A clear running gait with knee drive, a forward lean, bent arms swinging and a short flight phase.
Treadmill-style, in place, strict profile. It is very regular, which makes it easy to loop.

| | |
|---|---|
| Video | `jog_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | 1201 / 1 of 3 |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. In-game: 30 fps, in place, 4.0 m/s. Retime to the matching
stride.

## Prompt (action part; the design/background paragraph is in meta.json)
"The character in <Picture 1> jogs forward at a steady, moderate running pace (a light jog, faster than walking,
with a brief flight phase where both feet are off the ground) in a continuous, looping jog cycle, seen in strict
side view (profile), facing left. The camera tracks alongside like a treadmill shot ... Each stride: a blade foot
plants on the ground under the body, the backward-bending hock compresses, the leg pushes off strongly and the knee
drives forward. Arms bent, swinging opposite to the legs, slight forward lean."

## Cycle and key poses
**Step period ≈ 8 frames (0.33 s); full stride ≈ 16 frames (0.67 s)**, very regular across the whole clip. The legs
overlap in profile, so the two steps are called A and B. Frames are ±1-2.

| Event | Step A | Step B | A | B | ... |
|---|---|---|---|---|---|
| **Contact / mid-stance** (stance blade under the hips, knee of the swing leg driven high and forward) = **lowest** | 2 | 10 | 18 | 26 | every +8 |
| Push-off (stance leg extended behind; long stride shape) | 4-6 | 12-14 | 20-22 | 28-30 | |
| **Flight / highest** (both blades off the ground, legs split front/back) | 6 | 14 | 22 | 30 | |

Visible detail: in the swing the blade hooks trail behind and up (the hook opens backward). At contact the hook tips
land under or slightly ahead of the hips and the hock compresses. The arms are bent about 90° and swing opposite to
the legs, with the forward hand at chin/chest height.

**Loop:** 2 -> 66 (4 full strides, 64 frames). A single stride is 2 -> 18. Any 16-frame window that starts at a
contact works.

## Known artifacts
- The blades get slightly thinner/blurred in the fastest swing frames (motion blur), but the hook shape stays readable.
- Left/right leg identity is ambiguous in silhouette.
- The cadence (180 steps/min) is plausible for a jog, but the stride length can't be measured on a treadmill shot.
  Derive it from 4.0 m/s.
- A generated motion guide, not ground truth.
