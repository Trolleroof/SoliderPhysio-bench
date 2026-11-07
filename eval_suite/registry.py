"""Only the three confirmed new tasks belong to the active suite."""
import json
from pathlib import Path

ACTIVE_TASK_IDS = ('keep-going-or-pull-him', 'rulebook-versus-body', 'beat-ectemp')
ROOT = Path(__file__).resolve().parent.parent


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


def preflight(task_ids=ACTIVE_TASK_IDS):
    results = []
    for task_id in task_ids:
        task = resolve(task_id)
        missing = list(task['missing'])
        if not (ROOT/task['specification']).is_file():
            missing.append('task specification file')
        # No legacy adapter/provider fallback. A flag cannot replace implementation.
        results.append({'id':task_id, 'title':task['title'], 'ready':False,
                        'status':'implementation_required', 'missing':missing})
    return {'status':'blocked', 'tasks':results, 'model_requests_sent':0}


def run_task(task_id):
    task = preflight([task_id])['tasks'][0]
    raise TaskNotReadyError(
        f"{task['title']} is not implemented yet: " + '; '.join(task['missing']) +
        '. No model request was sent. Legacy tasks cannot be used as a fallback.'
    )
