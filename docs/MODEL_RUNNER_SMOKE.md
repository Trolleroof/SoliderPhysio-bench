# Model runner smoke results

Model: `deepseek/deepseek-v4.1-flash-1017` (roster rank 6), via OpenRouter.
The live smoke used an aggregate $1.00 cap; each retry received only the
previous attempt's remaining budget. All 52 requests have provider-reported
costs, with no outstanding conservative reservations.

| Attempt | Requests | Actual cost (USD) | Result |
|---|---:|---:|---|
| Initial smoke | 18 | 0.021078550 | KG-01 and RB-01 exhausted 8,192 tokens in reasoning; 3A research reached 16 turns without submission.py and was invalid |
| Text retry | 2 | 0.018984462 | Complete KG-01 and RB-01 answers with a 32,768-token ceiling |
| Research retry | 32 | 0.020720774 | Valid frozen 3A predictor; submitted after 116.9 seconds within its 180-second budget |
| Total | 52 | 0.060783786 | Remaining aggregate budget: $0.939216214 |

| Selected case | Final model output | Deterministic result |
|---|---|---|
| keep_going/KG-01 | KEEP; +15-minute core 38.30 C | Correct decision, absolute error 0.06 C; score 1.0 |
| rulebook_vs_body/RB-01 | OVERRIDE; core 39.0 C; rulebook 20/40, 0.75 qt/h, 60 minutes, 0.75 qt/h continuous | Correct override, error 0.08 C; rulebook 1/4 fields correct; total 0.625 |
| beat_ectemp/3A/H06 | Frozen submission.py plus final research explanation | Valid; hidden person MAE 0.290875 C |

The research retry made two development-scoring calls. Hidden scoring ran only
after artifact freezing and was never returned to the model. The scorer evaluates
both hidden people in variant 3A, but this smoke emits only the selected H06 case.
These are partial, unofficial development runs using Linux Landlock/seccomp
isolation, not a comparative model rating. No full roster run was performed.

Local evidence is retained under the ignored `.benchmark-runs/` directories
`live-smoke`, `live-smoke-text-retry`, and `live-smoke-research-retry`, including
submissions, transcripts, spend ledgers, frozen artifacts and grader reports.
They are not included in Git. Credentials remain in the ignored root `.env`.

The offline integration test exercises all 21 frozen cases with a fake model,
the fake judge CLI, and the combined-score CLI. Its baseline artifacts reproduce
the frozen per-person baseline MAEs. A second identical run with a distinct
fixture model ID verifies matched rating plumbing; it supplies no evidence about
real model performance. `tasks/judge.py` is unchanged by the runner work.

Final validation: `.venv/bin/python -m unittest discover -s tests` passed all
164 tests with one platform-specific skip. The environment has the requested
`openpyxl==3.1.5`. Live transcript hash chains and the frozen research artifact
hashes were also verified.

Official research still needs an installed, digest-pinned Docker image. This
environment's live validation covers the local development backend only. The
real judge provider is outside this runner change; validation uses the fake judge.
