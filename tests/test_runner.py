"""Offline inference, isolation, and runner -> fake judge -> rating integration."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from eval_suite.core.common import read, tree_hashes
from eval_suite.core.openrouter import OpenRouterClient
from eval_suite.core.spend import SpendLimitReached
from eval_suite.core.transcript import Transcript
from eval_suite.core.worker import execute
from eval_suite.runner import ROOT, run, roster_model, select_cases


class FakeModelClient:
    def __init__(self):
        self.calls = []

    def complete(self, body, **kw):
        self.calls.append(body)
        messages = body['messages']
        if 'tools' not in body:
            text = json.dumps({'decision': 'KEEP', 'core_c_in_15_min': 38.2,
                               'rulebook': {}, 'reasoning': 'Offline fixture.'})
            message = {'role': 'assistant', 'content': text}
        else:
            turns = sum(m['role'] == 'assistant' for m in messages)
            if turns < 2 and body.get('tool_choice') != 'none':
                name = 'execute' if turns == 0 else 'dev_score'
                args = {'argv': ['python3', '-c', "from pathlib import Path; Path('submission.py').write_text(Path('template.py').read_text())"]} if turns == 0 else {}
                message = {'role': 'assistant', 'content': '', 'tool_calls': [
                    {'id': str(turns), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
            else:
                message = {'role': 'assistant', 'content': 'Retained the baseline; development metrics were measured. This does not establish generalization.'}
        return {'text': message['content'], 'message': message, 'usage': {'cost': 0.0}, 'raw': {'choices': [{'message': message}]}}


class TransportTests(unittest.TestCase):
    def test_http_body_headers_raw_usage_and_timeout(self):
        raw = {'choices': [{'message': {'role': 'assistant', 'content': 'answer'}}],
               'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'cost': 0.001}}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(raw).encode())) as http:
            response = OpenRouterClient('fake-secret').complete({'model': 'fixture'}, timeout_s=7)
        request = http.call_args.args[0]
        self.assertEqual(json.loads(request.data), {'model': 'fixture'})
        self.assertEqual(request.get_header('Authorization'), 'Bearer fake-secret')
        self.assertEqual(http.call_args.kwargs['timeout'], 7)
        self.assertEqual(response['raw'], raw)
        self.assertEqual(response['usage']['cost'], .001)

    def test_http_errors_do_not_echo_credentials(self):
        exc = urllib.error.HTTPError('https://example.test', 401, 'fake-secret', {}, io.BytesIO(b'fake-secret'))
        with patch('urllib.request.urlopen', side_effect=exc):
            with self.assertRaisesRegex(RuntimeError, '^OpenRouter HTTP 401$'):
                OpenRouterClient('fake-secret').complete({})

    def test_roster_and_selection(self):
        self.assertEqual(roster_model('6'), roster_model('deepseek/deepseek-v4.1-flash-1017'))
        with self.assertRaisesRegex(ValueError, 'Skipped.*no openrouter_id'):
            roster_model('1')
        missing_id = dict(roster_model('6'))
        del missing_id['openrouter_id']
        with patch('eval_suite.runner.read', return_value={'models': [missing_id]}):
            with self.assertRaisesRegex(ValueError, 'Skipped.*no openrouter_id'):
                roster_model('6')
            with self.assertRaisesRegex(ValueError, 'Unknown roster model'):
                roster_model('unknown')
        self.assertEqual(len(select_cases()), 21)
        self.assertNotIn('keep_going/KG-03', select_cases())
        with self.assertRaises(ValueError): select_cases(cases='KG-03')
        self.assertEqual(select_cases(cases='KG-01,RB-01,3A/H06'),
                         ['keep_going/KG-01', 'rulebook_vs_body/RB-01', 'beat_ectemp/3A/H06'])


@unittest.skipUnless(sys.platform == 'linux', 'Linux local backend')
class IsolationTests(unittest.TestCase):
    def test_commands_cannot_read_private_or_network_or_signal_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)/'public'; public.mkdir()
            secret = Path(tmp)/'secret'; secret.write_text('PRIVATE')
            script = f'''import os,socket
for path in [{str(secret)!r}, {str(ROOT/'tasks/keep_going/private_ground_truth.json')!r}, '/proc/self/environ']:
    try: open(path).read()
    except PermissionError: pass
    else: raise AssertionError('private read permitted')
try: socket.socket()
except PermissionError: pass
else: raise AssertionError('network permitted')
try: os.kill(os.getppid(),0)
except PermissionError: pass
else: raise AssertionError('parent signal permitted')
open('allowed.txt','w').write('public only')
print('isolated')
'''
            r = execute(public, ['python3', '-c', script], backend='local', timeout_s=5, memory_gb=1)
            self.assertTrue(r['execution_valid'], r)
            self.assertIn('isolated', r['stdout'])
            self.assertFalse(r['scored_resource_isolation'])
            r = execute(public, ['python3', '-c', 'while True: pass'], backend='local', timeout_s=.2, memory_gb=1)
            self.assertEqual(r['failure_reason'], 'wall_budget_exhausted')


class RunnerTests(unittest.TestCase):
    def test_budget_stops_before_http_and_saves_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            with self.assertRaises(SpendLimitReached):
                run('6', tmp, 0.000001, cases='KG-01', client=fake)
            self.assertEqual(fake.calls, [])
            result = read(Path(tmp)/'submissions.json')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['spend']['requests'], 0)

    def test_request_timeout_is_recorded_and_passed_to_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            with patch.object(fake, 'complete', wraps=fake.complete) as call:
                result = run('6', tmp, 1, cases='KG-01', client=fake, request_timeout=600)
            self.assertGreater(call.call_args.kwargs['timeout_s'], 599)
            self.assertLessEqual(call.call_args.kwargs['timeout_s'], 600)
            self.assertEqual(result['request_timeout_s'], 600)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run('6', tmp, 1, cases='KG-01', client=FakeModelClient(), request_timeout=1201)

    def test_connection_reset_retries_and_preserves_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            response = fake.complete({'messages': []})
            with patch.object(fake, 'complete', side_effect=[ConnectionResetError('reset'), response]) as call:
                result = run('6', tmp, 1, cases='KG-01', client=fake)
            self.assertEqual(call.call_count, 2)
            self.assertEqual(len(result['cases']), 1)
            self.assertEqual(result['spend']['requests_with_reserved_cost'], 1)
            self.assertEqual(result['spend']['requests'], 2)

    def test_failed_request_keeps_reservation_and_partial_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            with patch.object(fake, 'complete', side_effect=[{'text': 'KEEP', 'usage': {'cost': 0}}, RuntimeError('offline failure')]):
                with self.assertRaisesRegex(RuntimeError, 'offline failure'):
                    run('6', tmp, 1, cases='KG-01,RB-01', client=fake)
            result = read(Path(tmp)/'submissions.json')
            self.assertEqual(len(result['cases']), 1)
            self.assertEqual(result['spend']['requests_with_reserved_cost'], 1)
            self.assertFalse(result['official'])

    def test_single_turn_has_no_tools_and_records_effort_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            result = run('6', tmp, 1, cases='KG-01,RB-01', client=fake)
            self.assertEqual(len(fake.calls), 2)
            self.assertTrue(all('tools' not in c for c in fake.calls))
            self.assertEqual(result['settings']['reasoning']['effort'], 'xhigh')
            self.assertEqual(fake.calls[0]['provider']['max_price'], {'prompt': .15, 'completion': .6, 'request': 0})
            trace = Transcript(Path(tmp)/'controller')
            try: records = trace.records()
            finally: trace.close()
            self.assertEqual(len([r for r in records if r['kind'] == 'model_request']), 2)
            self.assertTrue(all('prompt_sha256' in c for c in result['cases']))
            with self.assertRaisesRegex(ValueError, 'must be empty'):
                run('6', tmp, 1, cases='KG-01', client=fake)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux local backend')
    def test_missing_submission_is_invalid_and_final_turn_disables_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModelClient()
            result = run('6', tmp, 1, cases='3A/H06', client=fake, backend='local', max_steps=1, research_seconds=5)
            self.assertFalse(result['cases'][0]['grader']['valid'])
            self.assertEqual(fake.calls[0]['tool_choice'], 'none')
            self.assertEqual(result['cases'][0]['research_stop'], 'submitted')
            self.assertLess(result['cases'][0]['research_wall_s'], 5)
            self.assertFalse(result['official'])

    @unittest.skipUnless(sys.platform == 'linux', 'Linux local backend')
    def test_full_runner_fake_judge_and_rating_cli(self):
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', side_effect=AssertionError('No network in tests')):
            out = Path(tmp)/'model'
            fake = FakeModelClient()
            result = run('6', out, 1, client=fake, backend='local', research_seconds=30, max_steps=3)
            params = read(ROOT/'tasks/scoring_params.json')
            self.assertEqual({c['task']+'/'+c['case_id'] for c in result['cases']}, set(params['required_cases']))
            self.assertFalse(result['official'])
            for variant in ('3A', '3B'):
                g = read(out/variant/'grader.json')
                self.assertTrue(g['valid'])
                for p, mae in g['person_mae'].items():
                    self.assertAlmostEqual(mae, params['ectemp_B'][variant][p], places=5)
                self.assertEqual(tree_hashes(out/variant/'artifact'), read(out/variant/'artifact_hashes.json'))
                self.assertEqual(set(read(out/'public_seed/train.json')), set(__import__('tasks.beat_ectemp.benchmark', fromlist=['TRAIN']).TRAIN))
            judged = Path(tmp)/'run.json'
            process = subprocess.run([sys.executable, '-m', 'tasks.judge', str(out/'submissions.json'),
                                      '--judge', 'fake', '--out', str(judged)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            other = read(judged); other['model'] = 'offline-comparison-fixture'
            second = Path(tmp)/'other.json'; second.write_text(json.dumps(other))
            ratings = Path(tmp)/'ratings.json'
            process = subprocess.run([sys.executable, '-m', 'tasks.combined_score', str(judged), str(second),
                '--params', str(ROOT/'tasks/scoring_params.json'), '--n-boot', '2', '--out', str(ratings)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = read(ratings)
            self.assertEqual(len(result['ratings']), 2)
            self.assertTrue(all(r['elo'] == 1500 for r in result['ratings']))


if __name__ == '__main__': unittest.main()
