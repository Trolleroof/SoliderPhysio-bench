"""Calibration evidence for E_c, the keep_going forecast-error cutoff (docs/SCORING_AND_ELO.md).

Builds keep_going-style development windows from people NOT used in any keep_going task,
forecasts core temperature 15 minutes ahead with simple baselines, and reports absolute-error
distributions and the mean credit max(0, 1 - err / E) each baseline would get per candidate E.
Prints aggregates only; no per-window labels are written.

Run (needs openpyxl):
    .venv/bin/python tasks/calibrate_forecast_e.py [--workbook PATH] [--out evidence.json]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tasks' / 'beat_ectemp'))
import benchmark  # noqa: E402  (read_workbook: same parsing and MD5 check as Beat ECTemp)
import ectemp_baseline  # noqa: E402

sys.path.insert(0, str(ROOT))
from tasks.keep_going.build_tasks import CASES, MAX_STEP_C  # noqa: E402

HORIZON = 15
CUTOFFS = range(25, 46)          # keep_going cutoffs span 25-44
WINDOW = 25                      # rows the keep_going prompt shows
CANDIDATE_E = (0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0)
KG_SUBJECTS = {c['subject'] for c in CASES}


def windows(people, codes):
    out = []
    for p in codes:
        rows = people[p]
        core = {r['time_min']: r['core_temp'] for r in rows if r['core_temp'] is not None}
        for t in CUTOFFS:
            if t not in core or t + HORIZON not in core:
                continue
            steps = [abs(core[m] - core[m - 1]) for m in range(t + 1, t + HORIZON + 1) if m in core and m - 1 in core]
            if any(s > MAX_STEP_C for s in steps):
                continue
            watts = [r['watts'] for r in rows[t - WINDOW:t] if r['watts'] is not None]
            out.append({'person': p, 't': t, 'core_now': core[t], 'target': core[t + HORIZON],
                        'falling': bool(watts) and watts[-1] < max(watts),
                        'history': [{k: v for k, v in r.items() if k != 'core_temp'} for r in rows[:t]]})
    return out


def kg_windows(people):
    out = []
    for c in CASES:
        if c['role'] != 'primary':
            continue
        p, t = f"H{c['subject']:02d}", c['cutoff']
        rows = people[p]
        out.append({'person': p, 't': t, 'core_now': rows[t - 1]['core_temp'], 'target': rows[t + HORIZON - 1]['core_temp'],
                    'falling': None, 'history': [{k: v for k, v in r.items() if k != 'core_temp'} for r in rows[:t]]})
    return out


def forecasters(people, pool):
    """Each forecaster: f(window) -> forecast C. 'pool' people supply population statistics (LOPO)."""
    def lopo_core(person, minute):
        vals = [r['core_temp'] for p in pool if p != person
                for r in people[p] if r['time_min'] == minute and r['core_temp'] is not None]
        return sum(vals) / len(vals)

    def constant(w):  # no information: pooled mean core over the target minutes of other people
        vals = [r['core_temp'] for p in pool if p != w['person'] for r in people[p]
                if CUTOFFS.start + HORIZON <= r['time_min'] < CUTOFFS.stop + HORIZON and r['core_temp'] is not None]
        return sum(vals) / len(vals)

    return {
        'constant_population_mean': constant,
        'elapsed_time_only': lambda w: lopo_core(w['person'], w['t'] + HORIZON),
        'ectemp_style': lambda w: ectemp_baseline.predict({'task': '3A', 'horizon_min': HORIZON, 'history': w['history']})['mean'],
        # Oracle references: they read current core, which the keep_going prompt never shows.
        'oracle_persistence': lambda w: w['core_now'],
        'oracle_persistence_plus_elapsed_rise': lambda w: w['core_now'] + lopo_core(w['person'], w['t'] + HORIZON) - lopo_core(w['person'], w['t']),
    }


def pct(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo = int(i)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (i - lo)


def balanced(values, owners):
    by = {}
    for v, p in zip(values, owners):
        by.setdefault(p, []).append(v)
    return sum(sum(v) / len(v) for v in by.values()) / len(by)


def summarize(ws, fns):
    owners = [w['person'] for w in ws]
    out = {}
    for name, f in fns.items():
        err = [abs(f(w) - w['target']) for w in ws]
        out[name] = {
            'n_windows': len(err), 'n_people': len(set(owners)),
            'mae': round(sum(err) / len(err), 3),
            'person_balanced_mae': round(balanced(err, owners), 3),
            'abs_error_pct': {f'p{int(q * 100)}': round(pct(err, q), 3) for q in (0.25, 0.5, 0.75, 0.9)},
            'abs_error_max': round(max(err), 3),
            'mean_credit_by_E': {str(E): round(balanced([max(0.0, 1 - e / E) for e in err], owners), 3)
                                 for E in CANDIDATE_E},
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--workbook', type=Path, default=ROOT / 'sources' / 'figshare-heat' / 'core_cycling_2025.xlsx')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    people = benchmark.read_workbook(a.workbook)
    dev = sorted(p for p in people if int(p[1:]) not in KG_SUBJECTS)
    ws = windows(people, dev)
    fns = forecasters(people, dev)
    result = {
        'definition': {
            'development_people': dev,
            'excluded_keep_going_subjects': sorted(KG_SUBJECTS),
            'cutoffs_min': [CUTOFFS.start, CUTOFFS.stop - 1], 'horizon_min': HORIZON,
            'window_screen': f'core observed at t and t+15; no one-minute core step > {MAX_STEP_C} C in horizon',
            'falling_power': f'last watts in the {WINDOW}-row window below its max',
            'credit': 'max(0, 1 - abs_error / E), averaged per person then across people',
            'population_statistics': 'leave-one-person-out over development people only',
        },
        'all_windows': summarize(ws, fns),
        'falling_power_windows': summarize([w for w in ws if w['falling']], fns),
        'target_at_or_above_38.5': summarize([w for w in ws if w['target'] >= 38.5], fns),
        # Reference only, not for choosing E: the 12 scored keep_going cases (test set).
        'keep_going_scored_cases_reference': summarize(kg_windows(people), fns),
    }
    text = json.dumps(result, indent=2)
    if a.out:
        a.out.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
