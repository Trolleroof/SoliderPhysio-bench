"""Tests for the LLM judging harness (offline fake judge only; no API calls)."""
import json
import tempfile
import unittest
from pathlib import Path

from eval_suite.core.spend import SpendLedger, SpendLimitReached
from eval_suite.core.transcript import Transcript
from tasks import combined_score as cs
from tasks import judge as J
from tasks.keep_going import evaluator as kg
from tasks.rulebook_vs_body import evaluator as rb

KG_ANSWER = json.dumps({'decision': 'PULL', 'core_c_in_15_min': 38.7, 'confidence': 0.7,
                        'reasoning': 'Heart rate drifts upward at constant power.'})
RB_ANSWER = json.dumps({'rulebook': {'work_rest_min': 'NL', 'water_qt_per_hr': 0.75,
                                     'continuous_work_min': 'NL', 'continuous_water_qt_per_hr': 1.0},
                        'decision': 'OVERRIDE', 'predicted_core_c': 38.8, 'reasoning': 'Hot skin.'})
EC_MATERIALS = {'task_statement': 'Build a causal core-temperature predictor.',
                'dev_results': [{'valid': True, 'mae': 0.31, 'public_call_count': 2}]}


def dim(name, score, **kw):
    return {'name': name, 'score': score, 'explanation': 'cites the answer', 'answer_evidence': ['"PULL"'],
            'references': ['case table'], 'uncertainties': [], **kw}


def out(*dims):
    return json.dumps({'dimensions': list(dims)})


class Rubric(unittest.TestCase):
    def test_sections_and_hash(self):
        r = J.load_rubric()
        self.assertEqual(r['path'], 'docs/LLM_JUDGE_RUBRICS.md')
        self.assertEqual(len(r['sha256']), 64)
        for s in J.RUBRIC_SECTIONS.values():
            self.assertTrue(r['sections'][s].startswith('## ' + s))

    def test_prompt_contains_rubric_materials_answer_and_dims(self):
        client = J.FakeJudgeClient()
        rec = J.judge('rulebook_vs_body', 'RB-01', RB_ANSWER, client)
        p = rec['prompt']
        self.assertIn('## Common instructions', p)
        self.assertIn('### Override decision (0–5)', p)
        self.assertNotIn('## Keep going or pull him?', p)
        self.assertIn(rb.render_reference_table(rb.load_json(rb.TABLE_PATH)), p)
        self.assertIn(RB_ANSWER, p)
        self.assertIn('override_decision, reasoning', p)


class NoGroundTruthLeak(unittest.TestCase):
    def test_keep_going_prompt_excludes_private_truth(self):
        for case_id, truth in kg.load_ground_truth().items():
            rec = J.judge('keep_going', case_id, KG_ANSWER, J.FakeJudgeClient())
            p = rec['prompt']
            self.assertIn(kg.load_public()[case_id]['prompt'], p)
            for key in ('expected_decision', 'core_at_cutoff_plus_15_c', 'subject_id'):
                self.assertNotIn(key, p)
            self.assertNotIn(f"{truth['core_at_cutoff_plus_15_c']:.2f}", p.replace(KG_ANSWER, ''))

    def test_rulebook_prompt_excludes_private_truth(self):
        for case_id, truth in rb.load_ground_truth().items():
            p = J.judge('rulebook_vs_body', case_id, RB_ANSWER, J.FakeJudgeClient())['prompt']
            self.assertNotIn(truth['note'], p)
            self.assertNotIn(f"{truth['core_at_cutoff_plus_15_c']:.2f}", p.replace(RB_ANSWER, ''))
            for key in ('expected_decision', 'core_at_cutoff', 'subject_id', truth['design']):
                self.assertNotIn(key, p)

    def test_forecast_assessment_is_separate_and_not_in_judge_scores(self):
        client = J.FakeJudgeClient(score=4)
        case = J.run_case({'task': 'keep_going', 'case_id': 'KG-02', 'answer': KG_ANSWER}, client,
                          forecast_assessment=True)
        truth = kg.load_ground_truth()['KG-02']['core_at_cutoff_plus_15_c']
        self.assertEqual(set(case['judge']), {'decision', 'reasoning'})
        self.assertEqual(case['judge_reported'], {'forecast_assessment': 4})
        self.assertNotIn(str(truth), case['judge_record']['prompt'].replace(KG_ANSWER, ''))
        self.assertIn(f'{truth} C', case['judge_reported_record']['prompt'])
        self.assertEqual(len(client.calls), 2)

    def test_hidden_ectemp_results_rejected(self):
        with self.assertRaises(ValueError):
            J.judge('beat_ectemp', '3A', 'explanation', J.FakeJudgeClient(),
                    materials={'task_statement': 'x', 'dev_results': [{'public_to_hidden_gap': 0.1}]})


class Parsing(unittest.TestCase):
    D = ('decision', 'reasoning')

    def test_valid_and_fenced(self):
        text = '```json\n' + out(dim('decision', 5), dim('reasoning', 'not_scorable', not_scorable_reason='no doc')) + '\n```'
        p = J.parse_judgment(text, self.D)
        self.assertEqual(p['decision']['score'], 5)
        self.assertEqual(p['reasoning']['score'], 'not_scorable')
        self.assertEqual(p['reasoning']['not_scorable_reason'], 'no doc')

    def test_rejections(self):
        bad = [
            '', 'not json', '[]', json.dumps({'x': 1}),
            out(dim('decision', 5)),                                   # missing dimension
            out(dim('decision', 5), dim('decision', 4)),               # duplicate
            out(dim('decision', 5), dim('reasoning', 4), dim('extra', 1)),
            out(dim('decision', 6), dim('reasoning', 4)),              # out of range
            out(dim('decision', 4.0), dim('reasoning', 4)),            # float
            out(dim('decision', True), dim('reasoning', 4)),           # bool
            out(dim('decision', '4'), dim('reasoning', 4)),            # string number
            out(dim('decision', 4, explanation=' '), dim('reasoning', 4)),
            out(dim('decision', 4, references='doc'), dim('reasoning', 4)),
            out(dim('decision', 'not_scorable'), dim('reasoning', 4)),  # no reason
            'Here you go: ' + out(dim('decision', 4), dim('reasoning', 4)),
        ]
        for text in bad:
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                J.parse_judgment(text, self.D)


class Failures(unittest.TestCase):
    def test_parse_failure_retries_then_not_scorable_never_zero(self):
        client = J.FakeJudgeClient(outputs=['garbage', RuntimeError('timeout')])
        rec = J.judge('keep_going', 'KG-01', KG_ANSWER, client, max_attempts=2)
        self.assertEqual(rec['status'], 'not_scorable')
        self.assertEqual(rec['scores'], {'decision': 'not_scorable', 'reasoning': 'not_scorable'})
        self.assertEqual([a['raw_output'] for a in rec['attempts']], ['garbage', None])
        self.assertIn('RuntimeError: timeout', rec['attempts'][1]['error'])
        self.assertEqual(len(rec['errors']), 2)

    def test_retry_succeeds_and_keeps_failed_attempt(self):
        good = out(dim('decision', 2), dim('reasoning', 1))
        rec = J.judge('keep_going', 'KG-01', KG_ANSWER, J.FakeJudgeClient(outputs=['{', good]))
        self.assertEqual(rec['status'], 'scored')
        self.assertEqual(rec['scores'], {'decision': 2, 'reasoning': 1})
        self.assertEqual(len(rec['attempts']), 2)
        self.assertIsNone(rec['attempts'][1]['error'])

    def test_absent_answer_scores_zero_without_calling_judge(self):
        for answer in (None, '', '   \n'):
            client = J.FakeJudgeClient()
            rec = J.judge('beat_ectemp', '3A', answer, client, materials=EC_MATERIALS)
            self.assertEqual(rec['status'], 'absent_answer')
            self.assertEqual(rec['scores'], {'research_explanation': 0})
            self.assertEqual(client.calls, [])

    def test_missing_materials_not_scorable_without_call(self):
        client = J.FakeJudgeClient()
        rec = J.judge('beat_ectemp', '3A', 'my explanation', client)
        self.assertEqual(rec['scores'], {'research_explanation': 'not_scorable'})
        self.assertEqual(client.calls, [])

    def test_unconfigured_real_client_is_judge_failure(self):
        class Unwired(J.JudgeClient):
            model, settings = 'tbd', {'max_tokens': 100}
        rec = J.judge('keep_going', 'KG-01', KG_ANSWER, Unwired(), max_attempts=1)
        self.assertEqual(rec['status'], 'not_scorable')
        self.assertIn('NotImplementedError', rec['errors'][0])


class Audit(unittest.TestCase):
    def test_every_attempt_records_model_settings_hash_and_raw(self):
        rec = J.judge('keep_going', 'KG-01', KG_ANSWER, J.FakeJudgeClient(outputs=['x', out(dim('decision', 3), dim('reasoning', 3))]))
        self.assertEqual(rec['judge_model'], 'fake-judge-v1')
        self.assertEqual(rec['input_hashes']['prompt'], J._sha(rec['prompt']))
        for a in rec['attempts']:
            self.assertEqual(a['judge_model'], 'fake-judge-v1')
            self.assertEqual(a['judge_settings']['temperature'], 0)
            self.assertEqual(a['prompt_sha256'], rec['input_hashes']['prompt'])
            self.assertIsNotNone(a['raw_output'])
        self.assertEqual(rec['judgment']['decision']['answer_evidence'], ['"PULL"'])

    def test_transcript_and_spend_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Transcript(Path(tmp) / 'ctl')
            ledger = SpendLedger(Path(tmp) / 'spend.sqlite', 1.0)
            pricing = {'prompt': 1e-6, 'completion': 1e-6}
            J.judge('keep_going', 'KG-01', KG_ANSWER, J.FakeJudgeClient(outputs=['x', out(dim('decision', 3), dim('reasoning', 3))]),
                    transcript=t, ledger=ledger, pricing=pricing)
            kinds = [r['kind'] for r in t.records()]
            self.assertEqual(kinds, ['judge_attempt', 'judge_attempt', 'judge_result'])
            self.assertEqual(ledger.summary()['requests'], 2)
            tiny = SpendLedger(Path(tmp) / 'tiny.sqlite', 1e-6)
            with self.assertRaises(SpendLimitReached):
                J.judge('keep_going', 'KG-01', KG_ANSWER, J.FakeJudgeClient(), ledger=tiny, pricing=pricing)
            ledger.close(); tiny.close(); t.close()


class EndToEnd(unittest.TestCase):
    def test_run_file_feeds_combined_score(self):
        subs = {'model': 'm1', 'cases': [
            {'task': 'keep_going', 'case_id': 'KG-01', 'answer': KG_ANSWER},
            {'task': 'rulebook_vs_body', 'case_id': 'RB-01', 'answer': RB_ANSWER},
            {'task': 'beat_ectemp', 'case_id': '3A', 'answer': 'explanation',
             'grader': {'valid': True, 'person_mae': {'H13': 0.25}}, 'materials': EC_MATERIALS},
            {'task': 'keep_going', 'case_id': 'KG-02', 'answer': ''},
        ]}
        run = J.run_submissions(subs, J.FakeJudgeClient(score=5))
        run = json.loads(json.dumps(run))  # must survive a run-file round trip
        scores = cs.score_runs([run], {'E_c': 1.0, 'ectemp_B': {'3A': {'H13': 0.5}}})['m1']
        self.assertTrue(all(r['status'] == 'scored' for r in scores.values()))
        self.assertAlmostEqual(scores[('beat_ectemp', '3A/H13')]['combined'], 0.6 * 0.5 + 0.4)
        self.assertEqual(run['cases'][3]['judge'], {'decision': 0, 'reasoning': 0})

    def test_judge_failure_blocks_case_in_combined_score(self):
        subs = {'model': 'm1', 'cases': [{'task': 'keep_going', 'case_id': 'KG-01', 'answer': KG_ANSWER}]}
        run = J.run_submissions(subs, J.FakeJudgeClient(outputs=['bad', 'bad']))
        rec = cs.score_runs([run], {'E_c': 1.0})['m1'][('keep_going', 'KG-01')]
        self.assertEqual(rec['status'], 'not_scorable')

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / 'subs.json', Path(tmp) / 'run.json'
            src.write_text(json.dumps({'model': 'm', 'cases': [{'task': 'rulebook_vs_body', 'case_id': 'RB-02', 'answer': RB_ANSWER}]}))
            self.assertEqual(J.main([str(src), '--judge', 'fake', '--fake-score', '4', '--out', str(dst),
                                     '--controller', str(Path(tmp) / 'ctl')]), 0)
            run = json.loads(dst.read_text())
            self.assertEqual(run['cases'][0]['judge'], {'override_decision': 4, 'reasoning': 4})
            self.assertEqual(run['cases'][0]['grader']['rulebook']['score'], 1.0)


if __name__ == '__main__':
    unittest.main()
