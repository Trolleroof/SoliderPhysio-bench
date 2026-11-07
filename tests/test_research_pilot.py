import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_env.core.common import canonical, digest, file_hash, read, write
from research_env.judging.judge import RUBRIC, build_packets
from research_env.leaderboard import seal
from scripts.run_research_pilot import review_selection


class PilotReview(unittest.TestCase):
    def fixture(self, root):
        events = [
            {'event_id':'e00000', 'kind':'initial_evidence', 'content':{'task':'Public task'}},
            {'event_id':'e00001', 'kind':'result', 'result':{'execution_valid':True}},
            {'event_id':'e00002', 'kind':'final_selection', 'candidate_id':'candidate',
             'reason':'Public evidence', 'evidence_ids':['e00001']},
            {'event_id':'e00003', 'kind':'private_test_result', 'secret':'HIDDEN_SCORE'},
        ]
        packets = build_packets(events)
        write(root/'judge-packets.json', packets)
        (root/'trajectory.jsonl').write_bytes(canonical(events))
        write(root/'receipt.json', seal({'judge_packets_sha256':digest(packets),
              'trajectory_sha256':file_hash(root/'trajectory.jsonl'), 'score':{'secret':'HIDDEN_SCORE'}}))
        return packets

    def test_final_review_uses_sealed_public_packet_and_resumes_without_call(self):
        seen = []
        class Judge:
            config = {'fixture':True}
            def __call__(self, packet):
                seen.append(packet)
                return {k:packet[k] for k in ('rubric_version','packet_sha256','event_id')} | {
                    'criteria':{k:{'score':3, 'reason':'Observed evidence', 'evidence_ids':['e00001']} for k in RUBRIC},
                    'flags':[]}, {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            with patch('scripts.run_research_pilot.OpenAICompatibleJudge', return_value=Judge()):
                first = review_selection(root, {}, 'SECRET', None)
                second = review_selection(root, {}, 'SECRET', None)
            self.assertEqual(first['llm_judge_status'], 'complete')
            self.assertEqual(first, second)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]['kind'], 'final_selection')
            self.assertNotIn('HIDDEN_SCORE', canonical(seen).decode())
            self.assertNotIn('SECRET', (root/'selection-review/attempts.json').read_text())

    def test_changed_packet_rejected_before_paid_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packets = self.fixture(root)
            packets[0]['action']['reason'] = 'Changed'
            write(root/'judge-packets.json', packets)
            with patch('scripts.run_research_pilot.OpenAICompatibleJudge') as provider:
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    review_selection(root, {}, 'SECRET', None)
                provider.assert_not_called()

    def test_changed_trajectory_rejected_before_paid_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root/'trajectory.jsonl').write_text('Changed')
            with patch('scripts.run_research_pilot.OpenAICompatibleJudge') as provider:
                with self.assertRaisesRegex(ValueError, 'trajectory changed'):
                    review_selection(root, {}, 'SECRET', None)
                provider.assert_not_called()
