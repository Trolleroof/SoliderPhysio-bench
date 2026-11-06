"""Grade 'Keep going or pull him?' answers against the private ground truth.

Primary score: was the KEEP/PULL decision right? Secondary: absolute error of the model's
core-temperature estimate (C) against the measured rectal value at cutoff+15.

Library use:
    from tasks.keep_going.evaluator import grade, score_all
    grade('KG-02', model_text) -> dict
    score_all({'KG-01': text, ...}) -> summary dict

CLI:
    python -m tasks.keep_going.evaluator responses.json [--out scores.json]
    responses.json is {"KG-01": "<raw model text>", ...} or a list of {"task_id":..., "response":...}.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIVATE_PATH = HERE / 'private_ground_truth.json'
PUBLIC_PATH = HERE / 'public_tasks.json'

DECISIONS = ('KEEP', 'PULL')


def load_ground_truth(path=PRIVATE_PATH):
    data = json.loads(Path(path).read_text())
    return {t['task_id']: t for t in data['tasks']}


def load_public(path=PUBLIC_PATH):
    data = json.loads(Path(path).read_text())
    return {t['task_id']: t for t in data['tasks']}


def _first_json_object(text):
    """Return the first parseable JSON object in text, tolerating code fences and prose."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    starts = [m.start() for m in re.finditer(r'\{', text)]
    for i in starts:
        depth = 0
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[i:j + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r'-?\d+(?:\.\d+)?', value)
        if m:
            return float(m.group())
    return None


def parse_response(text):
    """Extract decision, core estimate and confidence from raw model text.

    Returns {'decision': 'KEEP'|'PULL'|None, 'core_c_in_15_min': float|None,
             'confidence': float|None, 'parse_mode': 'json'|'text'|'none'}.
    """
    out = {'decision': None, 'core_c_in_15_min': None, 'confidence': None, 'parse_mode': 'none'}
    if not isinstance(text, str) or not text.strip():
        return out
    obj = _first_json_object(text)
    if obj is not None:
        out['parse_mode'] = 'json'
        d = str(obj.get('decision', '')).strip().upper()
        if d in DECISIONS:
            out['decision'] = d
        elif 'PULL' in d and 'KEEP' not in d:
            out['decision'] = 'PULL'
        elif 'KEEP' in d and 'PULL' not in d:
            out['decision'] = 'KEEP'
        out['core_c_in_15_min'] = _number(obj.get('core_c_in_15_min'))
        out['confidence'] = _number(obj.get('confidence'))
        if out['confidence'] is not None and not 0 <= out['confidence'] <= 1:
            out['confidence'] = None
        if out['decision'] is not None:
            return out
    # Plain-text fallback: the decision word that appears as a standalone verdict.
    upper = text.upper()
    has_pull = re.search(r'\bPULL\b', upper) is not None
    has_keep = re.search(r'\bKEEP\b', upper) is not None
    if has_pull != has_keep:
        out['decision'] = 'PULL' if has_pull else 'KEEP'
        out['parse_mode'] = 'text' if out['parse_mode'] == 'none' else out['parse_mode']
    elif has_pull and has_keep:
        # Both words present (e.g. "keep going or pull"): take an explicit "decision: X" if any.
        m = re.search(r'DECISION\**\s*[:=]?\s*\**\s*(KEEP|PULL)\b', upper)
        if m:
            out['decision'] = m.group(1)
            out['parse_mode'] = 'text' if out['parse_mode'] == 'none' else out['parse_mode']
    if out['confidence'] is not None and not 0 <= out['confidence'] <= 1:
        out['confidence'] = None
    return out


def grade(task_id, response_text, ground_truth=None):
    """Grade one response. Raises KeyError for unknown task ids."""
    gt = (ground_truth or load_ground_truth())[task_id]
    parsed = parse_response(response_text)
    expected = gt['expected_decision']
    truth_c = gt['core_at_cutoff_plus_15_c']
    est = parsed['core_c_in_15_min']
    correct = parsed['decision'] == expected
    return {
        'task_id': task_id,
        'role': gt['role'],
        'design': gt['design'],
        'expected_decision': expected,
        'model_decision': parsed['decision'],
        'decision_correct': bool(correct),
        'score': 1.0 if correct else 0.0,
        'parse_mode': parsed['parse_mode'],
        'core_truth_c': truth_c,
        'core_estimate_c': est,
        'core_abs_error_c': None if est is None else round(abs(est - truth_c), 2),
        'confidence': parsed['confidence'],
        'error_type': (None if correct else
                       'unparsed' if parsed['decision'] is None else
                       'missed_pull' if expected == 'PULL' else 'false_pull'),
    }


def score_all(responses, ground_truth=None):
    """responses: {task_id: raw text}. Missing tasks count as unparsed (score 0)."""
    gt = ground_truth or load_ground_truth()
    if isinstance(responses, list):
        responses = {r['task_id']: r.get('response', '') for r in responses}
    results = [grade(tid, responses.get(tid, ''), gt) for tid in gt]
    primary = [r for r in results if r['role'] == 'primary']
    edge = [r for r in results if r['role'] == 'edge_case']
    errors = [r['core_abs_error_c'] for r in results if r['core_abs_error_c'] is not None]
    by_design = {r['design']: r['decision_correct'] for r in results}
    return {
        'n_tasks': len(results),
        'primary_accuracy': sum(r['score'] for r in primary) / len(primary) if primary else None,
        'overall_accuracy': sum(r['score'] for r in results) / len(results),
        'edge_case_correct': all(r['decision_correct'] for r in edge) if edge else None,
        'thermal_lag_trap_caught': by_design.get('falling_power_thermal_lag'),
        'false_pulls': sum(r['error_type'] == 'false_pull' for r in results),
        'missed_pulls': sum(r['error_type'] == 'missed_pull' for r in results),
        'unparsed': sum(r['error_type'] == 'unparsed' for r in results),
        'core_mae_c': round(sum(errors) / len(errors), 3) if errors else None,
        'results': results,
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    out_path = None
    if '--out' in argv:
        i = argv.index('--out')
        out_path = Path(argv[i + 1])
        del argv[i:i + 2]
    responses = json.loads(Path(argv[0]).read_text())
    summary = score_all(responses)
    text = json.dumps(summary, indent=2)
    if out_path:
        out_path.write_text(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
