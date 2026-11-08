# LLM judge rubrics — draft for calibration

These are proposed hackathon rubrics, not clinical validation. Freeze the
rubric, judge model and settings, case materials and scoring protocol before
comparing models. Test strong, weak, misleading, missing and ambiguous answers
before use; retain judgments and any calibration failures. Do not claim a
validated expert or leaderboard from an untested judge.

## Common instructions

**Outcome first (decided 2026-11-08).** Every judge prompt opens with a
VERIFIED OUTCOME block computed in code from the private ground truth and the
deterministic grader: the correct decision, the measured temperature, the
model's error and whether its decision was right. Read it before anything else
and score against it. A decision that the verified outcome shows to be wrong
scores at most 1 on the decision/override dimension. Reasoning that led to a
wrong conclusion scores at most 2 on reasoning, and reasoning must be judged in
light of what actually happened. Do not change any deterministic number in the
outcome block.

Judge only the final submitted answer, not tool-call history, intermediate
reasoning, writing length, model identity or provider. Use the frozen documents
and case evidence; do not invent symptoms, measurements or sources. Missing
information is unknown, not evidence of absence. Accept different defensible
actions and reasoning paths. Distinguish the model's predictions from observed
facts. Do not reward a confident unsupported claim or punish a candid limit.

For each dimension return an integer 0–5, a short explanation citing specific
passages or fields in the answer and supporting or contradicting case or
document evidence, and material uncertainty. Use `not_scorable` with a reason
when necessary case or reference information is unavailable; do not substitute
zero for a grader or data failure. An absent required response is scored 0 for
that dimension. The rubric does not define Elo, weights or invalid-run policy.

Use the anchors below for each dimension: 5 = excellent, complete and supported;
4 = sound with a minor omission; 3 = partly sound with a material omission;
2 = substantial flaws; 1 = minimally relevant or mostly unsupported; 0 = absent
or wholly fails the requested dimension. Apply the task-specific criteria below
and explicitly explain any safety-relevant error.

## Keep going or pull him?

Judge with the verified outcome (correct decision, measured +15-minute core
temperature, forecast error), the model-visible case and the frozen library.
The verified outcome is authoritative: score the decision against the correct
decision and the reasoning against what actually happened. The model's forecast
is one piece of information, not an observed thermometer reading.

### Forecast assessment (0–5)

Assess whether the submitted numerical forecast and uncertainty are coherent,
appropriately qualified and grounded in the available evidence. The numerical
error is calculated independently in code and reported in °C; do not invent
accuracy thresholds or override that measurement. A close guess alone does not
prove calibrated uncertainty, and a reasonable uncertain forecast does not make
its numerical error disappear. A missing or non-numeric forecast scores 0.

### Decision (0–5)

Assess whether the selected action matches the verified correct decision and is
well supported. A wrong decision scores at most 1. For a correct decision, give
5 when it is well supported and proportionate, 3–4 when correct but with a
material qualification or risk omitted, and 2 when correct but essentially
unsupported or lucky. Give 0 for no valid action or an
action that disregards clear, documented immediate danger. Do not treat a
temperature threshold as a universal label or assume unrecorded symptoms.

### Reasoning (0–5)

Assess relevant observed trends, appropriate use of frozen research, uncertainty
and missing information, tradeoffs, and the connection to the chosen action.
Give 5 when these are accurate and integrated; 3 when the conclusion has some
support but misses an important signal, limitation or tradeoff; 1–2 for major
misinterpretations or unsupported claims; 0 for absent or wholly irrelevant
reasoning. Cite the relevant document and case evidence when assessing claims.

## Rulebook versus body

The verified reference table and its qualifications are inputs to the judge;
the work/rest lookup is scored independently by code. Do not change or infer
the deterministic lookup result. Judge the override against the verified
outcome (expected FOLLOW/OVERRIDE decision and measured core temperature) first,
then against the individual evidence and frozen sources. Do not fabricate
findings.

### Override decision (0–5)

A decision that contradicts the verified expected decision scores at most 1.
For a correct decision give 5 when supported and proportionate, 3–4 with a
material omission, 2 when essentially unsupported; 0 for no decision or disregarding clear documented
immediate danger. Explain the evidence and limitations, including any relevant
table qualification. Do not equate a single thermometer value with an
operational label.

### Reasoning (0–5)

Give 5 for accurate use of the table and individual evidence, a clear account of
the override tradeoff and uncertainty, and supported references; 3 for partly
sound reasoning with a material omission; 1–2 for substantial misreading or
unsupported inference; 0 for absent or irrelevant reasoning. Explain whether
the stated evidence actually supports the chosen action.

## Beat ECTemp

The submitted predictor's validity, error, uncertainty and comparison with the
verified ECTemp baseline are scored deterministically on frozen held-out slices.
The verified outcome block gives the hidden held-out MAE for the case's person
and the ECTemp baseline MAE B. The judge does not alter those results. Judge the
research explanation in light of that outcome: claims of beating ECTemp that the
hidden result contradicts are unsupported, and a predictor that lost to ECTemp
caps the explanation at 3 unless the answer candidly anticipated that risk.

### Research explanation (0–5)

Assess whether the answer accurately explains the predictor, the evidence for
its selection and comparison, causal inputs and leakage controls, uncertainty,
and important data or generalization limits. Give 5 for a coherent, supported
explanation that distinguishes evidence from speculation; 4 for a sound account
with a minor omission; 3 for a partly supported account with a material gap;
2 for substantial unsupported or confused claims; 1 for minimal relevant
content; 0 for absent or irrelevant explanation. Do not award credit for an
experiment or result merely asserted without support in the permitted record.

## Judgment record

For each dimension save its name, integer score or `not_scorable`, explanation,
specific answer evidence, relevant case/document references and uncertainties.
Record the rubric version, judge model and settings, input hashes, raw judge
response, parsed judgment and errors. Keep deterministic metrics separate and
retain the full result for audit. A failed or malformed judgment is a judge
failure, not a score of zero.
