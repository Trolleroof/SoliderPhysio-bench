# Cheapest-model preflight — 2026-11-06

The live OpenRouter roster/catalog check selected DeepSeek V4 Flash as the
cheapest roster model. The smoke retained the configured Parasail FP8 route,
High effort, seed 0, two experiments, and the existing output limits. It used a
fresh suite freeze and a persistent $1 shared ledger, separate from old sweeps.
No full sweep or leaderboard publication was started.

## Flaws reproduced and fixed

- The experiment tool schema required only `reason`, while runtime validation
  required `code`. The first live attempt returned reason-only actions twice.
  Training now requires code; final selection requires a valid candidate index.
  Each phase exposes only its applicable fields.
- The compact observation discarded command stdout. Inspection-only experiments
  consequently gave the next call no inspection results. Bounded public stdout
  is now persisted and supplied with development feedback. Feedback remains
  within the existing 4,096-byte request ceiling.
- The prompt supplied file paths without the training manifest structure.
  It now includes a short public schema and explicitly says each experiment
  must train and save an artifact. These changes apply to all participants.

Every source change used a fresh freeze and separate attempt directory. Failed
attempts and API charges were retained. Existing sweep configs and sealed
receipts were preserved; they cannot be resumed under the changed code freeze.

## Live model outcome

On the final patched freeze, DeepSeek produced executable inspection code on
both experiments for each of load, heat and pulse. None saved an artifact:
**0/3 valid episodes**. All three failure receipts and blind reviews were saved.
The final attempts did not exhibit output truncation: reported completion token
counts stayed below 1,536 and responses finished with tool calls.

This is a failure under the compact protocol, not a measured prediction loss.
Hidden prediction replay could not run without an artifact. Repeatedly coaching
this model until it passes would not establish matched-roster readiness.

## Verification and controls

The full research-harness test set passed: **69 tests** across research environment,
leaderboard, transcript, OpenRouter, native actions, compact, accounting and
parallel orchestration modules. Legacy benchmark tests were outside this change.

A separate scripted reference control exercises the exact episode runner with
supplied baseline training code, two development evaluations, final selection,
sealed hidden replay and the configured independent live reviewer. It is labeled
as scripted and is not a DeepSeek completion or leaderboard entrant.

All three reference controls passed development evaluation, submission, sealed
hidden replay and live review: **3/3 valid controls**, versus **0/3 valid DeepSeek
episodes** on the final patched freeze. Pulse required 99 fresh development
bout workers per evaluation and 100 test workers, accounting for its longer
runtime. Its full cohort was retained.

Final shared spend readback: **$0.01940818 across 21 API requests**, no unresolved
cost reservations, **$0.98059182 remaining** under the enforced $1 cap. This
includes original/intermediate failures, final model attempts and live control
reviews. The scripted training/selection actions did not incur participant API
charges. All smoke processes exited and their worker containers were cleaned up.

Local evidence is under `.leaderboard-checks/deepseek-smoke-20261106/`:

- `before/`: original schema failure.
- `after-schema/`, `after-feedback/`: intermediate diagnostic attempts.
- `after-contract/`: final patched model attempts and suite freeze.
- `reference-control/`: independent pipeline controls.
- `spend.sqlite`: enforced shared $1 ledger across attempts and controls.
- `tests.log`: complete test output.
- `models-current.json`, `deepseek-endpoints-current.json`: public price evidence.

The data, traces, receipts and spend ledger are local ignored assets. A fresh full
sweep should wait for a participant smoke that produces a valid submission; the
scripted controls alone do not establish that the roster can complete the task.
