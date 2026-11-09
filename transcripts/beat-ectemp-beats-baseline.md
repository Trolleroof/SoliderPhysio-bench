# Beat ECTemp: predictor clearly beats the baseline

- **Model:** Muse Wonder 1.0 (`meta/muse-wonder`)
- **Case:** `beat_ectemp/3A/H13` · finish reason `None`
- **Combined score:** 0.729 · components {"research_explanation": 0.8, "predictor": 0.6817695444352945}
- **Source:** `results/rerun-20261107/continued-11-01/submissions.json`

## Prompt

Agentic research session; task spec in `tasks/beat_ectemp/README.md`.

## Model answer (raw)

```text
## Frozen predictor

`submission.py` is a self-contained, pure–Python-stdlib implementation. It does not import the baseline, scikit-learn, or any external file at prediction time.

For each request it:

1. Uses only the supplied causal `history`; no future values, core-temperature labels, person identity, or absolute clock are used.
2. Calculates elapsed time as `last time_min − first time_min`, making it invariant to an overall clock shift.
3. Derives 17 history covariates:
   - age and BMI;
   - mean heart rate, skin temperature, watts/kg, ambient temperature, and humidity;
   - mean skin temperature over the first three minutes and first available heart rate;
   - cumulative watts/kg and cumulative heart-rate excess above 100 bpm;
   - last heart rate multiplied by last watts/kg;
   - mean skin-minus-ambient temperature;
   - overall heart-rate and skin-temperature slopes, and their last-15-minute slopes.
4. Forms a 90-dimensional ridge-regression design from:
   - a target-time basis for \(u=\text{elapsed}+\text{horizon}\):  
     \(1, u/60, (u/60)^2, e^{-u/12}, e^{-u/30}\);
   - the 17 covariates;
   - interactions between the non-constant basis terms and every covariate.
5. Applies the embedded ridge coefficients, trained on all causal 15-minute-forecast origins from the 14 labeled training people. The raw ridge output is blended as  
   `0.6 × ridge + 0.4 × 38.484`.
6. Robustly winsorizes that result to \(38.05\)–\(38.85^\circ\text{C}\), then shrinks it again:
   `0.7 × winsorized + 0.3 × 38.65`.
7. Returns a fixed 90%-intended interval of mean ± \(0.65^\circ\text{C}\), i.e. width \(1.3^\circ\text{C}\), within the required \(0<\text{width}\le5^\circ\text{C}\).

The forecaster uses `horizon_min` when supplied; otherwise it uses 15 minutes for task 3A and 0 for other tasks.

## Development evidence actually obtained

Verified `dev_score` results were:

| Predictor | Person-balanced MAE | Overall MAE | 90% coverage | Interval score |
|---|---:|---:|---:|---:|
| Original ECTemp-style template | 0.539 | 0.520 | 44.0% | 3.605 |
| Constant 38.65 °C | 0.355 | 0.410 | 69.0% | 2.929 |
| Unclipped ridge model | 0.389 | 0.421 | 73.8% | 5.119 |
| **Frozen winsorized/shrunk ridge** | **0.324** | **0.368** | **73.8%** | **3.273** |

For the frozen predictor, the scorer also reported a hot-subset person-balanced MAE of 0.093. Per-person dev MAEs were 0.127, 0.911, 0.029, and 0.230 °C, showing that one development person remained difficult.

In leave-one-person-out evaluation on the labeled training data, the unrobustified ridge had person-balanced MAE of approximately 0.117 °C over the post-watts-decrease origins. The additional winsorizing/shrinkage worsened that internal estimate to about 0.148 °C but improved the verified development result from 0.389 to 0.324, so the more conservative version was frozen.

## Limitations

- Training contained only 14 people, so person-specific physiological offsets remain the dominant source of error.
- One development person still had MAE 0.911 °C; hidden people with covariate combinations unlike the training people may be similarly difficult.
- The interval is intentionally simple and fixed-width. Its observed development coverage was 73.8%, below the nominal 90%, because errors are correlated within a person through a systematic level offset.
- Early histories can lack heart-rate, ambient, and humidity measurements. These cases were handled with the same conventions used during training, but they necessarily provide less information.
- The predictor assumes broadly similar exercise/heat dynamics in hidden testing; it should not be interpreted as a validated reproduction of published ECTemp.
```

## Deterministic grade

```json
{
  "person_mae": 0.29674086287920975,
  "valid": true
}
```

## LLM judge marks

```json
{
  "research_explanation": 4
}
```
