# T015 texture regression: analysis

Requested by the human after preferring an earlier stone. Sources: reviewer triage, modeler-side response, git history.
Figures come from Cycles renders or unlit maps; none predicts Godot Mobile or device behaviour. One human preference
on four builds is n = 1, and metrics were chosen after the outcome, so rankings below are hypotheses to validate.

## Snapshots
Same camera, lights, exposure and resolution (`images/t015/`, tracked by DVC: run `dvc pull` to view; GitHub shows only pointers).
| File | Build |
|---|---|
| `snap_v1_7590125.png` | Version 1, pass 1 (3.9 m crown, no COLOR_0: judge wall and pier stone only) |
| `snap_v2_a6d7e65.png` | First reviewed build, the stone the human preferred |
| `snap_v4_3905db7.png` | Version 4, pass 4, shipped |
| `snap_4up.png` | All four with crypt.jpg and a back wall crop |
| `snap_4up_flat.png` | All four, flat lit |

## What went wrong
The drop was texture, not lighting. On the back wall, fine/coarse fell 0.73 -> 0.41 and blur (Crete) rose 0.331 -> 0.463,
about 100% from texture. Tonal span was about half lighting. It held under flat light (fine/coarse 0.68 -> 0.37).
It landed at `dad70d3` (pass 3a), not pass 4. Pass 4 added plaster clouds. The human had accepted pass 3 before any
fixed-rig comparison existed, and was told "some of the difference is lighting", which was wrong for sharpness.

| Change | Commit | Effect (measured) |
|---|---|---|
| Rim 0 -> 0.13 -> 0.18, dark falloff from joints | `dad70d3`, `51f1800` | Pillowed stones; leads on blur and fine/coarse |
| Stain 0.56 -> 0.22 with blur | `dad70d3` | Lost crisp speckle: gradient p99 0.0787 -> 0.0481 |
| Per-stone tone 0.10 -> 0.225 -> 0.24 | `dad70d3`, `87c4cb9` | Checkerboard; leads on `mid` |
| Exposure 0.42 -> 0.55 -> 0.85 | `dad70d3`, `87c4cb9` | Moved numbers while tuning |
| Plaster settings for web targets | `448c449` to `751344c` | Clouds: low-frequency energy x3 |

Cleared: zero-meaned course tone. Not isolated in renders: mortar, layout, normal grain, plaster parameters.
Restoring stain, tone and rim on pass 4 returned v2-like stone (blur 0.310) in a scratch build, with `mid` 0.0246, under
half the 0.06 target. The preferred look and the target directly conflicted.

## Why the process missed it
- **Bad reference box.** The `mid >= 0.06`, `span >= 0.40` box on crypt.jpg held the statue, a hard shadow and a light
  pool. Clean stone reads `mid` 0.036, `span` 0.31. Nobody inspected it.
- **Targets rewarded blotches.** `mid` measures 10-50 px contrast; rim, tone and patches are the cheap way to raise it.
  `fine` rose while speckle was destroyed. Nothing guarded sharpness or spectrum shape.
- **Shared ownership.** Review proposed the targets, the orchestrator passed them on and saw the checker but kept the
  metric, and the modeler chased them. Modeler self-score fell 8.2 -> 7.8 while its commit said "all look targets met".
- **Scores hid it.** Review look rose 7.4 -> 7.6 while the stone worsened, on different rigs. v2 was marked FAIL, so
  nothing protected it.
- **Nothing compared passes.** Tools printed against targets only, renders were overwritten, exposure moved.

## Evaluation for next time
Would have flagged the drop at `dad70d3`: spectrum shape distance (0.24 -> 0.93), blur (0.309 -> 0.441), fine/coarse
(0.87 -> 0.45). Did not rank v2 above v4: `mid`, `span`, `fine`, local contrast, histogram.

Answer to "more visual checks, more measurements or a better visual model?": a better process first. More targets of
the same kind would make it worse. Modeler image judgement works for checkerboard, repetition and colour at full frame,
but is weak on micro-texture without magnified crops.

| Check | Where | Rule |
|---|---|---|
| Reference region audit | Before targets are issued | Each target cites a stored stone-only crop |
| Frozen rig and metric hash | Modeler loop, automatic | Changes need sign-off and a new baseline |
| Fixed-rig before/after sheet | Modeler loop, every pass, committed | Far, close, flat, previous pass, reference; magnified crops |
| Spectrum, blur, fine/coarse; map stats against baseline | Modeler loop, automatic | A regression needs a written reason. Start at about 15% (unvalidated). Not a hard fail: single metrics dipped falsely |
| No accepted aspect worsens | Modeler loop | Aspects named per pass; explained trades allowed. The modeler says it would route around a rigid gate |
| Paired targets | Brief | No contrast target without a sharpness or spectrum guard |
| Human A/B | At look or direction changes | 30 seconds; essential, because v2 was only valued after it failed review |
| Independent review | After the pass | Character and realism. A rising score never overrides a regression. Self-scores are not trusted |

Build into the modeler: everything that can run on each pass. Keep in review: judgement and independence. Evaluation
should run during the work, because feedback that arrives after a pass cannot stop a pass going the wrong way.

Briefs also need: where each target came from, a named look to protect, the rule "look beats target; report a target
that hurts the look, do not chase it", locked exposure, and time to test parameters one at a time.

Locking an approved look: tag the commit, keep fixed-rig renders in DVC, keep material parameters in a versioned file,
save a metric baseline, name which aspects are locked, and require a human decision to unlock.

The goal was never simply v2: it had the right spectrum shape with too little contrast (`mid` 0.0236 vs 0.0364 clean
stone). Disputed between reviewer and modeler: which cause ranks first depends on the metric, and "would have flagged"
is hindsight unless those metrics were in the gate.
