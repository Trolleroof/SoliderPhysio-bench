# Task type 1: Keep going or pull him?

No-code decision tasks. The evaluated model sees how long the person has been riding,
the last 25 minutes of their wearable and chamber log (heart rate, skin temperature, room
temperature, humidity, pedal watts) and their age and body mass. This is the information
a medic on site would have. It never sees core temperature. It must decide whether to
**PULL** the person now because their core temperature 15 minutes later would be at or
above 38.5 C, or **KEEP** them going.

The hard part is thermal lag: when someone slows down (watts drop), core temperature keeps
rising for many minutes. A medic knows this. Models that treat falling power as "he is
cooling off now" miss the pull.

## Files

| File | Visibility | Contents |
|---|---|---|
| `build_tasks.py` | builder | Reads the Figshare workbook, writes everything below. Deterministic. |
| `public_tasks.json` | public | Task ids, rounded rows with real ride minutes, subject age and mass, full prompt text, answer format. |
| `prompts/KG-0x.md` | public | The same prompt as rendered markdown, one file per task. |
| `private_ground_truth.json` | private | Original subject number, original cutoff minute, measured core at cutoff and cutoff+15, expected decision, scorer. |
| `evaluator.py` | private | Parses the model answer and grades it. |

Rebuild (needs `openpyxl`, present in `.venv-research`):

```sh
.venv-research/bin/python -m tasks.keep_going.build_tasks
```

Grade a set of raw model answers (`{"KG-01": "<model text>", ...}`):

```sh
.venv-research/bin/python -m tasks.keep_going.evaluator responses.json --out scores.json
```

Tests:

```sh
.venv-research/bin/python -m unittest tests/test_keep_going.py -v
```

## Data source

`sources/figshare-heat/core_cycling_2025.xlsx`: D'Lugos (2025), Figshare 29120024 v1,
CC BY 4.0, https://doi.org/10.6084/m9.figshare.29120024.v1. 24 people cycled about 60
minutes in a 35 to 37 C chamber with a rectal probe sampled every minute. Workbook MD5
`01214bfc835215fe1a5d3f5da1e9ad52`; the builder refuses any other file.

Channels used: `Core Temp / Rectal` (ground truth only), `Skin Temp / YSI TSK`,
`Exercise Data / HR` and `Wattage`, `Environmental Conditions`, `Demographics`. Interval
labels such as `5-6` are aligned to their right edge. Heart rate is only logged in four
five-minute blocks per session; other minutes are blank in the prompt and the prompt says so.
Room conditions are carried forward from the last observation, never backward. Heart rate
outside 30 to 240 bpm (one 1176 bpm cell) is dropped. The vendor CORE sensor estimate,
VO2, RPE and subcutaneous fat are not used.

## Cases

12 scored tasks from 12 different people, plus 1 unscored edge case. Public ids carry no
hint of the design.

| Task | Design | Power in window | Measured core: cutoff to cutoff+15 | Expected |
|---|---|---|---|---|
| KG-01 | steady power, safe | 140 W flat | 38.02 to 38.24 C | KEEP |
| KG-02 | falling power, thermal-lag trap | 215 cut to 180 W | 38.30 to 38.88 C | PULL |
| KG-03 | falling power, core fell (edge case, unscored) | 205 cut to 188 W | 38.90 to 38.14 C | KEEP |
| KG-04 | steady power, rising | 123 W flat | 38.68 to 39.14 C | PULL |
| KG-05 | falling power, safe | 169 stepped to 141 W | 38.06 to 38.08 C | KEEP |
| KG-06 | steady power, rising | 277 W flat | 38.14 to 38.78 C | PULL |
| KG-07 | falling power, thermal-lag trap | 190 cut to 174 W | 38.28 to 38.78 C | PULL |
| KG-08 | steady power, safe | 195 W flat | 37.88 to 38.26 C | KEEP |
| KG-09 | falling power, safe | 105 cut to 96 W | 38.04 to 38.08 C | KEEP |
| KG-10 | steady power, rising | 152 W flat | 38.56 to 38.76 C | PULL |
| KG-11 | steady power, safe | 122 W flat | 38.16 to 38.32 C | KEEP |
| KG-12 | falling power, thermal-lag trap | 164 cut to 151 W | 38.50 to 38.90 C | PULL |
| KG-13 | falling power, safe | 151 cut to 139 W | 37.96 to 38.32 C | KEEP |

The decision rule is mechanical: `PULL` when the measured rectal temperature at
cutoff+15 is at or above 38.5 C, else `KEEP`. The private file stores the exact values.

**Balance.** The 12 scored cases are 6 KEEP and 6 PULL. Within each answer, 3 cases show a
power drop and 3 hold steady power. So always-PULL, always-KEEP and "power dropped, so
keep going" all score exactly 50 percent. The tests enforce this.

**Label quality rules**, enforced by the builder for every scored case:

- The measured core at cutoff+15 is at least 0.15 C from 38.5 C.
- No one-minute core change above 0.3 C anywhere in the 15-minute horizon, which screens
  out probe glitches. Subject 8 was dropped for this reason (a 0.34 C jump), and so were
  cutoffs whose horizon touches the single-minute artifacts in Subjects 20 and 24.

**Thermal-lag traps (KG-02, KG-07, KG-12).** In the workbook, power fell in 148 windows
across 14 people and core kept rising over the next 15 minutes in 97 percent of them. In
these three cases watts drop, yet core climbs another 0.40 to 0.58 C and crosses the
threshold. A model that reads the slowdown as relief says KEEP and is wrong.

**Falling-power safe cases (KG-05, KG-09, KG-13)** are the counterweight. Power also
drops here, but core stays under 38.5 C. A model that pulls everyone who slows down fails
these.

**Steady-power controls (KG-01, KG-04, KG-06, KG-08, KG-10, KG-11)** hold one wattage for
the whole window. They test whether the model can read heart-rate drift, workload
relative to body mass, and skin temperature without the power-drop cue.

**KG-03** is Subject 4, the only falling-power person in the workbook whose core actually
fell. It is labelled `edge_case` and reported separately (`edge_case_correct`). Label
caveat: core peaks at 39.06 C six minutes after the cutoff, then drops 1.7 C over the last
five recorded minutes, including about 1 C in a single minute. A rectal probe does not do
that physiologically, so the late readings look like probe displacement. Treat KG-03 as a
calibration probe. A confident PULL here is what a sensible medic would say.

## Scoring

`evaluator.grade(task_id, text)` parses the first JSON object in the answer (code fences
and surrounding prose tolerated), falls back to a standalone `KEEP` or `PULL` word, and
returns `decision_correct`, `score` (1 or 0), `core_abs_error_c` against the measured
value, the reported confidence and an `error_type` of `missed_pull`, `false_pull` or
`unparsed`. `evaluator.score_all` adds `primary_accuracy` over the 12 scored tasks,
`overall_accuracy`, `accuracy_by_design`, `edge_case_correct`,
`thermal_lag_traps_caught` out of `thermal_lag_traps_total`, counts of each error type and
`core_mae_c`. Answers that contain both words with no explicit `decision:` are unparsed and
score 0. No LLM grader. Chance level is 50 percent.

## Cheat risk, mitigations, residual risk

**Risk.** The workbook is public under CC BY 4.0. A model with the sheet in its training
data, or with tool access, could look up the rectal column for the matching subject and
minute and read the answer off the page instead of reasoning.

**Mitigations built into the public files.**

1. Elapsed time is shown on purpose. An earlier version re-zeroed the table to minutes
   0 to 24 to hide the protocol clock. That was dropped because a real medic knows how
   long the soldier has been working, and elapsed time is the strongest single predictor
   in this dataset. Hiding it would test a situation no human faces.
2. Values are rounded: heart rate, watts, humidity, age and mass to integers; skin and room
   temperature to one decimal. The sheet stores skin temperature at two decimals, so exact
   cell-value matching fails for most rows.
3. No subject number, person code, sex, height, VO2peak, visit or sheet reference appears
   in `public_tasks.json` or the prompts. Those live only in `private_ground_truth.json`.
4. No core temperature of any kind (rectal or vendor estimate) appears in public files, and
   the prompt says core is not measured.
5. The decision rule is defined in the prompt, so there is no hidden rubric to reverse
   engineer; only the hidden measurement.
6. The tests in `tests/test_keep_going.py` assert all of the above on the built files.

**Residual risk.**

- Heart-rate values are integers in the sheet, so a heart-rate block (five consecutive
  integers) plus the watts level is a near-unique fingerprint. A model that has memorised
  the workbook could match the pattern despite rounding. With 24 people and distinctive
  watt levels (for example 277, 215, 195) this is not a strong barrier.
- Watts are also unrounded integers in the sheet. Watts carry the protocol signal (the
  drop), so they cannot be jittered without changing the task.
- Showing real ride minutes makes lookup easier: a solver with the workbook only has to
  match the watts level and heart-rate block at a known minute. Rounding and the missing
  subject number remain the only barriers. This trade was chosen for realism.
- Twelve scored tasks is still a small sample. One answer moves accuracy by about 8
  points, and only three cases are thermal-lag traps. Run several samples per task and
  report the spread rather than a single accuracy.
- Memorisation can be checked directly: ask the model to name the dataset or the subject
  number before giving its answer. Any correct identification should void the run.
