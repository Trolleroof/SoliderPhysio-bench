"""Active task catalog and implementation/runtime preflight (never sends model requests)."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

ACTIVE_TASK_IDS = ('keep-going-or-pull-him', 'rulebook-versus-body', 'beat-ectemp')
ROOT = Path(__file__).resolve().parent.parent
PIECES = {
    ACTIVE_TASK_IDS[0]: ['tasks/keep_going/evaluator.py', 'tasks/keep_going/public_tasks.json',
                         'tasks/keep_going/private_ground_truth.json'],
    ACTIVE_TASK_IDS[1]: ['tasks/rulebook_vs_body/evaluator.py', 'tasks/rulebook_vs_body/task.json',
                         'tasks/rulebook_vs_body/private_ground_truth.json', 'tasks/rulebook_vs_body/tb_med_507.json'],
    ACTIVE_TASK_IDS[2]: ['tasks/beat_ectemp/benchmark.py', 'tasks/beat_ectemp/template.py',
                         'tasks/beat_ectemp/ectemp_baseline.py', 'eval_suite/core/worker.py',
                         'sources/figshare-heat/core_cycling_2025.xlsx'],
}


class TaskNotReadyError(RuntimeError):
    pass


def tasks():
    rows = json.loads(Path(__file__).with_name('tasks.json').read_text())['tasks']
    if tuple(t['id'] for t in rows) != ACTIVE_TASK_IDS:
        raise ValueError('Task catalog must contain exactly the three confirmed new tasks')
    return rows


def resolve(task_id):
    for task in tasks():
        if task['id'] == task_id:
            return task
    raise ValueError(f'Unknown or removed task: {task_id}. Choose one of {ACTIVE_TASK_IDS}')


def preflight(task_ids=ACTIVE_TASK_IDS, *, backend='docker', image=None):
    results = []
    params_path = ROOT/'tasks/scoring_params.json'
    required = json.loads(params_path.read_text())['required_cases'] if params_path.is_file() else []
    for task_id in task_ids:
        task = resolve(task_id)
        paths = [task['specification'], 'eval_suite/runner.py', 'eval_suite/core/openrouter.py',
                 'tasks/scoring_params.json', *PIECES[task_id]]
        folder = {'keep-going-or-pull-him': 'keep_going', 'rulebook-versus-body': 'rulebook_vs_body'}.get(task_id)
        if folder:
            paths += [f'tasks/{folder}/prompts/{key.split("/")[1]}.md'
                      for key in required if key.startswith(folder+'/')]
        missing = [p for p in paths if not (ROOT/p).is_file()]
        if not required:
            missing.append('frozen required_cases')
        if task_id == 'beat-ectemp':
            if importlib.util.find_spec('openpyxl') is None:
                missing.append('openpyxl==3.1.5 (workbook loader)')
            workbook = ROOT/'sources/figshare-heat/core_cycling_2025.xlsx'
            if workbook.is_file() and hashlib.md5(workbook.read_bytes()).hexdigest() != '01214bfc835215fe1a5d3f5da1e9ad52':
                missing.append('frozen workbook checksum mismatch')
            try:
                from eval_suite.core.worker import execute
                with tempfile.TemporaryDirectory() as tmp:
                    probe = execute(tmp, ['python3', '-c', 'print("ready")'], timeout_s=10,
                                    backend=backend, image=image, cpus=1, memory_gb=1)
                if not probe['execution_valid']:
                    missing.append('worker isolation probe: '+str(probe['failure_reason']))
            except Exception as exc:
                missing.append(f'worker isolation unavailable: {type(exc).__name__}: {exc}')
        results.append({'id': task_id, 'title': task['title'], 'ready': not missing,
                        'status': 'blocked' if missing else 'ready', 'missing': missing})
    return {'status': 'ready' if all(t['ready'] for t in results) else 'blocked',
            'tasks': results, 'model_requests_sent': 0, 'backend': backend,
            'official_resource_isolation': backend == 'docker'}


def run_task(task_id, **kwargs):
    resolve(task_id)
    if not {'model', 'out', 'spend_cap_usd'} <= kwargs.keys():
        raise TaskNotReadyError('Explicit model, output and spend cap required. No model request was sent.')
    from eval_suite.runner import run
    return run(task_ids=task_id, **kwargs)
