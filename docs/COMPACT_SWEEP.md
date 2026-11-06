# Five-model compact leaderboard

The user authorized a fresh $10 retry budget and then reduced the sweep to five models. This pool has its own persistent spend ledger; the earlier $9.86 accounted pilot remains archived and excluded.

Roster: Gemini 4 Argon, Claude Sonnet 5.5, Grok 4.6, GPT-6 Astra, and Gemini 3.8 Flash, through OpenRouter at Medium effort. A separate GPT-6.1 Sol Medium reviewer receives a compact blind episode packet.

Protocol: 5 models × 3 tasks × seed 0 = 15 episodes. Each episode gets two open-ended Python training experiments with development feedback, a final candidate selection, and one process review. Models may use published baseline helpers or write custom code. Training runs offline in the same immutable Docker image; final evaluation uses the unchanged held-out cohorts. No reference calibration is added. The controller stages execution and evaluation automatically to avoid spending model calls on file operations.

Normal API count: 45 participant requests + 15 judge requests = 60. One repair is allowed per phase, for at most 120 requests. Full participant request bodies are capped at 4,096 UTF-8 bytes and outputs at 1,536 tokens, including reasoning; judge bodies at 3,072 bytes and outputs at 1,025 tokens. Provider routing is pinned with frozen maximum prices. Reserving every request's byte bound plus 4,096 tokens of overhead and full output allowance costs at most $9.870018, including every permitted repair. The independent $10 ledger reserves before each call and retains a conservative reservation when billing is unknown. Unexpected provider overbilling stops the runner for audit.

This deliberately short protocol can truncate reasoning or produce invalid artifacts; failures are retained, not silently replaced. It evaluates model performance under this specific small inference budget. A single agent seed over fixed biological cohorts does not establish population-level ranking stability. Pulse ECG-derived reference labels remain provisional.

Requests, raw responses, timing, development decisions, executable artifact snapshots, final selections and sealed receipts are retained. Process review uses development evidence and decision excerpts, without model identity or hidden test scores. Numerical prediction and uncertainty Elo remain separate from the five process criteria. This compact review has less evidence than the earlier full-trajectory judging protocol.

Plan: `leaderboard/sweeps/compact-five/plan.json`. Frozen suite: `.leaderboard-runs/compact-suite.json`. Output: `.leaderboard-runs/compact-five/`. `status.json` includes live accounted spend and completion counts; `leaderboard.json` and `LEADERBOARD.md` are generated after all 15 attempts seal. Failed attempts remain explicit and unranked when no valid suite exists.

MISE reference: its fixed-worker runner sends small current-turn packets. The inspected Terra trajectory judge makes one review call per episode via the Codex subscription. This retry applies those compact-prompt and per-episode review patterns while using OpenRouter for both generation and review.
