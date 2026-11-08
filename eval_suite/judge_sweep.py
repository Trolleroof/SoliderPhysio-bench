"""Checkpointed, independent judging of a completed model-runner submission."""
from __future__ import annotations
import argparse
from pathlib import Path

from eval_suite.core.common import digest, read, write
from eval_suite.core.spend import SpendLedger
from eval_suite.core.transcript import Transcript
from tasks.judge import OpenRouterJudgeClient, run_case, load_rubric
from tasks.combined_score import check_judge_model


class FrontierJudge(OpenRouterJudgeClient):
    # Sol Pro uses the Sol model with the provider's higher-compute pro mode;
    # neither Sol nor Sol Pro is on the frozen participant roster.
    model = 'openai/gpt-6.1-sol-pro'
    pricing = {'prompt': '0.000002', 'completion': '0.000010'}

    def __init__(self):
        super().__init__(timeout=300)
        self.settings['max_tokens'] = 32768


def run(path, out, cap, *, allow_partial=False):
    submission = read(path)
    if submission.get('status') != 'complete' and not allow_partial:
        raise ValueError('Only completed model runs may be judged unless --allow-partial is set')
    if not submission.get('cases'):
        raise ValueError('No completed cases to judge')
    check_judge_model(FrontierJudge.model, [submission['model']])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rubric = load_rubric()
    client = FrontierJudge()
    identity = {'submission_sha256': digest(submission), 'rubric_sha256': rubric['sha256'],
                'judge_model': client.model, 'settings': client.settings,
                'source_status': submission.get('status')}
    meta = out/'identity.json'
    if meta.exists() and read(meta) != identity:
        raise ValueError('Submission or judge settings changed; use a new output directory')
    write(meta, identity)
    ledger = SpendLedger(out/'spend.sqlite', cap)
    transcript = Transcript(out/'controller')
    try:
        cases = []
        for index, case in enumerate(submission['cases']):
            p = out/f'case-{index:02d}.json'
            record = read(p) if p.exists() else {'input_sha256': digest(case), 'attempts': []}
            if record['input_sha256'] != digest(case):
                raise ValueError('Case changed since previous judge attempt')
            if not record['attempts'] or record['attempts'][-1]['judge_record']['status'] == 'not_scorable':
                result = run_case(case, client, max_attempts=2, ledger=ledger, pricing=client.pricing, transcript=transcript)
                record['attempts'].append(result)
                write(p, record)
            cases.append(record['attempts'][-1])
            write(out/'judged.json', {'model': submission['model'], 'cases': cases,
                                      'identity': identity, 'spend': ledger.summary()})
        return {'model': submission['model'], 'cases': len(cases),
                'not_scorable': sum(c['judge_record']['status'] == 'not_scorable' for c in cases),
                'spend': ledger.summary()}
    finally:
        transcript.close()
        ledger.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('submission')
    p.add_argument('--out', required=True)
    p.add_argument('--spend-cap-usd', required=True, type=float)
    p.add_argument('--allow-partial', action='store_true', help='judge saved cases from an incomplete run')
    a = p.parse_args()
    import json
    print(json.dumps(run(a.submission, a.out, a.spend_cap_usd, allow_partial=a.allow_partial), indent=2))


if __name__ == '__main__':
    main()
