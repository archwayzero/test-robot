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
