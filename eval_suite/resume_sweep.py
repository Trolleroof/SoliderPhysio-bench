"""Resume a roster sweep from saved, uniquely identified cases and spend ledgers."""
import argparse
import json
import fcntl
import os
import time
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
    args.root = args.root.resolve()
    control = args.root/'control'
    control.mkdir(parents=True, exist_ok=True)
    lock = (control/'sweep.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise SystemExit('A sweep supervisor already holds the lock')
    status = {'pid': os.getpid(), 'started_at': time.time(), 'state': 'running'}

    def checkpoint(**fields):
        status.update(fields, heartbeat_at=time.time())
        write(control/'status.json', status)

    def execute(cmd, phase, rank):
        checkpoint(phase=phase, rank=rank)
        child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)
        checkpoint(child_pid=child.pid)
        while True:
            try:
                code = child.wait(timeout=20)
                checkpoint(child_pid=None, last_exit_code=code)
                return code
            except subprocess.TimeoutExpired:
                checkpoint()

    checkpoint(phase='preflight')
    from eval_suite.registry import preflight
    report = preflight(backend='docker', image=args.image)
    if report['status'] != 'ready':
        checkpoint(state='blocked', preflight=report)
        lock.close()
        raise SystemExit('Worker preflight failed; see control/status.json')
    awake = None
    if sys.platform == 'darwin':
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    roster = read('eval_suite/roster.json')['models']
    required = select_cases()
    blocked = {}
    judge_failures = []
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
                blocked[row['openrouter_id']] = 'spend cap reached'
                break
            idx = 1
            while (args.root/f'continued-{rank:02d}-{idx:02d}').exists():
                idx += 1
            output = args.root/f'continued-{rank:02d}-{idx:02d}'
            cmd=[sys.executable,'-m','eval_suite','run','--model',str(rank), '--cases',','.join(missing),
                 '--spend-cap-usd',str(remaining),'--backend','docker','--image',args.image,'--out',str(output)]
            print(f'START {rank} attempt {attempt}: {len(missing)} missing, remaining cap ${remaining:.4f}',flush=True)
            code=execute(cmd, 'model', rank)
            print(f'EXIT {rank}: {code}',flush=True)
            saved = output/'submissions.json'
            if saved.exists() and 'SpendLimitReached' in read(saved).get('error', ''):
                blocked[row['openrouter_id']] = read(saved)['error']
                break
        found, spent = inventory(args.root, row)
        write(args.root/f'coverage-{rank:02d}.json', {'model':row['openrouter_id'], 'cases':found,
              'missing':[c for c in required if c not in found], 'accounted_usd':spent})
        # Visit all sources, including cases preserved before the supervisor existed.
        for source in sorted(set(found.values())):
            path = Path(source)
            submission = read(path)
            judge_dir = args.root/(path.parent.name+'-judge')
            identity = judge_dir/'identity.json'
            from eval_suite.core.common import digest
            if identity.exists() and read(identity).get('submission_sha256') != digest(submission):
                judge_dir = args.root/(path.parent.name+'-judge-'+digest(submission)[:12])
            judged_path = judge_dir/'judged.json'
            if judged_path.exists():
                judged = read(judged_path)
                if len(judged['cases']) == len(submission['cases']) and all(
                    c['judge_record']['status'] in ('scored', 'absent_answer') for c in judged['cases']):
                    continue
            command = [sys.executable,'-m','eval_suite.judge_sweep',str(path),'--allow-partial',
                       '--out',str(judge_dir),'--spend-cap-usd','5']
            if (judge_dir/'spend.sqlite').exists():
                import sqlite3
                db = sqlite3.connect(judge_dir/'spend.sqlite')
                limit = db.execute('SELECT limit_nano FROM budget WHERE id=1').fetchone()[0]/1e9
                db.close()
                command[-1] = str(limit)
            code = execute(command, 'judge', rank)
            if code != 0 or not judged_path.exists() or any(
                c['judge_record']['status'] not in ('scored', 'absent_answer')
                for c in read(judged_path)['cases']
            ) or len(read(judged_path)['cases']) != len(submission['cases']):
                judge_failures.append(str(judge_dir))

    missing = {}
    for row in roster:
        if row.get('openrouter_id'):
            found, _ = inventory(args.root, row)
            todo = [c for c in required if c not in found]
            if todo:
                missing[row['openrouter_id']] = todo
    retry = any(model not in blocked for model in missing)
    checkpoint(state='retrying' if retry else 'blocked' if missing or judge_failures else 'complete',
               phase='audit', child_pid=None, missing=missing, blocked=blocked,
               judge_failures=judge_failures)
    lock.close()
    if awake is not None:
        awake.terminate()
        awake.wait()
    print('Sweep pass finished; inspect coverage files and judge failures.',flush=True)
    if retry:
        raise SystemExit(75)


if __name__ == '__main__':
    main()
