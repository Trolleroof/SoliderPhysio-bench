"""Offline judging tests: fake judge and mocked OpenRouter HTTP; no API calls."""
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn(f'{truth} C', case['judge_record']['prompt'])  # outcome-first judging
        self.assertIn(f'{truth} C', case['judge_reported_record']['prompt'])
        self.assertEqual(len(client.calls), 2)

    def test_run_case_puts_verified_outcome_first(self):
        gt = kg.load_ground_truth()['KG-02']
        case = J.run_case({'task': 'keep_going', 'case_id': 'KG-02', 'answer': KG_ANSWER}, J.FakeJudgeClient())
        p = case['judge_record']['prompt']
        self.assertTrue(p.startswith('===== VERIFIED OUTCOME'))
        self.assertIn(f"Correct decision: {gt['expected_decision']}", p)
        self.assertIn(case['judge_record']['input_hashes']['outcome'], [J._sha(p.split('\n\n')[0].split('\n', 1)[1])])
        rb_case = J.run_case({'task': 'rulebook_vs_body', 'case_id': 'RB-01', 'answer': RB_ANSWER}, J.FakeJudgeClient())
        self.assertIn('Correct TB MED 507 lookup', rb_case['judge_record']['prompt'])
        be = J.run_case({'task': 'beat_ectemp', 'case_id': '3B/H18', 'answer': 'explanation',
                         'grader': {'valid': True, 'person_mae': 0.9},
                         'materials': {'task_statement': 'x'}}, J.FakeJudgeClient())
        self.assertIn('ECTemp baseline MAE B: 0.626188 C -> DID NOT BEAT ECTemp', be['judge_record']['prompt'])

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


class OpenRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = SpendLedger(Path(self.tmp.name) / 'spend.sqlite', 0.50)
        self.addCleanup(self.ledger.close)
        self.client = J.OpenRouterJudgeClient(api_key='test-secret')
        self.http = self.enterContext(patch('tasks.judge.urllib.request.urlopen'))
        self.sleep = self.enterContext(patch('tasks.judge.time.sleep'))

    def response(self, text=None, cost=0.0123):
        if text is None:
            text = out(dim('decision', 4), dim('reasoning', 3))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': text}}],
                                     'usage': {'cost': cost, 'prompt_tokens': 600,
                                               'completion_tokens': 110}}).encode())

    def run_judge(self, **kw):
        return J.judge('keep_going', 'KG-01', KG_ANSWER, self.client, ledger=self.ledger, **kw)

    def http_error(self, code):
        return urllib.error.HTTPError(self.client.endpoint, code, 'test error', {}, io.BytesIO(b'test-secret'))

    def test_request_audit_and_cost_settlement(self):
        self.http.return_value = self.response()
        rec = self.run_judge()
        req = self.http.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(req.full_url, 'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(req.get_method(), 'POST')
        self.assertEqual(req.get_header('Authorization'), 'Bearer test-secret')
        self.assertEqual(req.get_header('Content-type'), 'application/json')
        self.assertEqual(self.http.call_args.kwargs['timeout'], 120)
        self.assertEqual(body, {'model': 'openai/gpt-6.1-sol',
                               'messages': [{'role': 'user', 'content': rec['prompt']}],
                               'reasoning': {'effort': 'high'},
                               'max_tokens': 8192, 'response_format': {'type': 'json_object'},
                               'usage': {'include': True}, 'stream': False,
                               'provider': {'require_parameters': True}})
        self.assertEqual(rec['scores'], {'decision': 4, 'reasoning': 3})
        self.assertEqual(rec['attempts'][0]['request_body'], body)
        self.assertEqual(rec['judge_settings'], {**self.client.settings, 'max_attempts': 2})
        self.assertNotIn('test-secret', json.dumps(rec))
        self.assertEqual(self.ledger.summary()['accounted_usd'], 0.0123)
        self.assertEqual(self.ledger.summary()['requests_with_reserved_cost'], 0)

    def test_429_and_5xx_retry_with_separate_reservations(self):
        self.http.side_effect = [self.http_error(429), self.http_error(503), self.response()]
        rec = self.run_judge(max_attempts=3)
        self.assertEqual(rec['status'], 'scored')
        self.assertEqual(len(rec['attempts']), 3)
        self.assertEqual(self.ledger.summary()['requests'], 3)
        self.assertEqual(self.ledger.summary()['requests_with_reserved_cost'], 2)
        self.assertGreater(self.ledger.summary()['accounted_usd'], 0.0123)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [1, 2])
        self.assertNotIn('test-secret', json.dumps(rec))

    def test_retry_bound(self):
        self.http.side_effect = [self.http_error(500), self.http_error(502)]
        rec = self.run_judge(max_attempts=2)
        self.assertEqual(rec['status'], 'not_scorable')
        self.assertEqual(self.http.call_count, 2)
        self.assertEqual(self.sleep.call_count, 1)

    def test_nonretryable_failures(self):
        for error in [self.http_error(400), self.http_error(401), self.http_error(403),
                      urllib.error.URLError('test-secret'), TimeoutError('test-secret')]:
            with self.subTest(error=type(error).__name__):
                self.http.reset_mock()
                self.http.side_effect = error
                # Each failed call retains its ceiling; use a fresh ledger per case.
                with tempfile.TemporaryDirectory() as tmp:
                    ledger = SpendLedger(Path(tmp) / 'spend.sqlite', 0.5)
                    try:
                        rec = J.judge('keep_going', 'KG-01', KG_ANSWER, self.client, ledger=ledger)
                    finally:
                        ledger.close()
                self.assertEqual(rec['status'], 'not_scorable')
                self.assertEqual(self.http.call_count, 1)
                self.assertNotIn('test-secret', json.dumps(rec))

    def test_malformed_judgment_settles_without_retry(self):
        self.http.return_value = self.response('not json')
        rec = self.run_judge()
        self.assertEqual(rec['scores'], dict.fromkeys(J.JUDGED['keep_going'], 'not_scorable'))
        self.assertEqual(rec['attempts'][0]['raw_output'], 'not json')
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.ledger.summary()['accounted_usd'], 0.0123)

    def test_missing_message_still_settles_usage(self):
        self.http.return_value = io.BytesIO(b'{"usage":{"cost":0.004},"choices":[]}')
        self.assertEqual(self.run_judge()['status'], 'not_scorable')
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.ledger.summary()['accounted_usd'], 0.004)

    def test_invalid_provider_json_keeps_reservation_without_retry(self):
        self.http.return_value = io.BytesIO(b'{')
        self.assertEqual(self.run_judge()['status'], 'not_scorable')
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.ledger.summary()['requests_with_reserved_cost'], 1)

    def test_missing_cost_keeps_ceiling(self):
        self.http.return_value = self.response(cost=None)
        self.assertEqual(self.run_judge()['status'], 'scored')
        self.assertEqual(self.ledger.summary()['requests_with_reserved_cost'], 1)

    def test_price_overrun_halts_and_keeps_audit(self):
        self.http.return_value = self.response(cost=0.20)
        transcript = Transcript(Path(self.tmp.name) / 'audit')
        self.addCleanup(transcript.close)
        with self.assertRaises(SpendLimitReached):
            self.run_judge(transcript=transcript)
        records = transcript.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['data']['usage']['cost'], 0.20)
        self.assertIn('SpendLimitReached', records[0]['data']['error'])
        self.assertEqual(self.http.call_count, 1)

    def test_budget_blocks_http_including_retry(self):
        with self.assertRaisesRegex(ValueError, 'SpendLedger'):
            J.judge('keep_going', 'KG-01', KG_ANSWER, self.client)
        self.http.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            ledger = SpendLedger(Path(tmp) / 'spend.sqlite', 0.000001)
            try:
                with self.assertRaises(SpendLimitReached):
                    J.judge('keep_going', 'KG-01', KG_ANSWER, self.client, ledger=ledger)
            finally:
                ledger.close()
        self.http.assert_not_called()
        # Exactly one reservation fits; a 503 must not allow a second paid call.
        self.http.side_effect = self.http_error(503)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = SpendLedger(Path(tmp) / 'spend.sqlite', 0.15)
            try:
                with self.assertRaises(SpendLimitReached):
                    J.judge('keep_going', 'KG-01', KG_ANSWER, self.client, ledger=ledger)
                self.assertEqual(self.http.call_count, 1)
            finally:
                ledger.close()

    def test_roster_exclusion_before_http_and_when_scoring_subset(self):
        roster = json.loads((J.ROOT / 'eval_suite' / 'roster.json').read_text())
        ids = [m['openrouter_id'] for m in roster['models'] if m.get('openrouter_id')]
        self.assertNotIn(self.client.model, ids)
        for model in ids:
            with self.subTest(model=model):
                self.client.model = model
                with self.assertRaisesRegex(ValueError, 'rated roster'):
                    self.run_judge()
                with self.assertRaisesRegex(ValueError, 'rated roster'):
                    cs.check_judge_off_roster([{'model': 'different-model', 'cases': [
                        {'judge_record': {'judge_model': model}}]}])
        self.http.assert_not_called()

    def test_cli_requires_cap_and_reports_cost(self):
        src, dst = Path(self.tmp.name) / 'subs.json', Path(self.tmp.name) / 'run.json'
        src.write_text(json.dumps({'model': 'handwritten', 'cases': [
            {'task': 'keep_going', 'case_id': 'KG-01', 'answer': KG_ANSWER}]}))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            J.main([str(src), '--judge', 'openrouter'])
        self.assertEqual(error.exception.code, 2)
        self.http.assert_not_called()
        self.http.return_value = self.response()
        with patch.dict(J.os.environ, {'OPENROUTER_API_KEY': 'test-secret'}):
            self.assertEqual(J.main([str(src), '--judge', 'openrouter', '--spend-cap-usd', '0.5',
                                     '--out', str(dst)]), 0)
        self.assertEqual(json.loads(dst.read_text())['spend']['accounted_usd'], 0.0123)
        self.assertNotIn('test-secret', dst.read_text())


if __name__ == '__main__':
    unittest.main()
