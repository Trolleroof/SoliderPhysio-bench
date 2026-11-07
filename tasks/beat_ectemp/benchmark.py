"""Organizer-only data builder and scorer. Never mount this repository for entrants."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

SOURCE_MD5 = '01214bfc835215fe1a5d3f5da1e9ad52'
TRAIN = 'H01 H19 H07 H05 H14 H23 H16 H04 H09 H03 H02 H15 H10 H12'.split()
DEV = 'H21 H24 H08 H17 H20'.split()
TEST = 'H25 H22 H13 H06 H18'.split()
SPLITS = {'train': TRAIN, 'development': DEV, 'test': TEST}


def read_workbook(path):
    import openpyxl
    path = Path(path)
    if hashlib.md5(path.read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Workbook checksum mismatch')
    book = openpyxl.load_workbook(path, data_only=True, read_only=True)
    def series(sheet, start, person, low, high):
        rows = list(book[sheet].values)
        col = next(i for i in range(start, start + 24) if rows[1][i] == person)
        result = {}
        for row in rows[2:]:
            t = row[1]
            if t is None:
                continue
            minute = int(str(t).split('-')[-1])
            value = row[col]
            if isinstance(value, (int, float)) and math.isfinite(value) and low <= value <= high:
                result[minute] = float(value)
        return result
    demos = {int(r[0]): r for r in list(book['Demographics'].values)[1:] if isinstance(r[0], (int, float))}
    people = {}
    for pid in TRAIN + DEV + TEST:
        n = int(pid[1:]); d = demos[n]
        channels = {k: series(s, c, n, lo, hi) for k, s, c, lo, hi in [
            ('core_temp', 'Core Temp', 2, 30, 45), ('skin_temp', 'Skin Temp', 2, 20, 45),
            ('hr', 'Exercise Data', 27, 30, 240), ('watts', 'Exercise Data', 77, 0, 1000),
            ('ambient_temp', 'Environmental Conditions', 2, 0, 60), ('humidity', 'Environmental Conditions', 27, 0, 100)]}
        rows = []
        for t in range(1, 61):
            row = dict(time_min=t, age=d[2], mass=d[4], height=d[3])
            for key, values in channels.items():
                # Forward fill inputs only; never impute labels or look ahead.
                eligible = [v for v in values if v <= t] if key != 'core_temp' else [t] if t in values else []
                row[key] = values[max(eligible)] if eligible else None
            rows.append(row)
        people[pid] = rows
    book.close()
    return people


def requests(rows, task, offset=0):
    dropped = False
    for i, row in enumerate(rows):
        drop = i > 0 and row['watts'] is not None and rows[i-1]['watts'] is not None and row['watts'] < rows[i-1]['watts']
        dropped |= drop
        if task == '3A' and not drop:
            continue
        j = i + 15 if task == '3A' else i
        if j >= len(rows) or rows[j]['core_temp'] is None:
            continue
        history = [{k: v for k, v in r.items() if k != 'core_temp'} for r in rows[:i+1]]
        for r in history:
            r['time_min'] += offset
        yield {'task': task, 'history': history, 'horizon_min': 15 if task == '3A' else 0}, rows[j]['core_temp'], dropped


def build(workbook, split_file, public, private):
    if split_file is not None and json.loads(Path(split_file).read_text()) != SPLITS:
        raise ValueError('Split file does not match frozen person split')
    public, private = Path(public).resolve(), Path(private).resolve()
    if public == private or public in private.parents or private in public.parents:
        raise ValueError('Public and private directories must be separate')
    if public.exists() and any(public.iterdir()):
        raise ValueError('Public destination must be empty')
    people = read_workbook(workbook)
    public.mkdir(parents=True, exist_ok=True); private.mkdir(parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    (public/'train.json').write_text(json.dumps({p: people[p] for p in TRAIN}))
    dev = {task: [r for p in DEV for r, _, _ in requests(people[p], task)] for task in ('3A', '3B')}
    (public/'dev_requests.json').write_text(json.dumps(dev))
    for name in ('ectemp_baseline.py', 'template.py'):
        shutil.copyfile(Path(__file__).with_name(name), public/name)
    (private/'labels.json').write_text(json.dumps(people))


def valid(output):
    try:
        a, b, c = (output[k] for k in ('lower', 'mean', 'upper'))
        return all(type(x) in (int, float) and math.isfinite(x) for x in (a,b,c)) and a <= b <= c and 0 < c-a <= 5
    except (KeyError, TypeError):
        return False


def metrics(outputs, targets, mask):
    if len(outputs) != len(targets) or not all(valid(o) for o in outputs):
        return {'score': 0, 'valid': False, 'mae': None, 'primary_mae': None}
    errors = [abs(o['mean']-y) for o,y in zip(outputs,targets)]
    selected = [e for e,m in zip(errors,mask) if m]
    primary = sum(selected)/len(selected) if selected else None
    coverage = sum(o['lower'] <= y <= o['upper'] for o,y in zip(outputs,targets))/len(targets) if targets else None
    interval = [o['upper']-o['lower'] + 20*max(o['lower']-y,0) + 20*max(y-o['upper'],0) for o,y in zip(outputs,targets)]
    return {'valid': True, 'score': 1/(1+primary) if primary is not None else 0, 'mae': sum(errors)/len(errors) if errors else None,
            'primary_mae': primary, 'primary_count': len(selected), 'coverage_90': coverage,
            'interval_score_90': sum(interval)/len(interval) if interval else None}


WORKER = '''import sys,json,resource,importlib.util
resource.setrlimit(resource.RLIMIT_CPU,(1200,1200))
sys.path.insert(0,sys.argv[1])
out,sys.stdout=sys.stdout,sys.stderr  # submission prints must not corrupt the JSON result
spec=importlib.util.spec_from_file_location("submission",sys.argv[1]+"/submission.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=json.load(sys.stdin)
json.dump([m.predict(x) for x in r],out,allow_nan=False)
'''


def run_submission(public, batch, private=None):
    """macOS sandbox: private data is never inherited or readable; network denied."""
    public = Path(public).resolve()
    sandbox = shutil.which('sandbox-exec')
    if sys.platform != 'darwin' or not sandbox:
        raise RuntimeError('Requires macOS sandbox-exec; refusing unsandboxed execution')
    roots = [str(public), sys.base_prefix, sys.prefix, '/opt/homebrew', '/System', '/usr', '/bin', '/private/var/db', '/private/etc', '/Library/Frameworks', '/dev']
    allows = ' '.join('(subpath '+json.dumps(p)+')' for p in dict.fromkeys(roots + [str(Path(x).resolve()) for x in roots]))
    profile = '(version 1)(deny default)(allow process*)(allow file-read-metadata)(allow sysctl-read)(allow mach-lookup)(allow file-read* (require-any (require-not (subpath "/Users")) '+allows+'))(allow file-write* (literal "/dev/null"))'
    if private is not None:
        profile += '(deny file-read* (subpath '+json.dumps(str(Path(private).resolve()))+'))'
    result = subprocess.run([sandbox,'-p',profile,sys.executable,'-I','-c',WORKER,str(public)],
        input=json.dumps(batch), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=public, env={'PATH':'/usr/bin:/bin'}, timeout=1200)
    if result.returncode:
        raise ValueError('Submission failed ('+str(result.returncode)+'): '+result.stderr[-2000:])
    return json.loads(result.stdout)


def evaluate(public, private, task, hidden=False, runner=run_submission):
    private = Path(private)
    # Record attempts before executing untrusted code, including failures.
    log = private/'calls.jsonl'
    previous = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    call_count = sum(not x['hidden'] for x in previous) + (not hidden)
    with log.open('a') as f:
        f.write(json.dumps({'time':time.time(),'hidden':hidden,'task':task,'public_call_count':call_count})+'\n')
    people = json.loads((private/'labels.json').read_text())
    batch=[]; targets=[]; mask=[]
    for p in TEST if hidden else DEV:
        offset = random.SystemRandom().randint(-100000,100000) if hidden else 0
        for r,y,after_drop in requests(people[p],task,offset):
            batch.append(r); targets.append(y); mask.append(y >= 38.5 and after_drop if hidden else True)
    try:
        outputs = runner(public,batch,private) if runner is run_submission else runner(public,batch)
        result = metrics(outputs,targets,mask)
    except (ValueError, TypeError, subprocess.TimeoutExpired):
        result = metrics([],targets,mask)
    result['public_call_count'] = call_count
    report = private/('public_'+task+'.json')
    if hidden:
        prior = json.loads(report.read_text()) if report.exists() else {}
        result['public_to_hidden_gap'] = result['primary_mae']-prior['mae'] if result['primary_mae'] is not None and prior.get('mae') is not None else None
    else:
        report.write_text(json.dumps(result))
    return result


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build'); b.add_argument('--workbook',required=True); b.add_argument('--splits')
    for cmd in (b,sub.add_parser('score')):
        cmd.add_argument('--public',required=True); cmd.add_argument('--private',required=True)
    s=sub.choices['score']; s.add_argument('--task',choices=['3A','3B'],required=True); s.add_argument('--hidden',action='store_true')
    a=p.parse_args()
    if a.command=='build': build(a.workbook,a.splits,a.public,a.private)
    else: print(json.dumps(evaluate(a.public,a.private,a.task,a.hidden)))

if __name__=='__main__': main()
