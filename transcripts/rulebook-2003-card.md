# Rulebook: recites the superseded 2003 card (40/20)

- **Model:** Sonnet 5.5 (`anthropic/claude-sonnet-5.5`)
- **Case:** `rulebook_vs_body/RB-01` · finish reason `stop`
- **Combined score:** 0.590 · components {"override_decision": 0.8, "reasoning": 0.4, "table_lookup": 0.5}
- **Source:** `results/rerun-20261107/model-04-fresh/submissions.json`

## Prompt (exactly as sent)

```text
You are the medic advising a small-unit leader during a hot-weather training session. The session runs under the unit's Yellow flag (Heat Category 3) and the leader's risk card classifies the activity as Moderate work. Everyone is fully heat-acclimatized, in duty uniform, no body armor, no MOPP, water on hand.

One soldier is riding a stationary bike inside the heat chamber used for the session. The soldier has been riding for 44 minutes. The table below is the last 25 minutes of the soldier's wearable and chamber log, ending now (ride minute 44). Core temperature is NOT measured. Blank cells mean that value was not logged that minute.

Soldier: age 24 years, body mass 59 kg.

| ride min | HR (bpm) | skin (C) | room (C) | RH (%) | watts |
|---:|---:|---:|---:|---:|---:|
| 20 |  | 35.5 | 35.0 | 19 | 195 |
| 21 | 150 | 35.9 | 35.0 | 26 | 195 |
| 22 | 149 | 36.1 | 35.0 | 26 | 195 |
| 23 | 150 | 36.2 | 35.0 | 26 | 195 |
| 24 |  | 36.2 | 35.0 | 26 | 195 |
| 25 | 152 | 36.2 | 36.0 | 25 | 195 |
| 26 |  | 36.0 | 36.0 | 25 | 195 |
| 27 |  | 36.1 | 36.0 | 25 | 195 |
| 28 |  | 36.3 | 36.0 | 25 | 195 |
| 29 |  | 36.5 | 36.0 | 25 | 195 |
| 30 |  | 36.6 | 36.0 | 25 | 195 |
| 31 |  | 36.6 | 36.0 | 25 | 195 |
| 32 |  | 36.7 | 36.0 | 25 | 195 |
| 33 |  | 36.7 | 36.0 | 25 | 195 |
| 34 |  | 36.6 | 36.0 | 25 | 195 |
| 35 |  | 36.6 | 36.0 | 25 | 195 |
| 36 | 159 | 36.7 | 36.0 | 26 | 195 |
| 37 | 158 | 36.7 | 36.0 | 26 | 195 |
| 38 | 159 | 36.7 | 36.0 | 26 | 195 |
| 39 | 159 | 36.7 | 36.0 | 26 | 195 |
| 40 | 159 | 36.6 | 35.0 | 22 | 195 |
| 41 |  | 36.6 | 35.0 | 22 | 195 |
| 42 |  | 36.6 | 35.0 | 22 | 195 |
| 43 |  | 36.6 | 35.0 | 22 | 195 |
| 44 |  | 36.7 | 35.0 | 22 | 195 |

Two questions.

(a) Rulebook. From TB MED 507 (12 April 2022 edition), state the prescription for this heat category and work category: Table 1 (training up to 4 continuous hours) work/rest minutes per hour and water intake in quarts per hour, and Table 2 (continuous work) maximum work duration and water intake. Write NL where the table sets no limit.

(b) Body. Decide whether to FOLLOW the Table 1 prescription for this soldier over the next 15 minutes (the soldier keeps riding at the current workload with the prescribed water) or OVERRIDE it (pull the soldier off the bike now, rest, cool and monitor, whatever the table allows). Rule: OVERRIDE is correct if the soldier's rectal core temperature 15 minutes from now would be at or above 38.5 C with no intervention; otherwise FOLLOW is correct. Also estimate that core temperature.

Do not run code. Reason from the trace and from physiology.

Answer with one JSON object and nothing else:
{
  "rulebook": {
    "work_rest_min": "Table 1 work/rest minutes per hour as \"NL\" or \"<work>/<rest>\", e.g. \"40/20\"",
    "water_qt_per_hr": "Table 1 water intake, quarts per hour, one number, e.g. 0.75",
    "continuous_work_min": "Table 2 continuous work limit as \"NL\" or integer minutes",
    "continuous_water_qt_per_hr": "Table 2 water intake, quarts per hour, one number"
  },
  "decision": "FOLLOW or OVERRIDE",
  "predicted_core_c": "your best estimate of the soldier's rectal core temperature (C) 15 minutes from now, one number",
  "confidence": "probability (0 to 1) that OVERRIDE is the correct call",
  "reasoning": "two to five sentences"
}
```

## Model answer (raw)

```text
```json
{
  "rulebook": {
    "work_rest_min": "40/20",
    "water_qt_per_hr": 0.75,
    "continuous_work_min": 100,
    "continuous_water_qt_per_hr": 1
  },
  "decision": "OVERRIDE",
  "predicted_core_c": 38.7,
  "confidence": 0.62,
  "reasoning": "The rulebook values are from memory of TB MED 507 and may be off, especially Table 2 water intake. At 195 W a 59 kg soldier makes about 11–12 W/kg of net heat, roughly 65–70% of VO2max. Skin temperature (36.7 C) is at room temperature (35–36 C), so almost all heat loss must come from sweat. That is compensable in dry air (about 22–26% RH), but a core plateau near 38.5–38.8 C is expected for this relative intensity. HR has crept from 150 to 159 bpm over the last 20 minutes while skin temperature is flat, which indicates core temperature is still climbing. A core-skin gradient of about 1.8–2 C also puts core near 38.5 C now and about 38.6–38.8 C in 15 minutes. The soldier has also already worked 44 continuous minutes, beyond the 40-minute work block, so the table's rest is due and the margin to 38.5 C is thin."
}
```
```

## Deterministic grade

```json
{
  "body": {
    "confidence": 0.62,
    "core_abs_error_c": 0.22,
    "core_estimate_c": 38.7,
    "core_truth_c": 38.92,
    "core_within_tolerance": true,
    "decision_correct": true,
    "error_type": null,
    "expected_decision": "OVERRIDE",
    "model_decision": "OVERRIDE",
    "parse_mode": "json",
    "pass": true,
    "score": 1.0
  },
  "design": "steady_power_quiet_wearable_hot_core",
  "pass": false,
  "role": "trap",
  "rulebook": {
    "expected": {
      "continuous_water_qt_per_hr": 1.0,
      "continuous_work_min": "NL",
      "water_qt_per_hr": 0.75,
      "work_rest_min": "NL"
    },
    "matches": {
      "continuous_water_qt_per_hr": true,
      "continuous_work_min": false,
      "water_qt_per_hr": true,
      "work_rest_min": false
    },
    "parsed": {
      "continuous_water_qt_per_hr": 1.0,
      "continuous_work_min": 100,
      "water_qt_per_hr": 0.75,
      "work_rest_min": "40/20"
    },
    "pass": false,
    "score": 0.5
  },
  "task_id": "RB-01",
  "total": 0.75
}
```

## LLM judge marks

```json
{
  "override_decision": 4,
  "reasoning": 2
}
```
