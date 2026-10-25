---
name: ref-to-video
description: Procedure for generating a reference motion video for a 3D asset with the project's ComfyUI workflow (snapshot render, workflow run, frame extraction, DVC tracking).
---

# Reference-to-video procedure

Inputs: asset id `<asset>`, clip name `<clip>` (e.g. `walk-loop`), and a motion description from
docs/specs/RIGGING_ANIMATION.md. Output folder: `reference/<asset>/<clip>/`.

1. Check the server: `python3 tools/comfy/comfy_client.py ping`. If unreachable, stop and report
   (the human may need to start ComfyUI or check COMFY_URL). Never start or install ComfyUI yourself.
2. Snapshot (once per asset, reuse if it exists): render the exported model, not the rig:
   `blender -b -P tools/blender/render_snapshot.py -- --glb godot/assets/<asset>/model/<asset>.glb --out reference/<asset>/snapshot_front.png`
   Read the PNG to confirm it shows the asset's front, fully in frame. Adjust `--azimuth` if not.
3. Run the workflow (only the files in tools/comfy/workflows/; only inputs listed in its .map.json):
   `python3 tools/comfy/comfy_client.py run --workflow tools/comfy/workflows/ref_to_video.json --image reference/<asset>/snapshot_front.png --out reference/<asset>/<clip> --set prompt="<motion description>" --set seed=<n>`
   Write the prompt from the spec: action, direction (e.g. walking toward camera vs. away), speed, loop.
   Keep the seed in the report so the result is reproducible.
4. Frames for review: `python3 tools/comfy/comfy_client.py frames --video reference/<asset>/<clip>/<video> --out reference/<asset>/<clip>/frames`
   Read `contact_sheet.png`. Reject and re-run with a new seed (max 3 tries) if the subject changes identity,
   proportions drift badly, limbs merge, or the motion does not match the spec. Record what you saw.
5. If the workflow produced pose keypoints, keep them as text (JSON) next to the video.
6. Write `reference/<asset>/<clip>/NOTES.md`: prompt, seed, tries, frame rate, known artifacts, and which frames
   show the key poses (contact, passing, etc.). This is what the rigger and QA read.
7. Free the GPU: `python3 tools/comfy/comfy_client.py free` (ComfyUI keeps models in the 8 GB GPU memory; free it so the human can use the GPU).
8. Track binaries and commit: `dvc add` the video, snapshot and frames folder; `git add -A && git commit`.

Limits to state in your report: generated video is a motion guide, not ground truth; proportions and timing
can drift. Do not claim the reference is accurate beyond what the contact sheet shows.
