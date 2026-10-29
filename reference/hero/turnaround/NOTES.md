# Hero turnaround (T038): AI-generated orbit views of `full_body.png`

**Authority:** `reference/hero/full_body.png` (side view, character's left side) stays the ground truth. Everything
here except the 90° view is a MiniMax H3 interpretation of the unseen sides. Use it to compare your model's
silhouettes and proportions at each angle. It is not a measured blueprint: where it disagrees with
`full_body.png`, the PNG wins.

## Files
| File | What |
|---|---|
| `orbit_full.mp4` | full-body orbit, 864x480, 24 fps, 226 frames (9.4 s), seed 101 |
| `orbit_legs.mp4` | lower-body orbit, 864x480, 24 fps, 226 frames, seed 202 |
| `legs_input.png` | input for the legs clip: `full_body.png` cropped to y=370..807 (thigh plates to blade tips) |
| `full_000..315.png`, `legs_000..315.png` | stills at 45° steps (864x480; the character is in the centre third) |
| `contact_sheet.png` | top row full, bottom row legs, 0..315° left to right |
| `*.meta.json` | exact prompt, seed, workflow sha256 of each run (including the rejected one) |

Workflow: `tools/comfy/workflows/ref_to_video.json` (sha256 69012be1...), `seconds=9`. Generated audio is ignored.

## Tries
1. **Full, seed 101: accepted, first try.** A complete orbit in one direction (left side → back → right side → front →
   front-left), no walking or limb motion, hood/backpack/thigh plates/tines stable. Input: `full_body.png`.
2. **Legs, seed 201: rejected.** The input was `legs_input.png`. It does orbit, but in the back and front views the
   three tines merge into one blade, and the knee pod is weak.
3. **Legs, seed 202: accepted.** Same input with a stronger "close-up, three separate tines" prompt. The framing is the
   same as 201 (the workflow keeps the input's framing and ignores "close-up"), but the tines and the ankle spring read
   better. The legs fill the full 480 px frame height, about 2.4x larger than in the full clip.

Prompts (full text in the meta.json files):
- Full: "A slow, smooth 360-degree turntable camera orbit around the character in <Picture 1>. The character stands
  completely still ... Only the camera moves: it orbits horizontally ... at hip-to-chest height ... starting from the
  front (face visible), passing the left side, the back, the right side ... full body stays in frame ... Plain neutral
  grey seamless studio background, even soft studio lighting, realistic 3D render. Keep exactly the same character
  design ...: chainmail mesh hood over a pale face, ... green box backpack ..., wide boxy rust-stained armoured thigh
  plates reaching to the knee, thin mechanical digitigrade shins bent backwards with a large rounded knee joint, and
  feet made of three long curved blade tines each ..."
  (The model ignored "starting from the front" and started from the input view, the left side.)
- Legs (202): "Close-up product turntable of the mechanical legs in <Picture 1>. The legs fill the frame ... still
  object ... one slow full 360-degree horizontal orbit ... at knee height ... from the left side, around the back, the
  right side, the front ... each foot split into three separate long curved blade tines ..."

## Frame-to-angle mapping
Convention: 0° = front (face), 90° = character's left side (= `full_body.png`, facing image-left), 180° = back,
270° = right side. The camera goes 90 → 180 → 270 → 0 → 45. The speed is NOT constant: slow for the first ~2 s, then
roughly 45° per second. Neither clip closes the loop: each ends around 60–80° after about 330–340° of orbit.
I estimated the angles by eye from symmetry (backpack/pelvis centred = 180°, face/chest centred = 0°) and clean
profiles (90/270°), then interpolated for the 45° views.

| Angle | full: time (frame @24fps) | legs: time (frame) | Uncertainty |
|---|---|---|---|
| 0°   | 7.45 s (179) | 7.10 s (171) | ±5° |
| 45°  | 8.40 s (202) | 8.10 s (195) | ±10° |
| 90°  | 0.00 s (0)   | 0.00 s (0)   | ±3° (it is the input image) |
| 135° | 2.40 s (58)  | 1.50 s (36)  | ±15° (slow, uneven start) |
| 180° | 3.70 s (89)  | 2.75 s (66)  | ±5° |
| 225° | 4.75 s (114) | 4.00 s (96)  | ±10° |
| 270° | 5.65 s (136) | 5.05 s (122) | ±5° |
| 315° | 6.60 s (159) | 6.10 s (147) | ±10° |

Frame numbers are the 0-based frames that `ffmpeg -ss <time>` returns (the first frame at or after that time). A
re-extraction matched every committed still pixel for pixel. (The first version of this table had five of them
off by one.)

The camera height is roughly constant (slightly above the knees in the legs clip, at chest height in the full clip),
with some perspective, so the ground plane is seen slightly from above.

## Leg observations per angle (mostly from `legs_*`, cross-checked with `full_*`)
- **90° (source view):** matches `full_body.png`. The boxy thigh plate ends at the knee. Below it sits a large, rounded
  dark knee pod at the front-bottom of the plate. The shin is thin and runs down and back (digitigrade) to a hock, with
  a small coil spring there. **Feet (measured in `full_body.png`, checked in `legs_090.png` and mirrored
  `legs_270.png`; H = hock height above the ground, about 105-110 px in `full_body.png`):** each foot is a
  reverse-C hook, and most of its length is BEHIND the hock.
  - *Direction:* the tines leave the hock going BACKWARD (away from the face), roughly level or slightly downward. The
    outer tine starts on the back of the lower shin just above the spring; the inner tine starts at the spring.
  - *Arch:* the top of the arch is at about hock height (no tine rises clearly above its attachment), 0.4-0.7 H behind
    the hock (inner to outer tine). The tines then bend down. The rearmost point of the outer tine is about 0.8-0.9 H
    behind the hock and 0.6-0.8 H above the ground.
  - *Tips:* the tines sweep down and then forward, and the tips hook FORWARD at ground level. They land roughly under
    or just ahead of the hock: about 0.1 H ahead on the far foot and 0.35 H on the near foot. On the near foot the last
    part of the outer tine runs forward, flat along the ground, for about 0.5 H.
  - *Nesting:* three concentric reverse-C arcs share the hock. The OUTER arc (top/rear) is the longest, reaches
    furthest back and lowest, and is the one that clearly touches the ground (path length about 3 H). The middle tine
    runs just inside it and nearly parallel (about 2.5 H). The INNER tine is the shortest (about 2 H): its rearmost
    point is about 0.6 H behind the hock, and it ends at or just above the ground where it meets the outer tine's
    descending part. All of these lengths are rough estimates by eye on the pixel grid.
- **45° (front-left):** the knee pod is clearly a rounded capsule protruding forward below the plate. The shin reads
  S-shaped (forward under the knee, then back to the hock), thicker at the top and tapering. The coil spring is visible
  at the hock. Two or three tines are visible, fanning slightly sideways and still nested.
- **0° (front):** the thigh plates are wide and slightly splayed. The knee pod sits centred under each plate, as a
  dark rounded bulge. The shins are narrow vertical struts tapering downwards, slightly wider than a tine. The
  backward bend is invisible from the front (foreshortened). There is a kink at the hock; no clear spring. The three tines overlap in
  depth and read as ONE narrow blade with a small forward tip, so this view does not show their spread. In the full clip
  the feet look like pointed stilts.
- **315° (front-right):** mirror of 45°. Rounded knee pods, S-shaped shins, and the tines start to separate (three
  visible on the near foot).
- **270° (right side):** mirror of the source. Bent-back shin, hock spring, three clearly separated nested tines (the
  best tine view in the set, `legs_270.png`). The tines show the same reverse-C hook as at 90°, facing image-right:
  back from the hock, down, tips hooking forward under or just ahead of the hock. **Knee: AI invention.** Instead of the
  rounded pod, the generation drew a pointed upward spur at the front-bottom of the plate (around x=500, y=200 in
  `legs_270.png`). The source has no such spur. Modeler: follow 45°/90° for the knee shape, not 270°.
- **225° (back-right):** the camera looks at the hooks from behind, so each foot reads as a reverse-C that opens
  toward the front. The tines run from the hock back toward the camera, arch, drop, and their tips hook forward
  under/just ahead of the hock. Two or three tines per foot are visible (they overlap more than at 90/270°). The shin
  strut joins the plate bottom from behind; there is no rounded knee pod at the back. A pointed fin at the
  back of the knee, similar to the 270° spur, shows here too. It is an invention as well.
- **180° (back):** the plates end in open-looking tube rims at the knee. Below them a narrow, nearly straight shin strut
  has a small kink at the hock. The feet read as single hooked blades curling forward (the tines are stacked behind
  each other). The backward bend is foreshortened, so it is barely visible.
- **135° (back-left):** like 225°, mirrored. Three tines visible per foot, the shin seen from behind and the side.

Consistent across the orbit: the knee joint sits at the bottom of the thigh plate, and its rounded pod faces FORWARD
(visible at 0/45/90/315, hidden at 180; at 225/270 the model replaced it with a pointed spur, see above). The shins are
much thinner than the thighs (about 1/3 of the plate width). Each foot is a reverse-C hook of three nested tines. They
leave the hock BACKWARD, arch at about hock height, reach 0.8-0.9 H behind the hock (outer tine), and sweep down to
tips that hook FORWARD at ground level, roughly under or just ahead of the hock. The outer arc is the longest and
lowest, and the inner one the shortest. The tines are visible as separate only from the side or 3/4 views. From the
front/back they stack into one hooked blade.

## Known artifacts and inventions (treat as AI guesses)
- **Unseen sides are invented:** the front face and chest, the back of the torso and pelvis, the inner leg faces, and
  the right side are all generated. The model gives the pelvis a rounded "buttocks" armour shell at the back
  (180°/225°), which is not in the source.
- **Thigh plates:** from the back they look like brighter orange, more cylindrical trouser-like tubes, more uniform
  than the source's patchy rust on dark metal. Their width and length are about right (to the knee).
- **Knee spur at 225°/270°:** a pointed upward spur/fin at the knee (front-bottom of the plate in `legs_270.png`,
  around x=500, y=200) replaces the rounded pod. It is not in the source. Follow 45°/90° for the knee.
- **Tines in the front/back views** collapse into one blade (depth overlap, or the model simplified them). Do not read
  0°/180° as "one tine". Seed 201 merged them more and was rejected.
- **Shin bend at 0°/180°** is foreshortened to nearly straight. Use 45°/135°/225°/315° for the bend.
- **Lighting and background shift** during the orbit (the floor brightens around 180–270°). There is mild texture
  flicker, and the hands/arms subtly change shape. There is no walking, but slight sway in the legs clip.
- **The orbit is incomplete and has uneven speed:** about 330–340°, with a slow start. The angle estimates above carry
  the stated uncertainty.
- **Legs clip framing:** the top edge cuts through the hips. The "close-up" wording had no effect. The framing comes
  from the input crop.
- The full-clip resolution is low for leg detail (the legs are about 200 px tall). Use the `legs_*` stills for detail.

## Reproducing the derived images (run from the repo root)
All ffmpeg calls go through the memory guard. On 2026-10-28 every committed still and `legs_input.png` were
regenerated with exactly these commands, and the results are pixel-identical (PSNR inf) to the committed files.
```bash
T=reference/hero/turnaround
# legs-clip input: crop of the source image (y=370..807)
python3 tools/qa/memguard.py --expect-peak-mb 500 -- ffmpeg -y -i reference/hero/full_body.png -vf "crop=414:437:0:370" $T/legs_input.png
# stills: <angle>=<seconds> from the table above
for p in 000=7.45 045=8.40 090=0 135=2.40 180=3.70 225=4.75 270=5.65 315=6.60; do
  python3 tools/qa/memguard.py --expect-peak-mb 500 -- ffmpeg -y -ss ${p#*=} -i $T/orbit_full.mp4 -frames:v 1 $T/full_${p%=*}.png; done
for p in 000=7.10 045=8.10 090=0 135=1.50 180=2.75 225=4.00 270=5.05 315=6.10; do
  python3 tools/qa/memguard.py --expect-peak-mb 500 -- ffmpeg -y -ss ${p#*=} -i $T/orbit_legs.mp4 -frames:v 1 $T/legs_${p%=*}.png; done
# contact sheet: full tiles = centre 300x480 crop; legs tiles = centre 432x480 crop scaled to 300x333, padded grey
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; L="fontfile=$F:fontsize=20:fontcolor=white:x=6:y=6:box=1:boxcolor=black@0.5:boxborderw=2"
IN=""; FG=""; i=0
for a in 000 045 090 135 180 225 270 315; do IN="$IN -i $T/full_$a.png"; FG="$FG[$i]crop=300:480:282:0,drawtext=$L:text='full $a'[f$i];"; i=$((i+1)); done
for a in 000 045 090 135 180 225 270 315; do IN="$IN -i $T/legs_$a.png"; FG="$FG[$i]crop=432:480:216:0,scale=300:333,pad=300:480:0:73:gray,drawtext=$L:text='legs $a'[l$((i-8))];"; i=$((i+1)); done
FG="$FG[f0][f1][f2][f3][f4][f5][f6][f7]hstack=8[top];[l0][l1][l2][l3][l4][l5][l6][l7]hstack=8[bot];[top][bot]vstack=2"
python3 tools/qa/memguard.py --expect-peak-mb 500 -- ffmpeg -y $IN -filter_complex "$FG" $T/contact_sheet.png
```
The contact-sheet tiles are pixel-identical to the committed sheet except in the top 40 px label strip of each row.
The original label font and size were not recorded, so the labels in a rebuilt sheet differ slightly (whole-sheet
PSNR about 40 dB, PSNR inf outside the labels). Measured peak RSS for each of these calls is under 10 MB.
