# ComfyUI workflows

Put your reference-to-video workflow here, exported from ComfyUI in **API format**
(the "Export (API)" option; the regular workflow JSON will not work), for example `ref_to_video.json`.

Next to it, create `ref_to_video.map.json`. It names the ONLY inputs the agent may change:

```json
{
  "image":  {"node": "12", "input": "image"},
  "prompt": {"node": "6",  "input": "text"},
  "seed":   {"node": "3",  "input": "seed"},
  "frames": {"node": "40", "input": "length"}
}
```

Node ids and input names come from the API-format JSON. `image` must point at a LoadImage-style node.
Everything else in the workflow (models, samplers, resolution) stays as you saved it.

If the workflow includes a pose-estimation node that saves keypoints, add its output to the map's
documentation here so the agent knows to collect it.

## Current workflow: `ref_to_video.json` (MiniMax H3 reference-to-video)
Confirmed with the human at bootstrap (2026-10-25). One reference image (the second LoadImage was removed so no
example image leaks into every run). No pose-estimation node, so no keypoints. Output: 24 fps video with audio.

| Key | Node | Input | Meaning |
|---|---|---|---|
| `image` | 137 LoadImage | `image` | the asset snapshot (`--image`); it is `<Picture 1>` in the prompt |
| `prompt` | 138 Input Text (Prompt) | `value` | full prompt text, replaces the example |
| `seed` | 129 RandomNoise | `noise_seed` | integer seed |
| `seconds` | 132 Float (Duration) | `value` | duration in seconds (default 5). Node 131 turns it into frames: `max(5, round(s*24))`, rounded up to 17k+5 |

If you re-export the workflow, check these node ids still match and update `ref_to_video.map.json`.
