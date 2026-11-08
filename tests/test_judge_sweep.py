import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval_suite.core.common import read, write
from eval_suite import judge_sweep
from tasks.judge import FakeJudgeClient


class JudgeSweepTest(unittest.TestCase):
    def test_checkpoints_and_rejects_changed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'submission.json'
            data = {'status': 'complete', 'model': 'participant', 'cases': [
                {'task': 'keep_going', 'case_id': 'KG-01', 'answer': 'KEEP'}]}
            write(source, data)
            client = FakeJudgeClient(model='fake-judge-v1')
            client.pricing = {'prompt': '0', 'completion': '0'}
            with patch.object(judge_sweep, 'FrontierJudge', return_value=client):
                # check_judge_model also reads the class's model attribute.
                judge_sweep.FrontierJudge.model = client.model
                first = judge_sweep.run(source, root/'out', 1)
                second = judge_sweep.run(source, root/'out', 1)
                self.assertEqual(first['cases'], 1)
                self.assertEqual(second['not_scorable'], 0)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(len(read(root/'out/case-00.json')['attempts']), 1)
                data['cases'][0]['answer'] = 'PULL'
                write(source, data)
                with self.assertRaisesRegex(ValueError, 'changed'):
                    judge_sweep.run(source, root/'out', 1)


if __name__ == '__main__':
    unittest.main()
