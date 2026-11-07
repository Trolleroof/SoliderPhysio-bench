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

## Calibration evidence (2026-11-07)

Frozen values live in `tasks/scoring_params.json` (version `v1-2026-11-07`):
E_c = 0.30 °C and the B values below. All three were approved by the project
owner on PR #3.

### ECTemp baseline B

`ectemp_baseline.py`, run as the submission through `benchmark.evaluate` with
`hidden=True` on the frozen test split. The value is `person_balanced_mae`.

| Variant | B (°C) | Gated requests | People in gate |
| --- | ---: | ---: | --- |
| 3A | 0.9325 | 21 | H13 only |
| 3B | 0.9404 | 36 | H13 only |

- **Stable under time offsets.** The baseline reads only `hr`, `skin_temp`
  and `watts`, never `time_min`. Two hidden runs per task, each with a fresh
  random offset, gave identical results. Calling `predict` directly with offsets
  0 and 98765 on all 357 test requests gave a maximum difference of 0.
- **Caveat: one person.** The hidden gate (true core ≥38.5 °C after the first
  watts drop) admits only H13 among the five test people. "Person-balanced" B
  is one person's MAE, so the Beat ECTemp predictor score also depends on one
  person. Accepted as-is on PR #3; report it as a limitation.
- B is large because the baseline starts at 37 °C and lags. A predictor needs
  MAE below about 0.93 °C to get any predictor credit. Half credit needs about
  0.47 °C.

### Forecast cutoff E_c

Script: `tasks/calibrate_forecast_e.py`. Output:
`docs/forecast_e_calibration.json`.

**Development set.** Eleven people used in no keep_going task: H02, H05, H07,
H08, H09, H10, H15, H16, H19, H20 and H24. Cutoffs run from 25 to 45 minutes,
with a +15-minute target. Windows use the same probe-glitch screen as
keep_going: no one-minute step above 0.3 °C. That gives 175 windows. Population
statistics are leave-one-person-out within these people. Credit is
max(0, 1 − err/E), averaged per person, then across people.

**Baselines.**
- Constant: the pooled population mean, about 38.4 °C. Uses no information.
- Elapsed-time-only: the mean core of other people at minute t+15.
- ECTemp-style: the 3A forecast from `ectemp_baseline.py`.
- Two oracle references that read current core, which keep_going never shows:
  - Persistence: core(t).
  - Persistence plus the population's rise over the next 15 minutes.

All 175 development windows, person-balanced:

| Baseline | MAE | p50 | p90 | E=0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.75 | 1.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Constant (no info) | 0.18 | 0.13 | 0.33 | 0.40 | 0.46 | 0.51 | 0.60 | 0.67 | 0.76 | 0.82 |
| Elapsed time only | 0.19 | 0.14 | 0.37 | 0.38 | 0.44 | 0.49 | 0.58 | 0.65 | 0.74 | 0.81 |
| ECTemp-style | 0.64 | 0.57 | 0.93 | 0.00 | 0.00 | 0.01 | 0.04 | 0.07 | 0.21 | 0.37 |
| Oracle persistence | 0.23 | 0.16 | 0.37 | 0.23 | 0.29 | 0.35 | 0.47 | 0.55 | 0.70 | 0.77 |
| Oracle persistence + rise | 0.15 | 0.12 | 0.26 | 0.40 | 0.48 | 0.55 | 0.64 | 0.71 | 0.80 | 0.85 |

The falling-power windows (66 windows, 5 people) and the windows with target
≥38.5 °C (139 windows) show the same ordering; see the JSON.

**Reference only, not used to choose E.** On the 12 scored keep_going cases,
person-balanced MAE was:
- Constant: 0.33.
- Elapsed time: 0.25.
- ECTemp-style: 0.40.
- Oracle persistence plus rise: 0.23.

The test cases were selected to sit at least 0.15 °C from the threshold, with
large rises. That makes them harder for the constant baseline than the
development windows are.

**Findings.**
1. On this protocol, core temperature 25 to 60 minutes in is tightly
   clustered. A model that answers "about 38.4 °C" every time already gets a
   development MAE of 0.18 °C. Elapsed time adds nothing on development data.
   This matches `FALLING_POWER_DUEL.md` (fe57873), where elapsed time beat every
   wearable model.
2. Under every candidate E, the no-information forecast gets about as much
   credit as the elapsed-time control. The forecast component cannot reward
   physiological reasoning over a population prior. Decision and reasoning
   (70% of the weight) carry that signal.
3. Larger E mainly hands out free credit. At E=0.5, the constant answer earns
   0.67 of the forecast component, about 0.20 of the case score, for no work.
   At E=1.0 it earns 0.82.
4. E below about 0.2 °C approaches rectal-probe and minute-to-minute noise.
   It also gives zero credit to errors typical of the best oracle reference
   (p90 0.26).

**Recommended range: E_c = 0.25 to 0.35 °C. Frozen at 0.30 °C (approved on PR #3).**
- At 0.30, an error equal to the median for informed baselines (about
  0.15 °C) earns half credit. An error at their p90 (about 0.3 to 0.37 °C)
  earns zero.
- The no-information answer earns about half the forecast component on
  development data and about a quarter on the test cases.
- The ECTemp-style comparator earns almost nothing on development data.

An alternative is a skill-relative mapping that gives zero credit at the
constant-baseline error. It would remove the free credit, but it changes the
documented formula. It was rejected on PR #3; the formula stays
max(0, 1 − err/E).
