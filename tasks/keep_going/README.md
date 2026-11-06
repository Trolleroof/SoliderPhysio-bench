# Task type 1: Keep going or pull him?

No-code decision tasks. The evaluated model sees the last 25 minutes of one person's
wearable and chamber log (heart rate, skin temperature, room temperature, humidity, pedal
watts) plus age and body mass. It never sees core temperature. It must decide whether to
**PULL** the person now because their core temperature 15 minutes later would be at or
above 38.5 C, or **KEEP** them going.

The hard part is thermal lag: when someone slows down (watts drop), core temperature keeps
rising for many minutes. A medic knows this. Models that treat falling power as "he is
cooling off now" miss the pull.

## Files

| File | Visibility | Contents |
|---|---|---|
| `build_tasks.py` | builder | Reads the Figshare workbook, writes everything below. Deterministic. |
| `public_tasks.json` | public | Task ids, rounded/re-zeroed rows, subject age and mass, full prompt text, answer format. |
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

Three scored tasks plus one edge case. Public ids carry no hint of the design.

| Task | Design | Power in window | Measured core: cutoff to cutoff+15 | Expected |
|---|---|---|---|---|
| KG-01 | steady power, safe | 140 W flat | 38.02 to 38.24 C | KEEP |
| KG-02 | falling power, thermal-lag trap | 215 W, cut to 180 W five minutes before cutoff | 38.30 to 38.88 C | PULL |
| KG-03 | falling power, core actually fell (edge case) | 205 W, cut to 188 W three minutes before cutoff | 38.90 to 38.14 C | KEEP |
| KG-04 | steady power, rising | 123 W flat, heart rate drifting up | 38.68 to 39.14 C | PULL |

The decision rule is mechanical: `PULL` when the measured rectal temperature at
cutoff+15 is at or above 38.5 C, else `KEEP`. The private file stores the exact values.

**KG-02** is the thermal-lag trap. In the workbook, power fell in 148 windows across 14
people and core kept rising over the next 15 minutes in 97 percent of them. This person is
typical: watts drop, skin temperature drifts down (less heat delivered to the skin as pace
falls), and core climbs another 0.58 C. A model that reads the slowdown as relief says KEEP
and is wrong.

**KG-03** is the only falling-power person in the workbook whose core actually fell. It is
labelled `edge_case` and reported separately by the evaluator (`edge_case_correct`) rather
than folded into `primary_accuracy`. Label caveat: core peaks at 39.06 C six minutes after
the cutoff, then drops 1.7 C over the last five recorded minutes, including a one-minute
drop of about 1 C at minute 60. A rectal probe does not do that physiologically, so the
late readings look like probe displacement. The +15 value (38.14 C) is still the measured
label, but treat this task as a calibration probe: a model that says PULL here with high
confidence is making the same call a sensible medic would make with this evidence.

**KG-01 and KG-04** are the steady-power controls. They separate "does the model react to
the power drop" from "does the model just always pull". KG-04 shows classic cardiovascular
drift (heart rate from about 158 to 171 bpm at constant watts) and is a clear PULL; KG-01
is a lighter rider holding 140 W with a flat heart rate and stays under threshold.

## Scoring

`evaluator.grade(task_id, text)` parses the first JSON object in the answer (code fences
and surrounding prose tolerated), falls back to a standalone `KEEP` or `PULL` word, and
returns `decision_correct`, `score` (1 or 0), `core_abs_error_c` against the measured
value, the reported confidence and an `error_type` of `missed_pull`, `false_pull` or
`unparsed`. `evaluator.score_all` adds `primary_accuracy` (KG-01, KG-02, KG-04),
`overall_accuracy`, `edge_case_correct`, `thermal_lag_trap_caught`, counts of each error
type and `core_mae_c`. Answers that contain both words with no explicit `decision:` are
unparsed and score 0. No LLM grader.

## Cheat risk, mitigations, residual risk

**Risk.** The workbook is public under CC BY 4.0. A model with the sheet in its training
data, or with tool access, could look up the rectal column for the matching subject and
minute and read the answer off the page instead of reasoning.

**Mitigations built into the public files.**

1. Timestamps are re-zeroed. The prompt shows minutes 0 to 24; the real protocol minute of
   the cutoff (30 or 44 here) never appears, and the window start varies by case.
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
  watt levels (215, 140, 205, 123) this is not a strong barrier.
- Watts are also unrounded integers in the sheet. Watts carry the protocol signal (the
  drop), so they cannot be jittered without changing the task.
- The window length is fixed at 25 rows, which lets a solver recover the window start once
  it has matched the heart-rate block.
- Four tasks is a small sample. Treat the result as a qualitative read on the thermal-lag
  failure, not a statistically tight accuracy.
- Memorisation can be checked directly: ask the model to name the dataset or the subject
  number before giving its answer. Any correct identification should void the run.
