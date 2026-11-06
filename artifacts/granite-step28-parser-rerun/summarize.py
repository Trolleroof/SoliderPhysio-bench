"""Verify nine rerun receipts and recompute the existing ten-model pool in memory."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SITE = Path('/Users/nikhi/.codex/worktrees/granite-leaderboard/sd-biodefense 2/site')
BENCH = Path('/Users/nikhi/defensebio-physiology-plan/.claude/worktrees/compact-bench-eval/benchmarks/compact-coding-v1')
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(SITE / 'scripts'))
from research_env.leaderboard import verify, outcome
from research_env.core.common import read, write
source = read(ROOT / 'published-results-input.json')
published_audit = read(ROOT / 'published-elo-input.json')
target = next(m for m in source['models'] if m.get('competitor') == 'Fine-tuned Granite Micro for Defense')
label = target['competitor']
original = {(r['task'], r['seed']): r for r in read(ROOT / 'original-scores.json')}
receipts = [verify(read(p)) for p in sorted((ROOT / 'run').glob('runs/**/receipt.json'))]
assert len(receipts) == 9
assert {(r['run']['task'], r['run']['seed']) for r in receipts} == set(original)
cases = []
for receipt in receipts:
    run, score = receipt['run'], receipt['score']
    assert run['suite_sha256'] == source['suite_sha256']
    assert run['configuration']['checkpoint']['manifest_sha256'] == read(ROOT / 'config.json')['checkpoint']['manifest_sha256']
    prior = original[(run['task'], run['seed'])]
    row = next(r for r in source['raw_scores'] if (r['model'], r['task'], r['seed']) == (label, run['task'], run['seed']))
    row.update(execution_valid=score['execution_valid'], primary_loss=score['primary_loss'], failure_reason=score['failure_reason'])
    cases.append({'task': run['task'], 'seed': run['seed'], 'original_valid': prior['score']['execution_valid'],
                  'rerun_valid': score['execution_valid'], 'original_loss': prior['score']['primary_loss'],
                  'rerun_loss': score['primary_loss'], 'failure_reason': score['failure_reason'],
                  'original_receipt_sha256': prior['receipt_sha256'], 'rerun_receipt_sha256': receipt['sha256']})
def replay(board, task=None):
    # Keep the published match schedule: sorting renamed display names changes Elo order.
    ratings = {m['competitor']: 1000.0 for m in board['entries']}
    lookup = {(r['model'], r['task'], r['seed']): r for r in source['raw_scores']}
    for match in board['matches']:
        t, seed = (task, match['seed']) if task else match['seed']
        a, b = match['a'], match['b']
        win = outcome(lookup[(a, t, seed)], lookup[(b, t, seed)], 'prediction')
        assert win == match['outcome'], 'Rerun changed a match outcome'
        if win is None:
            continue
        delta = 32 * (win - 1 / (1 + 10 ** ((ratings[b] - ratings[a]) / 400)))
        assert abs(delta - match['delta']) < 1e-9
        ratings[a] += delta
        ratings[b] -= delta
    for entry in board['entries']:
        assert abs(ratings[entry['competitor']] - entry['elo']) < 1e-9
    return ratings[label]

overall = replay(published_audit['overall'])
task_ratings = {t: replay(published_audit['tasks'][t], t) for t in ('pulse', 'heat', 'load')}
summary = {'status': 'complete', 'episodes': 9, 'valid': sum(c['rerun_valid'] for c in cases),
           'original_valid': sum(c['original_valid'] for c in cases),
           'original_pooled_elo': target['overall_elo'], 'rerun_pooled_elo': overall,
           'pooled_elo_change': overall - target['overall_elo'],
           'original_task_elo': {t: target['tasks'][t]['elo'] for t in ('pulse', 'heat', 'load')},
           'rerun_task_elo': task_ratings,
           'rating_verification': 'Replayed all published matches, preserving their order; every outcome, delta and final model rating is unchanged.',
           'process_reviews': 'Not rerun; prediction Elo does not use process reviews. Original reviews were not copied to the rerun.',
           'site_changed': False, 'cases': cases}
write(ROOT / 'comparison.json', summary)
write(ROOT / 'rerun-pooled-elo-audit.json', published_audit)
print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}, indent=2))
