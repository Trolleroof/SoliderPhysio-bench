# DeepSeek interactive evaluation pilot

This development pilot uses DeepSeek V4 Flash High on the existing Parasail FP8
route. It uses the full interactive research runner, not the two-execution compact
protocol. The model can inspect public data, write and run training programs,
request development evaluations and submit its own selected frozen artifact.

Participant settings are in `leaderboard/pilots/deepseek-interactive/participant.json`:
32 calls per task, 8,192 response tokens including reasoning, one million total
tokens, seed 0 by default, and the existing two-hour/30-development-call CPU
environment. Whole-person splits, private mounts, causal requests and numerical
scoring are unchanged. These settings define a separate diagnostic pool; old
compact results are preserved and are not interchangeable with this pilot.

`conversation_mode: tools` retains the participant's own assistant tool calls
(including code edits and provider reasoning blocks) and returns actual public
controller events as matching tool results. Snapshot mode omitted edit contents,
causing repeated reads/rewrites in the earlier pilot. The durable conversation is
separate from the private diagnostic transcript, binds the configuration and
already-observed public ledger, and never imports hidden numerical results.
Reasoning blocks are passed back as described in the
[OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Submission phase

The pilot first asks the model to fit and evaluate a documented reference
(load ridge, heat elapsed, pulse ridge), then improve it using public development
feedback. If no development evaluation has occurred after 24 paid calls, a
native evaluate-only phase requires an actual evaluation. A failed result
reopens research for repairs; this gate never trains or substitutes an artifact.
It prevents the observed heat failure where the first valid evaluation happened
on the final available call, leaving no opportunity for submission.

The initial interactive attempt produced a valid load predictor but spent all
32 calls without submitting it. A soft budget reminder did not prevent further
code edits. The runner now enters a submission phase when at most four calls
remain, or its existing token-budget warning activates, **if a valid development
candidate exists**. The model receives the public candidate IDs/losses and a
submit-only tool schema. Non-submission actions are rejected without execution.
The model must still choose the candidate, supply evidence and submit it; the
controller never selects a fallback artifact. With no valid evaluated artifact,
the runner cannot manufacture success.

## Run and resume

Supply the OpenRouter credential through the existing environment or `--env-file`.
The command makes paid calls under the persistent shared cap:

```sh
.venv-research/bin/python -m scripts.run_research_pilot \
  .leaderboard-checks/deepseek-interactive-20261106/v5-pulse \
  --tasks pulse \
  --spend-path .leaderboard-checks/deepseek-interactive-20261106/spend.sqlite
```

The runner freezes a fresh suite when needed, binds settings and seed, takes an
exclusive output lock, preserves failures/spending, and skips sealed completed
attempts on resume. Source changes require a new output/freeze; reuse the spend
path to keep failed diagnostic charges inside the same $1 cap. It does not
publish a leaderboard. `pilot-status.json` records completion/review status and
the live spend readback.

The independent GPT-6.1 Sol Medium reviewer uses the standard research rubric
(1–5), the actual final-selection packet and all its preceding public evidence.
This avoids the compact reviewer's 3,072-byte limit. Review coverage is explicitly
one final-selection packet per task, not every intermediate decision. Hidden
outcomes never enter that packet; sealed packet and trajectory hashes are
verified before any review call. Cached validated reviews do not trigger another
paid request.

## Evidence boundaries

Use only training/public development evidence for repairs and model selection.
Hidden numerical replay occurs after final submission and is reported separately
from process judgments. These retrospective cohorts have prior operator exposure;
a repaired pilot is development evidence, not a new untouched final test.

The original compact failures are under
`.leaderboard-checks/deepseek-smoke-20261106/`; the first interactive failure and
its charges are under `.leaderboard-checks/deepseek-interactive-20261106/`.
The snapshot-mode `v2/` attempts finished with no submissions on all three tasks.
The conversation-mode `v3/` load attempt completed submission, hidden replay and
independent review, with development MAE 35.81 W (reference ridge: 32.16 W).
Its heat predictor passed development evaluation on its last call, then failed
for lack of a submission call. Its long pulse fitting command was explicitly
interrupted to apply the early-evaluation fix; its partial trace and charges are
preserved as an interrupted diagnostic, not a scored prediction attempt.
The baseline-first/early-evaluation rerun is in `v4/`.

`v4/` load and heat completed submission, replay and independent review. Pulse
spent 12 calls discovering the data/helper interface, then rejected the forced
evaluation phase and exhausted its protocol repairs. The pulse task now includes
an executable baseline CLI example, consistent with the heat/load task guides.
The current pilot configuration permits 24 calls before forcing the first
evaluation, leaving eight calls for correction/submission. `v5-pulse/` tests this
repair on pulse alone; task lists are explicitly bound into pilot identity so
partial diagnostics cannot be mistaken for a full suite. It is a separate freeze
and does not silently replace or merge previous receipts.

Pulse in `v5-pulse/` completed submission, full hidden replay and independent
review. Together with `v4/` load and heat, all three task paths are now verified.
See [final metrics, controls, costs and scope](DEEPSEEK_PILOT_RESULTS.md).
