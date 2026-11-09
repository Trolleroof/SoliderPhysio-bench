# Saved score components: roster rerun 2026-11-07

This report separates deterministic ground-truth outcomes from LLM judge assessments. Rows follow frozen roster order, not a new ranking. Machine-readable case details, judge explanations, hashes and saved variant metrics are in `.benchmark-runs/rerun-20261107/score-components.json`.

## Scope and checks

- Coverage: **14 models × 21 required cases = 294** (168 Keep going, 28 Rulebook, 98 research person-cases). Every model covers the same 12 KG, 2 RB and 7 research cases; KG-03 is excluded.
- Reused `eval_suite.resume_sweep.inventory`; all 24 source submissions have a unique canonical-hash-matching judge file. Verified 294 case checkpoint hashes and matching graders, 294 answer/rubric hashes, 276 reconstructed materials/outcome/prompt hashes and request-body hashes. The 18 absent answers have no judge prompt/request and receive deterministic rubric zeros.
- Judge: `openai/gpt-6.1-sol-pro`, verified outside the frozen roster. 276 scored + 18 absent answers; no remaining not-scorable records in this selection.
- Carbon unavailable. Gemini 3.7, diagnostic fixtures and initial DeepSeek pilots are outside this inventory. All saved artifacts, attempts and ledgers remain untouched.

## Raw deterministic outcomes

Accuracy uses all required cases, including absent/unparsed decisions as incorrect. Temperature error summaries use available numeric forecasts only; missing counts are explicit. These are saved deterministic grader results, not judge opinions.

Across the roster: **92/168 correct KG decisions**, **42/112 rulebook fields**, **11/28 correct overrides**, and **76/98 research person-cases beating baseline**. No rulebook case matched all four lookup fields (0/28). These pooled counts describe this case set; they are not a model ranking.

### Keep going

| Model | Correct /12 | Missed pull | False pull | Unparsed | Forecasts /12 | MAE °C | Median °C | Max °C |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| google/gemini-4-argon | 7 | 1 | 4 | 0 | 12 | 0.3217 | 0.3000 | 0.6800 |
| tencent/hy4 | 10 | 0 | 2 | 0 | 12 | 0.2392 | 0.2150 | 0.5400 |
| anthropic/claude-sonnet-5.5 | 10 | 2 | 0 | 0 | 12 | 0.2150 | 0.1200 | 0.6600 |
| anthropic/claude-opus-5.5 | 5 | 2 | 4 | 1 | 11 | 0.4218 | 0.4200 | 0.8400 |
| deepseek/deepseek-v4.1-flash-1017 | 5 | 2 | 5 | 0 | 12 | 0.3733 | 0.4100 | 0.6200 |
| google/gemini-3.8-flash | 6 | 2 | 4 | 0 | 12 | 0.3417 | 0.3400 | 0.6800 |
| openai/gpt-6.1-terra | 6 | 0 | 6 | 0 | 12 | 0.2983 | 0.2900 | 0.5400 |
| x-ai/grok-4.6 | 4 | 3 | 5 | 0 | 12 | 0.3700 | 0.4400 | 0.5200 |
| anthropic/claude-fable-5.1 | 6 | 2 | 4 | 0 | 12 | 0.3750 | 0.4100 | 0.7400 |
| meta/muse-wonder | 9 | 0 | 3 | 0 | 12 | 0.2733 | 0.2200 | 0.7200 |
| anthropic/claude-opus-5 | 6 | 3 | 2 | 1 | 11 | 0.3327 | 0.2200 | 0.8400 |
| moonshotai/kimi-k3.1-pro | 5 | 3 | 4 | 0 | 12 | 0.3683 | 0.3300 | 0.7400 |
| openai/gpt-6-astra | 6 | 0 | 6 | 0 | 12 | 0.3517 | 0.3500 | 0.7200 |
| anthropic/claude-fable-5 | 7 | 0 | 4 | 1 | 11 | 0.3182 | 0.2800 | 0.5800 |

### Rulebook versus body

Lookup is exact match on four fields per case; a case passes lookup only at 4/4. Override correctness is independently compared with the saved FOLLOW/OVERRIDE ground truth. The evaluator’s legacy 50/50 `total` is retained per case in JSON but is not the frozen mixed score.

| Model | Lookup fields /8 | Full lookup cases /2 | Override correct /2 | Missed override | False override | Unparsed | Forecasts /2 | MAE °C |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| google/gemini-4-argon | 4 | 0 | 1 | 0 | 1 | 0 | 2 | 0.2800 |
| tencent/hy4 | 2 | 0 | 0 | 0 | 1 | 1 | 1 | 0.2400 |
| anthropic/claude-sonnet-5.5 | 4 | 0 | 1 | 0 | 1 | 0 | 2 | 0.2300 |
| anthropic/claude-opus-5.5 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| deepseek/deepseek-v4.1-flash-1017 | 2 | 0 | 0 | 1 | 1 | 0 | 2 | 0.4300 |
| google/gemini-3.8-flash | 3 | 0 | 1 | 0 | 1 | 0 | 2 | 0.1800 |
| openai/gpt-6.1-terra | 4 | 0 | 1 | 0 | 1 | 0 | 2 | 0.1800 |
| x-ai/grok-4.6 | 4 | 0 | 2 | 0 | 0 | 0 | 2 | 0.1900 |
| anthropic/claude-fable-5.1 | 2 | 0 | 1 | 0 | 1 | 0 | 2 | 0.3300 |
| meta/muse-wonder | 4 | 0 | 1 | 0 | 1 | 0 | 2 | 0.2800 |
| anthropic/claude-opus-5 | 4 | 0 | 1 | 0 | 1 | 0 | 2 | 0.2300 |
| moonshotai/kimi-k3.1-pro | 3 | 0 | 1 | 0 | 1 | 0 | 2 | 0.3300 |
| openai/gpt-6-astra | 6 | 0 | 1 | 0 | 1 | 0 | 2 | 0.2300 |
| anthropic/claude-fable-5 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |

### Research predictors

All 98 person-cases have valid saved predictors and numeric MAE. There are 28 distinct variant artifacts (one 3A and one 3B per model), not 98 independent research runs. 3A covers H06/H13 (57 scored requests after watts drop); 3B covers five people (300 requests). MAE below is the equal-person mean. Improvement is baseline MAE minus model MAE in °C, so negative values are worse. No clipping is applied to these raw improvements. The comparator is ECTemp-style, not a validated reproduction of published ECTemp.

| Model | Variant | Valid people | MAE °C | Baseline °C | Improvement °C | People beating baseline | Interval coverage | Interval score |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| google/gemini-4-argon | 3A | 2/2 | 0.2550 | 0.5449 | 0.2899 | 2/2 | 1.0000 | 1.0745 |
| google/gemini-4-argon | 3B | 5/5 | 0.2909 | 0.5056 | 0.2147 | 5/5 | 0.8100 | 1.3997 |
| tencent/hy4 | 3A | 2/2 | 0.1786 | 0.5449 | 0.3663 | 2/2 | 1.0000 | 1.0000 |
| tencent/hy4 | 3B | 5/5 | 0.3097 | 0.5056 | 0.1959 | 4/5 | 0.7433 | 1.7954 |
| anthropic/claude-sonnet-5.5 | 3A | 2/2 | 0.3358 | 0.5449 | 0.2091 | 1/2 | 1.0000 | 1.4000 |
| anthropic/claude-sonnet-5.5 | 3B | 5/5 | 0.2715 | 0.5056 | 0.2341 | 4/5 | 0.9500 | 1.3510 |
| anthropic/claude-opus-5.5 | 3A | 2/2 | 0.2670 | 0.5449 | 0.2779 | 1/2 | 1.0000 | 1.2000 |
| anthropic/claude-opus-5.5 | 3B | 5/5 | 0.2532 | 0.5056 | 0.2524 | 4/5 | 0.9767 | 1.2669 |
| deepseek/deepseek-v4.1-flash-1017 | 3A | 2/2 | 0.2745 | 0.5449 | 0.2703 | 2/2 | 1.0000 | 2.2000 |
| deepseek/deepseek-v4.1-flash-1017 | 3B | 5/5 | 0.2792 | 0.5056 | 0.2264 | 4/5 | 0.9500 | 1.5020 |
| google/gemini-3.8-flash | 3A | 2/2 | 0.2248 | 0.5449 | 0.3201 | 1/2 | 1.0000 | 2.1000 |
| google/gemini-3.8-flash | 3B | 5/5 | 0.2906 | 0.5056 | 0.2150 | 4/5 | 0.9133 | 1.4126 |
| openai/gpt-6.1-terra | 3A | 2/2 | 0.3108 | 0.5449 | 0.2341 | 1/2 | 1.0000 | 1.4000 |
| openai/gpt-6.1-terra | 3B | 5/5 | 0.2684 | 0.5056 | 0.2372 | 5/5 | 0.9667 | 1.3276 |
| x-ai/grok-4.6 | 3A | 2/2 | 0.3370 | 0.5449 | 0.2079 | 1/2 | 1.0000 | 1.8000 |
| x-ai/grok-4.6 | 3B | 5/5 | 0.2787 | 0.5056 | 0.2269 | 4/5 | 0.9433 | 1.2906 |
| anthropic/claude-fable-5.1 | 3A | 2/2 | 0.2754 | 0.5449 | 0.2695 | 1/2 | 1.0000 | 1.5626 |
| anthropic/claude-fable-5.1 | 3B | 5/5 | 0.2841 | 0.5056 | 0.2215 | 4/5 | 0.9600 | 1.2009 |
| meta/muse-wonder | 3A | 2/2 | 0.2612 | 0.5449 | 0.2837 | 1/2 | 1.0000 | 1.3000 |
| meta/muse-wonder | 3B | 5/5 | 0.2252 | 0.5056 | 0.2804 | 4/5 | 0.9033 | 1.8798 |
| anthropic/claude-opus-5 | 3A | 2/2 | 0.2602 | 0.5449 | 0.2847 | 1/2 | 1.0000 | 2.1000 |
| anthropic/claude-opus-5 | 3B | 5/5 | 0.2191 | 0.5056 | 0.2865 | 4/5 | 0.9733 | 1.3870 |
| moonshotai/kimi-k3.1-pro | 3A | 2/2 | 0.2414 | 0.5449 | 0.3035 | 2/2 | 1.0000 | 1.6000 |
| moonshotai/kimi-k3.1-pro | 3B | 5/5 | 0.2931 | 0.5056 | 0.2125 | 4/5 | 0.9267 | 1.5572 |
| openai/gpt-6-astra | 3A | 2/2 | 0.4165 | 0.5449 | 0.1284 | 1/2 | 1.0000 | 1.5000 |
| openai/gpt-6-astra | 3B | 5/5 | 0.2735 | 0.5056 | 0.2321 | 4/5 | 0.9567 | 1.2405 |
| anthropic/claude-fable-5 | 3A | 2/2 | 0.3268 | 0.5449 | 0.2181 | 1/2 | 1.0000 | 1.6500 |
| anthropic/claude-fable-5 | 3B | 5/5 | 0.2437 | 0.5056 | 0.2619 | 4/5 | 0.9700 | 1.4362 |

Interval coverage/score are the saved variant-wide metrics over all prediction requests, not equal-person or exclusively post-drop aggregates. They do not enter the frozen predictor score. Saved request-weighted MAE, primary MAE, hot-slice metrics and public-to-hidden gaps are preserved in JSON.

#### Raw MAE for every held-out person

| Model | 3A H06 | 3A H13 | 3B H06 | 3B H13 | 3B H18 | 3B H22 | 3B H25 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frozen baseline | 0.1573 | 0.9325 | 0.1764 | 0.8653 | 0.6262 | 0.5578 | 0.3023 |
| google/gemini-4-argon | 0.0560 | 0.4539 | 0.1136 | 0.5328 | 0.3075 | 0.3885 | 0.1123 |
| tencent/hy4 | 0.1224 | 0.2348 | 0.2210 | 0.4804 | 0.2329 | 0.4641 | 0.1499 |
| anthropic/claude-sonnet-5.5 | 0.2494 | 0.4222 | 0.2456 | 0.3167 | 0.1396 | 0.4080 | 0.2475 |
| anthropic/claude-opus-5.5 | 0.2240 | 0.3100 | 0.3067 | 0.3647 | 0.1576 | 0.3137 | 0.1231 |
| deepseek/deepseek-v4.1-flash-1017 | 0.0808 | 0.4683 | 0.2730 | 0.3287 | 0.1480 | 0.4112 | 0.2350 |
| google/gemini-3.8-flash | 0.1960 | 0.2536 | 0.3376 | 0.3362 | 0.1371 | 0.4802 | 0.1621 |
| openai/gpt-6.1-terra | 0.2298 | 0.3917 | 0.1479 | 0.4022 | 0.2097 | 0.3914 | 0.1906 |
| x-ai/grok-4.6 | 0.1819 | 0.4922 | 0.2742 | 0.3275 | 0.1468 | 0.4056 | 0.2395 |
| anthropic/claude-fable-5.1 | 0.2584 | 0.2924 | 0.2732 | 0.3284 | 0.1478 | 0.4283 | 0.2428 |
| meta/muse-wonder | 0.2257 | 0.2967 | 0.0796 | 0.2164 | 0.0763 | 0.6131 | 0.1405 |
| anthropic/claude-opus-5 | 0.2185 | 0.3018 | 0.2433 | 0.2066 | 0.1251 | 0.2699 | 0.2506 |
| moonshotai/kimi-k3.1-pro | 0.1197 | 0.3630 | 0.2477 | 0.3413 | 0.1629 | 0.4500 | 0.2637 |
| openai/gpt-6-astra | 0.3994 | 0.4335 | 0.2466 | 0.4113 | 0.1492 | 0.3681 | 0.1921 |
| anthropic/claude-fable-5 | 0.2348 | 0.4189 | 0.2455 | 0.3314 | 0.0961 | 0.3568 | 0.1888 |

## Separate judge summaries

Means are on the original 0–5 scale. “All” includes deterministic zeros for absent answers; “scored only” excludes those absent answers. Missing explanations are not evidence of invalid predictors. The JSON contains per-case scores, score distributions, explanations, quoted answer evidence, references and uncertainties. Scores describe this frozen judge’s assessment, not an additional ground-truth measurement.

### keep_going

| Model | Scored | Absent | decision all / scored only | reasoning all / scored only |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 12 | 0 | 2.8333 / 2.8333 | 2.6667 / 2.6667 |
| tencent/hy4 | 12 | 0 | 4.3333 / 4.3333 | 3.6667 / 3.6667 |
| anthropic/claude-sonnet-5.5 | 12 | 0 | 3.8333 / 3.8333 | 2.9167 / 2.9167 |
| anthropic/claude-opus-5.5 | 11 | 1 | 2.2500 / 2.4545 | 2.3333 / 2.5455 |
| deepseek/deepseek-v4.1-flash-1017 | 12 | 0 | 2.5000 / 2.5000 | 2.6667 / 2.6667 |
| google/gemini-3.8-flash | 12 | 0 | 2.5000 / 2.5000 | 2.4167 / 2.4167 |
| openai/gpt-6.1-terra | 12 | 0 | 3.0000 / 3.0000 | 3.1667 / 3.1667 |
| x-ai/grok-4.6 | 12 | 0 | 1.9167 / 1.9167 | 2.0833 / 2.0833 |
| anthropic/claude-fable-5.1 | 12 | 0 | 2.6667 / 2.6667 | 2.4167 / 2.4167 |
| meta/muse-wonder | 12 | 0 | 3.4167 / 3.4167 | 2.8333 / 2.8333 |
| anthropic/claude-opus-5 | 12 | 0 | 2.4167 / 2.4167 | 2.5000 / 2.5000 |
| moonshotai/kimi-k3.1-pro | 12 | 0 | 2.6667 / 2.6667 | 2.8333 / 2.8333 |
| openai/gpt-6-astra | 12 | 0 | 3.0000 / 3.0000 | 3.4167 / 3.4167 |
| anthropic/claude-fable-5 | 11 | 1 | 2.6667 / 2.9091 | 2.4167 / 2.6364 |

### rulebook_vs_body

| Model | Scored | Absent | override_decision all / scored only | reasoning all / scored only |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 2 | 0 | 2.5000 / 2.5000 | 2.0000 / 2.0000 |
| tencent/hy4 | 1 | 1 | 0.5000 / 1.0000 | 1.0000 / 2.0000 |
| anthropic/claude-sonnet-5.5 | 2 | 0 | 2.5000 / 2.5000 | 2.0000 / 2.0000 |
| anthropic/claude-opus-5.5 | 0 | 2 | 0.0000 / — | 0.0000 / — |
| deepseek/deepseek-v4.1-flash-1017 | 2 | 0 | 1.0000 / 1.0000 | 2.0000 / 2.0000 |
| google/gemini-3.8-flash | 2 | 0 | 2.5000 / 2.5000 | 2.0000 / 2.0000 |
| openai/gpt-6.1-terra | 2 | 0 | 2.5000 / 2.5000 | 2.5000 / 2.5000 |
| x-ai/grok-4.6 | 2 | 0 | 4.0000 / 4.0000 | 2.0000 / 2.0000 |
| anthropic/claude-fable-5.1 | 2 | 0 | 2.5000 / 2.5000 | 2.5000 / 2.5000 |
| meta/muse-wonder | 2 | 0 | 2.5000 / 2.5000 | 2.5000 / 2.5000 |
| anthropic/claude-opus-5 | 2 | 0 | 2.5000 / 2.5000 | 2.5000 / 2.5000 |
| moonshotai/kimi-k3.1-pro | 2 | 0 | 2.5000 / 2.5000 | 2.5000 / 2.5000 |
| openai/gpt-6-astra | 2 | 0 | 3.0000 / 3.0000 | 3.0000 / 3.0000 |
| anthropic/claude-fable-5 | 0 | 2 | 0.0000 / — | 0.0000 / — |

### beat_ectemp

| Model | Scored | Absent | research_explanation all / scored only |
|---|---:|---:|---:|
| google/gemini-4-argon | 0 | 7 | 0.0000 / — |
| tencent/hy4 | 7 | 0 | 3.8571 / 3.8571 |
| anthropic/claude-sonnet-5.5 | 7 | 0 | 3.7143 / 3.7143 |
| anthropic/claude-opus-5.5 | 7 | 0 | 4.0000 / 4.0000 |
| deepseek/deepseek-v4.1-flash-1017 | 7 | 0 | 3.0000 / 3.0000 |
| google/gemini-3.8-flash | 7 | 0 | 3.1429 / 3.1429 |
| openai/gpt-6.1-terra | 7 | 0 | 3.1429 / 3.1429 |
| x-ai/grok-4.6 | 5 | 2 | 2.7143 / 3.8000 |
| anthropic/claude-fable-5.1 | 7 | 0 | 3.7143 / 3.7143 |
| meta/muse-wonder | 7 | 0 | 3.8571 / 3.8571 |
| anthropic/claude-opus-5 | 7 | 0 | 3.7143 / 3.7143 |
| moonshotai/kimi-k3.1-pro | 5 | 2 | 2.7143 / 3.8000 |
| openai/gpt-6-astra | 7 | 0 | 3.7143 / 3.7143 |
| anthropic/claude-fable-5 | 7 | 0 | 3.5714 / 3.5714 |

Research explanations are shared across person-cases within an artifact, but the judge sees each person’s verified outcome. Those scores can differ and are correlated. Unique nonempty explanation counts per model are available in JSON. **Argon’s missing research explanations are partly harness-caused by the 30-second finalization reserve. Explanation comparisons are provisional and need a versioned matched rerun.**

Absent-answer cases: google/gemini-4-argon: beat_ectemp/3A/H06, beat_ectemp/3A/H13, beat_ectemp/3B/H06, beat_ectemp/3B/H13, beat_ectemp/3B/H18, beat_ectemp/3B/H22, beat_ectemp/3B/H25; tencent/hy4: rulebook_vs_body/RB-01; anthropic/claude-opus-5.5: keep_going/KG-02, rulebook_vs_body/RB-01, rulebook_vs_body/RB-02; x-ai/grok-4.6: beat_ectemp/3A/H06, beat_ectemp/3A/H13; moonshotai/kimi-k3.1-pro: beat_ectemp/3A/H06, beat_ectemp/3A/H13; anthropic/claude-fable-5: keep_going/KG-10, rulebook_vs_body/RB-01, rulebook_vs_body/RB-02.

## Frozen weighting and interpretation

- Keep going: 30% deterministic forecast `max(0, 1 − absolute_error / 0.1712)` + 40% judge decision/5 + 30% judge reasoning/5. Missing forecasts receive zero forecast credit. Raw binary decision correctness is reported above; it is not itself a separate weighted component.
- Rulebook: 30% deterministic four-field lookup fraction + 40% judge override/5 + 30% judge reasoning/5. Raw override correctness and body forecast error remain separately visible; body forecast error has no direct mixed-score weight.
- Research: 60% deterministic per-person `clip(1 − MAE/B, 0, 1)` + 40% judge research explanation/5. `B` is the frozen baseline for that variant/person. Invalid artifacts get zero predictor credit; none of the 98 selected person-cases are invalid. Worse-than-baseline predictors all get zero normalized predictor credit even when their raw errors differ.
- Judge zeros for absent answers do not erase valid deterministic forecast/lookup/predictor outcomes. A missing/not-scorable judge dimension would block a mixed case instead of becoming zero; no such records remain here.
- These formulas are read from frozen `tasks/combined_score.py`; no scoring or protocol changes, new ranking, Elo fit or mixed leaderboard were produced by this report.

## Discrepancies and limits

- No coverage/hash discrepancies or wrong-decision rubric-cap violations were found.
- Provider/filter/length failures, generated-code problems and infrastructure/harness interruptions are different causes. This report preserves saved finish/stop metadata but does not infer cause from absent text or an error metric; the companion failure audit owns that attribution. In particular, a research wall-limit can leave a valid predictor.
- Completion-audit spend is **$141.201549259 provider-reported** and **$81.546314581 conservative reservations**. Reservations are not confirmed provider charges; these numbers are carried from the source audit, not independently reconciled here.
- Checks are entirely offline: inventory, canonical input hashes, saved grader/report consistency, frozen rubric caps and report arithmetic. Predictions and historical execution were not rerun. No provider requests, new dependencies, queue changes, automations, commits or pushes.

## Reproduce this saved-data report

Run `.venv-research/bin/python -m eval_suite.report_score_components` from the repository root. This only reads existing evidence and writes these two owned reports. The script asserts 14×21 coverage, audit status counts, unique source matches, grader consistency and judge input hashes before writing.
