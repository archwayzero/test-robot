# hero / idle_loop: motion reference (T012)

**Verdict: usable (accepted on try 1).** Identity and the digitigrade leg design are kept the whole time. The motion
is very subtle, so use it for pose and weight-shift timing only.

| | |
|---|---|
| Video | `idle_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio track. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270 = character's left side, facing image-left) |
| Seed / tries | 1001 / 1 of 3 |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps (every 2nd source frame); `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers below are **0-based source frames at 24 fps**. In-game the clip runs at 30 fps: retime, don't copy
frames 1:1.

## Prompt (action part; the shared design/background paragraph is in meta.json)
"The character in <Picture 1> stands in place in a relaxed idle pose, seen in strict side view (profile), facing
left, with a locked static camera. Subtle continuous idle loop: slow breathing, a slight weight shift from one leg to
the other, arms hanging relaxed at the sides with a small sway. The blade feet stay planted on the ground and do not
slide; the knees and backward-bending hocks flex only slightly with the weight shift. ..."

## What the clip shows
- A static camera on a strict profile. The character stands upright with arms hanging, the backpack on its back and
  the hood up.
- Legs: the thigh plates reach to the knee, the shins slant back to the hock, and the three-tine reverse-C blade feet
  stay planted throughout (no sliding is visible at this resolution).
- Key poses: **upright/neutral** at frames 0-12, 36-48 and 116-122. **Knees slightly flexed, weight settling down
  and forward** at about 16-26 (peak ~20) and 80-86 (peak ~82). Between those the body returns to upright, with a
  very small sway.
- Breathing is not clearly visible at this scale. The chest motion, if any, is under 2-3 px.
- **Loop:** frames 0 and 122 are close (both upright). The best single loop is **0-122**, the whole clip. A shorter
  loop is 36-98 (upright -> dip at 82 -> upright).

## Known artifacts
- The character is small in the frame (about 330 px tall) and lit dark, so fine detail is limited.
- The weight shift reads as a small knee dip rather than a clear left/right shift, because the legs overlap in profile.
- This is a generated motion guide, not ground truth. Timing and amplitude are approximate.
