# hero / walk_loop: motion reference (T012)

**Verdict: good (accepted on try 1).** Identity is kept: hood, pale face, backpack, rust thigh plates. The
**digitigrade legs and the three-tine reverse-C blade feet are kept in every frame**: the shins slant back to the
hock, and the hook tips plant on the ground. Treadmill-style: the character stays in place in a strict profile. It is
usable for stride timing, leg phases, body bob and arm swing.

| | |
|---|---|
| Video | `walk_loop.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio track. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270 = character's left side, facing image-left) |
| Seed / tries | 1101 / 1 of 3 |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps (every 2nd source frame); `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers below are **0-based source frames at 24 fps**. In-game: 30 fps, in place, 1.6 m/s. Retime the
cycle to the stride length that matches 1.6 m/s; don't copy the generated cadence blindly.

## Prompt
"The character in <Picture 1> walks forward at a steady, relaxed walking pace in a continuous, looping walk cycle,
seen in strict side view (profile), facing left. The camera tracks alongside like a treadmill shot so the character
stays centered; the full body from the top of the hood to the feet is always in frame and the feet are always
visible. Keep exactly the same character design: chainmail mesh hood over a pale face, dark rust-stained armoured
torso, black box backpack, wide boxy rust-orange armoured thigh plates down to the knee, and DIGITIGRADE mechanical
legs: thin dark shins that slant backward from the knee to a raised hock, and feet made of three long curved blade
tines forming a backward hook whose tips plant on the ground. Each step: a blade foot plants on the ground, the
backward-bending hock compresses, then the leg pushes off and swings forward. Arms swing naturally opposite to the
legs. Plain neutral grey seamless studio background, even soft studio lighting, realistic 3D render, no other
objects, no text."

## Cycle and key poses
**Step period ≈ 22 frames (0.92 s); full stride (2 steps) ≈ 44 frames (1.83 s).** This is a slow, deliberate walk:
for 1.6 m/s in-game, expect to shorten the cycle or lengthen the stride.

The legs overlap in profile, so which leg is near and which is far can't be told reliably. The two alternating steps
are called A and B. Frames are ±2.

| Event | Step A | Step B | Step A (repeat) | Step B (repeat) |
|---|---|---|---|---|
| Passing (legs together under the hips, swing blade passes the stance blade) / **highest** body | 20 | 44 | 66 | 88 |
| Lead-blade **contact** (front hook tips touch down; wide stance, both feet down) | 30-32 | 52-54 | 74-76 | 96-98 |
| **Lowest** body (just after contact, hock of the lead leg compresses) | 32-34 | 54-56 | 76-78 | 98-100 |
| Rear-blade toe-off (rear hook tips lift, leg starts to swing) | 36-38 | 58-60 | 80-82 | 102-104 |

Also visible: in the swing phase the lifted blade keeps its reverse-C hook shape and hangs behind/below the hock; it
does not flatten. The arms swing opposite to the legs, most clearly at the wide stances (front hand forward of the
hip at 30-32, 52-54). There is a slight vertical bob (a few px).

**Loop:** 20 -> 108 (passing A to passing A, 2 full strides, 88 frames). Frames 108-110 match 20 closely. A single
stride is 20 -> 64.

## Known artifacts
- The character is small in the frame (about 330 px tall) and lit dark, so tine detail is limited to 2-3 visible
  tines.
- The leg identity (left vs right) is ambiguous in silhouette. The step A/B timing is reliable; which leg is which is not.
- Slight foot sliding is possible. A treadmill shot does not give a true ground reference. Plant the blades in the
  rig with IK; don't trust the generated foot positions for sliding.
- A generated motion guide, not ground truth.
