# Task type 2: Rulebook versus body

One no-code task, two halves. The evaluated model is the medic advising a small-unit
leader. It is told the unit's WBGT flag and the work category on the leader's risk card,
and it sees the last 25 minutes of one soldier's wearable and chamber log (heart rate, skin
temperature, room temperature, humidity, pedal watts) plus his age and body mass. It never
sees core temperature. It must:

- **(a) Rulebook.** Reproduce the TB MED 507 (12 April 2022) prescription for that flag and
  work category: Table 1 work/rest minutes per hour and water intake, Table 2 continuous
  work limit and water intake. This half is deterministic and graded by exact match.
- **(b) Body.** Decide whether to **FOLLOW** that prescription for this soldier over the
  next 15 minutes or **OVERRIDE** it and pull him now, and estimate his rectal temperature
  15 minutes out. OVERRIDE is correct if and only if the measured rectal temperature at
  cutoff+15 is at or above 38.5 C. This half is graded exactly like Task Type 1.

The point of the pairing: the Army card is environment-driven and says nothing about the
individual. A medic who knows the card still has to look at the body in front of them.
A model can fail by not knowing the current card (the 2003 card had different cells), or
by trusting the card and a calm-looking wearable over a body that is already hot.

## Files

| File | Visibility | Contents |
|---|---|---|
| `tb_med_507.json` | reference | Both TB MED 507 tables, Heat Categories 1 to 5 (White, Green, Yellow, Red, Black) by work category, with source and notes. |
| `build_task.py` | builder | Reads the Figshare workbook through the Task Type 1 builder and writes the three files below. Deterministic. |
| `task.json` | public | Scenario inputs, subject age and mass, the 25 rounded re-zeroed rows, full prompt text, answer format. |
| `prompt.md` | public | The same prompt as rendered markdown. |
| `private_ground_truth.json` | private | Original subject number, protocol cutoff minute, measured rectal at cutoff and cutoff+15, expected decision, expected rulebook cells, vendor-sensor estimate for failure analysis. |
| `evaluator.py` | private | Table lookup, answer parsing, grading, prompt rendering, CLI. |

Rebuild (needs `openpyxl`, present in `.venv-research`; the workbook checksum is enforced
by the Task Type 1 loader):

```sh
.venv-research/bin/python -m tasks.rulebook_vs_body.build_task
```

Print the prompt (closed-book by default; `--with-table` appends both tables for an
open-book variant that isolates the body half):

```sh
.venv-research/bin/python tasks/rulebook_vs_body/evaluator.py --print-prompt
.venv-research/bin/python tasks/rulebook_vs_body/evaluator.py --print-prompt --with-table
```

Grade a raw model reply saved to a file (exit code 0 on pass, 1 otherwise):

```sh
.venv-research/bin/python tasks/rulebook_vs_body/evaluator.py --response reply.txt --out score.json
```

Tests:

```sh
.venv-research/bin/python -m unittest tests/test_rulebook_vs_body.py -v
```

## Rulebook source

`tb_med_507.json` encodes TB MED 507, *Heat Stress Control and Heat Casualty Management*,
12 April 2022, as reproduced on the Defense Centers for Public Health (Aberdeen) cards
*Fluid Replacement & Work-Rest Guidelines to Prevent Heat Illness* (TA-724-MAR23) and
*Heat Illness Prevention Guide* (TA-010-MAR23), both at ph.health.mil. Values were
transcribed on 2026-11-06 from the PDF text layer.

The 2022 edition has four work columns: Easy, Moderate, Heavy and Very Heavy. The 2003
edition had three (Easy, Moderate, Hard). The evaluator accepts `Hard` as an alias for
`Heavy`, so lookups phrased in the older vocabulary still resolve. Several cells changed
between editions; the one this task uses, Moderate work at Yellow flag, was 40/20 on the
2003 card and is NL (no limit) on the 2022 card. A model that recites the old card fails
the rulebook half on that cell.

Two tables are stored. Table 1 (work/rest per hour plus water, training up to 4 continuous
hours) is what the decision in part (b) refers to. Table 2 (continuous work duration plus
water, operations that may exceed 4 hours) is asked for as well so the lookup is not a
single cell.

## Data source and trace format

`sources/figshare-heat/core_cycling_2025.xlsx`: D'Lugos (2025), Figshare 29120024 v1,
CC BY 4.0. 24 people cycled about 60 minutes in a 35 to 37 C chamber with a rectal probe
sampled every minute. The trace is produced by `tasks.keep_going.build_tasks.make_window`,
so the de-identified format is identical to Task Type 1: 25 rows ending at the cutoff,
timestamps re-zeroed to 0..24, heart rate / watts / humidity / age / mass rounded to
integers, skin and room temperature to one decimal, room conditions carried forward only
after they were observed, heart rate blank outside the logged blocks. No core temperature
of any kind, no subject number, no sex, no height, no VO2peak.

The flag and work category are scenario inputs for the rulebook half. They are not derived
from the chamber: 35 C at about 20 percent humidity is below Heat Category 1 on the WBGT
scale, and no cell of the card applies to it. Moderate work at Yellow flag was chosen
because it is a no-limit cell in both tables, so the prescription does not depend on how
long the soldier has already been working and the protocol clock can stay hidden, as in
Task Type 1.

## The case

| Task | Design | Power in window | Heart rate in window | Measured rectal: cutoff to cutoff+15 | Expected |
|---|---|---|---|---|---|
| RB-01 | steady power, quiet wearable, hot core | 195 W flat | 149 to 159 bpm | 38.40 to 38.92 C | OVERRIDE |

The person is not used by Task Type 1 (which uses subjects 3, 4, 21 and 23). He is a
59 kg rider holding 195 W, about 3.3 W/kg, in a 35 to 36 C room. Heart rate drifts only
from the high 140s to the high 150s and power never changes, so nothing in the wearable
looks alarming and the card says no limit. What an expert can read: skin temperature sits
at 36.5 to 36.7 C, within about two degrees of a normal core, which means the skin-to-core
gradient that carries heat out of the body has nearly closed, and 3.3 W/kg in that room
is a large metabolic heat load for a small rider. The measured rectal temperature is
already 38.40 C at the cutoff and reaches 38.92 C fifteen minutes later, 0.42 C above the
threshold. The vendor CORE sensor estimate at the same two minutes reads 38.54 C and
38.62 C, so even the fielded wearable estimator under-reads the rise by 0.30 C.

A model that follows the card here makes the `missed_override` error. A model that
overrides but says the card is 40/20 makes the rulebook error. Both are reported
separately.

## Scoring

`evaluator.grade(text)` parses the first JSON object in the reply (code fences and prose
tolerated) and returns:

- `rulebook`: the four expected cells, the parsed cells, per-field matches, `score`
  (fraction of the four fields right) and `pass` (all four). Parsing accepts `NL`, `null`,
  `no limit`; `40/20`, `40:20`, `40 min work / 20 min rest`, or `{"work_min": 40,
  "rest_min": 20}`; water as `0.75`, `3/4`, `¾`, `1¼` or `1 1/2 qt/hr`. A missing key is
  not read as no-limit.
- `body`: `expected_decision`, `model_decision`, `decision_correct`, `score` (1 or 0),
  `core_abs_error_c` against the measured value, `core_within_tolerance` (0.5 C) and an
  `error_type` of `missed_override`, `false_override` or `unparsed`. This mirrors
  `tasks.keep_going.evaluator.grade`: the decision is the score, the temperature estimate
  is a reported secondary.
- `total` = 0.5 × rulebook score + 0.5 × body score; `pass` needs both halves to pass.

No LLM grader. The decision rule and the threshold are stated in the prompt, so the only
hidden quantity is the measurement.

## Cheat risk: low

**What a cheater would need.** The body half can only be short-cut by reading the rectal
column for the right person and minute out of the public workbook. The rulebook half can
only be short-cut by having the 2022 card, which is the thing being tested; a model that
has it is not cheating.

**Why the body half is hard to look up.**

1. Timestamps are re-zeroed. The prompt shows minutes 0 to 24; the protocol minute of the
   cutoff (44) appears nowhere public.
2. Values are rounded. Skin temperature is stored to two decimals in the sheet and shown to
   one, so cell-value matching fails for most rows.
3. No subject number, person code, sex, height, VO2peak or sheet reference appears in
   `task.json` or `prompt.md`. Those live only in `private_ground_truth.json`.
4. No core temperature of any kind (rectal or vendor estimate) appears in public files, and
   the prompt says core is not measured.
5. The tests assert all of the above on the built files and that the subject is not one
   used by Task Type 1.

**Residual risk.** Heart rate and watts are unrounded integers in the sheet, so the logged
heart-rate block plus the 195 W level is a near-unique fingerprint for a model that has
memorised the workbook. That is the same residual risk documented for Task Type 1 and is
checked the same way: ask the model to name the dataset or subject before answering, and
void any run that identifies either. With one task, treat the result as a qualitative read
on the two failure modes, not an accuracy estimate.
