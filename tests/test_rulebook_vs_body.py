"""Unit tests for the 'Rulebook versus body' task suite (tasks/rulebook_vs_body)."""
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tasks.rulebook_vs_body import build_task, evaluator

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "tasks" / "rulebook_vs_body"
TABLE = evaluator.load_json(TASK_DIR / "tb_med_507.json")
TASKS = evaluator.load_tasks(TASK_DIR / "task.json")
TRUTH = evaluator.load_ground_truth(TASK_DIR / "private_ground_truth.json")
PUBLIC_TEXT = (TASK_DIR / "task.json").read_text() + "".join(
    p.read_text() for p in sorted((TASK_DIR / "prompts").glob("*.md")))
SOURCE = build_task.DEFAULT_SOURCE

RULEBOOK = {"work_rest_min": "NL", "water_qt_per_hr": 0.75,
            "continuous_work_min": "NL", "continuous_water_qt_per_hr": 1.0}


def answer(task_id, decision=None, core=None, rulebook=None):
    truth = TRUTH[task_id]
    return {
        "rulebook": RULEBOOK if rulebook is None else rulebook,
        "decision": truth["expected_decision"] if decision is None else decision,
        "predicted_core_c": truth["core_at_cutoff_plus_15_c"] if core is None else core,
        "confidence": 0.7,
        "reasoning": "x",
    }


def grade(task_id, obj):
    return evaluator.grade(task_id, json.dumps(obj), TASKS, TRUTH, TABLE)


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
        # Cells reproduced by DCPH-A (TA-724-MAR23) from TB MED 507, 12 April 2022.
        self.assertEqual(evaluator.lookup(TABLE, "White", "Heavy")["work_rest_min"], "40/20")
        self.assertEqual(evaluator.lookup(TABLE, "Red", "Moderate")["work_rest_min"], "50/10")
        self.assertEqual(evaluator.lookup(TABLE, "Black", "Very Heavy")["work_rest_min"], "10/50")
        self.assertEqual(evaluator.lookup(TABLE, "Black", "Easy")["water_qt_per_hr"], 1.0)
        self.assertEqual(evaluator.lookup(TABLE, "Green", "Moderate")["work_rest_min"], "NL")
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


class TestSuiteShape(unittest.TestCase):
    def test_ids_match_across_files(self):
        self.assertEqual(sorted(TASKS), ["RB-01", "RB-02"])
        self.assertEqual(sorted(TRUTH), sorted(TASKS))
        self.assertEqual(sorted(p.stem for p in (TASK_DIR / "prompts").glob("*.md")), sorted(TASKS))
        self.assertEqual(build_task.TASK_IDS, ["RB-01", "RB-02"])

    def test_one_trap_one_control_with_opposite_answers(self):
        self.assertEqual(TRUTH["RB-01"]["role"], "trap")
        self.assertEqual(TRUTH["RB-01"]["expected_decision"], "OVERRIDE")
        self.assertEqual(TRUTH["RB-02"]["role"], "control")
        self.assertEqual(TRUTH["RB-02"]["expected_decision"], "FOLLOW")

    def test_same_rulebook_cell_for_both(self):
        for task in TASKS.values():
            self.assertEqual(task["inputs"]["heat_category"], "Yellow")
            self.assertEqual(task["inputs"]["heat_category_number"], 3)
            self.assertEqual(task["inputs"]["work_category"], "Moderate")
        self.assertEqual(TRUTH["RB-01"]["expected_rulebook"], TRUTH["RB-02"]["expected_rulebook"])

    def test_control_wearable_looks_worse_than_trap(self):
        # The point of the pair: heart rate is not the answer.
        hr = {tid: max(r["hr_bpm"] for r in t["rows"] if r["hr_bpm"] is not None) for tid, t in TASKS.items()}
        self.assertGreater(hr["RB-02"], hr["RB-01"] + 15)

    def test_two_different_people(self):
        subjects = {t["subject_id"] for t in TRUTH.values()}
        self.assertEqual(len(subjects), len(TRUTH))

    def test_labels_differ_from_task_type_1_on_same_person(self):
        # Task Type 1 reuses these people at other cutoffs; no prediction target may coincide.
        from tasks.keep_going import build_tasks as kg
        kg_targets = {(c["subject"], c["cutoff"] + kg.HORIZON_MIN) for c in kg.CASES}
        for truth in TRUTH.values():
            self.assertNotIn((truth["subject_id"], truth["cutoff_min"] + truth["horizon_min"]), kg_targets)


class TestPublicFiles(unittest.TestCase):
    def test_shape(self):
        for task in TASKS.values():
            self.assertEqual(task["horizon_min"], 15)
            self.assertEqual(task["threshold_c"], 38.5)
            self.assertEqual(set(task["subject_profile"]), {"age_years", "mass_kg"})
            self.assertEqual(task["answer_format"], evaluator.ANSWER_FORMAT)

    def test_rows_follow_task_type_1_format(self):
        for task in TASKS.values():
            rows = task["rows"]
            self.assertEqual(len(rows), build_task.WINDOW_MIN)
            # Real ride minutes, as in Task Type 1: the window ends at the cutoff minute.
            cutoff = TRUTH[task["task_id"]]["cutoff_min"]
            self.assertEqual([r["time_min"] for r in rows],
                             list(range(cutoff - build_task.WINDOW_MIN + 1, cutoff + 1)))
            for r in rows:
                self.assertEqual(tuple(r), evaluator.PUBLIC_ROW_KEYS)
                self.assertIsInstance(r["watts"], int)
                self.assertEqual(r["skin_c"], round(r["skin_c"], 1))
                self.assertIsInstance(r["humidity_pct"], int)
                if r["hr_bpm"] is not None:
                    self.assertIsInstance(r["hr_bpm"], int)
                    self.assertTrue(30 <= r["hr_bpm"] <= 240)
            self.assertTrue(any(r["hr_bpm"] is None for r in rows), "HR is only logged in blocks")

    def test_prompt_files_match_json_prompts(self):
        for tid, task in TASKS.items():
            self.assertEqual((TASK_DIR / "prompts" / f"{tid}.md").read_text(), task["prompt"])

    def test_prompt_contains_scenario_rule_and_table(self):
        for task in TASKS.values():
            p = task["prompt"]
            for needle in ("Yellow", "Heat Category 3", "Moderate", "TB MED 507", "12 April 2022",
                           "Table 1", "Table 2", "FOLLOW", "OVERRIDE", "38.5 C", "15 minutes",
                           "Core temperature is NOT measured", "ride minute", evaluator.render_table(task["rows"])):
                self.assertIn(needle, p)
            self.assertNotIn("Reference, TB MED 507", p, "default prompt is closed-book")

    def test_open_book_prompt_includes_tables(self):
        p = evaluator.render_prompt(TASKS["RB-01"], TABLE, include_table=True)
        self.assertIn("Reference, TB MED 507", p)
        self.assertIn("40/20, 0.75 qt", p)
        self.assertIn("| 4 Red |", p)

    def test_public_files_leak_nothing(self):
        lower = PUBLIC_TEXT.lower()
        # "rectal" appears in the prompt only as the quantity to be estimated; values do not.
        for needle in ("subject_id", "person_code", "cutoff", '"sex"', "vo2", "core_at", "role",
                       "trap", "control", "device_estimate", "expected_decision", "override_is_correct"):
            self.assertNotIn(needle, lower, needle)
        for truth in TRUTH.values():
            self.assertNotIn(truth["person_code"].lower(), lower)
            self.assertNotIn(f"{truth['core_at_cutoff_plus_15_c']:.2f}", PUBLIC_TEXT)
            self.assertNotIn(f"{truth['core_at_cutoff_c']:.2f}", PUBLIC_TEXT)

    def test_public_ids_carry_no_design_hint(self):
        self.assertEqual(sorted(TASKS), ["RB-01", "RB-02"])
        # Only the ride-minute numbers may differ above the soldier line.
        heads = [re.sub(r"\d+ minutes|ride minute \d+", "N", t["prompt"].split("Soldier:")[0])
                 for t in TASKS.values()]
        self.assertEqual(heads[0], heads[1])


class TestPrivateFile(unittest.TestCase):
    def test_truth_is_consistent(self):
        for tid, truth in TRUTH.items():
            self.assertEqual(truth["horizon_min"], TASKS[tid]["horizon_min"])
            self.assertEqual(truth["threshold_c"], TASKS[tid]["threshold_c"])
            self.assertEqual(truth["window_start_min"], truth["cutoff_min"] - build_task.WINDOW_MIN + 1)
            over = truth["core_at_cutoff_plus_15_c"] >= truth["threshold_c"]
            self.assertEqual(truth["expected_decision"], "OVERRIDE" if over else "FOLLOW")
            self.assertEqual(truth["override_is_correct"], over)
            self.assertAlmostEqual(truth["core_change_15_c"],
                                   round(truth["core_at_cutoff_plus_15_c"] - truth["core_at_cutoff_c"], 2))
            self.assertEqual(truth["expected_rulebook"], RULEBOOK)
            self.assertTrue(truth["rulebook_allows_work_through_horizon"])
            self.assertFalse(truth["power_dropped_in_window"])

    def test_labels_are_not_marginal(self):
        trap, control = TRUTH["RB-01"], TRUTH["RB-02"]
        self.assertLess(trap["core_at_cutoff_c"], trap["threshold_c"])
        self.assertGreaterEqual(trap["core_at_cutoff_plus_15_c"], trap["threshold_c"] + 0.3)
        self.assertLess(control["peak_core_next_15_c"], control["threshold_c"] - 0.1)


@unittest.skipUnless(SOURCE.exists(), "Figshare workbook not present")
class TestRebuild(unittest.TestCase):
    def test_build_is_deterministic_and_matches_committed_files(self):
        public, private = build_task.build(write=False)
        self.assertEqual({t["task_id"]: t for t in public}, TASKS)
        self.assertEqual({t["task_id"]: t for t in private}, TRUTH)

    def test_windows_match_task_type_1_builder(self):
        from tasks.keep_going import build_tasks as kg
        people = kg.load_workbook(SOURCE)
        for tid, truth in TRUTH.items():
            person = people[truth["subject_id"]]
            self.assertEqual(kg.make_window(person, truth["cutoff_min"]), TASKS[tid]["rows"])
            self.assertEqual(person["core"][truth["cutoff_min"] + 15], truth["core_at_cutoff_plus_15_c"])

    def test_build_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_task.build(out_dir=tmp)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["private_ground_truth.json", "prompts", "task.json"])
            self.assertEqual(sorted(p.name for p in (Path(tmp) / "prompts").iterdir()), ["RB-01.md", "RB-02.md"])


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
        text = "Sure.\n```json\n" + json.dumps(answer("RB-01")) + "\n```\nDone."
        parsed = evaluator.parse_response(text)
        self.assertEqual(parsed["parse_mode"], "json")
        self.assertEqual(parsed["decision"], "OVERRIDE")
        self.assertEqual(parsed["rulebook"]["work_rest_min"], "NL")

    def test_response_plain_text_fallback(self):
        parsed = evaluator.parse_response("I would OVERRIDE the table and pull him.")
        self.assertEqual(parsed["decision"], "OVERRIDE")
        self.assertEqual(parsed["parse_mode"], "text")
        self.assertIsNone(parsed["rulebook"])
        self.assertIsNone(evaluator.parse_response("Follow or override, hard to say.")["decision"])
        self.assertEqual(evaluator.parse_response("")["parse_mode"], "none")


class TestGrading(unittest.TestCase):
    def test_perfect_answers(self):
        for tid in TASKS:
            g = grade(tid, answer(tid))
            self.assertEqual(g["total"], 1.0, tid)
            self.assertTrue(g["pass"])
            self.assertEqual(g["body"]["core_abs_error_c"], 0.0)
            self.assertIsNone(g["body"]["error_type"])
            self.assertEqual(g["role"], TRUTH[tid]["role"])

    def test_flexible_rulebook_spellings_still_match(self):
        rb = {"work_rest": "no limit", "water": "¾ qt/hr", "continuous_work": None, "continuous_water": "1 quart/hour"}
        self.assertTrue(grade("RB-01", answer("RB-01", rulebook=rb))["rulebook"]["pass"])

    def test_old_2003_card_fails_rulebook_half(self):
        g = grade("RB-01", answer("RB-01", rulebook=dict(RULEBOOK, work_rest_min="40/20")))
        self.assertFalse(g["rulebook"]["pass"])
        self.assertEqual(g["rulebook"]["score"], 0.75)
        self.assertTrue(g["body"]["pass"])
        self.assertAlmostEqual(g["total"], 0.5 * 0.75 + 0.5)
        self.assertFalse(g["pass"])

    def test_missing_rulebook_key_is_not_read_as_no_limit(self):
        rb = {"water_qt_per_hr": 0.75, "continuous_water_qt_per_hr": 1}
        g = grade("RB-01", answer("RB-01", rulebook=rb))
        self.assertEqual(g["rulebook"]["score"], 0.5)
        self.assertIsNone(g["rulebook"]["parsed"]["work_rest_min"])

    def test_missed_override_on_trap(self):
        g = grade("RB-01", answer("RB-01", decision="FOLLOW", core=38.2))
        self.assertEqual(g["body"]["error_type"], "missed_override")
        self.assertFalse(g["body"]["core_within_tolerance"])
        self.assertAlmostEqual(g["total"], 0.5)

    def test_false_override_on_control(self):
        g = grade("RB-02", answer("RB-02", decision="OVERRIDE", core=38.7))
        self.assertEqual(g["body"]["error_type"], "false_override")
        self.assertEqual(g["body"]["score"], 0.0)
        self.assertTrue(g["body"]["core_within_tolerance"])

    def test_unparsed_and_garbage(self):
        g = grade("RB-01", {"rulebook": RULEBOOK, "predicted_core_c": 39})
        self.assertEqual(g["body"]["error_type"], "unparsed")
        self.assertEqual(g["total"], 0.5)
        g = evaluator.grade("RB-01", "no json here", TASKS, TRUTH, TABLE)
        self.assertEqual(g["total"], 0.0)
        self.assertEqual(g["body"]["parse_mode"], "none")

    def test_unknown_task_id_raises(self):
        with self.assertRaises(KeyError):
            evaluator.grade("RB-99", "{}", TASKS, TRUTH, TABLE)

    def test_defaults_load_committed_files(self):
        self.assertTrue(evaluator.grade("RB-02", json.dumps(answer("RB-02")))["pass"])


class TestScoreAll(unittest.TestCase):
    def test_perfect_suite(self):
        s = evaluator.score_all({tid: json.dumps(answer(tid)) for tid in TASKS})
        self.assertEqual(s["n_tasks"], 2)
        self.assertEqual(s["mean_total"], 1.0)
        self.assertTrue(s["all_pass"])
        self.assertTrue(s["discriminates_override_from_follow"])
        self.assertEqual(s["core_mae_c"], 0.0)

    def test_always_override_gets_half_the_body(self):
        s = evaluator.score_all({tid: json.dumps(answer(tid, decision="OVERRIDE")) for tid in TASKS})
        self.assertEqual(s["body_accuracy"], 0.5)
        self.assertEqual(s["false_overrides"], 1)
        self.assertFalse(s["discriminates_override_from_follow"])
        self.assertFalse(s["all_pass"])

    def test_always_follow_gets_half_the_body(self):
        s = evaluator.score_all({tid: json.dumps(answer(tid, decision="FOLLOW")) for tid in TASKS})
        self.assertEqual(s["body_accuracy"], 0.5)
        self.assertEqual(s["missed_overrides"], 1)
        self.assertFalse(s["discriminates_override_from_follow"])

    def test_missing_task_is_unparsed_and_list_input_works(self):
        s = evaluator.score_all([{"task_id": "RB-01", "response": json.dumps(answer("RB-01"))}])
        self.assertEqual(s["unparsed"], 1)
        self.assertEqual(s["rulebook_accuracy"], 0.5)


class TestCLI(unittest.TestCase):
    CMD = [sys.executable, "-m", "tasks.rulebook_vs_body.evaluator"]

    def test_print_prompt(self):
        out = subprocess.run(self.CMD + ["--print-prompt", "RB-02"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), TASKS["RB-02"]["prompt"].strip())
        out = subprocess.run(self.CMD + ["--print-prompt", "RB-01", "--with-table"], capture_output=True, text=True, cwd=ROOT)
        self.assertIn("Reference, TB MED 507", out.stdout)
        out = subprocess.run(self.CMD + ["--print-prompt", "RB-99"], capture_output=True, text=True, cwd=ROOT)
        self.assertNotEqual(out.returncode, 0)

    def test_score_file_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps({tid: "```json\n" + json.dumps(answer(tid)) + "\n```" for tid in TASKS}))
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({tid: json.dumps(answer(tid, decision="OVERRIDE")) for tid in TASKS}))
            scores = Path(tmp) / "scores.json"
            out = subprocess.run(self.CMD + [str(good), "--out", str(scores)], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(json.loads(scores.read_text())["all_pass"])
            out = subprocess.run(self.CMD + [str(bad)], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(out.returncode, 1)
            self.assertEqual(json.loads(out.stdout)["false_overrides"], 1)

    def test_main_in_process(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = evaluator.main(["--print-prompt", "RB-01"])
        self.assertEqual(code, 0)
        self.assertIn("Answer with one JSON object", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
