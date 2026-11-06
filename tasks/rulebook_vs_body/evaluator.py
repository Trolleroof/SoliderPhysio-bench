"""Grade 'Rulebook versus body' answers (Task Type 2, one no-code task).

Two halves, each worth half of the total:

1. Rulebook half (deterministic). The model must reproduce the TB MED 507
   (12 April 2022) prescription for the stated heat category and work category:
   Table 1 work/rest minutes and water intake, and Table 2 continuous work
   duration and water intake. The four fields are exact-match graded against
   ``tb_med_507.json``. ``score`` is the fraction of fields right; ``pass`` needs all four.

2. Body half (judgment), graded like Task Type 1 (``tasks/keep_going``): the
   FOLLOW/OVERRIDE decision is the score (1 or 0), the +15 min core-temperature
   estimate is reported as an absolute error against the measured rectal value,
   and the failure is typed ``missed_override``, ``false_override`` or ``unparsed``.

No network, no third-party packages, no LLM judge.

Library use:
    from tasks.rulebook_vs_body import evaluator
    evaluator.grade(model_text) -> dict

CLI:
    python tasks/rulebook_vs_body/evaluator.py --response reply.txt
    python tasks/rulebook_vs_body/evaluator.py --print-prompt [--with-table]
"""
from __future__ import annotations

import argparse
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TABLE_PATH = HERE / "tb_med_507.json"
TASK_PATH = HERE / "task.json"
TRUTH_PATH = HERE / "private_ground_truth.json"

RULEBOOK_WEIGHT = 0.5
BODY_WEIGHT = 0.5
CORE_TOLERANCE_C = 0.5   # secondary metric only: was the +15 estimate within this of the thermometer

RULEBOOK_FIELDS = (
    "work_rest_min",
    "water_qt_per_hr",
    "continuous_work_min",
    "continuous_water_qt_per_hr",
)
PUBLIC_ROW_KEYS = ("time_min", "hr_bpm", "skin_c", "room_temp_c", "humidity_pct", "watts")

FLAG_NAMES = {"white": "1", "green": "2", "yellow": "3", "red": "4", "black": "5"}
NL_TOKENS = {"nl", "no limit", "nolimit", "no-limit", "unlimited", "none", "n/a", "continuous"}
_VULGAR = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3"}


# --------------------------------------------------------------------------
# Table lookup
# --------------------------------------------------------------------------
def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_task(path: Path | str = TASK_PATH) -> dict[str, Any]:
    """Return the task record; task.json wraps it under 'task' next to source metadata."""
    data = load_json(path)
    return data["task"] if "task" in data else data


def normalize_flag(flag: Any) -> str:
    """Map 'Yellow', 'yellow flag', 'Cat 3', 3 or '3' to the category key '3'."""
    if isinstance(flag, bool):
        raise ValueError(f"unrecognised heat category: {flag!r}")
    if isinstance(flag, (int, float)):
        key = str(int(flag))
    else:
        text = str(flag).strip().lower()
        text = re.sub(r"\b(heat|cat(egory)?|flag)\b", " ", text).strip()
        key = FLAG_NAMES.get(text)
        if key is None:
            match = re.fullmatch(r"\s*([1-5])\s*", text)
            if match is None:
                raise ValueError(f"unrecognised heat category: {flag!r}")
            key = match.group(1)
    if key not in {"1", "2", "3", "4", "5"}:
        raise ValueError(f"heat category out of range: {flag!r}")
    return key


def normalize_work(work: Any, table: dict[str, Any]) -> str:
    """Map 'hard', 'Heavy work' or 'very heavy' to the canonical table column."""
    text = re.sub(r"\bwork\b", " ", str(work).strip().lower())
    text = re.sub(r"\s+", " ", text).strip()
    for name, spec in table["work_categories"].items():
        candidates = [name.lower()] + [alias.lower() for alias in spec.get("aliases", [])]
        if text in candidates:
            return name
    raise ValueError(f"unrecognised work category: {work!r}")


def lookup(table: dict[str, Any], flag: Any, work: Any) -> dict[str, Any]:
    """Return the four graded rulebook fields for a flag and work category."""
    cat = normalize_flag(flag)
    column = normalize_work(work, table)
    wr = table["work_rest_table"]["cells"][cat][column]
    cw = table["continuous_work_table"]["cells"][cat][column]
    return {
        "heat_category": int(cat),
        "flag": next(h["flag"] for h in table["heat_categories"] if str(h["category"]) == cat),
        "work_category": column,
        "work_rest_min": "NL" if wr["no_limit"] else f"{wr['work_min']}/{wr['rest_min']}",
        "water_qt_per_hr": float(wr["water_qt_per_hr"]),
        "continuous_work_min": "NL" if cw["no_limit"] else int(cw["max_work_min"]),
        "continuous_water_qt_per_hr": float(cw["water_qt_per_hr"]),
    }


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------
def first_json_object(text: str) -> dict[str, Any] | None:
    """Return the first parseable JSON object in text, tolerating code fences and prose."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    for start in (m.start() for m in re.finditer(r"\{", text)):
        depth = 0
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:j + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def parse_quantity(value: Any) -> float | None:
    """Parse 0.75, '3/4', '¾', '1¼', '1 1/2 qt/hr' to a float. Unit words are ignored."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    for glyph, frac in _VULGAR.items():
        text = text.replace(glyph, " " + frac)
    tokens = re.findall(r"\d+/\d+|\d+(?:\.\d+)?", text)
    if not tokens:
        return None
    return float(sum(Fraction(token) for token in tokens))


def _is_nl(text: str) -> bool:
    return text in NL_TOKENS or text.startswith("no limit") or text.startswith("nl")


def parse_no_limit_or_int(value: Any) -> str | int | None:
    """Return 'NL', an int, or None (unparseable)."""
    if value is None:
        return "NL"
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).strip().lower()
    if _is_nl(text):
        return "NL"
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def parse_work_rest(value: Any) -> str | None:
    """Return 'NL', 'W/R' such as '40/20', or None."""
    if value is None:
        return "NL"
    if isinstance(value, dict):
        work = value.get("work_min", value.get("work"))
        rest = value.get("rest_min", value.get("rest"))
        if value.get("no_limit") or parse_no_limit_or_int(work) == "NL":
            return "NL"
        if work is None or rest is None:
            return None
        return f"{int(work)}/{int(rest)}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None
    text = str(value).strip().lower()
    if _is_nl(text):
        return "NL"
    match = re.search(r"(\d+)\s*(?:min(?:utes)?)?\s*(?:work)?\s*(?:/|:|-|,)\s*(\d+)", text)
    if match:
        return f"{int(match.group(1))}/{int(match.group(2))}"
    return None


def _verdict_word(text: str) -> str | None:
    """The standalone verdict word, if exactly one appears or an explicit 'decision: X' does."""
    upper = text.upper()
    has_override = re.search(r"\bOVERRIDE\b", upper) is not None
    has_follow = re.search(r"\bFOLLOW\b", upper) is not None
    if has_override != has_follow:
        return "OVERRIDE" if has_override else "FOLLOW"
    if has_override and has_follow:
        match = re.search(r"DECISION\**\s*[:=]?\s*\**\s*(FOLLOW|OVERRIDE)\b", upper)
        return match.group(1) if match else None
    return None


def parse_decision(value: Any) -> str | None:
    """Decision field of the JSON answer: the verdict word, else a close synonym."""
    text = str(value or "").strip()
    if not text:
        return None
    verdict = _verdict_word(text)
    if verdict is not None:
        return verdict
    if re.search(r"\b(PULL|STOP|HALT|INTERVENE|REMOVE|WITHDRAW)\b", text.upper()):
        return "OVERRIDE"
    if re.search(r"\b(CONTINUE|COMPLY|KEEP|PROCEED|ADHERE)\b", text.upper()):
        return "FOLLOW"
    return None


def parse_response(text: Any) -> dict[str, Any]:
    """Extract rulebook fields, decision and core estimate from raw model text.

    Returns {'rulebook': dict|None, 'decision': 'FOLLOW'|'OVERRIDE'|None,
             'predicted_core_c': float|None, 'parse_mode': 'json'|'text'|'none'}.
    """
    out: dict[str, Any] = {"rulebook": None, "decision": None, "predicted_core_c": None, "parse_mode": "none"}
    if isinstance(text, dict):
        obj: dict[str, Any] | None = text
    elif isinstance(text, str) and text.strip():
        obj = first_json_object(text)
    else:
        return out
    if obj is not None:
        out["parse_mode"] = "json"
        rulebook = obj.get("rulebook")
        out["rulebook"] = rulebook if isinstance(rulebook, dict) else None
        out["decision"] = parse_decision(obj.get("decision"))
        out["predicted_core_c"] = parse_quantity(obj.get("predicted_core_c"))
        if out["decision"] is not None:
            return out
    if isinstance(text, str):
        # Plain-text fallback: a standalone verdict word in the reply (synonyms are not
        # trusted here because the prompt itself talks about pulling him).
        decision = _verdict_word(text)
        if decision is not None:
            out["decision"] = decision
            if out["parse_mode"] == "none":
                out["parse_mode"] = "text"
    return out


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------
def grade_rulebook(rulebook: dict[str, Any] | None, expected: dict[str, Any]) -> dict[str, Any]:
    rulebook = rulebook if isinstance(rulebook, dict) else {}
    aliases = {
        "work_rest_min": ("work_rest_min", "work_rest"),
        "water_qt_per_hr": ("water_qt_per_hr", "water"),
        "continuous_work_min": ("continuous_work_min", "continuous_work"),
        "continuous_water_qt_per_hr": ("continuous_water_qt_per_hr", "continuous_water"),
    }
    parsers = {
        "work_rest_min": parse_work_rest,
        "water_qt_per_hr": parse_quantity,
        "continuous_work_min": parse_no_limit_or_int,
        "continuous_water_qt_per_hr": parse_quantity,
    }
    parsed: dict[str, Any] = {}
    for field in RULEBOOK_FIELDS:
        present = [k for k in aliases[field] if k in rulebook]
        # An absent key is not an answer; only an explicit null or "NL" means no limit.
        parsed[field] = parsers[field](rulebook[present[0]]) if present else None
    matches = {}
    for field in RULEBOOK_FIELDS:
        exp, got = expected[field], parsed[field]
        if isinstance(exp, float):
            matches[field] = got is not None and abs(got - exp) < 1e-6
        else:
            matches[field] = got == exp
    score = sum(matches.values()) / len(RULEBOOK_FIELDS)
    return {
        "expected": {f: expected[f] for f in RULEBOOK_FIELDS},
        "parsed": parsed,
        "matches": matches,
        "score": score,
        "pass": score == 1.0,
    }


def grade_body(parsed: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    expected = truth["expected_decision"]
    truth_c = float(truth["core_at_cutoff_plus_15_c"])
    est = parsed["predicted_core_c"]
    correct = parsed["decision"] == expected
    err = None if est is None else round(abs(est - truth_c), 2)
    return {
        "expected_decision": expected,
        "model_decision": parsed["decision"],
        "decision_correct": bool(correct),
        "score": 1.0 if correct else 0.0,
        "pass": bool(correct),
        "parse_mode": parsed["parse_mode"],
        "core_truth_c": truth_c,
        "core_estimate_c": est,
        "core_abs_error_c": err,
        "core_within_tolerance": None if err is None else bool(err <= CORE_TOLERANCE_C),
        "error_type": (None if correct else
                       "unparsed" if parsed["decision"] is None else
                       "missed_override" if expected == "OVERRIDE" else "false_override"),
    }


def grade(
    response: Any,
    task: dict[str, Any] | None = None,
    truth: dict[str, Any] | None = None,
    table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grade one raw model reply (string or already-decoded dict)."""
    task = task if task is not None else load_task(TASK_PATH)
    truth = truth if truth is not None else load_json(TRUTH_PATH)
    table = table if table is not None else load_json(TABLE_PATH)
    parsed = parse_response(response)
    expected = lookup(table, task["inputs"]["heat_category"], task["inputs"]["work_category"])
    rulebook = grade_rulebook(parsed["rulebook"], expected)
    body = grade_body(parsed, truth)
    return {
        "task_id": task["task_id"],
        "rulebook": rulebook,
        "body": body,
        "total": RULEBOOK_WEIGHT * rulebook["score"] + BODY_WEIGHT * body["score"],
        "pass": rulebook["pass"] and body["pass"],
    }


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------
ANSWER_FORMAT = {
    "rulebook": {
        "work_rest_min": "Table 1 work/rest minutes per hour as \"NL\" or \"<work>/<rest>\", e.g. \"40/20\"",
        "water_qt_per_hr": "Table 1 water intake, quarts per hour, one number, e.g. 0.75",
        "continuous_work_min": "Table 2 continuous work limit as \"NL\" or integer minutes",
        "continuous_water_qt_per_hr": "Table 2 water intake, quarts per hour, one number",
    },
    "decision": "FOLLOW or OVERRIDE",
    "predicted_core_c": "your best estimate of his rectal core temperature (C) 15 minutes from now, one number",
    "confidence": "probability (0 to 1) that OVERRIDE is the correct call",
    "reasoning": "two to five sentences",
}


def _fmt(v: Any) -> str:
    return "" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))


def render_table(rows: list[dict[str, Any]]) -> str:
    head = "| min | HR (bpm) | skin (C) | room (C) | RH (%) | watts |"
    sep = "|---:|---:|---:|---:|---:|---:|"
    body = ["| " + " | ".join(_fmt(r[k]) for k in PUBLIC_ROW_KEYS) + " |" for r in rows]
    return "\n".join([head, sep] + body)


def render_reference_table(table: dict[str, Any]) -> str:
    cols = list(table["work_categories"].keys())
    lines = [f"{table['work_rest_table']['title']} (work/rest min per hour, water qt/hr)"]
    lines.append("| Cat | WBGT (F) | " + " | ".join(cols) + " |")
    lines.append("|---|---|" + "---|" * len(cols))
    for cat in table["heat_categories"]:
        key = str(cat["category"])
        cells = []
        for col in cols:
            cell = table["work_rest_table"]["cells"][key][col]
            wr = "NL" if cell["no_limit"] else f"{cell['work_min']}/{cell['rest_min']}"
            cells.append(f"{wr}, {cell['water_qt_per_hr']:g} qt")
        hi = "+" if cat["wbgt_f_max"] is None else f" to {cat['wbgt_f_max']}"
        lines.append(f"| {key} {cat['flag']} | {cat['wbgt_f_min']:g}{hi} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"{table['continuous_work_table']['title']} (max work min, water qt/hr)")
    lines.append("| Cat | " + " | ".join(cols) + " |")
    lines.append("|---|" + "---|" * len(cols))
    for cat in table["heat_categories"]:
        key = str(cat["category"])
        cells = []
        for col in cols:
            cell = table["continuous_work_table"]["cells"][key][col]
            cw = "NL" if cell["no_limit"] else str(cell["max_work_min"])
            cells.append(f"{cw}, {cell['water_qt_per_hr']:g} qt")
        lines.append(f"| {key} {cat['flag']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_prompt(task: dict[str, Any], table: dict[str, Any] | None = None, include_table: bool = False) -> str:
    inputs = task["inputs"]
    rows = task["rows"]
    demo = task["subject_profile"]
    last = rows[-1]["time_min"]
    horizon = task["horizon_min"]
    threshold = task["threshold_c"]
    reference = ""
    if include_table:
        reference = "\nReference, TB MED 507 (12 April 2022):\n\n" + render_reference_table(table or load_json(TABLE_PATH)) + "\n"
    return f"""You are the medic advising a small-unit leader during a hot-weather training session. The session runs under the unit's {inputs['heat_category']} flag (Heat Category {inputs['heat_category_number']}) and the leader's risk card classifies the activity as {inputs['work_category']} work. Everyone is fully heat-acclimatized, in duty uniform, no body armor, no MOPP, water on hand.

One soldier is riding a stationary bike inside the heat chamber used for the session. He has been riding for a while already. The table below is the last {len(rows)} minutes of his wearable and chamber log, ending now (minute {last}). Core temperature is NOT measured. Blank cells mean that value was not logged that minute.

Soldier: age {demo['age_years']} years, body mass {demo['mass_kg']} kg.

{render_table(rows)}
{reference}
Two questions.

(a) Rulebook. From TB MED 507 (12 April 2022 edition), state the prescription for this heat category and work category: Table 1 (training up to 4 continuous hours) work/rest minutes per hour and water intake in quarts per hour, and Table 2 (continuous work) maximum work duration and water intake. Write NL where the table sets no limit.

(b) Body. Decide whether to FOLLOW the Table 1 prescription for this soldier over the next {horizon} minutes (he keeps riding at his current workload with the prescribed water) or OVERRIDE it (pull him off the bike now, rest, cool and monitor, whatever the table allows). Rule: OVERRIDE is correct if his rectal core temperature {horizon} minutes from now would be at or above {threshold:.1f} C if he keeps going; otherwise FOLLOW is correct. Also estimate that core temperature.

Do not run code. Reason from the trace and from physiology.

Answer with one JSON object and nothing else:
{json.dumps(ANSWER_FORMAT, indent=2)}
"""


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--response", type=Path, help="file holding the raw model reply")
    parser.add_argument("--task", type=Path, default=TASK_PATH)
    parser.add_argument("--truth", type=Path, default=TRUTH_PATH)
    parser.add_argument("--table", type=Path, default=TABLE_PATH)
    parser.add_argument("--out", type=Path, help="write the grade JSON here as well")
    parser.add_argument("--print-prompt", action="store_true", help="print the public prompt and exit")
    parser.add_argument("--with-table", action="store_true", help="open-book variant: include the TB MED 507 tables")
    args = parser.parse_args(argv)

    task = load_task(args.task)
    table = load_json(args.table)
    if args.print_prompt:
        print(render_prompt(task, table, include_table=args.with_table))
        return 0
    if args.response is None:
        parser.error("--response is required unless --print-prompt is given")
    result = grade(args.response.read_text(encoding="utf-8"), task, load_json(args.truth), table)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
