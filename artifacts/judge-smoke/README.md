# OpenRouter judge smoke test

Two short hand-written answers, judged by `openai/gpt-6.1-sol` through the real
OpenRouter chat completions API. These are harness checks, not rated model runs.

| Case | Decision / override decision | Reasoning | Provider-reported cost (USD) |
| --- | --- | --- | --- |
| keep_going / KG-01 | 4/5 | 4/5 | 0.0189785 |
| rulebook_vs_body / RB-01 | 4/5 | 4/5 | 0.0220660 |
| Total | | | **0.0410445** |

Both requests succeeded on the first attempt. The shared persistent spend cap
was **$0.50**; all reservations settled to provider-reported USD costs.

Settings: reasoning effort `high`, `max_tokens: 8192`, JSON-object output,
`usage: {include: true}`, `stream: false`, `provider: {require_parameters: true}`.
Temperature was omitted because it is absent from the model's advertised
supported parameters. The [catalog snapshot](model.json) records the metadata
from [OpenRouter's models API](https://openrouter.ai/api/v1/models), including
the base $2/M input and $10/M output prices used by the spend ledger.

Files:

- `submissions.json`: the two hand-written answers.
- `model.json`: public model metadata used to check model ID, price and settings.
- `judged.json`: scores, prompts, raw judge output, settings sent, hashes, usage
  and spend summary. Credentials and authentication headers are excluded; the
  files were checked against the loaded credential before committing.
- `run/`: local, gitignored spend ledger and hash-chained audit database.

Command (requires the repo-root `.env` key or `OPENROUTER_API_KEY` environment
variable; reusing `run/` preserves cumulative spend):

```sh
.venv/bin/python -m tasks.judge artifacts/judge-smoke/submissions.json \
  --judge openrouter --spend-cap-usd 0.50 \
  --controller artifacts/judge-smoke/run \
  --out artifacts/judge-smoke/judged.json
```

Validation: 30 offline judge tests and 32 combined-scoring tests passed. Final
full-suite command, with `openpyxl==3.1.5` installed in `.venv`:

```sh
PATH="$PWD/.venv/bin:$PATH" python -m unittest discover -s tests
```

Result: **167 tests, OK (skipped=1)**. The existing macOS sandbox integration
test requires `sandbox-exec` and is skipped on Linux. No test made an API call.
