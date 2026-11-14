"""Export reported cases and provider-returned reasoning from controller logs."""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / '.benchmark-runs/rerun-20261107'

def reasoning(message):
    details = message.get('reasoning_details') or []
    parts = []
    saw_readable = False
    for detail in details:
        if not isinstance(detail, dict):
            continue
        kind = detail.get('type')
        text = detail.get('text') if kind == 'reasoning.text' else detail.get('summary') if kind == 'reasoning.summary' else None
        if isinstance(text, str) and text.strip():
            saw_readable = True
            parts.append({'kind': 'Reasoning summary' if kind == 'reasoning.summary' else 'Model reasoning', 'text': text})
        elif kind == 'reasoning.encrypted':
            data = detail.get('data')
            if isinstance(data, str) and data.strip():
                # Same label Inspect uses. The ciphertext stays in `data`; viewers should not present it as readable reasoning.
                parts.append({'kind': 'Reasoning encrypted by model provider', 'text': '', 'data': data, 'format': detail.get('format') or ''})
    # Providers often duplicate the same text in both fields.
    if not saw_readable and message.get('reasoning'):
        parts.insert(0, {'kind': 'Model reasoning', 'text': message['reasoning']})
    return parts


def single_reasoning(submission_path, sub):
    db = submission_path.parent / 'controller/controller.sqlite'
    if not db.exists():
        return []
    prompt = (sub.get('materials') or {}).get('prompt')
    requests, matches = set(), []
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        for (payload,) in conn.execute('SELECT payload FROM transcript ORDER BY seq'):
            record = json.loads(payload)
            kind, data = record['kind'], record['data']
            if kind == 'model_request' and data['body'].get('messages') == [{'role': 'user', 'content': prompt}]:
                requests.add(data['reservation'])
            elif kind == 'model_response' and data['reservation'] in requests and data.get('text') == (sub.get('answer') or ''):
                matches.append(reasoning(data.get('message') or {}))
    if len(matches) > 1 and any(m != matches[0] for m in matches[1:]):
        raise ValueError(f"Ambiguous reasoning for {submission_path} {sub['case_id']}")
    return matches[0] if matches else []


def activity(submission_path, variant):
    db = submission_path.parent / 'controller/controller.sqlite'
    if not db.exists():
        return []
    events, active = [], False
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        for (payload,) in conn.execute('SELECT payload FROM transcript ORDER BY seq'):
            record = json.loads(payload)
            kind, data = record['kind'], record['data']
            if kind == 'model_request':
                messages = data['body'].get('messages') or []
                prompt = messages[0].get('content', '') if messages else ''
                matches = prompt.startswith(f'Build submission.py with a stateless predict(request) for variant {variant}.')
                if matches and not active:
                    events.append({'kind': 'Task prompt', 'text': prompt})
                active = matches
            elif active and kind == 'model_response':
                message = data.get('message') or {}
                events.extend(reasoning(message))
                if message.get('content'):
                    events.append({'kind': 'Assistant message', 'text': message['content']})
                for call in message.get('tool_calls') or []:
                    events.append({'kind': 'Tool call', 'name': call['function']['name'], 'text': call['function']['arguments']})
            elif active and kind == 'tool_result':
                result = data['result']
                if data['call']['function']['name'] == 'execute':
                    result = {k: v for k, v in result.items() if k in {'stdout', 'stderr', 'exit_code', 'failure_reason', 'stdout_truncated', 'stderr_truncated'}}
                events.append({'kind': 'Tool result', 'name': data['call']['function']['name'], 'text': json.dumps(result, indent=2)})
            elif active and kind == 'research_finished':
                break
    return events


def build(activity_dir=None):
    traces = []
    for model in json.loads((RUN / 'final-leaderboard.json').read_text())['leaderboard']:
        for case in model['cases']:
            submission = json.loads((ROOT / case['submission']).read_text())
            sub = next(s for s in submission['cases'] if s['case_id'] == case['case_id'])
            judged = json.loads((ROOT / case['judged']).read_text())
            judge = next(s for s in judged['cases'] if s['case_id'] == case['case_id'])
            activity_path = None
            if case['task'] == 'beat_ectemp' and activity_dir is not None:
                variant = case['case_id'].split('/')[0]
                name = f"{model['roster_rank']}-{Path(case['submission']).parent.name}-{variant}.json"
                events = activity(ROOT / case['submission'], variant)
                if events:
                    serialized = json.dumps(events, ensure_ascii=False, indent=2)
                    assert not re.search(r'sk-(?:or-v1|ant|proj)-[A-Za-z0-9_-]{16,}', serialized)
                    (activity_dir / name).write_text(serialized)
                    activity_path = f'/traces/activity/{name}'
            case_reasoning = single_reasoning(ROOT / case['submission'], sub) if case['task'] != 'beat_ectemp' else []
            traces.append(dict(reasoning=case_reasoning,activity_path=activity_path,id=f"{model['roster_rank']}-{case['task']}-{case['case_id']}", model=model['display'], task=case['task'], case=case['case_id'], score=case['combined'], status=case['judge_status'], components=case['components'], prompt=(sub.get('materials') or {}).get('prompt'), answer=sub.get('answer'), grade=sub.get('grader'), judge=judge.get('judge'), finish_reason=sub.get('finish_reason')))
    assert len({t['id'] for t in traces}) == len(traces)
    assert len({t['model'] for t in traces}) == 14
    payload = json.dumps(traces, ensure_ascii=False, indent=2)
    assert not re.search(r'sk-(?:or-v1|ant|proj)-[A-Za-z0-9_-]{16,}', payload)
    return payload

if __name__ == '__main__':
    import sys
    target = Path(sys.argv[1])
    activity_dir = target.parent / 'activity'
    activity_dir.mkdir(exist_ok=True)
    target.write_text(build(activity_dir))
