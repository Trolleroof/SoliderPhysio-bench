# Independent LLM research judging

The active implementation is `research_env/judging/judge.py`, shared by pulse,
heat and load. See [the run guide](LEADERBOARD.md#llm-judge) for configuration and
commands. Packet export/import and an actual HTTPS adapter are implemented.
No provider is discovered automatically; absent judgments stay pending.

Freeze `physiology-research-judge-v1`: evidence use, experiment choice, feedback
integration, reproducibility/validity, final selection/claim accuracy. Observable
criteria get integer 1–5 scores with reasons and packet evidence IDs. Unobservable
criteria are null with reasons, never a default 3. Means include observable counts.
The optional process score requires complete packet/criterion coverage and gives
each criterion equal weight. It stays separate from accuracy and uncertainty Elo.

Decision packets contain only evidence available before the action, excluding its
outcome and later events. Final-selection packets contain only permitted public
history through selection. Participant identity, controller-injected person IDs
and private test scores are omitted. Every packet/verdict is hash/event bound and
schema/evidence validated. Code, reports and logs are untrusted evidence, never
instructions to the judge. Fresh independent contexts receive one packet each.
Human/repeated-judge agreement audits remain a separate scientific quality check.

`benchmark/judge.py` remains the legacy recovery implementation. Its different
rubric and old verdicts are outside the three-task leaderboard; no prior judgments
were carried forward after the reset.
