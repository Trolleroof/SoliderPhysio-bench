# Three-task leaderboard: run guide and frozen protocol

The leaderboard ranks research models on three fixed measured-data tasks. It starts
empty after the user-requested result reset. All prior pilot score/judge artifacts
were deleted; no old rating, baseline loss or preferred-model prior is imported.
Original sources, splits, quality masks and data-exposure history are preserved.
Deleting results does not make inspected data untouched.

## Scope and reference data

| Task | Prepared data | People train/dev/test | Target and metric |
|---|---|---|---|
| pulse | `.leaderboard-data/pulse` | 13/5/5 | ECG-derived trailing 8-second HR; person/bout-balanced bpm MAE |
| heat | `.leaderboard-data/heat` | 14/5/5 | Rectal temperature +5/+10/+20 minutes; equal horizon/person °C MAE |
| load | `.leaderboard-data/load` | 28/10/10 | Gross indirect-calorimetry power; equal person MAE in watts |

Pulse source: [GalaxyPPG 1.0.0](https://zenodo.org/records/14635823), CC BY 4.0.
P01 lacks required Galaxy signals/events. The retained 23-person prepared data
include original source hashes, private audit, clock/detection rules and frozen
window exclusions. ECG detector labels remain **provisional**. This is declared on
the leaderboard; annotation/alignment review remains necessary for stronger claims.
The earlier dataset's `benchmark_ready: false` flag is preserved as that scientific
review status, separate from whether the engineering pipeline can rank models.

Heat source: [D'Lugos (2025), Figshare 29120024 v1](https://doi.org/10.6084/m9.figshare.29120024.v1),
CC BY 4.0. Original workbook MD5 `01214bfc835215fe1a5d3f5da1e9ad52`;
SHA-256 `499f546648822d99465c476702183cd3e37bdbaa6274de383f542708b052d531`.
Importer retains cell lineage and flags `Exercise Data!AK9 = 1176` as out-of-range HR.
No replacement value is guessed. Past HR/environment may carry forward only after
observation; interval labels become available at the right edge. YSI skin is the
explicit skin input. No rectal history, vendor core estimate, VO2 or future actual
measurements are given at inference. Common cutoffs 10–40 minutes retain all three
horizons only when targets exist: 740 eligible requests across 24 people.

Load source: [Mateos (2020), EVOBREATH 2015 v1](https://doi.org/10.17632/rhmdzmx6kk.1),
CC BY 4.0. Original XLS SHA-256
`51b42232fd63e15f2566f1d1053c92fe2de88477c3c4f14ce95fdc75784c58da`.
All 48 people remain. Three missing source 15 kg targets (BE0002, BE0058, BE0063)
are excluded before comparison, leaving 189 measured conditions. Numeric strings
are parsed; original cells are retained. Gross kcal/day equivalent rates convert
as `watts = kcal_per_day * 4184 / 86400`, without RMR subtraction. Inputs are
mass, height, age, carried load, fixed speed 4/3.6 m/s and zero grade. No unloaded
reference, RMR, other load targets or laboratory body-composition features enter
primary inference. Prediction at other speed/grade/terrain is outside the task.

Public training includes labels. Public development has requests only. Private
development labels and all test records stay outside the participant mount. Whole
people and all their sessions/devices/conditions stay in one split. The three
primary tracks do not use inference-time reference calibration. Alternate tiers
must receive a new version and pool.

## Setup and source preparation

Run at the repository root with Python 3.13 and Docker Desktop running:

```sh
uv venv --python 3.13 .venv-research
uv pip install --python .venv-research/bin/python -r research_env/requirements.lock -r research_env/requirements-import.txt
```

Existing prepared datasets need not be regenerated. For a new data build, use fresh
output paths; preparation refuses to overwrite data. Original heat/load source
files are retained at `/Users/nikhi/Documents/Army_Physiology_Research_20261017/evidence/heat/`
and the adjacent `load/` directory. They are the original XLSX/XLS, not synthetic
replacements. The original heat metadata and load protocol PDF remain there.

```sh
.venv-research/bin/python -m research_env fetch .research-data/galaxy
.venv-research/bin/python -m research_env prepare .research-data/galaxy NEW_DATA/pulse
.venv-research/bin/python -m research_env prepare /Users/nikhi/Documents/Army_Physiology_Research_20261017/evidence/heat NEW_DATA/heat --task heat
.venv-research/bin/python -m research_env prepare /Users/nikhi/Documents/Army_Physiology_Research_20261017/evidence/load NEW_DATA/load --task load
```

To use a supplied person partition, pass `--splits split.json`; it must cover the
entire audited cohort with disjoint nonempty train/development/test lists. Use the
retained pulse partition/mask for this pool rather than silently regenerating it.

Build/select the CPU image before the offline participant session:

```sh
docker build -t physiology-research:v1 -f research_env/Dockerfile research_env
docker image inspect physiology-research:v1 --format '{{.Id}}'
```

The locally verified image is
`sha256:7751f6262d2768889bebc8b567c771af0dae369db54ef79b208db155ebae9314`.
Use an immutable ID, never a mutable tag, for scored runs. The image contains the
pinned numerical stack. Spreadsheet readers are trusted preparation dependencies
and are not required by participant inference.

## Freeze a pool

```sh
.venv-research/bin/python -m research_env.leaderboard freeze .leaderboard-data .leaderboard-runs/frozen-suite.json --image sha256:7751f6262d2768889bebc8b567c771af0dae369db54ef79b208db155ebae9314
```

The current local suite is already frozen at that path. Do not overwrite it. It
binds complete data trees (including private reference masks/splits), task/scoring
and provider-harness code, task instructions, dependency files, conventional grid,
Docker image, actual CPU/memory allocation, budgets, seeds, and rating rules. The runner rejects a changed Docker allocation. Any change requires a new freeze
and pool. Freeze records contain private paths and are controller assets, not
participant prompts. `init`, `run_model`, `finalize`, and leaderboard building verify
the frozen identity. The outer split is explicitly agent development: these public
retrospective tasks are not claimed to be untouched final evidence of general
research capability. A later outer-final-evaluation release needs a new pool.

## Run models and conventional search

Copy `leaderboard/configs/model.example.json` to a new model config. Fill exact
provider/endpoint/model version and declared decoding/inference budgets; keep
configuration identical for that competitor across tasks/seeds. Templates use an
inert example domain. Supply credentials through an explicit environment variable;
keys are not discovered or logged. Setup has not called a paid model.

```sh
.venv-research/bin/python -m research_env.batch .leaderboard-runs/frozen-suite.json MODEL.json .leaderboard-runs/MODEL --key-env PHYSIOLOGY_MODEL_KEY
.venv-research/bin/python -m research_env.batch .leaderboard-runs/frozen-suite.json leaderboard/configs/conventional.json .leaderboard-runs/conventional --conventional
```

Each command runs all tasks at agent seeds **0,1,2**: nine attempts per competitor.
Research runs get two hours, 30 public development calls, up to eight CPU cores and
32 GiB, capped by the actual Docker allocation. Model inference time counts within
the two hours. Every config's token/call caps, model settings and usage are saved.
Seeds control provider sampling where supported and conventional fitting, not new
biological people. Models with incompatible provider parameters need a separately
versioned adapter; do not silently drop decoding settings.

Conventional search predeclares 30 candidates per task and uses the same command,
evaluation and wall budget. Heat includes elapsed-time, ridge, saturating thermal
features and compact boosting; load includes mean-by-load, mass/load ridge and a
compact forest; pulse uses median, spectral, motion and ridge. The simple thermal
reference is a feature model, not an established physiological simulator. No
published load-cost equation is included without verified applicability.

Workers are offline, CPU-only, with bounded CPU/memory/pids, read-only root,
dropped capabilities and no private mounts. Training sees only staged public
assets. Trusted replay copies only frozen artifact plus entrypoint, streams one
request at a time, and resets state between bouts/people. Model serialization is
loaded inside the worker. Full source workbooks/ECG/private labels never enter it.
Artifact hashes, experiment evidence, source snapshots, commands and stdout/stderr
are retained in each private ledger. Checkpoints freeze the incumbent at
15/30/60/120 minutes, without exposing private scores to participants. Final
feedback closes before private test replay; only the submitted candidate is scored.

A single task may be driven through the JSON-lines protocol:

```sh
.venv-research/bin/python -m research_env.leaderboard init .leaderboard-runs/frozen-suite.json heat MODEL.json .leaderboard-runs/MODEL/heat-seed-0 --seed 0
.venv-research/bin/python -m research_env agent .leaderboard-runs/MODEL/heat-seed-0/private .leaderboard-runs/MODEL/heat-seed-0/workspace .leaderboard-data/heat/private/development/manifest.json --image sha256:7751f6262d2768889bebc8b567c771af0dae369db54ef79b208db155ebae9314
.venv-research/bin/python -m research_env.leaderboard finalize .leaderboard-runs/frozen-suite.json .leaderboard-runs/MODEL/heat-seed-0
```

An interrupted/failed attempt must be retained. To record a failure explicitly:

```sh
.venv-research/bin/python -m research_env.leaderboard finalize .leaderboard-runs/frozen-suite.json RUN --failure 'No submission after provider failure'
```

No reinitialization to reset development/time budgets. Provider usage persists
across restarts. A sealed final replay cannot be rerun into the same receipt. If
harness infrastructure fails, record it, fix/version the harness, and use a new
pool rather than cherry-picking a silent retry.

## Transcript inspection

Exact model requests/responses, linked actions/tool results, timing, usage, terminal
status and source edits are saved in a separate private transcript. Finalization
automatically exports `transcript.jsonl`, `transcript.html` and `run-status.json`.
For a live snapshot use `python -m research_env.trace RUN`. See
[transcript format, limits and inspection](TRANSCRIPTS.md). The private transcript
never becomes participant history or blind judge context. Final receipts bind its
hash and terminal status; the leaderboard rejects changed exports.

## LLM judge

Fill `leaderboard/configs/judge.example.json` with one independent exact judge
model/version, endpoint, temperature and call/token limits. Use that same config
for the entire pool. Each decision gets an independent context with evidence
available before its action, excluding its outcome and later evidence. The final
selection packet includes only permitted public selection history. Packets omit
controller-added person identities and private test results. Embedded code/logs
are untrusted data. Five criteria use scores 1–5 or null when unobservable; no
automatic neutral grade. Hash, event, evidence IDs and exact schema are validated.

After finalization, judge one run:

```sh
.venv-research/bin/python -m research_env judge-run RUN/judge-packets.json JUDGE.json RUN/judge-output --key-env PHYSIOLOGY_JUDGE_KEY
```

The provider saves config, usage, attempts, verdicts and a coverage report. Failed
calls consume budget; at most two repairs per packet use the same evidence in
fresh contexts. Missing verdicts remain missing. To import externally collected
verdicts for inspection use `judge-import`; official board builds load validated
`RUN/judge-output/verdicts.json` and its explicit `config.json`.

Each criterion's mean and observable count are separate. The optional process
score averages observable decisions within each criterion, then criteria equally,
and maps 1–5 to 0–100. It is unavailable until packet/criterion coverage is complete.
No numerical prediction result is mixed into the process score. Human double-review
and repeated-judge disagreement audits are still required before claiming reliable
semantic grading; their absence does not stop reporting labeled LLM judgments.

## Build the leaderboard

```sh
.venv-research/bin/python -m research_env.leaderboard build .leaderboard-runs/frozen-suite.json leaderboard .leaderboard-runs/MODEL/*-seed-* .leaderboard-runs/conventional/*-seed-*
```

Pass run directories explicitly or use the shown zsh glob after they exist.
Building with no run directories creates the empty board. Accepted entries are
sealed final receipts from this suite. Every included competitor must have all
three tasks at all three seeds, including explicit failures. Duplicate, missing,
mixed-version or changed-setting attempts are rejected. All attempts/raw physical
metrics and failures are exported; means over valid runs are labeled with validity.

For each task, one match compares two competitors on the same full held-out cohort
and agent seed. Windows, horizons, conditions and checkpoints do not become Elo
matches. Accuracy compares primary MAE; uncertainty independently compares IS90.
A valid run beats an invalid run. Two invalid runs are skipped; zero-valid-run
competitors are unranked. Single-competitor pools await opponents. Tolerance 1e-9
draws; everyone starts at 1000, K=32, logistic scale=400. Competitors/seeds are
canonicalized, then the full round-robin is shuffled once with seed 0. Every
outcome/update is exported. Ratings depend on this opponent pool and schedule;
they are not comparable to deleted or different task pools.

The overall suite gives the three tasks equal votes on each matched agent seed,
rather than mixing °C, bpm and watts. A fully valid suite beats one with any invalid
task; two incomplete invalid suites are skipped. With both suites valid, each
task gives win=1/draw=0.5/loss=0; a mean above/below 0.5 wins/loses the suite match.
Uncertainty suite Elo repeats that process on interval scores. Judge panels remain
separate. Three agent seeds reuse the same small biological cohorts; no Elo
confidence interval or broad population ranking is claimed.

## Verification evidence

`tests/test_leaderboard.py` covers independently calculated units/aggregation/
intervals, causal future invariance, forbidden channels, train/dev privacy, export
replay, matched batches, setting/hash drift, failures and provider-budget handling.
`tests/test_research_env.py` covers shared worker/session/pulse/judge invariants.

Development-only Docker checks are runnable as:

```sh
.venv-research/bin/python scripts/check_leaderboard_tasks.py heat .leaderboard-data NEW_CHECK --image sha256:7751f6262d2768889bebc8b567c771af0dae369db54ef79b208db155ebae9314
```

Repeat with pulse/load and different output roots. These train an unchanged
reference predictor, replay every development request, select/submit, and export
blind judge packets. They never read private test scores or enter the leaderboard.
Fresh local check receipts are under `.leaderboard-checks/`; readiness is recorded
in `leaderboard/readiness.json`. Live model and semantic judge calls remain pending
until actual provider/model/budget configurations are supplied and invoked.
