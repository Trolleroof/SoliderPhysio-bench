"""Build the 'Rulebook versus body' task (Task Type 2) from the CORE cycling workbook.

Source: D'Lugos (2025), Figshare 29120024 v1, CC BY 4.0, the same workbook as Task Type 1.
The trace is produced by the Task Type 1 builder (``tasks.keep_going.build_tasks``) so the
de-identified format is identical: a 25-row window ending at the cutoff, timestamps
re-zeroed to 0..24, heart rate / watts / humidity / age / mass rounded to integers, skin and
room temperature to one decimal, room conditions carried forward only after they were
observed, no core temperature of any kind, no subject number, no sex.

Writes ``task.json`` and ``prompt.md`` (public) and ``private_ground_truth.json`` (private).

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

TASK_ID = "RB-01"
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

# Subject 25 is not used by Task Type 1 (which uses 3, 4, 21 and 23). Steady 195 W, heart
# rate in the 150s, rectal 38.40 C at the cutoff and 38.92 C fifteen minutes later.
CASE = {
    "task_id": TASK_ID,
    "subject": 25,
    "cutoff": 44,
    "design": "steady_power_quiet_wearable_hot_core",
    "note": "Steady 195 W, about 3.3 W/kg, heart rate drifting only from the high 140s to the "
            "high 150s. Nothing in the wearable looks alarming and the rulebook cell is no-limit, "
            "but the measured rectal temperature is already 38.40 C at the cutoff and reaches "
            "38.92 C fifteen minutes later.",
}


def _device_estimate(path: Path, subject: int) -> dict[int, float]:
    """Vendor CORE sensor estimate for one person, keyed by protocol minute (private only)."""
    import openpyxl

    sheet = openpyxl.load_workbook(path, data_only=True, read_only=True)["Core Temp"]
    rows = list(sheet.iter_rows(values_only=True))
    start = rows[0].index("CORE")
    col = next(i for i in range(start, len(rows[1])) if rows[1][i] == subject)
    return {int(r[1]): float(r[col]) for r in rows[2:] if r[1] is not None and isinstance(r[col], (int, float))}


def build(source: Path = DEFAULT_SOURCE, out_dir: Path = HERE, write: bool = True):
    """Return (task, truth). Writes the three files when ``write`` is true."""
    source, out_dir = Path(source), Path(out_dir)
    people = kg.load_workbook(source)
    table = evaluator.load_json(HERE / "tb_med_507.json")
    person = people[CASE["subject"]]
    cutoff = CASE["cutoff"]
    rows = kg.make_window(person, cutoff)
    demo = {"age_years": kg._ri(person["demo"]["age_years"]), "mass_kg": kg._ri(person["demo"]["mass_kg"])}
    expected = evaluator.lookup(table, HEAT_CATEGORY, WORK_CATEGORY)
    core_now = person["core"][cutoff]
    core_later = person["core"][cutoff + HORIZON_MIN]
    future = [person["core"][t] for t in range(cutoff + 1, cutoff + HORIZON_MIN + 1)]
    device = _device_estimate(source, CASE["subject"])
    watts_window = [r["watts"] for r in rows]

    task = {
        "task_id": TASK_ID,
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
        "task_id": TASK_ID,
        "design": CASE["design"],
        "note": CASE["note"],
        "subject_id": CASE["subject"],
        "person_code": f"H{CASE['subject']:02d}",
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
    if write:
        (out_dir / "task.json").write_text(json.dumps({
            "source": {"url": SOURCE_URL, "license": "CC BY 4.0", "md5": SOURCE_MD5},
            "rulebook_source": "TB MED 507, 12 April 2022; see tb_med_507.json",
            "task": task}, indent=2) + "\n")
        (out_dir / "private_ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n")
        (out_dir / "prompt.md").write_text(task["prompt"])
    return task, truth


if __name__ == "__main__":
    _, t = build()
    print(f"{t['task_id']} {t['design']} core {t['core_at_cutoff_c']:.2f} -> "
          f"{t['core_at_cutoff_plus_15_c']:.2f}  expected {t['expected_decision']}; "
          f"rulebook {t['expected_rulebook']}")
