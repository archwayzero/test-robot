# hero / jump: motion reference (T012)

**Verdict: usable for phases and poses, with a look drift (accepted try 3 of 3).** A standing vertical hop in place
with clear anticipation, takeoff, a tucked airborne pose, landing compression and recovery. The **digitigrade legs
and blade feet are kept and read especially well** in the crouch and landing (deep hock compression), and the
blades hang below the tucked knees in the air. **However, the look drifted:** the armour renders as shiny
bronze/gold, the face is gold-lit, a floor with a spotlight appears, and the camera is closer than the input.
Use it for timing and poses, not for the look.

| | |
|---|---|
| Video | `jump.mp4`: 864x480, 24 fps, 124 frames (5.17 s), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | **1703** (accepted) / 3 of 3. Rejected: 1701, 1702 (prompts in `rejected_s170x.meta.json`) |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. In-game: 30 fps, in place, one-shot (not a loop).

## Prompt (as accepted; the design/background paragraph is in meta.json)
"The character in <Picture 1> performs one small standing vertical hop straight up in place, the feet rising only
about knee height off the ground, seen in strict side view (profile), facing left, with a locked static camera that
keeps the whole body including the hood and the blade feet inside the frame for the entire jump. Sequence: stands
still for a moment; anticipation crouch (knees bend deeply, the backward-bending hocks compress, arms swing back);
quick takeoff (legs extend, arms swing forward and up, the blade feet leave the ground); short airborne moment with
the legs slightly tucked; landing on both blade feet with the hocks and knees compressing to absorb the impact;
recovers back to a relaxed standing pose and stands still. ..."

## Tries
1. **Seed 1701: rejected.** Faithful look and a good phase structure (crouch ~20-46, airborne ~52-66, landing ~70-76),
   but at the apex the head and upper torso leave the top of the frame (~frames 52-68), and the blades smear in the
   air.
2. **Seed 1702: rejected.** A white glowing streak on the arm (frames ~48-90), the head still clipped at the top, and a
   weak, low jump.
3. **Seed 1703: accepted.** "Small hop" wording; the whole body stays in frame (the hood just touches the top edge at
   the apex). The look drifted (see above).

## Key poses (seed 1703)
| Phase | Frames | Notes |
|---|---|---|
| Stand | 0-6 | upright, arms down |
| Anticipation down | 8-20 | hips drop, torso leans forward, arms swing back |
| **Lowest anticipation** | ~20-22 | knees deeply bent and forward, hocks fully compressed, arms back |
| Takeoff | 24-26 | arms swing forward/up, legs extend |
| Blades leave the ground | ~28 | |
| **Apex (highest)** | ~34-36 | arms reaching forward/up, knees tucked forward, blades hanging below/behind |
| Descent | 38-42 | legs extend down toward the floor |
| **Landing contact** | ~44-46 | hook tips touch down |
| **Landing compression (lowest)** | ~52-58 | deep crouch, arms back/down |
| Recover up | 60-80 | |
| Settled stand | 80-122 | can be trimmed |

For a game jump, split this into takeoff (0-28), air/apex (28-44) and land (44-80) sub-clips as needed.

## Known artifacts
- The look drifted: shiny bronze/gold armour and a gold face, a floor/spotlight, the camera closer than the input.
- Unlike the treadmill clips, this clip shows a visible floor line and a cast shadow, so it gives a usable
  ground-contact reference (blades leave the ground ~28, landing contact ~44-46).
- The hood touches the top edge at the apex.
- The jump height is small (as asked, to keep it in frame). Scale the height to gameplay physics.
- A generated motion guide, not ground truth.
