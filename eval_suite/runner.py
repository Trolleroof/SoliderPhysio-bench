"""Roster inference, bounded public research, and judge-compatible submissions."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import signal
import tempfile
import time

from eval_suite.core.common import digest, read, tree_hashes, write
from eval_suite.core.openrouter import OpenRouterClient, api_key
from eval_suite.core.spend import SpendLedger
from eval_suite.core.transcript import Transcript
from eval_suite.core import worker
from eval_suite.registry import ROOT, ACTIVE_TASK_IDS, preflight, TaskNotReadyError

TASKS = dict(zip(ACTIVE_TASK_IDS, ('keep_going', 'rulebook_vs_body', 'beat_ectemp')))
WORKBOOK = ROOT/'sources/figshare-heat/core_cycling_2025.xlsx'
TOOLS = [
    {'type': 'function', 'function': {'name': 'execute', 'description': 'Run an offline command in the public workspace.',
     'parameters': {'type': 'object', 'properties': {'argv': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['argv'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {'name': 'dev_score', 'description': 'Score current submission.py on development people; labels stay private.',
     'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}},
]
STATEMENT = '''Build submission.py with a stateless predict(request) for variant {variant}.
Return JSON-compatible {{"mean": number, "lower": number, "upper": number}}: Celsius and a 90% interval, 0 < width <= 5 C.
3A forecasts core temperature +15 minutes at every origin after the first watts decrease.
3B estimates current core temperature on every request. Only the causal history is provided.
History fields: time_min, hr (bpm), skin_temp (C), watts, ambient_temp (C), humidity (%), age (years), mass (kg), height (cm). Missing inputs are null.
Optimize person-balanced mean absolute error on the scored requests; the scorer separately reports interval coverage and interval score.
Use only train.json (labeled training people), dev_requests.json (unlabeled development requests), ectemp_baseline.py, and template.py in this workspace.
The template is an ECTemp-style comparator, not a validated reproduction of published ECTemp.
Start by copying template.py to submission.py and calling dev_score to establish a working baseline. Keep a runnable submission.py throughout research. Python stdlib is guaranteed; check imports before relying on optional installed packages.
Use execute with an argv list (e.g. ["python3", "-c", "..."]) to inspect data, write submission.py, and run experiments. Use dev_score for verified development metrics.
No network, repository, original workbook, development labels, or hidden data are accessible. Do not identify people or obtain other data.
Hidden testing uses different people and independently shifted clocks. Avoid absolute time and identity shortcuts.
You have {seconds:g} seconds and at most {steps} model turns; each command has at most 60 seconds. Finish early if ready.
Submit your final research explanation as a normal text response without tool calls, describing your frozen predictor, actual development evidence, causal inputs, uncertainty and limitations.
Only submission.py and files you write here are retained; do not claim unrun experiments.
'''
PREDICT = '''import sys,json,importlib.util,os
sys.path.insert(0,os.getcwd())
out,sys.stdout=sys.stdout,sys.stderr
spec=importlib.util.spec_from_file_location('submission','submission.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for line in sys.stdin:
    result=m.predict(json.loads(line))
    out.write(json.dumps(result,allow_nan=False)+'\\n');out.flush()
'''


def roster_model(value):
    for row in read(ROOT/'eval_suite/roster.json')['models']:
        if str(value) in (str(row['rank']), row['apex_model_id'], row.get('openrouter_id'), row['model']):
            if not row.get('openrouter_id'):
                raise ValueError(f"Skipped {row['model']}: no openrouter_id in roster")
            return row
    raise ValueError(f'Unknown roster model: {value}')


def select_cases(task_ids='all', cases=None):
    selected = list(TASKS.values()) if task_ids == 'all' else [TASKS.get(t, t) for t in task_ids.split(',')]
    if not selected or any(t not in TASKS.values() for t in selected):
        raise ValueError('Unknown tasks; use all, '+', '.join(TASKS.values()))
    required = read(ROOT/'tasks/scoring_params.json')['required_cases']
    result = [c for c in required if c.split('/')[0] in selected]
    if cases:
        wanted = cases.split(',') if isinstance(cases, str) else list(cases)
        matches = [c for c in result if c in wanted or c.split('/', 1)[1] in wanted]
        if any(not any(w in (c, c.split('/', 1)[1]) for c in matches) for w in wanted):
            raise ValueError('Cases must belong to selected frozen required_cases (KG-03 is excluded)')
        result = matches
    return result


def run(model, out, spend_cap_usd, *, task_ids='all', cases=None, client=None,
        backend='docker', image=None, research_seconds=1200, max_steps=64, max_tokens=131072, request_timeout=900):
    row = roster_model(model)
    selected = select_cases(task_ids, cases)
    if not 0 < research_seconds <= 1200 or not 1 <= max_steps <= 64 or max_tokens <= 0 or not 0 < request_timeout <= 1200:
        raise ValueError('Invalid research/token limits (wall <=1200s, turns <=64)')
    report = preflight([k for k, v in TASKS.items() if any(c.startswith(v+'/') for c in selected)],
                       backend=backend, image=image)
    if report['status'] != 'ready':
        raise TaskNotReadyError(json.dumps(report))
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Output directory must be empty; use a new directory to preserve prior evidence')
    fake = client is not None
    client = client or OpenRouterClient(api_key(ROOT), timeout_s=request_timeout)
    ledger = SpendLedger(out/'spend.sqlite', spend_cap_usd)
    transcript = Transcript(out/'controller')
    # OpenRouter's effort vocabulary uses xhigh, not max. Keep both for audit.
    effort = 'xhigh' if row['effort'] == 'max' else row['effort']
    # Requested budget is clamped to the provider's advertised output limit (roster).
    max_tokens = min(max_tokens, row.get('max_output_tokens') or max_tokens)
    settings = {'max_tokens': max_tokens, 'reasoning': {'effort': effort},
                'provider': {'require_parameters': True, 'max_price': {
                    'prompt': row['usd_per_mtok_in'], 'completion': row['usd_per_mtok_out'], 'request': 0}}}
    pricing = {'prompt': row['usd_per_mtok_in']/1e6, 'completion': row['usd_per_mtok_out']/1e6}
    result = {'schema': 'model-runner-v1', 'model': row['openrouter_id'], 'roster': row,
              'settings': settings, 'official': False, 'fake_model': fake, 'backend': backend,
              'image': image, 'request_timeout_s': request_timeout, 'required_cases': selected, 'cases': [], 'status': 'running',
              'scoring_params_sha256': digest(read(ROOT/'tasks/scoring_params.json'))}
    transcript.append('run_start', result)

    def save():
        result['spend'] = ledger.summary()
        write(out/'submissions.json', result)

    def complete(messages, tools=None, remaining=None, final=False):
        timeout = min(request_timeout, remaining) if remaining is not None else request_timeout
        body = {'model': row['openrouter_id'], **settings, 'messages': messages}
        if tools:
            body['tools'] = tools
            if final:
                body['tool_choice'] = 'none'
        deadline = time.monotonic() + timeout
        for attempt in range(1, 4):
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('Model request wall budget exhausted')
            reservation = ledger.reserve(body, pricing)
            transcript.append('model_request', {'reservation': reservation, 'attempt': attempt, 'body': body,
                              'prompt_sha256': digest(messages), 'request_sha256': digest(body)})
            save()
            def expired(*_):
                raise TimeoutError('Model request wall budget exhausted')
            previous = signal.signal(signal.SIGALRM, expired)
            signal.setitimer(signal.ITIMER_REAL, left)
            try:
                response = client.complete(body, timeout_s=left)
                transcript.append('model_response', {'reservation': reservation, **response})
                ledger.settle(reservation, response.get('usage') or {})
                return response
            except BaseException as exc:
                transcript.append('model_error', {'reservation': reservation, 'attempt': attempt, 'error': str(exc)})
                if not isinstance(exc, (ConnectionResetError, BrokenPipeError)) or attempt == 3:
                    raise
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous)
                save()

    def execute(public, argv, timeout=60, requests=None):
        execution = worker.execute(public, argv, timeout_s=timeout, backend=backend, image=image,
                                   cpus=2, memory_gb=1, requests=requests)
        transcript.append('worker', execution)
        return execution

    def predictor(public, batch, timeout=120):
        # Each scoring call gets a disposable copy, keeping submitted artifacts immutable.
        tree_hashes(public)
        with tempfile.TemporaryDirectory(prefix='predictor-') as tmp:
            staged = Path(tmp)/'public'
            shutil.copytree(public, staged)
            execution = execute(staged, ['python3', '-I', '-c', PREDICT], timeout, batch)
        if not execution['execution_valid']:
            raise ValueError('Predictor execution failed: '+str(execution['failure_reason']))
        return execution['responses']

    try:
        for key in selected:
            task, case = key.split('/', 1)
            if task == 'beat_ectemp':
                continue
            prompt = (ROOT/'tasks'/task/'prompts'/f'{case}.md').read_text()
            response = complete([{'role': 'user', 'content': prompt}])
            from tasks.judge import grade_case
            result['cases'].append({'task': task, 'case_id': case, 'run': 0, 'answer': response['text'],
                                    'grader': grade_case(task, case, response['text']),
                                    'materials': {'prompt': prompt}, 'prompt_sha256': digest(prompt),
                                    'usage': response.get('usage'), 'finish_reason': response.get('finish_reason')})
            save()
        variants = sorted({c.split('/')[1] for c in selected if c.startswith('beat_ectemp/')})
        if variants:
            from tasks.beat_ectemp import benchmark
            benchmark.build(WORKBOOK, None, out/'public_seed', out/'private')
        for variant in variants:
            public = out/variant/'workspace'
            shutil.copytree(out/'public_seed', public)
            statement = STATEMENT.format(variant=variant, seconds=research_seconds, steps=max_steps)
            messages = [{'role': 'user', 'content': statement}]
            dev_results, answer = [], ''
            started = time.monotonic()
            deadline = started+research_seconds
            stop = 'turn_limit'
            for step in range(max_steps):
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    stop = 'wall_limit'
                    break
                try:
                    final = step == max_steps-1 or remaining <= min(30, research_seconds*.15)
                    if final:
                        messages.append({'role': 'user', 'content': 'Final turn: submit your research explanation now. No more tool calls are available.'})
                    response = complete(messages, TOOLS, remaining, final=final)
                except TimeoutError:
                    stop = 'wall_limit'
                    break
                message = response.get('message') or {'role': 'assistant', 'content': response['text']}
                messages.append(message)
                calls = message.get('tool_calls') or []
                if not calls:
                    answer, stop = response['text'], 'submitted'
                    break
                for call in calls:
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        stop = 'wall_limit'
                        break
                    fn = call['function']
                    try:
                        args = json.loads(fn['arguments'])
                        if fn['name'] == 'execute':
                            reply = execute(public, args['argv'], min(60, remaining))
                        elif fn['name'] == 'dev_score':
                            reply = benchmark.evaluate(public, out/'private', variant, hidden=False,
                                runner=lambda p, batch: predictor(p, batch, min(60, remaining)))
                            dev_results.append(reply)
                        else:
                            raise ValueError('Unknown tool')
                    except (ValueError, KeyError, TypeError) as exc:
                        reply = {'error': str(exc)}
                    # Bound context while retaining the full result in the transcript.
                    transcript.append('tool_result', {'call': call, 'result': reply})
                    messages.append({'role': 'tool', 'tool_call_id': call['id'],
                                     'content': json.dumps({'result': reply, 'remaining_model_turns': max_steps-step-1,
                                                            'remaining_seconds': max(0, deadline-time.monotonic())})[:20000]})
            # Freeze before hidden scoring. Never send hidden metrics or workspace back to the model.
            research_wall_s = time.monotonic()-started
            hashes = tree_hashes(public)
            frozen = out/variant/'artifact'
            shutil.copytree(public, frozen)
            write(out/variant/'artifact_hashes.json', hashes)
            hidden = benchmark.evaluate(frozen, out/'private', variant, hidden=True, runner=predictor)
            write(out/variant/'grader.json', hidden)
            transcript.append('research_finished', {'variant': variant, 'stop': stop, 'wall_s': research_wall_s, 'artifact_hashes': hashes,
                                                   'hidden': hidden})
            for key in selected:
                if key.startswith(f'beat_ectemp/{variant}/'):
                    person = key.rsplit('/', 1)[1]
                    result['cases'].append({'task': 'beat_ectemp', 'case_id': variant+'/'+person, 'run': 0,
                        'answer': answer, 'grader': {'valid': hidden['valid'],
                            'person_mae': (hidden.get('person_mae') or {}).get(person)},
                        'materials': {'task_statement': statement, 'dev_results': dev_results},
                        'research_stop': stop, 'research_wall_s': research_wall_s, 'artifact_sha256': digest(hashes), 'artifact': f'{variant}/artifact',
                        'grader_report': f'{variant}/grader.json'})
            save()
        result['status'] = 'complete'
        result['official'] = (not fake and selected == read(ROOT/'tasks/scoring_params.json')['required_cases']
                              and (not variants or backend == 'docker'))
    except BaseException as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        transcript.append('run_error', {'error': result['error']})
        raise
    finally:
        save()
        transcript.append('run_end', {'status': result['status'], 'spend': result['spend']})
        transcript.close()
        ledger.close()
    return result
