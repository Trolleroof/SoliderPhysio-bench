# Representative transcripts

Real saved cases from the 2026-11-07 run, one file each: prompt, raw model answer, deterministic grade and judge marks. Full raw outputs for every case are in `results/rerun-20261107/`. Regenerate with `python scripts/extract_transcripts.py`.

| File | What it shows | Model | Case |
|---|---|---|---|
| [rulebook-2003-card.md](rulebook-2003-card.md) | Rulebook: recites the superseded 2003 card (40/20) | Sonnet 5.5 | `RB-01` |
| [rulebook-correct-NL.md](rulebook-correct-NL.md) | Rulebook: one of the 3 answers that got the 2022 card cell right (NL) | GPT-6 Astra | `RB-01` |
| [keep-pull-false-pull.md](keep-pull-false-pull.md) | Keep/Pull: needless pull of a soldier who stayed below 38.5 C | GPT-6 Astra | `KG-01` |
| [keep-pull-missed-pull.md](keep-pull-missed-pull.md) | Keep/Pull: missed pull, soldier crossed 38.5 C (dangerous direction) | Sonnet 5.5 | `KG-02` |
| [keep-pull-thermal-lag-caught.md](keep-pull-thermal-lag-caught.md) | Keep/Pull: thermal lag caught (near miss turned success) | Hy4 | `KG-02` |
| [beat-ectemp-worse-than-baseline.md](beat-ectemp-worse-than-baseline.md) | Beat ECTemp: predictor no better than the baseline (predictor score 0) | GPT-6 Astra | `3A/H06` |
| [beat-ectemp-beats-baseline.md](beat-ectemp-beats-baseline.md) | Beat ECTemp: predictor clearly beats the baseline | Muse Wonder 1.0 | `3A/H13` |

## One transcript per model

Each model's lowest-scoring answered single-turn case (Keep/Pull or Rulebook), so every reported model has a failure on file. Beat ECTemp failures are above.

| Model | Case | Combined | Transcript |
|---|---|---:|---|
| GPT-6 Astra | `KG-01` | 0.200 | [by-model/gpt-6-astra.md](by-model/gpt-6-astra.md) |
| Muse Wonder 1.0 | `KG-05` | 0.200 | [by-model/muse-wonder-1-0.md](by-model/muse-wonder-1-0.md) |
| Sonnet 5.5 | `KG-02` | 0.200 | [by-model/sonnet-5-5.md](by-model/sonnet-5-5.md) |
| GPT-6.1 Terra | `KG-01` | 0.200 | [by-model/gpt-6-1-terra.md](by-model/gpt-6-1-terra.md) |
| Opus 5 | `KG-11` | 0.120 | [by-model/opus-5.md](by-model/opus-5.md) |
| Hy4 | `KG-05` | 0.200 | [by-model/hy4.md](by-model/hy4.md) |
| Kimi K3.1 Pro | `KG-02` | 0.200 | [by-model/kimi-k3-1-pro.md](by-model/kimi-k3-1-pro.md) |
| Grok 4.6 | `KG-02` | 0.200 | [by-model/grok-4-6.md](by-model/grok-4-6.md) |
| Fable 5.1 | `KG-04` | 0.200 | [by-model/fable-5-1.md](by-model/fable-5-1.md) |
| Gemini 3.8 Flash | `KG-02` | 0.200 | [by-model/gemini-3-8-flash.md](by-model/gemini-3-8-flash.md) |
| Gemini 4 Argon | `KG-05` | 0.200 | [by-model/gemini-4-argon.md](by-model/gemini-4-argon.md) |
| DeepSeek-V4.1-Flash-1017 | `KG-01` | 0.200 | [by-model/deepseek-v4-1-flash-1017.md](by-model/deepseek-v4-1-flash-1017.md) |
| Fable 5 | `KG-05` | 0.200 | [by-model/fable-5.md](by-model/fable-5.md) |
| Opus 5.5 | `KG-01` | 0.200 | [by-model/opus-5-5.md](by-model/opus-5-5.md) |
