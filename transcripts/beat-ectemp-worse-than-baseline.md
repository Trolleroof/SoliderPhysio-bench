# Beat ECTemp: predictor no better than the baseline (predictor score 0)

- **Model:** GPT-6 Astra (`openai/gpt-6-astra`)
- **Case:** `beat_ectemp/3A/H06` · finish reason `None`
- **Combined score:** 0.240 · components {"research_explanation": 0.6, "predictor": 0.0}
- **Source:** `results/rerun-20261107/continued-14-01/submissions.json`

## Prompt

Agentic research session; task spec in `tasks/beat_ectemp/README.md`.

## Model answer (raw)

```text
Implemented and froze `submission.py`.

### Predictor
- Stateless, self-contained, Python standard library only.
- Forecasts core temperature 15 minutes ahead using elapsed time and 15-minute exponential averages of heart rate, skin temperature, and watts.
- Uses person-centered ridge regression fitted on training data.
- Uses no identifiers, demographics, absolute-clock features, or future measurements.
- Handles missing inputs and returns a fixed **1.50°C-wide** interval: mean − 0.85°C to mean + 0.65°C.

### Verified development results
Across 84 scored requests:

| Metric | Template | Frozen predictor |
|---|---:|---:|
| Person-balanced MAE | 0.539°C | **0.286°C** |
| Request-level MAE | 0.520°C | **0.298°C** |
| 90% interval coverage | 44.0% | **94.0%** |
| Interval score | 3.605 | **2.233** |

Person-balanced MAE improved by approximately **47%**. Clock-shift invariance, JSON-compatible output, interval constraints, and missing-input handling were checked.

### Limitations
Evidence is limited to 14 training people and four scored development people. Error remains uneven across people—the largest development person-level MAE was 0.792°C. The interval is empirical, not a coverage guarantee for unseen people, and this is not a clinically validated temperature estimator. Variant 3B was not the optimization target.
```

## Deterministic grade

```json
{
  "person_mae": 0.39939943775668557,
  "valid": true
}
```

## LLM judge marks

```json
{
  "research_explanation": 3
}
```
