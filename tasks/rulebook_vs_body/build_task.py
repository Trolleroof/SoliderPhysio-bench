"""Build the 'Rulebook versus body' task (Task Type 2) from the CORE cycling workbook.

Source: D'Lugos (2025), Figshare 29120024 v1, CC BY 4.0, the same workbook as Task Type 1.
The trace is produced by the Task Type 1 builder (``tasks.keep_going.build_tasks``) so the
de-identified format is identical: a 25-row window ending at the cutoff, timestamps
re-zeroed to 0..24, heart rate / watts / humidity / age / mass rounded to integers, skin and
room temperature to one decimal, room conditions carried forward only after they were
observed, no core temperature of any kind, no subject number, no sex.

Writes ``task.json`` and ``prompts/RB-0x.md`` (public) and ``private_ground_truth.json`` (private).

Run:  .venv-research/bin/python -m tasks.rulebook_vs_body.build_task
"""
from __future__ import annotations

import json
from pathlib import Path

from tasks.keep_going import build_tasks as kg
from tasks.rulebook_vs_body import evaluator

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = kg.DEFAULT_SOURCE
SOURCE_URL = kg.SOURCE_URL
SOURCE_MD5 = kg.SOURCE_MD5

THRESHOLD_C = kg.THRESHOLD_C
HORIZON_MIN = kg.HORIZON_MIN
WINDOW_MIN = kg.WINDOW_MIN

# Scenario. The flag and work category are inputs to the rulebook half; they are not
# derived from the chamber (35 C at about 20 percent humidity is below Heat Category 1
# on the WBGT scale). Moderate work at Yellow flag is a no-limit cell in both tables, so
# the prescription does not depend on how long he has already been working, and the
# protocol clock can stay hidden exactly as in Task Type 1.
HEAT_CATEGORY = "Yellow"
WORK_CATEGORY = "Moderate"

# Two cases under the same flag and work category, so the rulebook answer is identical and
# only the body differs. Neither person is used by Task Type 1 (subjects 3, 4, 21 and 23).
CASES = [
    {"task_id": "RB-01", "subject": 25, "cutoff": 44, "role": "trap",
     "design": "steady_power_quiet_wearable_hot_core",
     "note": "Steady 195 W, about 3.3 W/kg, heart rate drifting only from the high 140s to the "
             "high 150s. Nothing in the wearable looks alarming and the rulebook cell is no-limit, "
             "but the measured rectal temperature is already 38.40 C at the cutoff and reaches "
             "38.92 C fifteen minutes later."},
    {"task_id": "RB-02", "subject": 12, "cutoff": 30, "role": "control",
     "design": "steady_power_alarming_heart_rate_safe_core",
     "note": "Steady 122 W, about 1.6 W/kg, heart rate 169 to 180 bpm. The wearable looks "
             "alarming, but measured rectal temperature only rises from 38.22 C to 38.36 C and "
             "never reaches the threshold in the next 15 minutes. An always-override policy "
             "fails here."},
]
TASK_IDS = [c["task_id"] for c in CASES]


def _device_estimate(path: Path, subject: int) -> dict[int, float]:
    """Vendor CORE sensor estimate for one person, keyed by protocol minute (private only)."""
    import openpyxl

    sheet = openpyxl.load_workbook(path, data_only=True, read_only=True)["Core Temp"]
    rows = list(sheet.iter_rows(values_only=True))
    start = rows[0].index("CORE")
    col = next(i for i in range(start, len(rows[1])) if rows[1][i] == subject)
    return {int(r[1]): float(r[col]) for r in rows[2:] if r[1] is not None and isinstance(r[col], (int, float))}


def build_case(case, people, source: Path, table):
    person = people[case["subject"]]
    cutoff = case["cutoff"]
    rows = kg.make_window(person, cutoff)
    demo = {"age_years": kg._ri(person["demo"]["age_years"]), "mass_kg": kg._ri(person["demo"]["mass_kg"])}
    expected = evaluator.lookup(table, HEAT_CATEGORY, WORK_CATEGORY)
    core_now = person["core"][cutoff]
    core_later = person["core"][cutoff + HORIZON_MIN]
    future = [person["core"][t] for t in range(cutoff + 1, cutoff + HORIZON_MIN + 1)]
    device = _device_estimate(source, case["subject"])
    watts_window = [r["watts"] for r in rows]

    task = {
        "task_id": case["task_id"],
        "task_type": "rulebook_vs_body",
        "horizon_min": HORIZON_MIN,
        "threshold_c": THRESHOLD_C,
        "inputs": {
            "heat_category": HEAT_CATEGORY,
            "heat_category_number": expected["heat_category"],
            "work_category": WORK_CATEGORY,
        },
        "subject_profile": demo,
        "rows": rows,
        "answer_format": evaluator.ANSWER_FORMAT,
    }
    task["prompt"] = evaluator.render_prompt(task, table)
    truth = {
        "task_id": case["task_id"],
        "role": case["role"],
        "design": case["design"],
        "note": case["note"],
        "subject_id": case["subject"],
        "person_code": f"H{case['subject']:02d}",
        "sex": person["demo"]["sex"],
        "cutoff_min": cutoff,
        "window_start_min": cutoff - WINDOW_MIN + 1,
        "horizon_min": HORIZON_MIN,
        "threshold_c": THRESHOLD_C,
        "core_at_cutoff_c": core_now,
        "core_at_cutoff_plus_15_c": core_later,
        "peak_core_next_15_c": max(future),
        "core_change_15_c": round(core_later - core_now, 2),
        "device_estimate_at_cutoff_c": device.get(cutoff),
        "device_estimate_at_cutoff_plus_15_c": device.get(cutoff + HORIZON_MIN),
        "power_dropped_in_window": max(watts_window) > watts_window[-1],
        "watts_first": watts_window[0],
        "watts_last": watts_window[-1],
        "rulebook_allows_work_through_horizon": expected["work_rest_min"] == "NL",
        "expected_rulebook": {k: expected[k] for k in evaluator.RULEBOOK_FIELDS},
        "expected_decision": "OVERRIDE" if core_later >= THRESHOLD_C else "FOLLOW",
        "override_is_correct": bool(core_later >= THRESHOLD_C),
        "scorer": "tasks.rulebook_vs_body.evaluator.grade",
    }
    return task, truth


def build(source: Path = DEFAULT_SOURCE, out_dir: Path = HERE, write: bool = True):
    """Return (public tasks, private truths). Writes task.json, prompts/ and the truth file."""
    source, out_dir = Path(source), Path(out_dir)
    people = kg.load_workbook(source)
    table = evaluator.load_json(HERE / "tb_med_507.json")
    pairs = [build_case(case, people, source, table) for case in CASES]
    public = [t for t, _ in pairs]
    private = [g for _, g in pairs]
    if write:
        (out_dir / "task.json").write_text(json.dumps({
            "source": {"url": SOURCE_URL, "license": "CC BY 4.0", "md5": SOURCE_MD5},
            "rulebook_source": "TB MED 507, 12 April 2022; see tb_med_507.json",
            "tasks": public}, indent=2) + "\n")
        (out_dir / "private_ground_truth.json").write_text(json.dumps({
            "threshold_c": THRESHOLD_C, "horizon_min": HORIZON_MIN, "window_min": WINDOW_MIN,
            "tasks": private}, indent=2) + "\n")
        (out_dir / "prompts").mkdir(parents=True, exist_ok=True)
        for task in public:
            (out_dir / "prompts" / f"{task['task_id']}.md").write_text(task["prompt"])
    return public, private


if __name__ == "__main__":
    _, truths = build()
    for t in truths:
        print(f"{t['task_id']} {t['role']:7s} {t['design']:42s} core {t['core_at_cutoff_c']:.2f} -> "
              f"{t['core_at_cutoff_plus_15_c']:.2f}  expected {t['expected_decision']}")
