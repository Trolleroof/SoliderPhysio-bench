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
  .leaderboard-checks/deepseek-interactive-20261106/v3 \
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
The conversation-mode rerun is in `v3/`; its outcome remains pending until sealed
receipts and independent reviews exist.
