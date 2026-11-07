import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eval_suite.registry import ACTIVE_TASK_IDS, ROOT, TaskNotReadyError, preflight, resolve, run_task, tasks
from eval_suite.core.spend import SpendLedger, SpendLimitReached
from eval_suite.core.common import tree_hashes


def cli(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=10)


class TaskSuite(unittest.TestCase):
    def test_catalog_contains_only_confirmed_new_specs(self):
        expected=('keep-going-or-pull-him','rulebook-versus-body','beat-ectemp')
        self.assertEqual(ACTIVE_TASK_IDS, expected)
        result=cli('-m','eval_suite','list')
        self.assertEqual(result.returncode,0,result.stderr)
        rows=json.loads(result.stdout)['tasks']
        self.assertEqual(tuple(t['id'] for t in rows),expected)
        for task in rows:
            self.assertTrue((ROOT/task['specification']).is_file())

    def test_legacy_identifiers_are_rejected_without_model_calls(self):
        with patch('urllib.request.urlopen') as network:
            for task in ('pulse','heat','load','galaxy-pulse-causal-v1',''):
                with self.subTest(task=task),self.assertRaisesRegex(ValueError,'Unknown or removed'):
                    resolve(task)
            network.assert_not_called()
        for task in ('pulse','heat','load'):
            result=cli('-m','eval_suite','run',task)
            self.assertEqual(result.returncode,2)
            self.assertIn('invalid choice',result.stderr)

    def test_new_task_runs_are_blocked_until_implementation_exists(self):
        with patch('urllib.request.urlopen') as network:
            for task in ACTIVE_TASK_IDS:
                with self.subTest(task=task),self.assertRaisesRegex(TaskNotReadyError,'No model request was sent'):
                    run_task(task)
            network.assert_not_called()
        result=cli('-m','eval_suite','run','beat-ectemp')
        self.assertEqual(result.returncode,2)
        self.assertIn('not implemented yet',result.stderr)
        self.assertIn('cannot be used as a fallback',result.stderr)

    def test_preflight_is_honestly_blocked_and_has_no_default_run(self):
        result=cli('-m','eval_suite','preflight')
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'blocked')
        self.assertEqual(report['model_requests_sent'],0)
        self.assertEqual(len(report['tasks']),3)
        self.assertTrue(all(not t['ready'] and t['missing'] for t in report['tasks']))
        self.assertNotEqual(cli('-m','eval_suite','run').returncode,0)
        self.assertNotEqual(cli('-m','eval_suite').returncode,0)

    def test_historical_python_entrypoints_cannot_import_or_run(self):
        modules=('research_env','research_env.compact','research_env.sweep',
                 'research_env.run_model','research_env.batch','research_env.leaderboard',
                 'research_env.tasks.pulse.baselines','benchmark','benchmark.pilot')
        for module in modules:
            with self.subTest(module=module):
                result=cli('-m',module,'unused-plan','unused-output')
                self.assertNotEqual(result.returncode,0)
                self.assertIn('tasks were removed',result.stderr)
                self.assertIn('python -m eval_suite list',result.stderr)
        for script in ('parallel_compact','run_research_pilot','uncapped_compact','run_pulse_baselines'):
            with self.subTest(script=script):
                self.assertFalse((ROOT/'scripts'/f'{script}.py').exists())
                self.assertNotEqual(cli('-m',f'scripts.{script}').returncode,0)

    def test_catalog_edits_cannot_reenable_legacy_or_fake_readiness(self):
        rows=tasks()
        fake={'tasks':[dict(t,status='ready',missing=[]) for t in rows]}
        with patch('eval_suite.registry.Path.read_text',return_value=json.dumps(fake)):
            self.assertTrue(all(not t['ready'] for t in preflight()['tasks']))
            with self.assertRaises(TaskNotReadyError):run_task(ACTIVE_TASK_IDS[0])
        fake['tasks'][0]['id']='heat'
        with patch('eval_suite.registry.Path.read_text',return_value=json.dumps(fake)):
            with self.assertRaisesRegex(ValueError,'exactly the three'):tasks()


class ReusedGuards(unittest.TestCase):
    def test_spend_cap_persists_and_unknown_calls_keep_reservations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'spend.sqlite'
            ledger=SpendLedger(path,0.02)
            body={'model':'fixture','max_tokens':1}
            ledger.reserve(body,{'prompt':0.000001,'completion':0.000001})
            before=ledger.summary()
            ledger.close()
            ledger=SpendLedger(path,0.02)
            self.assertEqual(ledger.summary(),before)
            with self.assertRaises(SpendLimitReached):
                ledger.reserve(body,{'prompt':1,'completion':1})
            ledger.close()
            with self.assertRaisesRegex(ValueError,'persisted spend cap'):SpendLedger(path,1)

    def test_asset_hashing_rejects_links_to_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);public=root/'public';public.mkdir()
            private=root/'private.txt';private.write_text('private fixture')
            (public/'escape').symlink_to(private)
            with self.assertRaisesRegex(ValueError,'Symlinks forbidden'):tree_hashes(public)
