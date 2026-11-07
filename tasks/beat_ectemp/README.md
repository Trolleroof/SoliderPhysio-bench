# Beat ECTemp: Task Type 3

Two causal code tasks, with one `submission.py` exposing `predict(request)`:

- **3A:** At every minute from the first observed watts decrease onward, forecast rectal core temperature 15 minutes later and a 90% prediction interval. Only origins with an observed target 15 minutes later are scored.
- **3B:** Estimate current core temperature and a 90% interval online, from the available history. Each call receives a prefix, never future measurements.

Return `{"mean": 38.0, "lower": 37.5, "upper": 38.5}`. Requests contain `task`, `horizon_min`, and `history`. History fields: `time_min`, `hr`, `skin_temp`, `watts`, `ambient_temp`, `humidity`, `age`, `mass`, `height`. Units are minutes, bpm, Celsius, watts, Celsius, percent, years, kg, cm. Missing inputs are null. Predict must be stateless across calls; use the supplied history.

`ectemp_baseline.py` is a transparent ECTemp-style sequential comparator combining HR, skin temperature and watts. It is **not a reproduction or validation of the published ECTemp algorithm**. Its initial core estimate is 37 C; its +15-minute forecast extrapolates the final filtered slope. The template delegates to this baseline.

## Organizer setup

Run from repository root, using the research Python environment (openpyxl required):

```sh
.venv-research/bin/python tasks/beat_ectemp/benchmark.py build \
  --workbook sources/figshare-heat/core_cycling_2025.xlsx \
  --public /path/to/participant --private /path/to/private
```

Destinations must be separate; public must be empty. (If `--splits` is passed, it is verified against the frozen split.) The participant folder contains only labeled train data, label-free dev requests, baseline, and template. Copy template.py to submission.py and implement predict. Never give participants access to this source repository, original workbook, private directory, organizer shell, or scorer process. Use a separate account/container to expose the public folder and a scoring endpoint; the command below is the organizer-side entrypoint behind that endpoint. A folder layout alone does not isolate a participant with unrestricted organizer shell access.

```sh
.venv-research/bin/python tasks/beat_ectemp/benchmark.py score \
  --public /path/to/participant --private /path/to/private --task 3A
# Organizer-only final evaluation:
.venv-research/bin/python tasks/beat_ectemp/benchmark.py score \
  --public /path/to/participant --private /path/to/private --task 3A --hidden
```

The runner requires macOS sandbox-exec and fails closed elsewhere. It denies network, private-label reads and filesystem writes, limits CPU to 1200 seconds, and adds a 1200-second wall timeout. Runtime system directories and Python environments must contain no benchmark labels. Run evaluations serially. Each predict invocation sees only its causal request; no labels are sent over stdin. The scorer retains labels in its own process. Test requests are never exported to the public folder.

## Data contract

Frozen split (checked against the specified JSON):

- Train: H01 H19 H07 H05 H14 H23 H16 H04 H09 H03 H02 H15 H10 H12
- Dev: H21 H24 H08 H17 H20
- Test: H25 H22 H13 H06 H18

Rectal temperature is the target, YSI is skin temperature. Exercise HR and Wattage blocks provide body and load inputs. Demographics supply age, mass, height. Workbook MD5 `01214bfc835215fe1a5d3f5da1e9ad52` is verified before loading. Time ranges such as 5–6 map to minute 6. Heart rate outside 30 to 240 bpm (three four-digit typo cells: 1176, 1556 and 1152 bpm) is omitted before carry-forward. Sparse inputs use latest observation carried forward; before first observation they remain null. Labels are never imputed. The CORE wearable temperature block is deliberately excluded to avoid target leakage.

## Scoring and cheat blocks

Public scoring uses all eligible dev targets. Hidden primary MAE uses **every request with a strictly lower observed wattage at or before the prediction origin** (all requests after the first watts drop; the gate stays active). Missing watts do not create a drop. Results include `person_mae` (MAE per test person over these requests), which `tasks/combined_score.py` scores as one case per person. True core temperature >=38.5 C (for 3A, at the forecast target) is reported as a separate slice: `hot_mae`, `hot_person_balanced_mae`, `hot_count`. In the frozen test split only H06 and H13 have a watts drop. No eligible hidden minutes yields a null MAE and zero score. Score is `1/(1+primary_mae)`; overall MAE, interval coverage, and the proper 90% interval score (width plus 20 times each missed tail) are reported separately.

1. Dev-label training: dev labels exist only outside the participant folder, and submission sandbox reads are denied.
2. Clock shortcut: hidden requests add an independent random integer offset per person to all time_min values, preserving relative spacing. This defeats absolute-clock lookup; it does not eliminate shortcuts based on elapsed duration or history length.
3. Hardcoded test answers: all five test people and their requests remain private until sandboxed final inference; IDs are omitted from inference requests.
4. Garbage intervals: missing fields, nonnumeric/bool values, NaN/inf, unordered bounds, zero widths or widths above 5 C invalidate the entire evaluation and score zero. Runtime/JSON failures also score zero.
5. Public scorer spam: allowed. Every attempt is appended to organizer-only calls.jsonl before execution, including failures. Results report cumulative public_call_count. Hidden results report public_to_hidden_gap = hidden primary MAE minus latest public overall MAE for the same task (null if unavailable). Lower is better for all MAE/interval metrics.

Tests include real workbook export, causal request boundaries, all five cheat blocks, persistent post-drop gate, separately reported inclusive hot slice, per-person MAE, baseline clock invariance/body sensitivity, and a real sandbox label/network denial probe.

```sh
.venv-research/bin/python -m unittest tests/test_beat_ectemp.py -v
```
