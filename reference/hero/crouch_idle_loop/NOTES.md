# hero / crouch_idle_loop: motion reference (T012)

**Verdict: usable (accepted on try 1). Use only the crouch hold, frames 60-122.** The clip starts standing and sinks
into the crouch over the first ~56 frames. That part is a bonus stand-to-crouch transition reference. Identity and
the digitigrade legs are kept. In the crouch the knee pod sits low and forward, the shins fold back behind it, and
the tines stay visible.

| | |
|---|---|
| Video | `crouch_idle_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | 1301 / 1 of 3 |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. Retime to 30 fps in-game.

## Prompt (action part; the design/background paragraph is in meta.json)
"The character in <Picture 1> holds a low crouch in place, seen in strict side view (profile), facing left, with a
locked static camera. Knees deeply bent, body lowered by about a third of its height, torso leaning slightly forward,
hands held loosely in front of the body, alert stance. The backward-bending hocks are strongly compressed and the
blade feet stay planted flat on the ground without sliding. Subtle continuous idle loop ... does not walk, stand up or
turn. ..."

## Key poses
- **0-14: standing** (same as the idle start).
- **16-56: transition down.** The knees come forward, the hips drop and the torso leans forward. The arms come
  forward with the hands open in front of the body by ~40.
- **lowest point / settled crouch: ~60.** From then on the hold is roughly constant to 122. The thigh plates angle down
  and forward (about 45° below horizontal), the rounded knee pod is the lowest/front-most point of the leg and is close
  to the ground, the thin shins run back and up from the knee to the hock, and the three-tine blades plant on the
  ground behind/under the hock. The torso leans forward about 20-30° and the hands hang open in front of the knees.
- Idle motion in the hold is very small: slight hand/arm drift and a small up/down settle. Breathing is not clearly
  visible.
- **Loop:** 60-122. The start and end poses are close. Crossfade a few frames at the seam; no clear cycle exists.

## Known artifacts
- The crouch is deep. The knee pod nearly touches the floor, so it reads close to a kneel. Use the in-game crouch
  height from the capsule spec, not this exact depth.
- The legs overlap in profile, so it is hard to tell the near and far legs apart in the hold.
- The character is small and dark in the frame. A generated motion guide, not ground truth.
