# Physiology evaluation suite

Only these three confirmed new task types are active:

| Task | Model's job | Current state |
|---|---|---|
| [Keep going or pull him?](tasks/keep_going/README.md) | Forecast +15-minute core temperature and decide KEEP/PULL | 12 frozen cases, single-turn runner and deterministic grader |
| [Rulebook versus body](tasks/rulebook_vs_body/README.md) | Apply TB MED 507 and assess an individual override | 2 frozen cases, single-turn runner and deterministic grader |
| [Beat ECTemp](tasks/beat_ectemp/README.md) | Build a predictor using public training data and development scores | 2 research sessions, 7 per-person hidden cases |

The scored roster is `eval_suite/roster.json`; the 21 required cases and normalization
constants are frozen in `tasks/scoring_params.json`. KG-03 is excluded. Source data
are civilian chamber measurements, not validation of clinical or military decisions.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install openpyxl==3.1.5
python -m eval_suite list
python -m eval_suite preflight --backend local
# OPENROUTER_API_KEY must be set in the environment or repo-root .env.
python -m eval_suite run --model 6 --tasks all --spend-cap-usd 1.00 \
  --backend local --out .benchmark-runs/model-6
python -m tasks.judge .benchmark-runs/model-6/submissions.json --judge fake \
  --out .benchmark-runs/model-6/judged.json
python -m tasks.combined_score .benchmark-runs/model-6/judged.json \
  --params tasks/scoring_params.json --out .benchmark-runs/model-6/rating.json
python -m unittest discover -s tests
```

`--model` accepts a roster rank, APEX id or OpenRouter id; entries without a provider
id fail before inference. Every run requires a positive spend cap and an empty output
directory. Failed/unknown requests retain their conservative spend reservation. Settings,
prompt hashes, raw responses, finish reasons, usage and costs are retained in the controller transcript;
partial submissions and spend are saved on failure. Roster `max` effort maps to OpenRouter
`xhigh`, following the [OpenRouter effort vocabulary](https://openrouter.ai/docs/api_reference/parameters); both the requested roster effort and sent settings are recorded. Provider price ceilings match the frozen roster prices. The default output budget is 131,072 tokens including reasoning (4x the original 32,768, raised 2026-11-08 after rulebook answers were truncated), clamped per model to the provider's `max_output_tokens` in the roster (65,536 for Hy4 and Gemini 3.7 Flash; 128,000 for most others). Every request reserves its full output ceiling against the spend cap, so a single Fable 5 / GPT-6 Astra request reserves up to about $6.40: set caps accordingly.

Beat ECTemp gets up to 1200 wall seconds and 64 model turns **per variant**. Tools execute
commands on public data or return development metrics; hidden scoring happens only after
the artifact freezes. `--cases KG-01,RB-01,3A/H06 --research-seconds 240` selects a short,
incomplete smoke run. A selected Beat ECTemp person uses one variant session and emits
only that case; the existing hidden scorer still evaluates the whole variant.

The default worker is Docker and requires `--image <digest-pinned-installed-image>`.
Linux `--backend local` requires kernel Landlock ABI >=3 and system libseccomp; it blocks
network, repository/private reads and access to other processes. It fails closed when
those facilities are unavailable. macOS offers `--backend macos-development`. Both local
backends are development-only and mark `official: false`; Docker resource accounting is
required for official research runs. Interpreter/system library directories must contain
no private benchmark data. Preflight checks files, workbook checksum, loader availability
and the selected worker; it does not test credentials or provider model availability.

`submissions.json` is the judge input, with deterministic `grader` results and only
model-visible `materials`. Per-variant `grader.json` retains full hidden metrics and
`artifact/` plus `artifact_hashes.json` retain the submitted predictor. Controller and
private directories must never be shown to participants. Fake judging is an offline
integration test, not a calibrated evaluation. The judge's output does not carry runner
metadata: retain submissions alongside it when checking official status. A single model
or partial smoke cannot establish a matched comparative rating; supply complete judged
runs for at least two models. No full roster run is performed by these commands.

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
