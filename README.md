# Physiology evaluation suite

Only these three confirmed new task types are active:

| Task | Model's job | Current state |
|---|---|---|
| [Keep going or pull him?](tasks/keep-going-or-pull-him/SPEC.md) | Forecast +15-minute core temperature and provide a rubric-based decision | Specification only |
| [Rulebook versus body](tasks/rulebook-versus-body/SPEC.md) | Apply TB MED 507 and assess a justified individual override | Specification only |
| [Beat ECTemp](tasks/beat-ectemp/SPEC.md) | Build and verify a predictor against ECTemp on frozen measured slices | Specification only |

The design contains three task types (the prior proposal suggested 3 + 1 + 2
cases). These definitions are preserved. Their implementations and validated
graders are not present in this checkout yet. **No new-task model run has finished.**

```sh
python -m eval_suite list
python -m eval_suite preflight
python -m unittest discover -s tests -v
```

Preflight exits with status 2 and lists missing implementation/grading work.
`python -m eval_suite run TASK_ID` stops before any model request. There is no
default task, legacy adapter, model configuration or provider fallback.

## Legacy tasks removed

The pulse-estimation, generic heat-forecasting, load-regression and earlier
recovery task implementations, launch scripts, sweep plans and active
leaderboard were deleted. Importing `research_env` or `benchmark`, including
historical module commands, stops with a removal error. Git history retains the
old source; it is not an alternative active suite.

Raw datasets and historical run evidence are preserved in their existing local
data directories. Task-independent hashing, transcripts, spending controls and
the offline worker were retained under `eval_suite/core/`. Historical reports
are in [docs/history](docs/history); their results do not validate the new tasks.
[Removal record](docs/LEGACY_REMOVAL.json).
