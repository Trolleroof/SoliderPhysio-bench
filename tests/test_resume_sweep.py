import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from eval_suite.core.common import write
from eval_suite.core.common import read
from eval_suite.resume_sweep import inventory, main

class ResumeSweepTest(unittest.TestCase):
    def test_preserves_cases_and_charges_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); row={'openrouter_id':'provider/model'}
            a={'model':'provider/model','cases':[{'task':'keep_going','case_id':'KG-01'}],
               'spend':{'accounted_usd':0.5}}
            write(root/'first/submissions.json',a)
            write(root/'second/submissions.json',{'model':'provider/model','cases':[],
                                                   'spend':{'accounted_usd':0.3}})
            found,cost=inventory(root,row)
            self.assertEqual(set(found),{'keep_going/KG-01'})
            self.assertAlmostEqual(cost,0.8)
            write(root/'duplicate/submissions.json',a)
            with self.assertRaisesRegex(ValueError,'duplicate completed case'):
                inventory(root,row)

    def test_preflight_failure_stops_before_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv', ['resume_sweep', '--root', tmp, '--image', 'fixture']), \
                 patch('eval_suite.registry.preflight', return_value={'status': 'blocked'}) , \
                 patch('subprocess.Popen') as spawn:
                with self.assertRaises(SystemExit):
                    main()
            self.assertFalse(spawn.called)
            self.assertEqual(read(Path(tmp)/'control/status.json')['state'], 'blocked')

    def test_missing_cases_are_never_reported_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {'rank': 2, 'openrouter_id': 'provider/model'}
            with patch('sys.argv', ['resume_sweep', '--root', tmp, '--image', 'fixture', '--max-attempts', '0']), \
                 patch('eval_suite.registry.preflight', return_value={'status': 'ready'}), \
                 patch('eval_suite.resume_sweep.read', return_value={'models': [row]}), \
                 patch('eval_suite.resume_sweep.select_cases', return_value=['keep_going/KG-01']):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 75)
            state = read(Path(tmp)/'control/status.json')
            self.assertEqual(state['state'], 'retrying')
            self.assertEqual(state['missing'], {'provider/model': ['keep_going/KG-01']})
