# hero / crawl_loop: motion reference (T012)

**Verdict: usable (accepted try 3 of 3).** A hands-and-knees crawl in place (treadmill-style). Plain grey background,
the full body including the blades in frame, and identity kept. The digitigrade legs read correctly on all fours: the
knee pod is on the floor, and the thin shin and three-tine hook trail behind with the hook arching up and the tips on
the floor. The cycle is somewhat irregular. Use it for the poses and rough timing.

| | |
|---|---|
| Video | `crawl_loop.mp4`: 864x480, 24 fps, 158 frames (6.6 s; requested `seconds=6`), MiniMax H3 reference-to-video. Ignore the audio. |
| Input image | `../snapshot_side.png` (exported `hero.glb`, azimuth 270, profile facing image-left) |
| Seed / tries | **1603** (accepted) / 3 of 3. Rejected: 1601, 1602 (prompts in `rejected_s16xx.meta.json`) |
| Exact prompt | `meta.json` (`params.prompt`) |
| Frames | `frames/frame_NNNN.png` at 12 fps; `frame_NNNN` = source frame 2*(NNNN-1), ±1. `frames/contact_sheet.png` shows all of them. |

Frame numbers are **0-based source frames at 24 fps**. In-game: 30 fps, in place, 0.5 m/s.

## Prompt (as accepted; the design paragraph is in meta.json)
"Wide shot in an empty, smooth, matte grey photo studio cyclorama, exactly the same dim grey backdrop as <Picture 1>.
The character in <Picture 1> crawls forward slowly on all fours on the floor, on hands and knees, body low and
roughly horizontal, in a continuous, steady, looping crawl cycle: the left hand and right knee move forward together,
then the right hand and left knee. Seen in strict side view (profile), facing left; the camera is far back and tracks
alongside like a treadmill shot, so the character stays centered and small ... At each step a rounded knee joint
slides forward and plants on the floor, the thin backward-bending shins and the curved blade-tine feet trail behind
the knees with the blade tips dragging lightly on the ground, and each hand reaches forward and plants flat on the
floor. The character does not stand up."

## Tries
1. **Seed 1601: rejected.** The camera was too close: the character filled the frame and the blade tips were cut off at
   the right edge. There was a faint cracked-wall texture behind, and the knees barely advanced.
2. **Seed 1602: rejected.** Good wide framing and a crawl, but the background filled with floating black/gold dots
   (probably triggered by the "no spots" wording).
3. **Seed 1603: accepted.** The background is described only in positive terms. Clean.

## Cycle and key poses (near = camera-side limbs; on all fours the near/far limbs separate better than when standing)
- **Near leg extended back** (thigh plate near horizontal, shin and hook trailing far behind): ~0-15, ~60-69,
  ~138-150.
- **Near knee planted under the hip** (thigh plate near vertical, knee pod on the floor, hook arching up behind): ~24-42,
  ~72-87, ~117-126.
- **Near hand lift / reach** (hand curled, swinging forward): ~21, ~51-54, ~102, ~135. **Near hand plant**: ~3-6
  frames after each lift (e.g. ~57, ~108).
- **Highest** torso: the knee-under phases (hips up). **Lowest**: the leg-extended phases (hips drop, body stretched).
- The full near-leg cycle is ≈ 60-75 frames (2.5-3 s), uneven. About two cycles in the clip.

**Loop:** 60 -> 138 (near leg extended -> extended, 78 frames). The seam needs a few frames of blending because the cycle
is not perfectly periodic.

## Known artifacts
- The contralateral pattern (hand + opposite knee) is only roughly followed. The hands move more often than the
  knees.
- Hand fingers sometimes curl or smear during the reach.
- The far-side limbs are partly hidden behind the body.
- A generated motion guide, not ground truth.
