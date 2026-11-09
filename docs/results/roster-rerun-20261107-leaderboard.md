# Roster rerun leaderboard (2026-11-07)

Descriptive mixed scores from the completed saved inventory. Overall is the equal-weight mean of the three task means, each task mean being the mean of that task’s frozen per-case combined scores (weights in `tasks/combined_score.py`). **These are not accuracy percentages, Elo ratings, or a claim of general ability.**

- Checked against `.benchmark-runs/rerun-20261107/control/completion-audit.json`: 14 models × 21 required cases = 294 cases; 276 scored + 18 absent_answer.
- Judge `openai/gpt-6.1-sol-pro` (outside roster). Carbon unavailable. Gemini 3.7, diagnostic fixtures, and initial DeepSeek pilots excluded.
- Cross-check vs sibling score-components: **294 cases, 0 diffs**.
- Spend (from completion audit only): provider-reported **$141.201549**; conservative reservations **$81.546315** (not confirmed charges).
- Sibling reports (read-only): [score components](/Users/nikhi/SoliderPhysio-bench/docs/results/roster-rerun-20261107-score-components.md), [rerun decision](/Users/nikhi/SoliderPhysio-bench/docs/results/roster-rerun-20261107-rerun-decision.md).

## Plain-language walkthrough

Think of each case as a small exam question with a frozen grading key. Keep/Pull mixes a thermometer-error score with a judge’s marks for the keep/pull call and the write-up. Rulebook mixes “did you copy the table fields?” with a judge’s marks for whether to override and why. Research mixes “how close was your predictor to the hidden labels, versus a frozen baseline?” with a judge’s mark for the research explanation. Overall just averages the three subject scores so a task with more cases cannot bully the others—like averaging midterm, lab, and essay even if the essay has fewer pages.

Zeros for missing text are rubric rules, not proof the model “knew nothing.” Some research zeros are partly a harness timing flaw (no protected finalization budget); predictors can still be valid. Treat explanation columns and any overall that embeds them as **provisional** until a matched Beat ECTemp rerun under a repaired protocol (see sibling decision report).

## Leaderboard (descriptive overall /100)

| Rank | Model | Keep/Pull | Rulebook | Research | Overall | Coverage |
|---:|---|---:|---:|---:|---:|---:|
| 1 | GPT-6 Astra | 47.6 | 64.5 | 51.4 | **54.5** | 21/21 |
| 2 | Muse Wonder 1.0 | 50.8 | 50.0 | 59.9 | **53.6** | 21/21 |
| 3 | Sonnet 5.5 | 60.1 | 47.0 | 50.4 | **52.5** | 21/21 |
| 4 | GPT-6.1 Terra | 46.7 | 50.0 | 47.5 | **48.1** | 21/21 |
| 5 | Opus 5 | 38.5 | 50.0 | 54.8 | **47.7** | 21/21 |
| 6 | Hy4 | 63.2 | 17.5 | 54.1 | **44.9** | 21/21 |
| 7 | Kimi K3.1 Pro | 42.2 | 46.2 | 43.3 | **43.9** | 21/21 |
| 8 | Grok 4.6 | 30.8 | 59.0 | 41.8 | **43.9** | 21/21 |
| 9 | Fable 5.1 | 37.7 | 42.5 | 51.1 | **43.8** | 21/21 |
| 10 | Gemini 3.8 Flash | 38.7 | 43.2 | 48.5 | **43.5** | 21/21 |
| 11 | Gemini 4 Argon | 41.5 | 47.0 | 28.6 | **39.0** | 21/21 |
| 12 | DeepSeek-V4.1-Flash-1017 | 38.1 | 27.5 | 48.5 | **38.0** | 21/21 |
| 13 | Fable 5 | 39.5 | 0.0 | 52.1 | **30.6** | 21/21 |
| 14 | Opus 5.5 | 32.7 | 0.0 | 57.9 | **30.2** | 21/21 |

Research and overall columns include provisional explanation credit (including harness-caused absences scored as zero). Predictor-only comparisons should use the sibling score-components research tables.

## Raw metrics (sibling-validated)

| Model | KG correct/12 | KG forecast MAE °C | RB fields/8 | RB overrides/2 | Research people beating B |
|---|---:|---:|---:|---:|---:|
| GPT-6 Astra | 6/12 | 0.3517 | 6/8 | 1/2 | 5/7 |
| Muse Wonder 1.0 | 9/12 | 0.2733 | 4/8 | 1/2 | 5/7 |
| Sonnet 5.5 | 10/12 | 0.2150 | 4/8 | 1/2 | 5/7 |
| GPT-6.1 Terra | 6/12 | 0.2983 | 4/8 | 1/2 | 6/7 |
| Opus 5 | 6/12 | 0.3327 | 4/8 | 1/2 | 5/7 |
| Hy4 | 10/12 | 0.2392 | 2/8 | 0/2 | 6/7 |
| Kimi K3.1 Pro | 5/12 | 0.3683 | 3/8 | 1/2 | 6/7 |
| Grok 4.6 | 4/12 | 0.3700 | 4/8 | 2/2 | 5/7 |
| Fable 5.1 | 6/12 | 0.3750 | 2/8 | 1/2 | 5/7 |
| Gemini 3.8 Flash | 6/12 | 0.3417 | 3/8 | 1/2 | 5/7 |
| Gemini 4 Argon | 7/12 | 0.3217 | 4/8 | 1/2 | 7/7 |
| DeepSeek-V4.1-Flash-1017 | 5/12 | 0.3733 | 2/8 | 0/2 | 6/7 |
| Fable 5 | 7/12 | 0.3182 | 0/8 | 0/2 | 5/7 |
| Opus 5.5 | 5/12 | 0.4218 | 0/8 | 0/2 | 5/7 |

Pooled roster totals (not a ranking): 92/168 KG decisions correct; 42/112 rulebook fields; 11/28 overrides; 76/98 research person-cases beating baseline (98 valid predictors).

## Representative failures (saved cases)

Distinguish generated-code/model/filter/length failures from infrastructure/harness problems. Absent explanations under `wall_limit` can coexist with valid predictors.

- **harness_finalization_or_wall_limit** — Gemini 4 Argon `beat_ectemp/3A/H06` (judge `absent_answer`, finish `wall_limit`, research_wall_s `1200.215`). Submission [.benchmark-runs/rerun-20261107/continued-02-02/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-02-02/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-02-02-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-02-02-judge/judged.json). Empty explanation with valid saved predictor; Task3 attributes Argon/Grok/Kimi 3A (and Argon 3B) absences to unprotected research-deadline finalization / wall_limit, not to an LLM judgment that the explanation was poor.
- **harness_finalization_or_wall_limit** — Gemini 4 Argon `beat_ectemp/3B/H06` (judge `absent_answer`, finish `wall_limit`, research_wall_s `1200.266`). Submission [.benchmark-runs/rerun-20261107/continued-02-02/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-02-02/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-02-02-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-02-02-judge/judged.json). Empty explanation with valid saved predictor; Task3 attributes Argon/Grok/Kimi 3A (and Argon 3B) absences to unprotected research-deadline finalization / wall_limit, not to an LLM judgment that the explanation was poor.
- **harness_finalization_or_wall_limit** — Grok 4.6 `beat_ectemp/3A/H06` (judge `absent_answer`, finish `wall_limit`, research_wall_s `1200.193`). Submission [.benchmark-runs/rerun-20261107/continued-09-02/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-09-02/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-09-02-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-09-02-judge/judged.json). Empty explanation with valid saved predictor; Task3 attributes Argon/Grok/Kimi 3A (and Argon 3B) absences to unprotected research-deadline finalization / wall_limit, not to an LLM judgment that the explanation was poor.
- **harness_finalization_or_wall_limit** — Kimi K3.1 Pro `beat_ectemp/3A/H06` (judge `absent_answer`, finish `wall_limit`, research_wall_s `1202.880`). Submission [.benchmark-runs/rerun-20261107/continued-13-01/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-13-01/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-13-01-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-13-01-judge/judged.json). Empty explanation with valid saved predictor; Task3 attributes Argon/Grok/Kimi 3A (and Argon 3B) absences to unprotected research-deadline finalization / wall_limit, not to an LLM judgment that the explanation was poor.
- **provider_filter_or_length** — Opus 5.5 `keep_going/KG-02` (judge `absent_answer`, finish `content_filter`). Submission [.benchmark-runs/rerun-20261107/model-05-fresh/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/model-05-fresh/submissions.json); judged [.benchmark-runs/rerun-20261107/model-05-fresh-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/model-05-fresh-judge/judged.json). Single-turn empty answer. Recorded finish_reason distinguishes content_filter refusal from length/token exhaustion; not the Beat ECTemp finalization path.
- **provider_filter_or_length** — Opus 5.5 `rulebook_vs_body/RB-01` (judge `absent_answer`, finish `content_filter`). Submission [.benchmark-runs/rerun-20261107/model-05-fresh/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/model-05-fresh/submissions.json); judged [.benchmark-runs/rerun-20261107/model-05-fresh-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/model-05-fresh-judge/judged.json). Single-turn empty answer. Recorded finish_reason distinguishes content_filter refusal from length/token exhaustion; not the Beat ECTemp finalization path.
- **provider_filter_or_length** — Fable 5 `rulebook_vs_body/RB-02` (judge `absent_answer`, finish `content_filter`). Submission [.benchmark-runs/rerun-20261107/continued-15-01/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-15-01/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-15-01-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-15-01-judge/judged.json). Single-turn empty answer. Recorded finish_reason distinguishes content_filter refusal from length/token exhaustion; not the Beat ECTemp finalization path.
- **provider_filter_or_length** — Hy4 `rulebook_vs_body/RB-01` (judge `absent_answer`, finish `length`). Submission [.benchmark-runs/rerun-20261107/continued-03-01/submissions.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-03-01/submissions.json); judged [.benchmark-runs/rerun-20261107/continued-03-01-judge/judged.json](/Users/nikhi/SoliderPhysio-bench/.benchmark-runs/rerun-20261107/continued-03-01-judge/judged.json). Single-turn empty answer. Recorded finish_reason distinguishes content_filter refusal from length/token exhaustion; not the Beat ECTemp finalization path.

## Caveats

- Descriptive mixed scores only; not accuracy%, Elo, clinical competence, or general ability.
- Equal task weighting: overall = mean(Keep/Pull, Rulebook, Research) after per-task mean of frozen combined scores.
- Argon (and some Grok/Kimi) absent research explanations are partly harness-caused; explanation and overall comparisons are provisional pending a versioned matched Beat ECTemp rerun (see roster-rerun-20261107-rerun-decision.md).
- Predictor artifacts remain valid recorded outcomes even when explanations are absent; do not treat absent_answer as proof of an invalid predictor.
- Provider content_filter / length empties (Opus 5.5, Fable 5, Hy4 RB-01) are different mechanisms from harness finalization.
- Carbon unavailable; Gemini 3.7, diagnostic fixtures, and initial DeepSeek pilots excluded.
- Provider-reported spend and conservative reservations are separate figures from the completion audit; reservations are not confirmed charges.
- All artifacts, attempts, and ledgers were preserved; this report only reads them.
- score-snapshot.json is stale relative to the completed audit; this report recomputes from current inventory + judged files.

## Reproduce

```bash
.venv-research/bin/python -m eval_suite.report_leaderboard
```

Machine-readable twin: `.benchmark-runs/rerun-20261107/final-leaderboard.json`.

