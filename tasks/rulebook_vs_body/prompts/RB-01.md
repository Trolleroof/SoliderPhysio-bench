You are the medic advising a small-unit leader during a hot-weather training session. The session runs under the unit's Yellow flag (Heat Category 3) and the leader's risk card classifies the activity as Moderate work. Everyone is fully heat-acclimatized, in duty uniform, no body armor, no MOPP, water on hand.

One soldier is riding a stationary bike inside the heat chamber used for the session. He has been riding for a while already. The table below is the last 25 minutes of his wearable and chamber log, ending now (minute 24). Core temperature is NOT measured. Blank cells mean that value was not logged that minute.

Soldier: age 24 years, body mass 59 kg.

| min | HR (bpm) | skin (C) | room (C) | RH (%) | watts |
|---:|---:|---:|---:|---:|---:|
| 0 |  | 35.5 | 35.0 | 19 | 195 |
| 1 | 150 | 35.9 | 35.0 | 26 | 195 |
| 2 | 149 | 36.1 | 35.0 | 26 | 195 |
| 3 | 150 | 36.2 | 35.0 | 26 | 195 |
| 4 |  | 36.2 | 35.0 | 26 | 195 |
| 5 | 152 | 36.2 | 36.0 | 25 | 195 |
| 6 |  | 36.0 | 36.0 | 25 | 195 |
| 7 |  | 36.1 | 36.0 | 25 | 195 |
| 8 |  | 36.3 | 36.0 | 25 | 195 |
| 9 |  | 36.5 | 36.0 | 25 | 195 |
| 10 |  | 36.6 | 36.0 | 25 | 195 |
| 11 |  | 36.6 | 36.0 | 25 | 195 |
| 12 |  | 36.7 | 36.0 | 25 | 195 |
| 13 |  | 36.7 | 36.0 | 25 | 195 |
| 14 |  | 36.6 | 36.0 | 25 | 195 |
| 15 |  | 36.6 | 36.0 | 25 | 195 |
| 16 | 159 | 36.7 | 36.0 | 26 | 195 |
| 17 | 158 | 36.7 | 36.0 | 26 | 195 |
| 18 | 159 | 36.7 | 36.0 | 26 | 195 |
| 19 | 159 | 36.7 | 36.0 | 26 | 195 |
| 20 | 159 | 36.6 | 35.0 | 22 | 195 |
| 21 |  | 36.6 | 35.0 | 22 | 195 |
| 22 |  | 36.6 | 35.0 | 22 | 195 |
| 23 |  | 36.6 | 35.0 | 22 | 195 |
| 24 |  | 36.7 | 35.0 | 22 | 195 |

Two questions.

(a) Rulebook. From TB MED 507 (12 April 2022 edition), state the prescription for this heat category and work category: Table 1 (training up to 4 continuous hours) work/rest minutes per hour and water intake in quarts per hour, and Table 2 (continuous work) maximum work duration and water intake. Write NL where the table sets no limit.

(b) Body. Decide whether to FOLLOW the Table 1 prescription for this soldier over the next 15 minutes (he keeps riding at his current workload with the prescribed water) or OVERRIDE it (pull him off the bike now, rest, cool and monitor, whatever the table allows). Rule: OVERRIDE is correct if his rectal core temperature 15 minutes from now would be at or above 38.5 C if he keeps going; otherwise FOLLOW is correct. Also estimate that core temperature.

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
  "predicted_core_c": "your best estimate of his rectal core temperature (C) 15 minutes from now, one number",
  "confidence": "probability (0 to 1) that OVERRIDE is the correct call",
  "reasoning": "two to five sentences"
}
