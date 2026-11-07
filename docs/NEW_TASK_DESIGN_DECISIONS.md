# New task design decisions

Working handoff for implementation. Decisions below are agreed in the design
discussion; open questions and proposals are not implementation requirements.
The existing task specifications remain the starting point. No task is ready to
run until its data, grading and execution prerequisites are satisfied.

## Benchmark goal

Assess how models combine practical thinking and research ability to reason
through consequential situations. Models decide what evidence matters and how
to weigh current observations and predicted outcomes.

## Keep going or pull him?

### Agreed

- The model forecasts core temperature at +15 minutes, chooses continue,
  slow, or stop/cool, and submits its reasoning, uncertainty and references to
  the supplied documents. The decision can consider both present evidence and
  the forecast; the model determines their importance.
- No internet access. All models receive the same library containing only
  documents selected and frozen beforehand, with no case-specific briefing.
- Provide the information realistically available to a medic in the scenario,
  constrained by what the measured record actually contains. Do not invent
  symptoms, observations or history; mark missing information as unavailable.
  Provide the recorded history from minute 0 through minute 30, with the
  decision at minute 30 and the +15-minute forecast targeting minute 45. Hide
  core-temperature measurements and all observations after the cutoff. Audit
  each case for sufficient measured coverage before selecting it.
- An independent LLM judge assesses forecast, decision and reasoning separately
  using a rubric. Calculate numerical forecast error in code as well. This is
  an expert-style hackathon assessment, not human expert validation.
- Record a viewable, ordered trajectory, including tool calls, arguments,
  results and errors, the final answer, and any intermediate reasoning or
  reasoning summaries the provider exposes. Mark withheld or unavailable
  reasoning honestly; full chain of thought is not guaranteed. Show outcome
  and judge scores separately from the model trajectory.
- The trajectory is for inspection and is not graded. The judge assesses the
  submitted forecast, decision and stated reasoning, not the sequence of tool
  calls or intermediate trace.

### Open design work

- Select and freeze the actual research documents, measured cases and cutoffs;
  audit medic-relevant inputs against available data and specify the tools and
  output schema.
- Define and test the judge rubric, scoring scales, judge inputs and handling
  of hindsight; pin the judge and preserve judgments for review.
- Verify that the measured data support any proposed case categories. A clear
  stop/cool case, an ambiguous case and a continue control were suggested, but
  have not been confirmed or selected.
- Decide how the three scores are reported or combined, and define completion,
  invalid response and missing-data handling.

## Other tasks

Rulebook versus body and Beat ECTemp have not yet been designed in this
discussion. Their existing specifications and readiness blockers still apply.
