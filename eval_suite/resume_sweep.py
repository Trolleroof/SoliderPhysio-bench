"""Resume a roster sweep from saved, uniquely identified cases and spend ledgers."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from eval_suite.core.common import read, write
from eval_suite.runner import select_cases

CAPS = {2:35, 3:15, 4:35, 5:45, 6:10, 7:25, 8:25, 9:35,
        10:70, 11:50, 12:50, 13:35, 14:70, 15:70}


def inventory(root, row):
    cases, spend = {}, 0.0
    for p in sorted(root.glob('*/submissions.json')):
        d = read(p)
        if d.get('model') != row['openrouter_id']:
            continue
        spend += d.get('spend', {}).get('accounted_usd', 0)
        for c in d.get('cases', []):
            key = c['task']+'/'+c['case_id']
            if key in cases:
                raise ValueError(f'duplicate completed case {key}: {cases[key]} and {p}')
            cases[key] = str(p)
    return cases, spend


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--image', required=True)
    ap.add_argument('--max-attempts', type=int, default=3)
    args = ap.parse_args()
    roster = read('eval_suite/roster.json')['models']
    required = select_cases()
    for row in roster:
        rank = row['rank']
        if rank not in CAPS or not row.get('openrouter_id'):
            print(f'SKIP {rank}: no available provider', flush=True)
            continue
        for attempt in range(1, args.max_attempts+1):
            found, spent = inventory(args.root, row)
            missing = [c for c in required if c not in found]
            if not missing:
                print(f'COMPLETE {rank}: all {len(required)} cases', flush=True)
                break
            remaining = round(CAPS[rank]-spent, 9)
            if remaining <= 0:
                print(f'STOP {rank}: cap reached ({spent:.4f})', flush=True)
                break
            idx = 1
            while (args.root/f'continued-{rank:02d}-{idx:02d}').exists():
                idx += 1
            output = args.root/f'continued-{rank:02d}-{idx:02d}'
            cmd=[sys.executable,'-m','eval_suite','run','--model',str(rank), '--cases',','.join(missing),
                 '--spend-cap-usd',str(remaining),'--backend','docker','--image',args.image,'--out',str(output)]
            print(f'START {rank} attempt {attempt}: {len(missing)} missing, remaining cap ${remaining:.4f}',flush=True)
            proc=subprocess.run(cmd,stdin=subprocess.DEVNULL,check=False)
            print(f'EXIT {rank}: {proc.returncode}',flush=True)
            path=output/'submissions.json'
            if path.exists() and read(path).get('cases'):
                judge=args.root/(output.name+'-judge')
                subprocess.run([sys.executable,'-m','eval_suite.judge_sweep',str(path),'--allow-partial',
                                '--out',str(judge),'--spend-cap-usd','5'],stdin=subprocess.DEVNULL,check=False)
        found, spent = inventory(args.root, row)
        write(args.root/f'coverage-{rank:02d}.json', {'model':row['openrouter_id'], 'cases':found,
              'missing':[c for c in required if c not in found], 'accounted_usd':spent})
    print('Sweep pass finished; inspect coverage files and judge failures.',flush=True)


if __name__ == '__main__':
    main()
