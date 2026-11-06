# OpenRouter ten-model sweep

The canonical prepared roster is `leaderboard/sweeps/openrouter-frontier-10-tools/manifest.json`.
It follows the first ten rows of the user's reference screenshot. All ten participants
and the independent judge use **Medium effort**. External APEX percentages are not
benchmark results here. Exact provider routes, model IDs, prices, config hashes and
catalog metadata are saved alongside the manifest.

| Participant | Exact OpenRouter ID | Provider route | Effort |
|---|---|---|---|
| Gemini 4 Argon | google/gemini-4-argon | Google AI Studio | Medium |
| Claude Sonnet 5.5 | anthropic/claude-sonnet-5.5 | Anthropic | Medium |
| Claude Opus 5.5 | anthropic/claude-opus-5.5 | Anthropic | Medium |
| Claude Fable 5.1 | anthropic/claude-fable-5.1 | Anthropic | Medium |
| Gemini 3.7 Flash | google/gemini-3.7-flash | Google AI Studio | Medium |
| Claude Opus 5 | anthropic/claude-opus-5 | Anthropic | Medium |
| Grok 4.6 | x-ai/grok-4.6 | xAI | Medium |
| GPT-6 Astra | openai/gpt-6-astra | OpenAI | Medium |
| Gemini 3.8 Flash | google/gemini-3.8-flash | Google AI Studio | Medium |
| Claude Fable 5 | anthropic/claude-fable-5 | Anthropic | Medium |


The judge is `openai/gpt-6.1-sol`, Medium, outside the participant roster. Numerical
prediction scoring and blind-packet reasoning review remain separate.

## Native action protocol

The initial live JSON-text pilot exposed transport failures: a single malformed
reply ended otherwise usable research attempts. The repaired pool uses a native
`take_action` function with the same edit/command/evaluate/select/submit operations.
All models receive the same schema and `tool_choice: auto`. The system requests
exactly one call; missing, multiple, wrong-name or malformed calls execute nothing.
A public protocol error is returned, preserving prior artifacts and development
results. Three consecutive malformed replies end the attempt. This limit persists
across interruption/resume, and every reply consumes the normal call/token/spend
budgets. A valid action resets the consecutive error count.

Auto tool choice preserves compatibility with thinking-enabled Claude models;
forced named/required calls are rejected by some selected endpoints. See the
[OpenRouter tool documentation](https://openrouter.ai/docs/guides/features/tool-calling)
and [Claude migration guidance](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/model-migrations/claude-5-5).

Every observation includes remaining inference calls and tokens, plus a near-limit
submission instruction. The controller remains isolated from host credentials and
private test labels. Exact requests, native tool calls, responses, usage, faults
and action/result correlations are saved in the private transcript.

## Frozen comparison

The target remains **90 attempts**: ten models, all three tasks, repeats 0/1/2,
followed by independent judging. Each attempt has two hours, 30 development
evaluations, 150 inference calls, 2,000,000 total tokens and a 64,000-token response
ceiling including reasoning. Configured request socket timeouts are at most 600
seconds and capped by remaining wall time. Provider pins, no fallback, parameter
requirements and price ceilings are explicit. No temperature is forced; Claude
omits unsupported provider seeds, while repeat identities remain recorded.

CPU training/replay uses the pinned local Docker image with the frozen eight-core
maximum and available Docker memory. OpenRouter hosts inference. No RunPod GPU
rental was started. Repeats are agent trials over fixed held-out biological cohorts.
Pulse ECG references remain provisional; Heat and Load use retrospective measured
references. This protocol is our own comparison, not APEX's original harness.

## Verified status and pilot separation

- 55 focused harness, sweep, logging, scoring and recovery tests pass.
- All ten live native-tool compatibility probes passed at Medium effort.
- Those diagnostics use 512 output tokens for OpenAI and 1,025 for the others;
  they use no benchmark data and execute no actions. They prove native routing
  and parsing, not completed research attempts or full 64,000-token preflight.
- The native pool has **zero official attempts**. Its full-config preflight and
  90-run comparison are pending a higher authorized budget.
- Prior JSON pilot traces and receipts remain in
  `.leaderboard-runs/openrouter-frontier-10-v2/`, with their original frozen suite.
  They are excluded from the repaired comparison. Their numerical and judge
  coverage is reported separately in `leaderboard/SWEEP_PROGRESS.md`.
- Elo is withheld for incomplete matched batches. Paused attempts remain unsealed;
  they are never turned into fabricated model failures or successful submissions.

Native diagnostic evidence is under `.leaderboard-checks/openrouter-native-probes/`.
The current suite, code/data fingerprints, resource allocation and empty official
board are frozen under `.leaderboard-runs/frozen-suite.json` and `leaderboard/`.

## Spending constraint

The user authorized **$10 total**, covering probes, interrupted attempts,
participants and judging. All pools share the original persistent SQLite ledger.
Unknown/canceled-request cost retains its conservative reservation. Native
compatibility diagnostics also count toward the same cap. No increase is authorized.
The final accounting snapshot and remaining coverage are in the completion audit.

`cost-scenarios.json` contains arithmetic examples for the 90 participant attempts:
250k input + 50k output per attempt totals about **$207.45**; 1M input + 200k output
about **$829.80**. They are illustrative token scenarios, not forecasts. Judging and
probes add cost. The full comparison cannot be represented as complete within the
current cap. Funding approval is required before continuing paid benchmark work.

Reservations use conservative input/output ceilings before network requests.
Provider-reported usage releases unused reservations; missing cost retains the
ceiling. `max_price` limits upstream token prices. The manifest's approved cap is
also checked before network access. New output folders must share the existing
ledger; replacing it would discard already-accounted charges.

## Prepared invocation

After a higher cap is explicitly authorized and recorded in both the plan and
persistent ledger, use the authorized cap in this command:

```sh
.venv-research/bin/python -m research_env.sweep \
  leaderboard/sweeps/openrouter-frontier-10-tools/manifest.json \
  .leaderboard-runs/openrouter-frontier-10-tools \
  --env-file /ABSOLUTE/PATH/TO/.env --max-usd 10
```

The shown $10 value is the current authorization and will pause under the existing
ledger; it is not enough to launch the full comparison. Credentials are read as
data from the named variable/file, never sourced or printed. No credential was
saved to a workspace file while running these probes. The runner first validates all ten models with
the full participant configuration, then resumes sealed attempts/verdicts without
rerunning them. Interrupted wall budgets are not silently reset.
