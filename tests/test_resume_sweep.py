import tempfile
import unittest
from pathlib import Path
from eval_suite.core.common import write
from eval_suite.resume_sweep import inventory

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
