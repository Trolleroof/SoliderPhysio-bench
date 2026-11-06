# Physiology research-agent leaderboard

Three CPU research tasks: **pulse estimation**, **core-temperature forecasting**, and
**load-carriage metabolic-cost modeling**. A model gets a public research workspace,
writes/trains predictors, evaluates on development data, and submits its selected
executable artifact. Private numerical replay determines accuracy and uncertainty
Elo. A separate blind LLM judge assesses the experiment decisions.

[Benchmark overview](docs/BENCHMARK_OVERVIEW.md) · [Current leaderboard](leaderboard/LEADERBOARD.md) · [Run guide and frozen rules](docs/LEADERBOARD.md) · [Transcript inspection](docs/TRANSCRIPTS.md)

The leaderboard starts empty. Prior pilot results, ratings, judge outputs and result
reports were deleted at user request; source data and audit provenance were preserved.
The deletion manifest is [RESULTS_RESET.json](docs/RESULTS_RESET.json).

| Task | Reference | Train / development / test people | Primary loss |
|---|---|---|---|
| Pulse | GalaxyPPG ECG-derived HR | 13 / 5 / 5 | Person/bout-balanced bpm MAE |
| Heat | CORE cycling measured rectal temperature | 14 / 5 / 5 | Equal-horizon/person °C MAE at +5/+10/+20 min |
| Load | EVOBREATH indirect calorimetry | 28 / 10 / 10 | Equal-person watt MAE across available recorded loads |

This is a retrospective leaderboard on fixed measured-data tasks. Pulse ECG labels
remain provisional and the leaderboard displays that fact. Heat is one cycling
protocol; load is level walking at one speed. Those boundaries do not prevent model
ranking, and rankings do not establish clinical or field performance. Deleting old
results does not make previously inspected data unexposed.

## Current eight-model comparison

The authorized run uses eight models across all three tasks and agent seeds 0, 1 and 2: **72 episodes, nine per model**. Each episode has two coding experiments, final artifact selection and a blind process review. Kimi K3 and DeepSeek V4 Flash use High effort; the other six use Medium. The shared $16 ledger includes compatibility probes, all participant calls, repairs and judging.

See the [eight-model protocol](docs/COMPACT_EIGHT_SWEEP.md) and [frozen plan](leaderboard/sweeps/compact-eight/plan.json). Live artifacts are in `.leaderboard-runs/compact-eight/`. Earlier pilot pools are retained separately.

## Run a fresh comparison

Use the local numerical environment and running Docker Desktop. The prepared data
are under `.leaderboard-data/`; original data remain under `.research-data/` and
external evidence paths documented in the run guide. Data and run artifacts are
ignored by Git. The existing numerical Docker image is selected by immutable ID.

```sh
.venv-research/bin/python -m research_env.leaderboard build .leaderboard-runs/frozen-suite.json leaderboard
```

That command renders the empty board. To run actual models, fill the explicit
provider/model/budget configuration and use the [batch commands](docs/LEADERBOARD.md).
The prepared [OpenRouter ten-model Medium-effort sweep](docs/OPENROUTER_SWEEP.md) includes exact configurations and a shared spend guard. No provider is auto-discovered and setup does not start paid inference. Each model
runs three agent seeds on every task. One missing/failed attempt must be recorded
explicitly. Separate task tables and an equal-task suite rating are generated.

## Checks

```sh
.venv-research/bin/python -m unittest discover -s tests -p test_research_env.py -v
.venv-research/bin/python -m unittest discover -s tests -p test_leaderboard.py -v
```

Legacy recovery examples remain in `benchmark/`, with their own source contracts.
They are outside this leaderboard. Their executor checks use the system interpreter
because that legacy sandbox does not permit virtualenv startup paths.
