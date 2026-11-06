# Granite GRPO step 28: parser correction and complete rerun

The rerun completed all nine compact-coding-v1 episodes. It still produced one valid predictor. Pooled Elo remains **863.0762**, with **zero change** under the published ten-model match schedule.

| Task | Original valid | Rerun valid | Rerun held-out MAE | Task Elo |
| --- | --- | --- | --- | --- |
| Load | 0/3 | 0/3 | None | 895.3975 |
| Heat | 0/3 | 0/3 | None | 866.1509 |
| Pulse | 1/3 | 1/3 | 10.014156740055713 bpm | 998.7811 |

## What changed

The serving process on the existing A100 pod `z9cd4z86nwyhlb` now uses `--tool-call-parser granite4`, replacing `hermes`. The model checkpoint, tokenizer, template, decoding, prompts, seeds 0/1/2, retry budget, numerical scoring policy, frozen datasets and Docker image were preserved. The original run remains intact. Checkpoint manifest SHA-256: `b863338f2ff35bdbac8dcceff3717b01fd50ef9f19f3bdaf1647c1a0596eec33`.

The installed vLLM 0.24.0 Granite parser preserves already serialized JSON tool arguments. The Hermes parser serializes them again, causing a string rather than an object after the benchmark's JSON decode. `check_parser.py` reproduces this difference with both object-valued and string-valued arguments; `parser-check.txt` records its successful assertions. vLLM recommends the Granite-specific parser: [official tool calling documentation](https://docs.vllm.ai/en/stable/features/tool_calling/).

## Remaining failures

Six episodes that previously failed before code execution now reached the sandbox and attempted both experiments, but produced no valid predictor. Together with the existing load seed-0 execution failure, seven episodes now fail on code/artifact construction. Examples include importing unavailable `pandas`, invalid Python syntax, using `/` between strings, expecting fitted files that do not exist, and defining a prediction function without writing `artifact/inference.py`, fitted files and `requirements.lock`. Heat seed 0 still fails its two response attempts: the first reason is 191 characters, exceeding the 160-character limit; the second reply has no accepted tool call.

The pulse seed-0 successful artifact and test MAE are unchanged. No generated code was repaired by hand, and no failed episode was omitted or retried again to select a favorable outcome.

## Rating verification and scope

`summarize.py` verifies all nine sealed receipt hashes, task/seed coverage, suite identity and checkpoint identity. It replays all 405 published pooled matches and the three published task schedules; every match outcome, delta and final rating is unchanged. It preserves the published match order because re-sorting renamed display labels can change sequential Elo even with identical outcomes. Saved public input snapshots make this check reproducible without reading a changing site checkout.

New process reviews were not requested; prediction Elo does not use those reviews. The site was not changed or published. This rerun supports correcting the serving configuration, but provides no evidence of improved predictive validity or higher Elo.

The next useful improvement is training/evaluating artifact construction and protocol compliance under this exact compact task interface. Another unchanged rerun does not address the observed code errors. Any new prompt, sampling policy or checkpoint should be declared as a new configuration and evaluated across all nine episodes.

Both existing pods were left running: A100 `z9cd4z86nwyhlb` at $1.79/hour and A40 `kmjf521oldfp74` at $0.59/hour, as reported by RunPod during this investigation. Training remains paused; its serving process was restarted solely to select the correct parser.
