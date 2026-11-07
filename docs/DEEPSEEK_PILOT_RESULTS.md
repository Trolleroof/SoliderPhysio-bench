# DeepSeek pilot results — 2026-11-07

**Scope correction:** these runs exercised the legacy pulse, heat and load
regression tasks. They did **not** exercise the newly discussed task types
“Keep going or pull him?”, “Rulebook versus body”, or “Beat ECTemp”. The earlier
claim that the intended three-task suite was complete was incorrect. These
results are legacy harness diagnostics only; they do not establish readiness,
completion or ratings for the new task suite.

DeepSeek V4 Flash High produced valid submitted predictors for load, heat and
pulse. Every selected artifact completed full-cohort hidden replay and an
independent GPT-6.1 Sol Medium final-selection review. This proves that the model
can participate through the repaired interface; accuracy is not uniformly better
than the reference controls.

| Task | Selected development MAE | Hidden test MAE | Control hidden MAE | Control |
|---|---:|---:|---:|---|
| Load | 34.37 W | 33.51 W | 29.34 W | Supplied ridge |
| Heat | 0.282 C | 0.239 C | 0.184 C | Supplied ridge |
| Pulse | 12.93 bpm | 10.01 bpm | 16.15 bpm | Training median |

Load's selected standardized ridge improved its initial mean-by-load development
reference from 48.22 W to 34.37 W. Heat selected the supplied elapsed-time model:
its development loss was better than the ridge control's 0.490 C, although ridge
generalized better on this held-out cohort. Pulse selected the supplied fitted
ridge; it explicitly rejected selecting an unevaluated random forest based only
on its lower training error. The pulse result is use of an available reference,
not discovery of a new estimator.

Training/development evidence drove repairs and selection. Hidden results were
collected after submission and were not fed into participant history or reviewer
packets. No further tuning was performed after reading this comparison.

## What changed

- Compact tool schemas now require executable code or a valid selection for the
  applicable phase; public command stdout is retained in feedback.
- The interactive participant can retain its own tool calls, exact code edits,
  reasoning blocks and actual public tool results across turns and restarts.
  Configuration and public-ledger identity are checked on resume.
- A submission phase requires the model to choose a valid evaluated candidate
  before call/token exhaustion. An optional evaluation deadline obtains earlier
  development feedback, leaving calls for repairs and submission.
- Pulse now documents an executable baseline command, matching the practical
  guidance already available for heat/load. The clearer command moved pulse
  training/evaluation to its first two calls in the successful diagnostic.
- The pilot runner binds explicit task scope, settings, freeze and shared spend;
  final-selection reviews verify sealed public evidence and resume without
  repeating completed paid reviews.

These are scaffolded development diagnostics at agent seed 0, with a single model
and separately recorded freezes/settings. Load and heat completed in `v4/`;
pulse completed in `v5-pulse/`. They are not a matched multi-model leaderboard or
a repeatability study. Source data hashes, scorer implementation and Docker image
were checked against the reference controls before comparing numerical losses.
The new protocol requires a new matched pool and budget plan for a broader sweep.

## Verification and cost

All **76 research-harness tests passed**. The completion audit verified receipt,
configuration, dataset, trajectory, transcript and review-packet hashes for each
successful task, plus validated reviewer verdicts. No pilot workers remain.

Independent review coverage is one final-selection packet per task, using all
preceding public evidence. It is not a review of every intermediate decision.
Training reproduction for load/heat also depends on the retained run source
snapshots; final artifacts alone do not contain every training script. Process
judgments remain separate from numerical losses.

Interactive diagnostics: **$0.83937419**, 282 API requests, zero unresolved cost
reservations, **$0.16062581 remaining** under the shared $1 cap. Including the
earlier smoke/reference checks, recorded API spending was **$0.85878237** across
303 requests. Failed and interrupted attempts remain recorded and charged.

Machine-readable metrics, receipt/freeze hashes, settings and review means/counts
are in [results.json](../leaderboard/pilots/deepseek-interactive/results.json).
The [pilot guide](INTERACTIVE_PILOT.md) contains the launch command and protocol.
Local raw evidence is retained under
`.leaderboard-checks/deepseek-interactive-20261106/`, including earlier failures,
the explicitly interrupted `v3/pulse` fitting command, `v4/`, `v5-pulse/`,
`tests-final.log`, `verified-summary.json` and the original shared `spend.sqlite`.
These ignored run assets are on this Mac; they are not included in Git.
