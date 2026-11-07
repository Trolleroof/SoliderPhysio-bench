"""Unit tests for the 'Keep going or pull him?' task suite (tasks/keep_going)."""
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tasks.keep_going import build_tasks, evaluator

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / 'tasks' / 'keep_going'
SOURCE = build_tasks.DEFAULT_SOURCE
PUBLIC = json.loads((TASK_DIR / 'public_tasks.json').read_text())
PRIVATE = json.loads((TASK_DIR / 'private_ground_truth.json').read_text())
PUBLIC_BY_ID = {t['task_id']: t for t in PUBLIC['tasks']}
PRIVATE_BY_ID = {t['task_id']: t for t in PRIVATE['tasks']}
PUBLIC_TEXT = (TASK_DIR / 'public_tasks.json').read_text() + ''.join(
    p.read_text() for p in sorted((TASK_DIR / 'prompts').glob('*.md')))


class TestSuiteShape(unittest.TestCase):
    def test_ids_match_across_files(self):
        self.assertEqual(sorted(PUBLIC_BY_ID), sorted(PRIVATE_BY_ID))
        prompts = sorted(p.stem for p in (TASK_DIR / 'prompts').glob('*.md'))
        self.assertEqual(prompts, sorted(PUBLIC_BY_ID))

    def test_at_least_ten_primary_tasks_plus_edge_case(self):
        roles = [t['role'] for t in PRIVATE['tasks']]
        self.assertGreaterEqual(roles.count('primary'), 10)
        self.assertEqual(roles.count('edge_case'), 1)

    def test_primary_tasks_use_distinct_people(self):
        subjects = [t['subject_id'] for t in PRIVATE['tasks'] if t['role'] == 'primary']
        self.assertEqual(len(subjects), len(set(subjects)))

    def test_prompt_file_matches_json_prompt(self):
        for tid, task in PUBLIC_BY_ID.items():
            self.assertEqual((TASK_DIR / 'prompts' / f'{tid}.md').read_text(), task['prompt'])

    def test_prompt_contains_rendered_table_and_rule(self):
        for task in PUBLIC['tasks']:
            self.assertIn(build_tasks.render_table(task['rows']), task['prompt'])
            self.assertIn('38.5 C', task['prompt'])
            self.assertIn('15 minutes', task['prompt'])
            self.assertIn('KEEP or PULL', task['prompt'])
            self.assertIn(f"age {task['subject_profile']['age_years']} years", task['prompt'])
            self.assertIn(f"body mass {task['subject_profile']['mass_kg']} kg", task['prompt'])


class TestNoLeakage(unittest.TestCase):
    def test_public_rows_have_only_allowed_columns(self):
        for task in PUBLIC['tasks']:
            for row in task['rows']:
                self.assertEqual(tuple(row), build_tasks.PUBLIC_ROW_KEYS)

    def test_public_task_keys_exclude_private_fields(self):
        forbidden = {'subject', 'subject_id', 'person', 'person_code', 'cutoff_min', 'role', 'design',
                     'note', 'core_at_cutoff_c', 'core_at_cutoff_plus_15_c', 'expected_decision',
                     'window_start_min', 'sex', 'height_cm'}
        for task in PUBLIC['tasks']:
            self.assertFalse(forbidden & set(task), forbidden & set(task))
            self.assertFalse(forbidden & set(task['subject_profile']))

    def test_no_subject_identifiers_in_public_text(self):
        for pattern in (r'\bsubject\b', r'\bparticipant\b', r'\bH\d{2}\b', r'\bS\d{2}\b',
                        r'\bperson\b', r'\bcutoff\b', r'\btrap\b', r'\bedge\b', r'\bsteady\b'):
            self.assertIsNone(re.search(pattern, PUBLIC_TEXT, flags=re.IGNORECASE), pattern)
        for gt in PRIVATE['tasks']:
            self.assertNotIn(gt['person_code'], PUBLIC_TEXT)
            self.assertNotIn(f"Subject {gt['subject_id']}", PUBLIC_TEXT)

    def test_no_core_temperature_in_public_text(self):
        for word in ('rectal', 'Rectal', 'core_at_cutoff', 'peak_core', 'core_change', 'CORE'):
            self.assertNotIn(word, PUBLIC_TEXT)
        for gt in PRIVATE['tasks']:
            for key in ('core_at_cutoff_c', 'core_at_cutoff_plus_15_c', 'peak_core_next_15_c'):
                self.assertNotIn(f'{gt[key]:.2f}', PUBLIC_TEXT, f'{gt["task_id"]} {key}')
        # The only mention of "core" in a prompt is the statement that it is not measured.
        for task in PUBLIC['tasks']:
            mentions = re.findall(r'[^.\n]*\bcore\b[^.\n]*', task['prompt'], flags=re.IGNORECASE)
            for m in mentions:
                self.assertTrue(('NOT measured' in m) or ('core temperature 15 minutes' in m)
                                or ('core_c_in_15_min' in m) or ('estimate of core' in m), m)

    def test_expected_decision_not_hinted_in_prompt(self):
        for tid, task in PUBLIC_BY_ID.items():
            body = task['prompt'].split('Decide: KEEP or PULL')[0]
            self.assertNotIn('PULL', body)
            self.assertNotIn('KEEP', body)


class TestRezeroAndRounding(unittest.TestCase):
    def test_timestamps_re_zeroed_and_consecutive(self):
        for tid, task in PUBLIC_BY_ID.items():
            times = [r['time_min'] for r in task['rows']]
            self.assertEqual(times, list(range(build_tasks.WINDOW_MIN)))
            self.assertNotEqual(times[-1], PRIVATE_BY_ID[tid]['cutoff_min'])
            self.assertEqual(PRIVATE_BY_ID[tid]['cutoff_min'] - PRIVATE_BY_ID[tid]['window_start_min'],
                             build_tasks.WINDOW_MIN - 1)

    def test_original_cutoff_minute_absent_from_prompt_header(self):
        for tid, task in PUBLIC_BY_ID.items():
            self.assertIn(f"ending now (minute {build_tasks.WINDOW_MIN - 1})", task['prompt'])

    def test_values_rounded(self):
        for task in PUBLIC['tasks']:
            self.assertIsInstance(task['subject_profile']['age_years'], int)
            self.assertIsInstance(task['subject_profile']['mass_kg'], int)
            for row in task['rows']:
                for key in ('hr_bpm', 'humidity_pct', 'watts'):
                    self.assertTrue(row[key] is None or isinstance(row[key], int), (key, row))
                for key in ('skin_c', 'room_temp_c'):
                    v = row[key]
                    self.assertTrue(v is None or round(v, 1) == v, (key, row))
                self.assertIsNotNone(row['skin_c'])
                self.assertIsNotNone(row['watts'])

    def test_rounding_changes_raw_values(self):
        """Exact-value lookup against the sheet must fail: rounded skin differs from raw somewhere."""
        helper = _raw_person_cache()
        for tid, task in PUBLIC_BY_ID.items():
            gt = PRIVATE_BY_ID[tid]
            person = helper(gt['subject_id'])
            if person is None:
                self.skipTest('source workbook not available')
            changed = sum(
                person['skin'][gt['window_start_min'] + r['time_min']] != r['skin_c'] for r in task['rows'])
            self.assertGreater(changed, 0, tid)
            raw_mass = person['demo']['mass_kg']
            self.assertEqual(task['subject_profile']['mass_kg'], int(round(raw_mass)))
            if raw_mass != int(raw_mass):
                self.assertNotEqual(raw_mass, task['subject_profile']['mass_kg'])

    def test_hr_is_blank_where_not_logged(self):
        for task in PUBLIC['tasks']:
            logged = [r['hr_bpm'] for r in task['rows'] if r['hr_bpm'] is not None]
            self.assertTrue(0 < len(logged) < len(task['rows']))
            self.assertTrue(all(30 <= h <= 240 for h in logged))


class TestEdgeCaseCoverage(unittest.TestCase):
    PRIMARY = [t for t in PRIVATE['tasks'] if t['role'] == 'primary']

    def _watts(self, tid):
        return [r['watts'] for r in PUBLIC_BY_ID[tid]['rows']]

    def _design(self, name):
        return [t for t in PRIVATE['tasks'] if t['design'] == name]

    def test_designs_present(self):
        designs = {t['design'] for t in PRIVATE['tasks']}
        self.assertEqual(designs, {'steady_power_safe', 'steady_power_rising', 'falling_power_safe',
                                   'falling_power_thermal_lag', 'falling_power_core_fell'})

    def test_balanced_answers_so_constant_guess_scores_half(self):
        answers = [t['expected_decision'] for t in self.PRIMARY]
        self.assertEqual(answers.count('PULL'), answers.count('KEEP'))

    def test_power_drop_is_not_a_giveaway(self):
        for answer in ('KEEP', 'PULL'):
            group = [t for t in self.PRIMARY if t['expected_decision'] == answer]
            drops = [t['power_dropped_in_window'] for t in group]
            self.assertTrue(any(drops) and not all(drops), answer)

    def test_thermal_lag_traps(self):
        traps = self._design('falling_power_thermal_lag')
        self.assertGreaterEqual(len(traps), 2)
        for gt in traps:
            watts = self._watts(gt['task_id'])
            self.assertLess(watts[-1], max(watts), gt['task_id'])
            self.assertTrue(gt['power_dropped_in_window'])
            self.assertLessEqual(gt['core_at_cutoff_c'], build_tasks.THRESHOLD_C)
            self.assertGreaterEqual(gt['core_at_cutoff_plus_15_c'], build_tasks.THRESHOLD_C)
            self.assertGreater(gt['core_change_15_c'], 0.3)
            self.assertEqual(gt['expected_decision'], 'PULL')
            self.assertEqual(gt['role'], 'primary')

    def test_falling_power_safe_cases(self):
        cases = self._design('falling_power_safe')
        self.assertGreaterEqual(len(cases), 2)
        for gt in cases:
            self.assertTrue(gt['power_dropped_in_window'], gt['task_id'])
            self.assertLess(gt['peak_core_next_15_c'], build_tasks.THRESHOLD_C)
            self.assertEqual(gt['expected_decision'], 'KEEP')

    def test_steady_power_controls(self):
        steady = [t for t in self.PRIMARY if t['design'].startswith('steady_power')]
        self.assertGreaterEqual(len(steady), 2)
        for gt in steady:
            self.assertEqual(len(set(self._watts(gt['task_id']))), 1, gt['task_id'])
            self.assertFalse(gt['power_dropped_in_window'])
        for gt in self._design('steady_power_safe'):
            self.assertEqual(gt['expected_decision'], 'KEEP')
            self.assertLess(gt['peak_core_next_15_c'], build_tasks.THRESHOLD_C)
        for gt in self._design('steady_power_rising'):
            self.assertEqual(gt['expected_decision'], 'PULL')
        self.assertTrue(self._design('steady_power_safe') and self._design('steady_power_rising'))

    def test_subject_four_core_fell_edge_case(self):
        (gt,) = self._design('falling_power_core_fell')
        self.assertEqual(gt['subject_id'], 4)
        self.assertEqual(gt['person_code'], 'H04')
        self.assertTrue(42 <= gt['cutoff_min'] <= 45)
        self.assertTrue(gt['power_dropped_in_window'])
        self.assertLess(gt['core_at_cutoff_plus_15_c'], gt['core_at_cutoff_c'])
        self.assertLess(gt['core_at_cutoff_plus_15_c'], build_tasks.THRESHOLD_C)
        self.assertEqual(gt['expected_decision'], 'KEEP')
        self.assertEqual(gt['role'], 'edge_case')

    def test_scored_labels_are_clear_and_glitch_free(self):
        for gt in self.PRIMARY:
            self.assertGreaterEqual(gt['label_margin_c'], build_tasks.MIN_MARGIN_C, gt['task_id'])
            self.assertLessEqual(gt['max_core_step_c'], build_tasks.MAX_STEP_C, gt['task_id'])
            self.assertAlmostEqual(gt['label_margin_c'],
                                   abs(gt['core_at_cutoff_plus_15_c'] - build_tasks.THRESHOLD_C), 2)

    def test_expected_decisions_follow_threshold_rule(self):
        for gt in PRIVATE['tasks']:
            want = 'PULL' if gt['core_at_cutoff_plus_15_c'] >= build_tasks.THRESHOLD_C else 'KEEP'
            self.assertEqual(gt['expected_decision'], want, gt['task_id'])
            self.assertEqual(gt['scorer'], 'tasks.keep_going.evaluator.grade')


class TestBuilderDeterminism(unittest.TestCase):
    @unittest.skipUnless(SOURCE.exists(), 'source workbook not available')
    def test_rebuild_matches_committed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_tasks.build(SOURCE, tmp)
            for name in ('public_tasks.json', 'private_ground_truth.json'):
                self.assertEqual(json.loads((Path(tmp) / name).read_text()),
                                 json.loads((TASK_DIR / name).read_text()), name)
            for p in (TASK_DIR / 'prompts').glob('*.md'):
                self.assertEqual((Path(tmp) / 'prompts' / p.name).read_text(), p.read_text())

    @unittest.skipUnless(SOURCE.exists(), 'source workbook not available')
    def test_builder_rejects_wrong_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'x.xlsx'
            bad.write_bytes(b'not the workbook')
            with self.assertRaises(ValueError):
                build_tasks.load_workbook(bad)

    def test_window_bounds(self):
        person = {'env': {}, 'skin': {1: 33.0}, 'watts': {1: 100.0}, 'hr': {}}
        with self.assertRaises(ValueError):
            build_tasks.make_window(person, cutoff=5, window=10)


class TestParsing(unittest.TestCase):
    def test_clean_json(self):
        p = evaluator.parse_response('{"decision": "PULL", "core_c_in_15_min": 38.9, "confidence": 0.8}')
        self.assertEqual((p['decision'], p['core_c_in_15_min'], p['confidence'], p['parse_mode']),
                         ('PULL', 38.9, 0.8, 'json'))

    def test_fenced_json_with_prose_and_string_numbers(self):
        text = 'Thinking...\n```json\n{"decision": "keep", "core_c_in_15_min": "38.2 C", "confidence": "0.35"}\n```\nDone.'
        p = evaluator.parse_response(text)
        self.assertEqual((p['decision'], p['core_c_in_15_min'], p['confidence']), ('KEEP', 38.2, 0.35))

    def test_plain_text_fallback(self):
        self.assertEqual(evaluator.parse_response('I would PULL him now.')['decision'], 'PULL')
        self.assertEqual(evaluator.parse_response('keep going')['decision'], 'KEEP')
        self.assertEqual(evaluator.parse_response('keep going')['parse_mode'], 'text')

    def test_ambiguous_text_is_unparsed(self):
        self.assertIsNone(evaluator.parse_response('Keep going or pull him? Hard to say.')['decision'])
        self.assertIsNone(evaluator.parse_response('')['decision'])
        self.assertIsNone(evaluator.parse_response(None)['decision'])
        self.assertIsNone(evaluator.parse_response('{"decision": "maybe"}')['decision'])

    def test_both_words_with_explicit_decision(self):
        self.assertEqual(evaluator.parse_response('Keep or pull? Decision: PULL')['decision'], 'PULL')
        self.assertEqual(evaluator.parse_response('pull vs keep... **decision**: keep')['decision'], 'KEEP')

    def test_out_of_range_confidence_dropped(self):
        p = evaluator.parse_response('{"decision": "PULL", "confidence": 80}')
        self.assertIsNone(p['confidence'])

    def test_sentence_containing_pull_does_not_override_json(self):
        p = evaluator.parse_response('{"decision": "KEEP"} I considered whether to pull.')
        self.assertEqual(p['decision'], 'KEEP')


class TestGrading(unittest.TestCase):
    def test_correct_and_incorrect(self):
        trap = next(t['task_id'] for t in PRIVATE['tasks'] if t['design'] == 'falling_power_thermal_lag')
        safe = next(t['task_id'] for t in PRIVATE['tasks'] if t['design'] == 'steady_power_safe')
        good = evaluator.grade(trap, '{"decision": "PULL", "core_c_in_15_min": 38.7}')
        self.assertTrue(good['decision_correct'])
        self.assertEqual(good['score'], 1.0)
        self.assertIsNone(good['error_type'])
        self.assertAlmostEqual(good['core_abs_error_c'], abs(38.7 - PRIVATE_BY_ID[trap]['core_at_cutoff_plus_15_c']), 2)
        bad = evaluator.grade(trap, '{"decision": "KEEP"}')
        self.assertFalse(bad['decision_correct'])
        self.assertEqual(bad['error_type'], 'missed_pull')
        self.assertIsNone(bad['core_abs_error_c'])
        self.assertEqual(evaluator.grade(safe, 'PULL')['error_type'], 'false_pull')
        self.assertEqual(evaluator.grade(safe, '???')['error_type'], 'unparsed')

    def test_unknown_task_id(self):
        with self.assertRaises(KeyError):
            evaluator.grade('KG-99', 'PULL')

    def test_score_all_perfect(self):
        responses = {t['task_id']: json.dumps({'decision': t['expected_decision'],
                                               'core_c_in_15_min': t['core_at_cutoff_plus_15_c']})
                     for t in PRIVATE['tasks']}
        s = evaluator.score_all(responses)
        self.assertEqual(s['primary_accuracy'], 1.0)
        self.assertEqual(s['overall_accuracy'], 1.0)
        self.assertTrue(s['edge_case_correct'])
        self.assertEqual(s['thermal_lag_traps_caught'], s['thermal_lag_traps_total'])
        self.assertTrue(all(v == 1.0 for v in s['accuracy_by_design'].values()))
        self.assertEqual(s['core_mae_c'], 0.0)
        self.assertEqual((s['false_pulls'], s['missed_pulls'], s['unparsed']), (0, 0, 0))

    def test_constant_guesses_score_half(self):
        keep = evaluator.score_all({t['task_id']: 'KEEP' for t in PRIVATE['tasks']})
        pull = evaluator.score_all({t['task_id']: 'PULL' for t in PRIVATE['tasks']})
        self.assertEqual(keep['primary_accuracy'], 0.5)
        self.assertEqual(pull['primary_accuracy'], 0.5)
        self.assertEqual(keep['thermal_lag_traps_caught'], 0)
        self.assertTrue(keep['edge_case_correct'])
        self.assertFalse(pull['edge_case_correct'])
        self.assertIsNone(keep['core_mae_c'])

    def test_power_drop_heuristic_scores_half(self):
        """'Power dropped means he is cooling, keep him' should not beat a coin flip."""
        responses = {t['task_id']: 'KEEP' if t['power_dropped_in_window'] else 'PULL'
                     for t in PRIVATE['tasks']}
        s = evaluator.score_all(responses)
        self.assertEqual(s['primary_accuracy'], 0.5)
        self.assertEqual(s['thermal_lag_traps_caught'], 0)

    def test_score_all_accepts_list_and_missing(self):
        s = evaluator.score_all([{'task_id': 'KG-01', 'response': 'KEEP'}])
        self.assertEqual(s['n_tasks'], len(PRIVATE['tasks']))
        self.assertEqual(s['unparsed'], len(PRIVATE['tasks']) - 1)

    def test_cli_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / 'r.json'
            out = Path(tmp) / 's.json'
            inp.write_text(json.dumps({t['task_id']: 'PULL' for t in PRIVATE['tasks']}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(evaluator.main([str(inp), '--out', str(out)]), 0)
            self.assertIn('primary_accuracy', json.loads(out.read_text()))


def _raw_person_cache():
    cache = {}

    def get(subject):
        if not SOURCE.exists():
            return None
        if not cache:
            cache.update(build_tasks.load_workbook(SOURCE))
        return cache[subject]
    return get


if __name__ == '__main__':
    unittest.main()
