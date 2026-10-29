# hero / crouch_walk_loop: motion reference (T012)

**Verdict: good (accepted on try 1).** Identity is kept. The body stays low the whole time (knees deeply bent, torso
leaning forward, arms bent low in front), and the **digitigrade legs and blade feet are kept**: the knee pods lead,
the shins slant back to the hock, and the hook tips plant. Treadmill-style, in place, full body always in frame.

| | |
|---|---|
| Video | `crouch_walk_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | 1401 / 1 of 3 |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. In-game: 30 fps, in place, 1.0 m/s.

## Prompt (action part; the design/background paragraph is in meta.json)
"The character in <Picture 1> sneaks forward in a deep crouch, walking slowly and carefully in a continuous, looping
crouch-walk cycle, seen in strict side view (profile), facing left. Knees deeply bent the whole time, body kept low
(about a third lower than standing), torso leaning forward, arms bent and held low in front. The camera tracks
alongside like a treadmill shot ... Each slow step: a blade foot reaches forward and plants on the ground, the
strongly compressed backward-bending hock takes the weight, then the rear foot lifts and swings forward low over the
ground. The character never stands up."

## Cycle and key poses
**Step period ≈ 23 frames (0.96 s); full stride ≈ 46 frames (1.9 s).** The two steps are called A and B (the leg
identity is ambiguous in profile). Frames are ±2.

| Event | A | B | A | B | A |
|---|---|---|---|---|---|
| Passing / gathered (legs together under the hips, knees closest; body **highest**) | 0-2 | 24-26 | 46-48 | 70-72 | 94-96 |
| Lead-blade **contact** / wide stance (front hook planted far ahead, rear shin near horizontal) = **lowest** | 12-16 | 36-40 | 60-62 | 84-86 | 110-112 |
| Rear-blade lift (rear hook leaves the ground and swings forward low) | ~18 | ~42 | ~66 | ~90 | ~116 |

Pose detail: the torso leans about 35-45° forward, the head is forward and level, and the arms hang bent in front of
the knees. At the wide stance the front thigh plate is near horizontal with the knee pod leading. The rear thigh is
near vertical, with its shin running back almost flat and the hook planted behind.

**Loop:** 24 -> 118 (passing B to passing B, about 2 strides, 94 frames). A single stride is 24 -> 70.

## Known artifacts
- The vertical orange plate in the stance leg can read like a human shin with a kneeling knee. Read the leg as
  thigh plate -> knee pod -> thin back-slanting shin -> hook. Compare with `../snapshot_side.png`.
- Left/right leg identity is ambiguous.
- The character is dark and small in the frame. A generated motion guide, not ground truth.
