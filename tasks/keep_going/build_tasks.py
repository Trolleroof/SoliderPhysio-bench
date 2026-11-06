"""Build the 'Keep going or pull him?' no-code prompt tasks from the CORE cycling workbook.

Source: D'Lugos (2025), Figshare 29120024 v1, CC BY 4.0. 24 people, ~60 min of cycling in a
hot chamber, rectal core temperature every minute. The evaluated model never sees core
temperature, the subject ID, or the raw protocol clock; it sees a re-zeroed, rounded window of
wearable-style data and must decide whether to pull the person before core temperature reaches
the threshold 15 minutes later.

Run:  .venv-research/bin/python -m tasks.keep_going.build_tasks
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent.parent / 'sources' / 'figshare-heat' / 'core_cycling_2025.xlsx'
SOURCE_URL = 'https://doi.org/10.6084/m9.figshare.29120024.v1'
SOURCE_MD5 = '01214bfc835215fe1a5d3f5da1e9ad52'

THRESHOLD_C = 38.5          # pull if core at cutoff+HORIZON is at or above this
HORIZON_MIN = 15            # decision horizon in minutes
WINDOW_MIN = 25             # rows shown to the model: cutoff-24 .. cutoff, re-zeroed to 0..24
HR_RANGE = (30, 240)        # HR outside this is a source error (e.g. 1176) and is omitted

PUBLIC_ROW_KEYS = ('time_min', 'hr_bpm', 'skin_c', 'room_temp_c', 'humidity_pct', 'watts')

# Case design. Subject numbers are the original workbook column labels; they never reach
# the public files. Roles: 'primary' (the three scored tasks) and 'edge_case' (Subject 4,
# whose core fell after the power drop; see README for the label caveat).
CASES = [
    {'task_id': 'KG-01', 'subject': 21, 'cutoff': 30, 'role': 'primary',
     'design': 'steady_power_safe',
     'note': 'Steady 140 W for the whole window; core climbs slowly and stays under threshold.'},
    {'task_id': 'KG-02', 'subject': 3, 'cutoff': 30, 'role': 'primary',
     'design': 'falling_power_thermal_lag',
     'note': 'Power cut from 215 W to 180 W five minutes before the cutoff; core keeps rising '
             'through the threshold over the next 15 minutes (thermal lag).'},
    {'task_id': 'KG-03', 'subject': 4, 'cutoff': 44, 'role': 'edge_case',
     'design': 'falling_power_core_fell',
     'note': 'Power cut from 205 W to 188 W three minutes before the cutoff; core peaks then '
             'falls below threshold by cutoff+15. The only falling-power person in the workbook '
             'whose core fell. Final-minute values are steep enough to suggest probe movement; '
             'label confidence is low.'},
    {'task_id': 'KG-04', 'subject': 23, 'cutoff': 30, 'role': 'primary',
     'design': 'steady_power_rising',
     'note': 'Steady 123 W; heart rate drifts upward at constant power and core is already '
             'well above threshold at cutoff+15.'},
]


def _minute(value):
    if isinstance(value, str) and '-' in value:
        return int(value.split('-')[1])  # interval averages are aligned to their right edge
    return int(value)


def _series(sheet, col, lower=None, upper=None):
    out = {}
    for row in range(3, sheet.max_row + 1):
        t, v = sheet.cell(row, 2).value, sheet.cell(row, col).value
        if t is None or v is None:
            continue
        v = float(v)
        if lower is not None and not lower <= v <= upper:
            continue
        out[_minute(t)] = v
    return out


def load_workbook(path=DEFAULT_SOURCE):
    """Return {subject_number: {'demo':..., 'core':..., 'skin':..., 'hr':..., 'watts':..., 'env':...}}."""
    import openpyxl
    path = Path(path)
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    if digest != SOURCE_MD5:
        raise ValueError(f'Workbook checksum mismatch: {digest}')
    w = openpyxl.load_workbook(path, data_only=True, read_only=False)
    core, skin, ex, env, demo = (w[n] for n in ('Core Temp', 'Skin Temp', 'Exercise Data',
                                                  'Environmental Conditions', 'Demographics'))
    core_cols = {int(core.cell(2, c).value): c for c in range(3, 27)}
    skin_cols = {int(skin.cell(2, c).value): c for c in range(3, 27)}
    hr_cols = {int(ex.cell(2, c).value): c for c in range(28, 52)}
    watt_cols = {int(ex.cell(2, c).value): c for c in range(78, 102)}
    env_cols = {int(env.cell(2, c).value): c for c in range(3, 27)}
    if ex.cell(1, 28).value != 'HR' or ex.cell(1, 78).value != 'Wattage':
        raise ValueError('Unexpected Exercise Data layout')
    people = {}
    for r in range(2, demo.max_row + 1):
        d = [demo.cell(r, c).value for c in range(1, 6)]
        if not isinstance(d[0], int):
            continue
        s = d[0]
        people[s] = {
            'demo': {'sex': d[1], 'age_years': float(d[2]), 'height_cm': float(d[3]), 'mass_kg': float(d[4])},
            'core': _series(core, core_cols[s], 30, 45),
            'skin': _series(skin, skin_cols[s], 20, 45),
            'hr': _series(ex, hr_cols[s], *HR_RANGE),
            'watts': _series(ex, watt_cols[s], 0, 1000),
            'env': {t: (a, rh) for t, a in _series(env, env_cols[s], 0, 60).items()
                    for rh in [_series(env, env_cols[s] + 25, 0, 100).get(t)] if rh is not None},
        }
    if len(people) != 24:
        raise ValueError(f'Expected 24 people, found {len(people)}')
    return people


def _r1(x):
    return None if x is None else round(x + 1e-9, 1)


def _ri(x):
    return None if x is None else int(round(x))


def make_window(person, cutoff, window=WINDOW_MIN):
    """Public rows for minutes cutoff-window+1 .. cutoff, re-zeroed to 0 .. window-1 and rounded."""
    start = cutoff - window + 1
    if start < 1:
        raise ValueError('Window starts before the record')
    rows = []
    for t in range(start, cutoff + 1):
        envs = [k for k in person['env'] if k <= t]       # carry forward only after observation
        amb, rh = person['env'][max(envs)] if envs else (None, None)
        if t not in person['skin'] or t not in person['watts']:
            raise ValueError(f'Missing skin or watts at minute {t}')
        rows.append({
            'time_min': t - start,
            'hr_bpm': _ri(person['hr'].get(t)),
            'skin_c': _r1(person['skin'][t]),
            'room_temp_c': _r1(amb),
            'humidity_pct': _ri(rh),
            'watts': _ri(person['watts'][t]),
        })
    return rows


def _fmt(v):
    return '' if v is None else (f'{v:.1f}' if isinstance(v, float) else str(v))


def render_table(rows):
    head = '| min | HR (bpm) | skin (C) | room (C) | RH (%) | watts |'
    sep = '|---:|---:|---:|---:|---:|---:|'
    body = ['| ' + ' | '.join(_fmt(r[k]) for k in PUBLIC_ROW_KEYS) + ' |' for r in rows]
    return '\n'.join([head, sep] + body)


ANSWER_FORMAT = {
    'decision': 'KEEP or PULL',
    'core_c_in_15_min': 'your best estimate of core temperature (C) 15 minutes from now, one number',
    'confidence': 'probability (0 to 1) that PULL is the correct call',
    'reasoning': 'two to five sentences',
}


def render_prompt(rows, demo):
    last = rows[-1]['time_min']
    return f"""You are the medic watching one soldier on a stationary bike inside a heat chamber. He has been riding for a while already. The table below is the last {len(rows)} minutes of his wearable and chamber log, ending now (minute {last}). Core temperature is NOT measured. Blank cells mean that value was not logged that minute.

Soldier: age {demo['age_years']} years, body mass {demo['mass_kg']} kg.

{render_table(rows)}

Rule: he must be pulled now if his core temperature {HORIZON_MIN} minutes from now would be at or above {THRESHOLD_C:.1f} C. Otherwise he keeps going at whatever workload he is currently holding.

Decide: KEEP or PULL. Do not run code. Reason from the trace and from physiology.

Answer with one JSON object and nothing else:
{json.dumps(ANSWER_FORMAT, indent=2)}
"""


def build(source=DEFAULT_SOURCE, out_dir=HERE):
    out_dir = Path(out_dir)
    people = load_workbook(source)
    public, private = [], []
    for case in CASES:
        p = people[case['subject']]
        cutoff = case['cutoff']
        rows = make_window(p, cutoff)
        demo = {'age_years': _ri(p['demo']['age_years']), 'mass_kg': _ri(p['demo']['mass_kg'])}
        core_now = p['core'][cutoff]
        core_later = p['core'][cutoff + HORIZON_MIN]
        future = [p['core'][t] for t in range(cutoff + 1, cutoff + HORIZON_MIN + 1)]
        watts_window = [r['watts'] for r in rows]
        public.append({
            'task_id': case['task_id'],
            'task_type': 'keep_going_or_pull',
            'horizon_min': HORIZON_MIN,
            'threshold_c': THRESHOLD_C,
            'subject_profile': demo,
            'rows': rows,
            'prompt': render_prompt(rows, demo),
            'answer_format': ANSWER_FORMAT,
        })
        private.append({
            'task_id': case['task_id'],
            'role': case['role'],
            'design': case['design'],
            'note': case['note'],
            'subject_id': case['subject'],
            'person_code': f'H{case["subject"]:02d}',
            'cutoff_min': cutoff,
            'window_start_min': cutoff - WINDOW_MIN + 1,
            'horizon_min': HORIZON_MIN,
            'threshold_c': THRESHOLD_C,
            'core_at_cutoff_c': core_now,
            'core_at_cutoff_plus_15_c': core_later,
            'peak_core_next_15_c': max(future),
            'core_change_15_c': round(core_later - core_now, 2),
            'power_dropped_in_window': max(watts_window) > watts_window[-1],
            'watts_first': watts_window[0],
            'watts_last': watts_window[-1],
            'expected_decision': 'PULL' if core_later >= THRESHOLD_C else 'KEEP',
            'scorer': 'tasks.keep_going.evaluator.grade',
        })
    (out_dir / 'prompts').mkdir(parents=True, exist_ok=True)
    (out_dir / 'public_tasks.json').write_text(json.dumps({
        'source': {'url': SOURCE_URL, 'license': 'CC BY 4.0', 'md5': SOURCE_MD5},
        'tasks': public}, indent=2) + '\n')
    (out_dir / 'private_ground_truth.json').write_text(json.dumps({
        'threshold_c': THRESHOLD_C, 'horizon_min': HORIZON_MIN, 'window_min': WINDOW_MIN,
        'tasks': private}, indent=2) + '\n')
    for task in public:
        (out_dir / 'prompts' / f'{task["task_id"]}.md').write_text(task['prompt'])
    return public, private


if __name__ == '__main__':
    pub, priv = build()
    for t in priv:
        print(f"{t['task_id']} {t['role']:9s} {t['design']:28s} core {t['core_at_cutoff_c']:.2f} -> "
              f"{t['core_at_cutoff_plus_15_c']:.2f}  expected {t['expected_decision']}")
