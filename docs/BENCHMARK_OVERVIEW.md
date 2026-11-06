# How the physiology benchmark works

This page explains what the benchmark does, why it is built this way, how scoring works, and how a run reaches the leaderboard.

For the exact rules, see the [run guide](LEADERBOARD.md). Each task's `TASK.md` and `DATA_DICTIONARY.md` explain its inputs and outputs.

## The short version

An AI gets a workspace, public data, and a limited amount of time and computing power. It builds a program that predicts a physiology measurement. It can test its program on development data, then choose and submit one final version. After submission, the benchmark tests that version on hidden data. A separate reviewer looks at the AI's recorded research choices.

## What is the environment?

The active environment is in `research_env/`. It is a research workspace managed by the benchmark. It is not a simulator of the human body, and it does not train an AI with an RL reward.

Each run has:

1. **One fixed task and dataset.** The controller records which task, data, and worker are being used. Restarting a run cannot quietly change them.
2. **Public information.** The AI gets task instructions, allowed training data, a workspace, and results from allowed development evaluations.
3. **Limits.** A run can use up to two hours and 30 development calls. Training and evaluation use CPU only. Worker CPU and memory are limited. Model calls also use a shared spending limit when applicable.
4. **Research actions.** The AI edits files, runs programs, evaluates a candidate, chooses a candidate, and submits it. For important actions, it records what evidence it used, what it expects to happen, and why it made the change.
5. **Hidden scoring.** The controller keeps development labels and test labels private. It saves private checkpoint results but never shows them to the AI. The AI must choose its final program using public results. The benchmark tests only the submitted program on the hidden test data.
6. **A run record.** The controller saves actions, program versions, and model requests and responses. These records help audit the run. The private transcript is not given to the AI as evidence or to the reviewer.

The AI starts without a completed prediction program. It must create an artifact with `artifact/inference.py` and the function `predict(artifact_dir, request)`. It chooses the model, inputs, training method, uncertainty estimates, and experiments. The supplied baselines are examples for comparison, not required solutions.

## Why it is built this way

### Score the research, too

A final prediction score does not show how the AI reached its answer. The run record shows what information it had, what it planned to test, what code it changed, and what happened. A separate reviewer can use this record to assess the research process.

### Let models choose their approach, but compare them fairly

The AI can build its own predictor. Every competitor still gets the same task, data split, time, computing limits, and scoring rules. People are kept separate across data splits so recordings from one person do not appear in both training and testing. Different AI run seeds show run-to-run variation; they do not add more people to the study.

### Keep test answers hidden

Development scores help the AI improve its program. Hidden test scores do not. This makes it harder to tune directly to the test set. It cannot undo possible exposure to public datasets during model pretraining or prove that every kind of data leak is impossible.

### Only allow information available at prediction time

Each task limits the AI to measurements that would be available at that point in time. During testing, the worker gets the program and prediction requests, but not the source recordings, answer labels, or scoring code. Docker workers have no network access and run with resource limits. These controls help protect the evaluation, but this is still a research prototype, not a hardened security product.

### Keep different scores separate

Prediction accuracy, interval quality, research decisions, and whether the program ran correctly measure different things. They are reported separately. A high reviewer score cannot make inaccurate predictions good, and a low prediction error does not prove that the research was sound or that the model is ready for real-world use.

## The three active tasks

These are three separate tests on recorded data. They are not steps in one body simulator.

| Task | What the AI predicts | What it may use when predicting | Main score |
| --- | --- | --- | --- |
| **Pulse** | Average heart rate over the previous 8 seconds, updated every 2 seconds, with a 90% prediction interval | Recent wrist optical pulse and three-axis movement. ECG labels are for training only. | Mean absolute error in bpm, averaged across windows, recording bouts, then people equally |
| **Heat** | Measured rectal temperature 5, 10, and 20 minutes ahead | Past and current heart rate, skin temperature, room temperature, humidity, age, height, mass, and limited model state. No past rectal temperature or future measurements. | Mean absolute error across time points, forecast times equally, then people equally (°C) |
| **Load** | Metabolic power in watts while walking on level ground at 4 km/h with 0, 5, 10, or 15 kg carried | Age, height, mass, carried load, speed, and slope. No resting metabolic rate, lab body-composition values, or targets from other conditions. | Mean absolute error across measured loads for each person, then people equally (W) |

The frozen suite uses GalaxyPPG for Pulse (13/5/5 training, development, and test people), a CORE cycling dataset for Heat (14/5/5), and EVOBREATH lab measurements for Load (28/10/10). Pulse ECG labels are still provisional. Heat covers one cycling protocol. Load covers level walking at one speed and slope. These tests support comparisons on these datasets; they do not prove medical or field performance.

Each task file gives the full input and output format. Predictions must be complete, finite, and in the required order. Missing or invalid predictions make the attempt invalid. The program and saved model must include what is needed to reproduce the result. The AI may train only on allowed training data, not on the people in the evaluation sets.

## What is the reward?

The active benchmark has **no RL reward function**. The AI does not receive a reward signal for training its policy. Here, “reward” usually means the final test score: the prediction error after submission.

The main score is mean absolute error, or MAE. Lower is better. The benchmark also checks each task's required output and whether the program ran successfully.

Prediction intervals are scored separately with the 90% interval score:

`IS90 = interval width + 20 × amount below the lower bound + 20 × amount above the upper bound`

This score penalizes intervals that miss the measured value and intervals that are too wide. Coverage and interval width are also reported.

The leaderboard uses **accuracy Elo** to compare prediction errors and a separate **uncertainty Elo** to compare IS90. These ratings depend on which competitors are in the pool and the match schedule. A valid run ranks above an invalid one; two invalid runs are skipped. A competitor with no valid runs is unranked. The overall rating gives Pulse, Heat, and Load equal weight instead of adding bpm, degrees, and watts together.

A separate blind AI reviewer scores the recorded research process. It looks at evidence use, experiment choice, use of feedback, reproducibility and validity, and whether the final choice and claims match the evidence. Each score is 1–5, or null when there is not enough evidence to judge. These scores are not mixed into prediction error or Elo. Human review is still needed to check how reliable the AI reviewer is.

The benchmark reports four separate areas:

- **Prediction:** hidden-test MAE.
- **Uncertainty:** IS90, coverage, and interval width.
- **Research process:** the separate review of recorded decisions.
- **Execution:** whether the program ran and followed the resource limits.

## What happens in one run?

1. **Set the rules.** The suite records data and code versions, worker image, limits, random seeds, baselines, and rating rules.
2. **Start the run.** The controller creates the AI's workspace and keeps private data and labels elsewhere.
3. **Build and test.** The AI edits code and runs CPU programs. It records its reasons and expected results for important experiments.
4. **Check development results.** The controller runs the candidate and returns allowed development feedback. Each call uses some of the budget, even if it fails.
5. **Choose a final version.** The AI picks a saved candidate using public evidence. It cannot use hidden checkpoint scores because it never sees them.
6. **Submit and test.** Submission closes development feedback. The evaluator runs the saved program in a worker and compares its predictions with hidden answers.
7. **Save the result.** A receipt records hashes for the program, score, run history, transcript, and review packets. Failures are recorded instead of quietly erased by restarting.
8. **Review the research.** The blind reviewer sees one action's evidence at a time. It does not see that action's result or later information. It also does not see hidden test scores.
9. **Build the leaderboard.** Each competitor needs results for all three tasks and all three agent seeds, including records for failed runs. The board shows task scores, separate ratings, and an overall equal-task comparison.

## Why is the evaluator separate?

The AI's workspace is for building a predictor. A trusted controller keeps the budgets, data lists, hidden answers, saved program, and scoring code. During hidden testing, the worker gets only the saved program and prediction requests. The controller keeps the measured answers and calculates the score.

The benchmark also records file hashes and data sources. A result is useful only when we know which data, program, evaluator, and limits produced it. Changing one of these means making a new comparison.

## Older environment in `benchmark/`

The `benchmark/` folder holds an older recovery-prediction prototype. It has four rounds: **Build → Investigate → Transfer → Sustain**. The participant starts with a calibration recording and a blank predictor. It can spend credits to get more recordings, test its predictor, and save a checkpoint before moving to the next round. Hidden checkpoint scores track progress and whether earlier skills were kept, but are never shown to the participant.

Some campaign examples use sitting, walking, stairs, and cycling activity segments. The synthetic data generator uses statistics from PPG-DaLiA; it is not a realistic body simulator. This prototype was made to test whether model design, choosing useful experiments, applying what was learned to a new condition, and retaining earlier performance could matter.

This older campaign is separate from the active three-task leaderboard. It is not an RL training system and does not prove performance on independent future sessions, combat physiology, or clinical outcomes. See [campaign details](CAMPAIGNS.md) and [episode rules](EPISODES.md).

## What the benchmark can and cannot tell us

The benchmark can compare submitted prediction programs on the same recorded data and held-out people. It can also keep a record of research decisions and computing use.

It cannot show that a system can diagnose or treat someone, work safely in the field, predict physiology during combat or stress, generalize to everyone, or improve through post-training. The current benchmark has no RL reward or post-training loop. Results apply to the listed datasets, inputs, and test groups.

## Code map

- Agent actions and interface: `research_env/core/agent.py`
- Budgets, candidate files, and action history: `research_env/core/session.py`
- Hidden scoring and replay: `research_env/core/evaluation.py`
- Offline worker: `research_env/core/worker.py`
- Task selection: `research_env/tasks/registry.py`
- Task data, inputs, and scores: `research_env/tasks/{pulse,heat,load}/`
- Blind process review: `research_env/judging/judge.py`
- Frozen run rules: [LEADERBOARD.md](LEADERBOARD.md)
- Older recovery campaigns: `benchmark/` and [CAMPAIGNS.md](CAMPAIGNS.md)
