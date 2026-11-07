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

Frozen values live in `tasks/scoring_params.json`. B is filled in. E_c is
`null` until the user approves a value, so keep_going cases stay not scorable.

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
  person. This needs a decision before freezing.
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

**Recommended range: E_c = 0.25 to 0.35 °C (point suggestion 0.30).**
- At 0.30, an error equal to the median for informed baselines (about
  0.15 °C) earns half credit. An error at their p90 (about 0.3 to 0.37 °C)
  earns zero.
- The no-information answer earns about half the forecast component on
  development data and about a quarter on the test cases.
- The ECTemp-style comparator earns almost nothing on development data.

An alternative is a skill-relative mapping that gives zero credit at the
constant-baseline error. It would remove the free credit, but it changes the
documented formula, so it is not proposed here. The user must approve E_c
before any official run.

## Fit stress test (synthetic, 2026-11-07)

No model outputs exist yet, so the pinned `FIT` choices in
`tasks/combined_score.py` were stress-tested on synthetic rosters of 3-10
models with the real case counts (13 keep_going incl. KG-03, 2 rulebook, 2
beat_ectemp). Raw measurements (forecast error rounded to 0.01 °C, integer
judge scores, 4-field table fraction, MAE/B) are simulated per model and case,
then go through the production normalization, pairing and Davidson fit.
Scenarios: `typical` (moderate skill spread), `close` (small spread),
`ceiling` (judges near 5) and `tie_heavy` (judges saturate, nobody beats
ECTemp; ~36% of pair weight is ties). Reproduce with
`python3 -m tasks.elo_stress --only {extremes,priors,rmse,bootstrap,mapping}`
(seed 20261107; each section is reproducible on its own; the full run takes ~6 min
with sections in parallel). These are properties of the procedure under an
assumed data model, not evidence about real models.

### Bugs fixed (with tests)

1. **Eligibility used the union of all observed cases.** One model running an
   extra case excluded every other model. `rate()` now takes a frozen
   `required_cases` list (params key `required_cases`, `"task/case_id"`
   strings). Only those cases are rated; cases outside it are scored and listed
   under `extra_cases_not_rated` but never exclude anyone; a blocked or missing
   required case still excludes. A missing list is now an error (decided
   2026-11-07); only tests/dev may set `"dev_allow_union_cases": true` to fall
   back to the union rule, and that output carries a "not official" warning.
2. **Ties by rounding could split float-noise twins.** `round(x, 9)` puts two
   values 4e-19 apart on opposite sides of a rounding boundary. Ties now use
   `abs(a - b) <= 1e-9` (`FIT['tie_tolerance']`, replacing
   `tie_rounding_decimals`). Repeat-run means are order-dependent in the last
   bit, so this can happen in practice, just rarely.
3. **Percentile CI bounds were off by one rank upward** (index `int(q*n)`:
   2.6th and 97.6th percentiles at 1000 draws). Now linear interpolation,
   numpy's default.

### Findings

**Rank order never depends on the fitting choices.** In a complete matched
design every pair has the same total weight (3, one per task), so every
Bradley-Terry-type fit with a symmetric prior ranks models by their total
pairwise score (sum over opponents of task-averaged wins + ties/2). In 2,400
simulated rosters, no tie model or prior setting changed the order. The fit
only sets the spacing and the intervals. A test locks in this property.

**(1) Davidson vs ties-as-half-win.** Same ranks. Davidson spreads ratings a
little more when ties are common, because a high tie rate means a given
win/loss margin implies a bigger strength gap. Median Elo spread, Davidson vs
half-win: typical n=5 496 vs 463; ceiling n=10 504 vs 434; tie_heavy n=10 435
vs 267 (median max shift 95 Elo). **Recommend: keep Davidson.** It models the
ties judges' integer scores produce instead of hiding them, and reports nu.

**(2) Prior sensitivity.** `log_nu_prior_precision` hardly matters: 0.001-0.1
moves any rating by ≤ 5 Elo (median ≤ 3); 1.0 moves the most-shifted rating by up to 26 (median across scenarios ≤ 26). **Keep
0.01.** `theta_prior_precision` shrinks the spread: at typical n=5 the median
spread is 531 / 496 / 439 / 329 for 0.01 / 0.1 / 0.3 / 1.0. Against the
infinite-case rating, RMSE is lowest at 0.1-0.3 when skills are spread out
(typical n=5: 96 / 79 / 75 / 92 Elo for 0.01 / 0.1 / 0.3 / 1.0) and at 1.0 when
models are close (close n=5: 80 / 76 / 69 / 56). Interval coverage is about the
same for 0.01-0.3 and drops at 1.0 (typical n=3: 0.39). **Recommend: keep 0.1.**
It is near-optimal in the spread-out case, safe in the close case, and never
reorders models. Note that each pair carries only 3 units of evidence however
many cases there are, so the prior never washes out. Report that Elo gaps are
shrunk by a fixed amount.

**(3) Within-task case bootstrap.** No crashes or degenerate output. All-ties
resamples give [1500, 1500] and separated resamples stay finite. A 2-case task
has only 3 distinct resamples (AA 1/4, AB 1/2, BB 1/4), so the two small tasks
give at most 9 configurations. **The intervals under-cover.** Coverage of
the infinite-case rating at nominal 95% is 0.65-0.79 for the full suite. It is
0.90 for keep_going alone (13 cases) but 0.49 for rulebook alone and 0.41 for
beat_ectemp alone (2 cases each). Two causes: (a) a 2-case bootstrap
underestimates case variance by half (factor (n-1)/n), and (b) finite-case
ratings overstate gaps (median sample/population spread 1.12-1.81), a bias the
bootstrap does not see. Drawing n-1 cases per task (rescaled bootstrap) adds
2-5 points of coverage and makes intervals ~20% wider: not worth changing the
pin. The point estimate was never outside its interval. **Decided: keep the
method; intervals are exploratory, with about 70% real coverage of the nominal
95%.** `rate()` output carries this as `ci95_note`. Do not call two models
different because their intervals don't overlap. The only real fix is more rulebook and
beat_ectemp cases.

**(4) Perfect separation and all ties.** Both behave. Under total separation the
prior alone sets the gap (Elo spread at theta precision 0.1: 527 for 2 models,
876 for 3, 1371 for 5, 2149 for 10; at 0.01 roughly double). That spread is an
artefact of the prior, not a measurement. All ties give every model exactly
1500 with zero-width intervals, and nu goes large (123 for 2 models, 3327 for
10). **Decided and implemented:** each rating carries `separation`
(`wins_all`, `loses_all` or null) and a `separation_note`. A model is flagged
when it won (or lost) every matched case comparison against every opponent,
with no ties; its rating gap is set by the prior, not the data.

**(5) Eligibility.** Fixed above. **Decided:** `required_cases` is frozen in
the params file (`tasks/scoring_params.json`) and a missing list is an error.
KG-03, the unscored edge case (low label confidence per
`tasks/keep_going/README.md`), is left out of the list: if a model answers it,
the case is scored and listed under `extra_cases_not_rated` but never rated.
Case ids may contain `/` (e.g. per-person `beat_ectemp/3A/<person>`); the task
is the part before the first slash.

**(6) Weight and mapping rank sensitivity** (6 models, 300 rosters each, same
answers re-scored; share of rosters where the top model changes / any order
changes):

| Alternative | typical | close |
| --- | ---: | ---: |
| Equal component weights | 4% / 28% | 10% / 46% |
| Deterministic-heavy (0.5/0.3/0.2; ECTemp 0.8/0.2) | 12% / 53% | 20% / 75% |
| Judge-heavy (0.2/0.5/0.3; ECTemp 0.4/0.6) | 7% / 39% | 14% / 56% |
| E = 0.5 °C (vs 1.0) | 3% / 19% | 6% / 30% |
| E = 2.0 °C | 1% / 16% | 5% / 25% |
| ECTemp B × 2 (parity earns 0.5) | 5% / 32% | 12% / 43% |
| Case-proportional instead of equal task weights | 29% / 84% | 34% / 94% |

Mid-table order is fragile under any plausible reweighting. The top model is
fairly stable except under task weighting. The equal-task-weight rule matters
far more than any component weight or E. **Recommend:** keep the spec weights.
Publish this sensitivity table recomputed on the real outputs (rerun each
alternative on the real answers) next to the ratings, and state that adjacent
mid-table ranks are not robust.

### Recommended FIT (unchanged except the fixes)

`tie_model` davidson; `theta_prior_precision` 0.1; `log_nu_prior_precision`
0.01; `tie_tolerance` 1e-9; bootstrap as pinned, labelled exploratory (~70%
real coverage); a frozen `required_cases` in params without KG-03, required for
official runs; separation flags on every rating.
