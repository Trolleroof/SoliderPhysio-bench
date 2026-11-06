# Research-run transcripts

Every run now has a private transcript alongside its numerical and judge outputs.
It follows the useful parts of [Archipelago's trajectory model](https://github.com/Mercor-Intelligence/archipelago/blob/5e2d940584e63cc296d3b0b6e65ff733ac69b368/agents/runner/agents/models.py):
inputs, returned messages/actions, tool results, usage, elapsed time, final answer,
status and structured failures. It is our own task-specific format, not a native
Archipelago export or a claim of full Archipelago compatibility.

## Files

| File | Contents |
|---|---|
| `private/controller.sqlite` | Durable controller ledger and separate private transcript table, written as a run progresses |
| `provider-call-NNNN.json` | Exact API request body, bounded raw response body, returned action, model IDs, usage, timestamps, latency and failure fields |
| `provider-usage.json` | Persisted call count and token-budget accounting; resumed runs keep their original counters |
| `transcript.jsonl` | Ordered transcript export, linked with SHA-256 hashes |
| `transcript.html` | Standalone, escaped, expandable inspection report |
| `run-status.json` | Running/completed/failed/cancelled status, final selection explanation, candidate, usage, elapsed time and structured fault |
| `trajectory.jsonl` | Existing controller-only trajectory, unchanged in purpose |
| `judge-packets.json` | Existing chronology-limited blind judge evidence; never built from the private transcript |
| `receipt.json` | Sealed private numerical result and hashes binding controller trajectory, transcript, terminal status and judge packets |

The exact request body includes system/user messages and sampling settings. HTTP
Authorization headers and API credentials are never intentionally passed to the
logger. Provider response bodies are limited to 2 MB, as before. If a provider
returns optional response fields, those are retained in the bounded response body;
this does not recover internal reasoning that a provider does not expose. We do
not request private chain of thought. Substantive experiment justifications are
recorded through the existing decision schema.

## Timeline and correlation

`physiology-transcript-v1` records have a `trace_id`, Unix timestamp, kind, data,
previous hash and current hash. The controller's SQLite transactions preserve
controller events and their transcript copies together. Provider records use the
same database with a separate connection and durable writes before network calls.

The normal sequence is:

1. `model_request`: exact request and call ID, saved before sending.
2. `model_response`: matching request trace ID, raw response text, decoded action,
   configured/reported model IDs, provider usage, latency and any structured fault.
3. `action_start`: call ID and complete action, including edited file contents.
4. `controller_event`: existing event ID, evidence, experiment, development result,
   candidate selection and checkpoint records.
5. `action_result`: matching action trace ID, call ID, elapsed time, exact returned
   controller result and all controller event IDs produced by that action.
6. `run_status`: final submitted explanation, candidate, elapsed time, validity and
   typed fault, with no private test loss in the transcript/status report.

Conventional/manual actions use the same action/result logging without invented
model calls. JSON-lines mode also saves exact emitted observations/results as
`protocol_output`; caller-supplied Python providers save their input observation.
Only the built-in HTTPS adapter can capture its exact provider request/response;
external clients must retain any additional prompts they add themselves.

Tool stdout/stderr currently retain the last 65,536 characters each. Explicit
`stdout_truncated`, `stderr_truncated` and `log_tail_character_limit` fields identify
that limit. The transcript records exactly the returned feedback, not an invented
complete command output. Model response token accounting says `provider_reported`
when actual total usage is supplied; otherwise budget consumption remains a labeled
conservative reservation. Dollar cost is not inferred from token count.

## Inspect a running or finished run

```sh
.venv-research/bin/python -m research_env.trace RUN
```

This reads the durable private database, verifies its transcript hash chain, and
writes `RUN/transcript.jsonl`, `RUN/transcript.html` and `RUN/run-status.json`.
Open the HTML file locally. The report escapes source code, tool output and other
untrusted text; it does not execute participant HTML/scripts or load remote assets.
Re-run the command to refresh a live snapshot. No hosted dashboard or streaming
frontend is required. Finalization exports the same files automatically.

A provider or protocol failure is retained with its failed call/action. Keyboard
interruption exports a cancelled, resumable status without sealing a failed score;
resuming keeps the original wall/development/inference budgets. Completed/failed
finalization seals the exported transcript and status in the private receipt.
Leaderboard builds reject changed transcript/status hashes. Inspection exports of
an unchanged finished run preserve those hashes.

## Separation and limits

Private transcript records are excluded from `ResearchEnvironment.observe()` and
`build_packets()`. This keeps provider prompts, unblinded context and future outcomes
out of the participant history and the blind judge's evidence. Private test scores
stay in the separate final receipt. Do not mount the run root/controller in the
participant container or feed the inspection transcript to a pre-action judge.

Focused tests cover exact payload capture, source edits, action/result correlation,
latency/usage, malformed replies, error durability, secret-header exclusion, HTML
escaping, transcript tampering, interruption/resume budgets and judge separation.
A scripted provider exercises the full controller/finalizer path without external
inference. A fresh Docker load-development check exercises real command/evaluation
logging. Neither check creates an official model result.

The logging change requires a fresh suite fingerprint before the model sweep.
No model scores were carried across the empty-suite refresh. Actual model/provider
and semantic-judge calls still require explicit configurations; no paid call was
used to implement or test this logging.
