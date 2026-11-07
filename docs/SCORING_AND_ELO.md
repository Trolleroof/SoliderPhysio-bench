# Scoring and Elo design

Status: implementation design; calibrate and freeze the data-dependent values
before any official run. No scores or ratings exist yet.

## Per-case scores

Keep raw measurements, deterministic results and judge scores visible. Convert
each component to a value in [0, 1], then compute the weighted sum:

| Task | Component | Weight | Normalization |
| --- | --- | ---: | --- |
| Keep going or pull him? | Forecast | 0.30 | Deterministic absolute error: max(0, 1 - error °C / E) |
| | Decision | 0.40 | Judge score / 5 |
| | Reasoning | 0.30 | Judge score / 5 |
| Rulebook versus body | Table lookup | 0.30 | Fraction of predeclared required fields correct |
| | Override decision | 0.40 | Judge score / 5 |
| | Reasoning | 0.30 | Judge score / 5 |
| Beat ECTemp | Predictor performance | 0.60 | max(0, min(1, 1 - MAE / B)) |
| | Research explanation | 0.40 | Judge score / 5 |

E is an error in °C at which forecast credit reaches zero; B is the frozen
ECTemp MAE on the same held-out people and prediction requests. Neither is a
clinical threshold. Choose E from development evidence and document its
rationale before freezing; no arbitrary value is approved here. For Beat
ECTemp, compute MAE per person then average people equally. Require a valid,
finite, positive baseline B; otherwise report not scorable. A predictor that
matches ECTemp receives zero performance credit under this provisional mapping;
report raw error and relative improvement prominently so the mapping is clear.
Freeze slice definitions and report each slice separately; the performance
component uses the predeclared overall person-balanced MAE. Report uncertainty
metrics and validity separately; do not silently invent a weighting for them.
The judge's forecast assessment is reported separately from deterministic
forecast error and does not override it.

Scoring requires all components. A missing model answer receives the rubric's
zero where applicable; a judge failure, unavailable reference or invalid
ground truth is not a zero and blocks the affected comparison. Define artifact
invalidity and missing-output penalties before runs, and never silently discard
failures. Retain every attempt and status.

## Matched comparisons and ratings

Compare models on the same frozen case and task version. Higher combined score
wins; exact equality is a tie. Each model pair receives one comparison per
matched case. Average comparisons within each task type before combining the
three task types equally, so the proposed 3/1/2 case counts do not implicitly
weight a task more heavily. Treat independent runs on the same case as repeated
measurements, not new cases; predeclare aggregation and seeds.

Fit a Bradley–Terry model with ties and equal task weights to the resulting
pairwise outcomes, then express ratings on the Elo scale: 1500 plus 400 times
the base-10 logarithm of relative strength, centered so the eligible roster's
mean is 1500. Pin the tie model, optimizer and regularization before running;
retain pairwise outcomes and all inputs so ratings are reproducible. Ratings
are relative to this roster, not a measure of medical competence. Require a
connected comparison graph and matching case coverage; publish coverage and
uncertainty, and do not assign an official rating to an incomplete model. With
only a few cases, ratings are exploratory and uncertainty can be large.

## Before freezing

Calibrate E and the predictor mapping with development cases and simple
baselines, including an elapsed-time-only control. Validate judge consistency,
test fabricated and ambiguous answers, audit leakage and compare plausible
weight and mapping choices for rank sensitivity. Specify table fields,
missing-output treatment, repeated-run aggregation, tie implementation and
confidence interval method. Freeze versioned artifacts and publish limitations
before requesting model responses. These steps are not yet completed.
