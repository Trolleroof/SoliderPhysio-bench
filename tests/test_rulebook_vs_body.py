"""Unit tests for the 'Rulebook versus body' task (tasks/rulebook_vs_body)."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tasks.rulebook_vs_body import build_task, evaluator

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "tasks" / "rulebook_vs_body"
TABLE = evaluator.load_json(TASK_DIR / "tb_med_507.json")
PUBLIC = evaluator.load_json(TASK_DIR / "task.json")
TASK = evaluator.load_task(TASK_DIR / "task.json")
PRIVATE = evaluator.load_json(TASK_DIR / "private_ground_truth.json")
PUBLIC_TEXT = (TASK_DIR / "task.json").read_text() + (TASK_DIR / "prompt.md").read_text()
SOURCE = build_task.DEFAULT_SOURCE

PERFECT = {
    "rulebook": {"work_rest_min": "NL", "water_qt_per_hr": 0.75,
                 "continuous_work_min": "NL", "continuous_water_qt_per_hr": 1.0},
    "decision": "OVERRIDE",
    "predicted_core_c": PRIVATE["core_at_cutoff_plus_15_c"],
    "confidence": 0.8,
    "reasoning": "x",
}


def _grade(obj):
    return evaluator.grade(json.dumps(obj), TASK, PRIVATE, TABLE)


class TestRulebookTable(unittest.TestCase):
    def test_five_categories_with_flags(self):
        cats = TABLE["heat_categories"]
        self.assertEqual([c["category"] for c in cats], [1, 2, 3, 4, 5])
        self.assertEqual([c["flag"] for c in cats], ["White", "Green", "Yellow", "Red", "Black"])
        self.assertEqual(cats[0]["wbgt_f_min"], 78.0)
        self.assertIsNone(cats[4]["wbgt_f_max"])

    def test_every_cell_present_in_both_tables(self):
        cols = list(TABLE["work_categories"])
        self.assertEqual(cols, ["Easy", "Moderate", "Heavy", "Very Heavy"])
        for name in ("work_rest_table", "continuous_work_table"):
            cells = TABLE[name]["cells"]
            self.assertEqual(sorted(cells), ["1", "2", "3", "4", "5"])
            for cat in cells.values():
                self.assertEqual(list(cat), cols)
                for cell in cat.values():
                    self.assertIn("no_limit", cell)
                    self.assertGreater(cell["water_qt_per_hr"], 0)

    def test_spot_checks_against_published_card(self):
        # Table 1 cells reproduced by DCPH-A (TA-724-MAR23) from TB MED 507, 12 April 2022.
        self.assertEqual(evaluator.lookup(TABLE, "White", "Heavy")["work_rest_min"], "40/20")
        self.assertEqual(evaluator.lookup(TABLE, "Red", "Moderate")["work_rest_min"], "50/10")
        self.assertEqual(evaluator.lookup(TABLE, "Black", "Very Heavy")["work_rest_min"], "10/50")
        self.assertEqual(evaluator.lookup(TABLE, "Black", "Easy")["water_qt_per_hr"], 1.0)
        self.assertEqual(evaluator.lookup(TABLE, "Green", "Moderate")["work_rest_min"], "NL")
        # Table 2 continuous work.
        self.assertEqual(evaluator.lookup(TABLE, "White", "Heavy")["continuous_work_min"], 100)
        self.assertEqual(evaluator.lookup(TABLE, "Red", "Moderate")["continuous_work_min"], 180)
        self.assertEqual(evaluator.lookup(TABLE, "Red", "Moderate")["continuous_water_qt_per_hr"], 1.25)
        self.assertEqual(evaluator.lookup(TABLE, "Black", "Heavy")["continuous_water_qt_per_hr"], 1.5)
        self.assertEqual(evaluator.lookup(TABLE, "Yellow", "Easy")["continuous_work_min"], "NL")

    def test_easy_work_is_never_limited(self):
        for cat in "12345":
            self.assertEqual(evaluator.lookup(TABLE, cat, "Easy")["work_rest_min"], "NL")
            self.assertEqual(evaluator.lookup(TABLE, cat, "Easy")["continuous_work_min"], "NL")

    def test_flag_and_work_aliases(self):
        for flag in ("Yellow", "yellow flag", "YELLOW", "Cat 3", "category 3", "Heat Category 3", 3, "3"):
            self.assertEqual(evaluator.normalize_flag(flag), "3", flag)
        for work in ("Hard", "hard work", "Heavy", "HEAVY WORK"):
            self.assertEqual(evaluator.normalize_work(work, TABLE), "Heavy", work)
        self.assertEqual(evaluator.normalize_work("very heavy", TABLE), "Very Heavy")
        self.assertEqual(evaluator.normalize_work("Very Hard", TABLE), "Very Heavy")

    def test_bad_inputs_raise(self):
        for flag in ("Purple", 0, 6, "", True):
            with self.assertRaises(ValueError):
                evaluator.normalize_flag(flag)
        with self.assertRaises(ValueError):
            evaluator.normalize_work("extreme", TABLE)

    def test_old_2003_card_differs_from_2022(self):
        # The 2003 card said 40/20 for Moderate work at Yellow flag; 2022 says NL.
        self.assertEqual(evaluator.lookup(TABLE, "Yellow", "Moderate")["work_rest_min"], "NL")


class TestPublicFiles(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(TASK["task_id"], "RB-01")
        self.assertEqual(TASK["horizon_min"], 15)
        self.assertEqual(TASK["threshold_c"], 38.5)
        self.assertEqual(TASK["inputs"]["heat_category"], "Yellow")
        self.assertEqual(TASK["inputs"]["heat_category_number"], 3)
        self.assertEqual(TASK["inputs"]["work_category"], "Moderate")
        self.assertEqual(set(TASK["subject_profile"]), {"age_years", "mass_kg"})
        self.assertEqual(TASK["answer_format"], evaluator.ANSWER_FORMAT)

    def test_rows_follow_task_type_1_format(self):
        rows = TASK["rows"]
        self.assertEqual(len(rows), build_task.WINDOW_MIN)
        self.assertEqual([r["time_min"] for r in rows], list(range(build_task.WINDOW_MIN)))
        for r in rows:
            self.assertEqual(tuple(r), evaluator.PUBLIC_ROW_KEYS)
            self.assertIsInstance(r["watts"], int)
            self.assertEqual(r["skin_c"], round(r["skin_c"], 1))
            self.assertIsInstance(r["humidity_pct"], int)
            if r["hr_bpm"] is not None:
                self.assertIsInstance(r["hr_bpm"], int)
                self.assertTrue(30 <= r["hr_bpm"] <= 240)
        self.assertTrue(any(r["hr_bpm"] is None for r in rows), "HR is only logged in blocks")
        self.assertTrue(any(r["hr_bpm"] is not None for r in rows))

    def test_prompt_file_matches_json_prompt(self):
        self.assertEqual((TASK_DIR / "prompt.md").read_text(), TASK["prompt"])

    def test_prompt_contains_scenario_rule_and_table(self):
        p = TASK["prompt"]
        for needle in ("Yellow", "Heat Category 3", "Moderate", "TB MED 507", "12 April 2022",
                       "Table 1", "Table 2", "FOLLOW", "OVERRIDE", "38.5 C", "15 minutes",
                       "Core temperature is NOT measured", evaluator.render_table(TASK["rows"])):
            self.assertIn(needle, p)
        self.assertNotIn("Reference, TB MED 507", p, "default prompt is closed-book")

    def test_open_book_prompt_includes_tables(self):
        p = evaluator.render_prompt(TASK, TABLE, include_table=True)
        self.assertIn("Reference, TB MED 507", p)
        self.assertIn("40/20, 0.75 qt", p)
        self.assertIn("| 4 Red |", p)

    def test_public_files_leak_nothing(self):
        lower = PUBLIC_TEXT.lower()
        # "rectal" appears in the prompt only as the quantity to be estimated; the values do not.
        for needle in ("subject_id", "person_code", "h25", "cutoff", '"sex"', "vo2", "core_at",
                       "device_estimate", "expected_decision", "override_is_correct"):
            self.assertNotIn(needle, lower, needle)
        self.assertNotIn(str(PRIVATE["subject_id"]) + ",", json.dumps(TASK["subject_profile"]))
        self.assertNotIn(f"{PRIVATE['core_at_cutoff_plus_15_c']:.2f}", PUBLIC_TEXT)
        self.assertNotIn(f"{PRIVATE['core_at_cutoff_c']:.2f}", PUBLIC_TEXT)
        self.assertEqual(TASK["rows"][0]["time_min"], 0)
        self.assertNotIn(str(PRIVATE["cutoff_min"]), [str(r["time_min"]) for r in TASK["rows"]])


class TestPrivateFile(unittest.TestCase):
    def test_truth_is_consistent(self):
        self.assertEqual(PRIVATE["task_id"], TASK["task_id"])
        self.assertIsInstance(PRIVATE["subject_id"], int)
        self.assertEqual(PRIVATE["horizon_min"], TASK["horizon_min"])
        self.assertEqual(PRIVATE["threshold_c"], TASK["threshold_c"])
        self.assertEqual(PRIVATE["window_start_min"], PRIVATE["cutoff_min"] - build_task.WINDOW_MIN + 1)
        over = PRIVATE["core_at_cutoff_plus_15_c"] >= PRIVATE["threshold_c"]
        self.assertEqual(PRIVATE["expected_decision"], "OVERRIDE" if over else "FOLLOW")
        self.assertEqual(PRIVATE["override_is_correct"], over)
        self.assertAlmostEqual(PRIVATE["core_change_15_c"],
                               round(PRIVATE["core_at_cutoff_plus_15_c"] - PRIVATE["core_at_cutoff_c"], 2))
        self.assertEqual(PRIVATE["expected_rulebook"],
                         {k: v for k, v in evaluator.lookup(TABLE, "Yellow", "Moderate").items()
                          if k in evaluator.RULEBOOK_FIELDS})
        self.assertTrue(PRIVATE["rulebook_allows_work_through_horizon"])
        self.assertEqual(PRIVATE["scorer"], "tasks.rulebook_vs_body.evaluator.grade")

    def test_this_case_is_the_override_trap(self):
        self.assertEqual(PRIVATE["expected_decision"], "OVERRIDE")
        self.assertLess(PRIVATE["core_at_cutoff_c"], PRIVATE["threshold_c"])
        self.assertGreaterEqual(PRIVATE["core_at_cutoff_plus_15_c"], PRIVATE["threshold_c"] + 0.3)
        self.assertFalse(PRIVATE["power_dropped_in_window"])
        self.assertNotIn(PRIVATE["subject_id"], {3, 4, 21, 23}, "must not reuse a Task Type 1 person")


@unittest.skipUnless(SOURCE.exists(), "Figshare workbook not present")
class TestRebuild(unittest.TestCase):
    def test_build_is_deterministic_and_matches_committed_files(self):
        task, truth = build_task.build(write=False)
        self.assertEqual(task, TASK)
        self.assertEqual(truth, PRIVATE)

    def test_window_matches_task_type_1_builder(self):
        from tasks.keep_going import build_tasks as kg
        person = kg.load_workbook(SOURCE)[PRIVATE["subject_id"]]
        self.assertEqual(kg.make_window(person, PRIVATE["cutoff_min"]), TASK["rows"])
        self.assertEqual(person["core"][PRIVATE["cutoff_min"] + 15], PRIVATE["core_at_cutoff_plus_15_c"])

    def test_build_writes_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_task.build(out_dir=tmp)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["private_ground_truth.json", "prompt.md", "task.json"])


class TestParsing(unittest.TestCase):
    def test_quantities(self):
        for raw, want in (("¾", 0.75), ("3/4", 0.75), ("3/4 qt/hr", 0.75), ("1¼", 1.25), ("1 1/2", 1.5),
                          ("1 quart per hour", 1.0), (0.5, 0.5), (1, 1.0), ("0.75 qt", 0.75)):
            self.assertAlmostEqual(evaluator.parse_quantity(raw), want, msg=raw)
        for raw in (None, "NL", "", True):
            self.assertIsNone(evaluator.parse_quantity(raw))

    def test_work_rest(self):
        for raw, want in (("NL", "NL"), ("no limit", "NL"), (None, "NL"), ("40/20", "40/20"),
                          ("40 / 20", "40/20"), ("40 min work / 20 min rest", "40/20"), ("40:20", "40/20"),
                          ({"work_min": 40, "rest_min": 20}, "40/20"), ({"no_limit": True}, "NL"),
                          ({"work_min": "NL"}, "NL")):
            self.assertEqual(evaluator.parse_work_rest(raw), want, raw)
        for raw in ("", "forty", 40, {"work_min": 40}):
            self.assertIsNone(evaluator.parse_work_rest(raw), raw)

    def test_no_limit_or_int(self):
        for raw, want in (("NL", "NL"), (None, "NL"), ("unlimited", "NL"), (100, 100), ("100 min", 100), (70.0, 70)):
            self.assertEqual(evaluator.parse_no_limit_or_int(raw), want, raw)
        self.assertIsNone(evaluator.parse_no_limit_or_int("many"))
        self.assertIsNone(evaluator.parse_no_limit_or_int(True))

    def test_decisions(self):
        self.assertEqual(evaluator.parse_decision("OVERRIDE"), "OVERRIDE")
        self.assertEqual(evaluator.parse_decision("override: pull him now"), "OVERRIDE")
        self.assertEqual(evaluator.parse_decision("Follow"), "FOLLOW")
        self.assertEqual(evaluator.parse_decision("pull"), "OVERRIDE")
        self.assertEqual(evaluator.parse_decision("continue"), "FOLLOW")
        self.assertIsNone(evaluator.parse_decision("follow or override"))
        self.assertEqual(evaluator.parse_decision("decision: OVERRIDE (not follow)"), "OVERRIDE")
        self.assertIsNone(evaluator.parse_decision(""))
        self.assertIsNone(evaluator.parse_decision(None))

    def test_response_json_in_fence_and_prose(self):
        text = "Sure.\n```json\n" + json.dumps(PERFECT) + "\n```\nDone."
        parsed = evaluator.parse_response(text)
        self.assertEqual(parsed["parse_mode"], "json")
        self.assertEqual(parsed["decision"], "OVERRIDE")
        self.assertEqual(parsed["rulebook"]["work_rest_min"], "NL")
        self.assertAlmostEqual(parsed["predicted_core_c"], PERFECT["predicted_core_c"])

    def test_response_plain_text_fallback(self):
        parsed = evaluator.parse_response("I would OVERRIDE the table and pull him.")
        self.assertEqual(parsed["decision"], "OVERRIDE")
        self.assertEqual(parsed["parse_mode"], "text")
        self.assertIsNone(parsed["rulebook"])
        self.assertIsNone(evaluator.parse_response("Follow or override, hard to say.")["decision"])
        self.assertEqual(evaluator.parse_response("")["parse_mode"], "none")


class TestGrading(unittest.TestCase):
    def test_perfect_answer(self):
        g = _grade(PERFECT)
        self.assertEqual(g["total"], 1.0)
        self.assertTrue(g["pass"])
        self.assertTrue(all(g["rulebook"]["matches"].values()))
        self.assertEqual(g["body"]["core_abs_error_c"], 0.0)
        self.assertTrue(g["body"]["core_within_tolerance"])
        self.assertIsNone(g["body"]["error_type"])

    def test_flexible_rulebook_spellings_still_match(self):
        obj = dict(PERFECT, rulebook={"work_rest": "no limit", "water": "¾ qt/hr",
                                      "continuous_work": None, "continuous_water": "1 quart/hour"})
        self.assertTrue(_grade(obj)["rulebook"]["pass"])

    def test_old_2003_card_fails_rulebook_half(self):
        obj = dict(PERFECT, rulebook=dict(PERFECT["rulebook"], work_rest_min="40/20"))
        g = _grade(obj)
        self.assertFalse(g["rulebook"]["pass"])
        self.assertEqual(g["rulebook"]["score"], 0.75)
        self.assertFalse(g["rulebook"]["matches"]["work_rest_min"])
        self.assertTrue(g["body"]["pass"])
        self.assertAlmostEqual(g["total"], 0.5 * 0.75 + 0.5)
        self.assertFalse(g["pass"])

    def test_missing_rulebook_key_is_not_read_as_no_limit(self):
        obj = dict(PERFECT, rulebook={"water_qt_per_hr": 0.75, "continuous_water_qt_per_hr": 1})
        g = _grade(obj)
        self.assertEqual(g["rulebook"]["score"], 0.5)
        self.assertIsNone(g["rulebook"]["parsed"]["work_rest_min"])

    def test_wrong_decision_is_missed_override(self):
        obj = dict(PERFECT, decision="FOLLOW", predicted_core_c=38.2)
        g = _grade(obj)
        self.assertTrue(g["rulebook"]["pass"])
        self.assertEqual(g["body"]["score"], 0.0)
        self.assertEqual(g["body"]["error_type"], "missed_override")
        self.assertAlmostEqual(g["body"]["core_abs_error_c"], round(PRIVATE["core_at_cutoff_plus_15_c"] - 38.2, 2))
        self.assertFalse(g["body"]["core_within_tolerance"])
        self.assertAlmostEqual(g["total"], 0.5)
        self.assertFalse(g["pass"])

    def test_false_override_on_a_follow_case(self):
        truth = dict(PRIVATE, expected_decision="FOLLOW", core_at_cutoff_plus_15_c=38.2, override_is_correct=False)
        g = evaluator.grade(json.dumps(PERFECT), TASK, truth, TABLE)
        self.assertEqual(g["body"]["error_type"], "false_override")
        self.assertEqual(g["body"]["score"], 0.0)

    def test_unparsed_and_garbage(self):
        g = _grade({"rulebook": PERFECT["rulebook"], "predicted_core_c": 39})
        self.assertEqual(g["body"]["error_type"], "unparsed")
        self.assertEqual(g["body"]["score"], 0.0)
        self.assertEqual(g["total"], 0.5)
        g = evaluator.grade("no json here", TASK, PRIVATE, TABLE)
        self.assertEqual(g["total"], 0.0)
        self.assertEqual(g["body"]["parse_mode"], "none")
        self.assertFalse(g["pass"])
        g = evaluator.grade("", TASK, PRIVATE, TABLE)
        self.assertEqual(g["total"], 0.0)

    def test_grade_uses_committed_files_by_default(self):
        g = evaluator.grade(json.dumps(PERFECT))
        self.assertEqual(g["task_id"], "RB-01")
        self.assertTrue(g["pass"])

    def test_dict_input_accepted(self):
        self.assertTrue(evaluator.grade(PERFECT, TASK, PRIVATE, TABLE)["pass"])


class TestCLI(unittest.TestCase):
    PY = sys.executable
    SCRIPT = str(TASK_DIR / "evaluator.py")

    def test_print_prompt(self):
        out = subprocess.run([self.PY, self.SCRIPT, "--print-prompt"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), TASK["prompt"].strip())
        out = subprocess.run([self.PY, self.SCRIPT, "--print-prompt", "--with-table"], capture_output=True, text=True, cwd=ROOT)
        self.assertIn("Reference, TB MED 507", out.stdout)

    def test_grade_file_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.txt"
            good.write_text("```json\n" + json.dumps(PERFECT) + "\n```")
            bad = Path(tmp) / "bad.txt"
            bad.write_text(json.dumps(dict(PERFECT, decision="FOLLOW")))
            scores = Path(tmp) / "scores.json"
            out = subprocess.run([self.PY, self.SCRIPT, "--response", str(good), "--out", str(scores)],
                                 capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(json.loads(scores.read_text())["pass"])
            out = subprocess.run([self.PY, self.SCRIPT, "--response", str(bad)], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(out.returncode, 1)
            self.assertEqual(json.loads(out.stdout)["body"]["error_type"], "missed_override")

    def test_main_in_process(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = evaluator.main(["--print-prompt"])
        self.assertEqual(code, 0)
        self.assertIn("Answer with one JSON object", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
