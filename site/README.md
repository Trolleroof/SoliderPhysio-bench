# SoldierPhysio results site

Next.js static site for the 2026-11-07 roster run: leaderboard, findings, methodology, and trace explorer.

**Live:** [https://soliderphys-bench.pages.dev](https://soliderphys-bench.pages.dev)

## Local dev

```sh
cd site
npm install
npm run dev          # http://localhost:3000
```

`lib/soldier.json` and `public/traces/cases.json` come from the saved benchmark run. Regenerate from the repo root (no API calls):

```sh
python scripts/build_site_data.py
# optional: .venv-research/bin/python -m eval_suite.report_leaderboard  # if final-leaderboard.json is stale
```

## Deploy (Cloudflare Pages)

```sh
cd site
npm run deploy
```

Model logos under `public/model-logos/` are vendored from [Lobe Icons](https://github.com/lobehub/lobe-icons); see `public/model-logos/README.md`.