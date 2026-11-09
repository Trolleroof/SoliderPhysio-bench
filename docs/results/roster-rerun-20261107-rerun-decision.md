# Finalization audit and matched-rerun decision

Audit date: 2026-11-08. Evidence root: `.benchmark-runs/rerun-20261107/` (all relative run paths below use this root).

**Recommendation: a versioned matched Beat ECTemp rerun is necessary before presenting explanation scores or the resulting overall ratings as a fair comparison under a repaired finalization protocol.** Execution is not authorized. Preserve the existing results as observations under the original harness; do not replace absent explanations, erase attempts, or silently recalculate them under new rules. Existing deterministic grades remain recorded outcomes of the saved answers and artifacts. They do not establish what the same models would achieve under a repaired time allocation.

## Scope and identity

The supplied `control/completion-audit.json` reports 294 unique cases for 14 available roster models: 276 scored judgments and 18 `absent_answer` judgments. I independently reproduced that coverage using `eval_suite.resume_sweep.inventory`, which rejects duplicate completed case identities and includes cases saved before a source run failed. There are 24 submission sources with completed cases and 28 frozen research artifact sets. Judge: `openai/gpt-6.1-sol-pro`, outside the participant roster. Carbon is unavailable. Gemini 3.7, diagnostic fixtures, and initial DeepSeek pilots are excluded.

For all 294 cases, I matched the judge directory's submission digest, `case-NN.json` input digest, final saved attempt, and answer hash to the source submission. All 24 source transcript hash chains and all 28 artifact manifests/tree hashes matched. These are integrity checks, not a fresh execution of predictors or an independent replay of deterministic graders.

Only this report is an output of this task. No runner, protocol, scoring, test, artifact, ledger, queue, or automation changes were made. No provider requests or evaluation runs were performed.

## The flaw

In `eval_suite/runner.py:189-238`, the 1,200-second research deadline covers model requests and tools. The harness decides a request is final only at a loop boundary: last permitted turn, or remaining time at most `min(30, research_seconds * .15)` (30 seconds here). It then adds the final-turn instruction and sets `tool_choice: none`. Ordinary requests may consume the entire remaining deadline; returned tools can consume more of it. There is no protected finalization interval. Request retries also share their request deadline. The saved answer is assigned only when a response has no tool calls; text accompanying tool calls is not the final explanation.

Consequently, the runner can (a) miss the threshold entirely, or (b) reach it with much less than 30 seconds left. Calling this a “30-second reserve” overstates the implementation: it is a threshold, not a reserved budget. A timeout does not reveal whether a provider was about to answer, whether it would have chosen more tools, or whether a larger final budget would have succeeded.

After research, the runner freezes the current workspace and scores it on hidden requests regardless of explanation presence. The hidden scoring execution is outside the measured `research_wall_s`. Each variant's one explanation is copied into its per-person cases, so 11 absent Beat ECTemp case judgments represent four missing explanations, not 11 independent failures.

## Exact affected research cases

Transcript identifiers below refer to `<source>/controller/controller.sqlite`. `remaining` is feedback in the last tool message carried by the request; it slightly precedes dispatch, rather than measuring the exact request timeout.

| Model and source | Variant and affected case suffixes | Saved outcome | Trace evidence and bounded attribution |
|---|---|---|---|
| `google/gemini-4-argon`, `continued-02-02` | `3A/H06`, `3A/H13` | Empty answer; `wall_limit`; 1,200.215 s; valid artifact | No final request. `t000153` starts with about 44.415 s remaining, tools enabled. `t000154` returns after 40.504 s with `finish_reason=tool_calls`, empty text, `execute` and `dev_score`. Both tools complete (`t000155-158`); the next iteration has no time. `t000160` records research completion. This directly demonstrates the harness failing to protect finalization time. It does not prove an alternative final request would succeed. |
| Same model/source | `3B/H06`, `3B/H13`, `3B/H18`, `3B/H22`, `3B/H25` | Empty answer; `wall_limit`; 1,200.266 s; valid artifact | `t000319` starts an ordinary request with about 37.592 s remaining. `t000320` returns tool calls after 24.725 s; tools finish at `t000324`. Final request `t000325` does carry `tool_choice=none` and the final instruction, with about 9.062 s remaining. `t000326` records `Model request wall budget exhausted` after 9.280 s. `t000328` records completion. The finalization opportunity was sharply reduced by scheduling; no final response or finish reason was received. |
| `x-ai/grok-4.6`, `continued-09-02` | `3A/H06`, `3A/H13` | Empty answer; `wall_limit`; 1,200.193 s; valid artifact | No final request. `t000157` starts with about 37.246 s remaining, tools enabled; `t000158` records the wall-budget timeout after 37.415 s. `t000160` records completion. Same unprotected-deadline path, but the timeout does not establish the unreturned response's contents or why it was slow. Earlier tool-call response `t000150` contains 105 text characters, which the harness did not treat as a final explanation. |
| `moonshotai/kimi-k3.1-pro`, `continued-13-01` | `3A/H06`, `3A/H13` | Empty answer; `wall_limit`; 1,202.880 s; valid artifact | No final request. Ordinary request `t000129` follows about 605.861 s remaining; `t000130` records connection reset, then retry `t000131` ends at `t000132` with wall-budget exhaustion. The timestamp gaps are 2,801.260 s and 3,642.118 s respectively, inconsistent with the recorded monotonic research duration. This is transport/timing ambiguity, not evidence of provider filtering, token exhaustion, a deliberate refusal, or a demonstrated 30-second-threshold crossing. Suspend, clock adjustment, and related host behavior are hypotheses, not established causes. |

The corresponding judge checkpoints are `continued-02-02-judge/case-00.json` through `case-06.json`; `continued-09-02-judge/case-00.json` and `case-01.json`; and `continued-13-01-judge/case-14.json` and `case-15.json`. All have matched input hashes and status `absent_answer`; their answer input hash is null. These deterministic zero judgments were produced by the absent-answer rule in `tasks/judge.py:419`, not an LLM inference that the absent explanation was poor research.

All other 24 research sessions have nonempty saved explanations, `research_stop=submitted`, final received response `finish_reason=stop`, and valid saved graders: HY4, Sonnet 5.5, Opus 5.5, DeepSeek V4.1 Flash, Gemini 3.8 Flash, Terra, Fable 5.1, Muse Wonder, Opus 5, Astra, and Fable 5 (both variants), plus Grok and Kimi 3B. They are observed successes, not proof that the timing rule is safe. Forced-final successes include HY4 3B (`t000512-513`, 49.750 s response latency) and Gemini 3.8 Flash 3A/3B (`t000253-254`, 29.660 s; `t000509-510`, 24.672 s). The HY4 example demonstrates that even an observed successful final response can take longer than 30 seconds; no universal sufficient reserve follows from these examples.

## Other absent judgments: different mechanisms

| Model/source | Exact cases | Saved provider evidence | Judge checkpoints |
|---|---|---|---|
| `anthropic/claude-opus-5.5`, `model-05-fresh` | `keep_going/KG-02`, `rulebook_vs_body/RB-01`, `rulebook_vs_body/RB-02` | Empty response text; `content_filter`, native `refusal`; transcript responses `t000004`, `t000026`, `t000028` | `model-05-fresh-judge/case-01.json`, `case-12.json`, `case-13.json` |
| `anthropic/claude-fable-5`, `continued-15-01` | `keep_going/KG-10`, `rulebook_vs_body/RB-01`, `rulebook_vs_body/RB-02` | Empty response text; `content_filter`, native `refusal`; responses `t000018`, `t000026`, `t000028` | `continued-15-01-judge/case-08.json`, `case-12.json`, `case-13.json` |
| `tencent/hy4`, `continued-03-01` | `rulebook_vs_body/RB-01` | `t000026`: empty response text; normalized/native finish `length`; 65,536 completion tokens, all reported as reasoning tokens | `continued-03-01-judge/case-12.json` |

These seven cases are single-response tasks; the Beat ECTemp finalization threshold does not apply. The recorded refusal/filter indicators identify the provider response path, but do not distinguish a model decision from a downstream safety filter or reveal the underlying trigger. HY4 shows output-budget exhaustion without a final text answer, not wall-time finalization failure. Retain the frozen zeros; do not invent answers from private reasoning or relax filters/token settings selectively.

## Deterministic validity and possible artifact effects

All 28 saved `grader.json` files report `valid=true`, including the four explanation-less sessions. The affected artifacts' saved per-person MAEs (C) are:

| Model/variant | Saved hidden MAEs |
|---|---|
| Argon 3A | H06 0.055977; H13 0.453942 |
| Argon 3B | H06 0.113634; H13 0.532800; H18 0.307462; H22 0.388531; H25 0.112270 |
| Grok 3A | H06 0.181909; H13 0.492174 |
| Kimi 3A | H06 0.119740; H13 0.363033 |

The frozen scoring code weights Beat ECTemp predictor performance 60% and explanation 40%. Absent explanations contribute zero to the latter. The difference from a hypothetical explanation score is bounded by 0.40 per affected combined case; this is not an estimate of recovered credit or an Elo correction.

A finalization repair can affect predictors as well as text. Argon's last 3A `execute` writes a predictor; its last 3B `execute` changes predictor weights and interval width. Their subsequent development scoring completes. Protecting time earlier could prevent those edits. Conversely, a timeout may leave a model's intended subsequent edit unexecuted. The valid frozen files establish what was actually graded, not optimality, intended final selection, or equivalence under a revised budget. No evidence here establishes the direction or size of a predictor change.

Do not label all command failures infrastructure. Examples include a generated-code `TypeError` in `continued-02-01/t000053`; Grok's null-handling errors in `queue-model-09/t000049,t000059`; and Kimi's invalid Python invocation, null comparisons, and undefined `np` in `continued-13-01`. Argon `continued-02-02/t000241` instead records a tool wall-budget exhaustion; that alone does not identify its underlying cause. Such failures can consume research time, but their causal contribution to final absence is unquantified. They coexist with recovered valid artifacts.

Failed/partial sources also record connection resets, broken pipes, TLS errors, and timeouts, including Argon attempts before `continued-02-02` and `continued-09-01` before Grok's completed source. A source's failed status does not erase its earlier completed cases. Preserve all sources and ledgers, including zero-case attempts and unfinished workspaces; do not count them as additional completed cases or silently substitute their artifacts. Earlier exposure and changes to request/retry handling limit claims of a perfectly matched historical execution even beyond this finalization defect.

## Minimal prospective repair and controls

These are recommendations only, not implemented changes.

1. Version the runner protocol with a fixed research phase and a protected explanation phase. Keep a declared total budget (for example, 1,080 s research plus 120 s finalization within 1,200 s); treat that split as a new design choice requiring validation, not a proven sufficient allocation. Reserve the final model turn from the existing turn cap. Bound ordinary requests, retries, and each tool batch by the research cutoff, rather than merely checking the cutoff between requests. Include serialization/ledger overhead in deadline handling.
2. Freeze/hash the artifact before entering finalization. The final request must be text-only with tools disabled, use only already available public development evidence, and receive no hidden results or artifact mutation capability. Early voluntary final submission still ends research. Do not grant extra experiments, retries, or time to an individual model after seeing its result.
3. Log protocol/code/settings hashes and phase transitions, monotonic elapsed time, UTC timestamps, actual timeout passed to every request/retry/tool, final-dispatch status, raw finish reason, usage, and artifact hash. Explicitly distinguish no final dispatch, final timeout, transport failure, empty filtered response, length exhaustion, and nonempty submission. A host timing anomaly should be marked separately from a model-quality failure; prescribe its handling before execution.
4. Use fake clients and a fake clock for offline tests: an ordinary response crossing the old 30 s threshold; an oversized/slow tool batch; a reset/retry near the research cutoff; the final reserved turn; early normal submission; empty `stop`, filter, and length responses; final timeout; and a UTC/monotonic timing discrepancy. Assert that research cannot consume finalization capacity, final tools cannot execute, artifacts remain unchanged, and hidden results never enter the final prompt. Exercise failed-request reservations and duplicate inventory/judge-hash rejection. Existing `tests/test_runner.py` checks last-turn disabling and request timeouts but does not establish a protected phase. No tests were run in this audit.
5. Before any paid matched rerun, validate the chosen split and failure handling with those offline controls. Freeze all choices and the retry policy before observing new results. A separate authorized transport check may be useful; it is not authorized here and cannot establish that every future final request will finish.

## Matched-rerun scope and interpretation

The minimum repaired-protocol comparison reruns **both Beat ECTemp variants for all 14 available models**: 28 research sessions, 98 per-person cases. Use the same frozen workbook, splits, causal inputs, development/hidden requests, scoring parameters, rubric, model IDs, effort/token ceilings, backend/isolation settings, and off-roster judge; record provider availability/settings drift. Preserve the previous 196 Keep Going/Rulebook cases as explicitly reused original-protocol evidence if producing an updated aggregate. Their filters/length outcomes remain unchanged. Label this a matched Beat ECTemp rerun with reused other tasks, not a wholly new 294-case sweep. A claim that every task was freshly rerun requires a separately authorized full 294-case sweep.

Run all 14 models, not just Argon or only the four failed sessions. Repairing allocation changes the procedure for successful competitors too. Do not select the better old/new predictor or explanation. New outputs require new versioned directories and a separate declared spend budget; keep every prior attempt, grader, judge record, transcript, and reservation. The new phase split may yield different predictors, so rerun hidden grading and judging against each newly frozen artifact with the existing scoring rules. Predeclare treatment of transport failures and avoid success-dependent retries.

An explanation-only replay against all 28 old frozen artifacts could diagnose sensitivity to text collection if separately authorized. It would be a new task with retrospective context constraints, not a repair of the original research runs and not a substitute for the matched rerun. Never feed hidden outcomes back to its participant models.

The existing scores are reproducible records under the frozen implementation. Explanation rankings and overall ratings remain provisional as evidence of comparative capability; predictor-only reporting is descriptive of the saved artifacts, with research timing/retry caveats. Nothing in this audit supports a counterfactual ranking, a guaranteed Argon explanation, or a claim that provider filtering would disappear after the repair.

## Checks and accounting boundary

Read-only assertions with `.venv-research/bin/python` passed: 14 × 21 unique case coverage, 24 matching judge submission identities, 294 matching case/answer input hashes and final attempts, 276 scored plus 18 absent statuses, 24 valid source transcript chains, and 28 matching frozen artifact trees/manifests and submission artifact digests. All 28 saved artifact graders report valid. No deterministic grading or judge request was re-executed.

Current inspected SHA-256 values: `eval_suite/runner.py` = `29b8e393c9c2f398c34076a97cf501aa1a4bb9a2b6bfba30469a43ff242b193d`; frozen `tasks/combined_score.py` = `2d181bde73d9e1fbf3cf29c752b778b8726ac1d69b18bad0d471100d0df87e28`; `tasks/scoring_params.json` = `ec0696bfd6d79231685f550e089a91655a679bd722e8f79dfc3b92cadf4ece6d`. These identify inspected files, not independently attested historical code for every attempt.

The supplied completion audit separates **$141.201549259 provider-reported spend** from **$81.546314581 conservative reservations**. Reservations cover unsettled/unknown requests and are not confirmed additional provider billing; no fresh billing reconciliation was done here. In particular, timed-out requests may have incurred unknown charges. Queue stoppage and monitor pause are supplied context, not reverified or altered by this task.
