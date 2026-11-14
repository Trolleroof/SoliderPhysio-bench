"""Build site/lib/soldier.json and refresh public traces from the saved roster run.

    python scripts/build_site_data.py [RUN_DIR]

No API calls. Requires final-leaderboard.json (run report_leaderboard first if missing).
"""
from __future__ import annotations

import collections
import glob
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".benchmark-runs/rerun-20261107"
LB_PATH = RUN / "final-leaderboard.json"
AUDIT_PATH = RUN / "control/completion-audit.json"

KEEP_LABELS = {
    "falling_power_thermal_lag": "Slowed down, core still rising",
    "steady_power_rising": "Steady work, core rising",
    "falling_power_safe": "Slowed down, actually safe",
    "steady_power_safe": "Steady work, actually safe",
}

RB_LABELS = {
    "40/20 (2003 card)": "40/20 (2003 card)",
    "other value": "Other value",
    "no answer": "No answer",
    "NL (correct, 2022)": "NL (2022 card, correct)",
}


def provider_slug(openrouter_id: str) -> str:
    return openrouter_id.split("/")[0]


def task_of_prompt(body: str) -> str:
    if "TB MED" in body:
        return "rulebook"
    if "predict" in body and "submission" in body:
        return "research"
    if "stationary bike" in body:
        return "keep_going"
    return "other"


def load_task_spend() -> tuple[dict[str, float], dict[str, collections.Counter], float]:
    reservation_to_task: dict[str, str] = {}
    for db in glob.glob(str(RUN / "**/controller.sqlite"), recursive=True):
        try:
            rows = sqlite3.connect(db).execute("select payload from transcript").fetchall()
        except sqlite3.Error:
            continue
        for (payload,) in rows:
            rec = json.loads(payload)
            if rec.get("kind") != "model_request":
                continue
            res = rec.get("data", {}).get("reservation")
            if not res:
                continue
            body = json.dumps(rec["data"].get("body", ""))
            reservation_to_task[res] = task_of_prompt(body)

    per_model: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    judge_usd = 0.0
    for db in glob.glob(str(RUN / "**/spend.sqlite"), recursive=True):
        try:
            rows = sqlite3.connect(db).execute(
                "select id, model, charged_nano, accounting from charges"
            ).fetchall()
        except sqlite3.Error:
            continue
        for cid, model, nano, accounting in rows:
            if accounting != "provider_reported" or not nano:
                continue
            usd = nano / 1e9
            if "sol-pro" in model or model == "openai/gpt-6.1-sol-pro":
                judge_usd += usd
                continue
            task = reservation_to_task.get(cid, "other")
            per_model[model][task] += usd

    totals = {m: sum(c.values()) for m, c in per_model.items()}
    return totals, per_model, judge_usd


def aggregate_charts(lb_models: set[str]) -> tuple[dict[str, int], list[dict]]:
    wr: collections.Counter = collections.Counter()
    kg: collections.Counter = collections.Counter()
    seen: set[tuple[str, str]] = set()
    for path in sorted(glob.glob(str(RUN / "*-judge*/judged.json"))):
        judged = json.loads(Path(path).read_text())
        model = judged["model"]
        if model not in lb_models:
            continue
        for case in judged["cases"]:
            key = (model, case["case_id"])
            if key in seen:
                continue
            seen.add(key)
            grader = case.get("grader") or {}
            cid = case["case_id"]
            if cid.startswith("RB"):
                got = str(((grader.get("rulebook") or {}).get("parsed") or {}).get("work_rest_min"))
                if got == "40/20":
                    bucket = "40/20 (2003 card)"
                elif got == "NL":
                    bucket = "NL (correct, 2022)"
                elif got == "None":
                    bucket = "no answer"
                else:
                    bucket = "other value"
                wr[bucket] += 1
            if cid.startswith("KG") and "design" in grader:
                design = grader["design"]
                et = grader.get("error_type")
                if et is None and grader.get("decision_correct"):
                    outcome = "correct"
                else:
                    outcome = et or "correct"
                kg[(design, outcome)] += 1

    rulebook = {RB_LABELS[k]: wr[k] for k in RB_LABELS if wr[k]}
    keep_pull = []
    for design, label in KEEP_LABELS.items():
        keep_pull.append({
            "design": label,
            "correct": kg[(design, "correct")],
            "false_pull": kg[(design, "false_pull")],
            "missed": kg[(design, "missed_pull")],
        })
    return rulebook, keep_pull


def build_soldier() -> dict:
    lb_doc = json.loads(LB_PATH.read_text())
    audit = json.loads(AUDIT_PATH.read_text())
    roster = {r["openrouter_id"]: r for r in json.loads((ROOT / "eval_suite/roster.json").read_text())["models"] if r.get("openrouter_id")}

    lb_models = {r["model"] for r in lb_doc["leaderboard"]}
    totals, per_task, judge_usd = load_task_spend()
    rulebook, keep_pull = aggregate_charts(lb_models)

    models = []
    for row in lb_doc["leaderboard"]:
        mid = row["model"]
        raw = row["raw"]
        roster_row = roster.get(mid, {})
        costs = per_task.get(mid, collections.Counter())
        cost = round(totals.get(mid, row.get("accounted_usd_inventory") or 0.0), 2)
        models.append({
            "rank": row["rank"],
            "id": mid,
            "name": row["display"],
            "provider": provider_slug(mid),
            "effort": roster_row.get("effort", "max"),
            "overall": round(row["overall_100"], 1),
            "keep": round(row["task_scores_100"]["keep_going"], 1),
            "rulebook": round(row["task_scores_100"]["rulebook_vs_body"], 1),
            "research": round(row["task_scores_100"]["beat_ectemp"], 1),
            "cost": cost,
            "cost_tasks": {
                "keep_going": round(costs.get("keep_going", 0), 2),
                "rulebook": round(costs.get("rulebook", 0), 2),
                "research": round(costs.get("research", 0), 2),
            },
            "calls": raw["keep_going"]["correct"],
            "cells": raw["rulebook_vs_body"]["lookup_fields_correct"],
            "overrides": raw["rulebook_vs_body"]["override_correct"],
            "beat": raw["beat_ectemp"]["people_beating_baseline"],
            "mae": round(raw["keep_going"]["mae_c"] or 0, 3),
        })

    research_usd = sum(c.get("research", 0) for c in per_task.values())
    single_usd = sum(c.get("keep_going", 0) + c.get("rulebook", 0) for c in per_task.values())
    provider_total = audit["spend"]["provider_reported"]

    return {
        "run": "2026-11-07/08",
        "judge": audit["judge_model"],
        "total_usd": round(provider_total, 2),
        "judge_usd": round(judge_usd, 2),
        "rulebook": rulebook,
        "keep_pull": keep_pull,
        "models": models,
        "model_usd": round(provider_total - judge_usd, 2),
        "research_usd": round(research_usd, 2),
        "single_turn_usd": round(single_usd, 2),
    }


def main() -> int:
    if not LB_PATH.exists():
        sys.exit(f"missing {LB_PATH}; run: .venv-research/bin/python -m eval_suite.report_leaderboard")
    if not AUDIT_PATH.exists():
        sys.exit(f"missing {AUDIT_PATH}")

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "lib").mkdir(parents=True, exist_ok=True)
    soldier = build_soldier()
    out = SITE / "lib/soldier.json"
    out.write_text(json.dumps(soldier, indent=1) + "\n")
    print(f"wrote {out.relative_to(ROOT)} ({len(soldier['models'])} models)")

    traces_dir = SITE / "public/traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("index.html", "index.txt"):
        p = traces_dir / stale
        if p.exists():
            p.unlink()

    export = ROOT / "scripts/export_web_traces.py"
    cases = traces_dir / "cases.json"
    subprocess.run([sys.executable, str(export), str(cases)], check=True, cwd=ROOT)
    print(f"wrote {cases.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())