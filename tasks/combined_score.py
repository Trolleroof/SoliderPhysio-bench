"""Combined per-case scores and matched Bradley-Terry/Elo ratings.

Implements docs/SCORING_AND_ELO.md on top of the existing task graders.

Run file (one per model run):
    {"model": "name", "cases": [
        {"task": "keep_going", "case_id": "KG-01", "run": 0,
         "grader": <tasks.keep_going.evaluator.grade(...)>,
         "judge": {"decision": 4, "reasoning": 3}},
        {"task": "rulebook_vs_body", "case_id": "RB-01",
         "grader": <tasks.rulebook_vs_body.evaluator.grade(...)>,
         "judge": {"override_decision": 5, "reasoning": 4}},
        {"task": "beat_ectemp", "case_id": "3A",
         "grader": <tasks.beat_ectemp.benchmark.evaluate(..., hidden=True)>,
         "judge": {"research_explanation": 3}}]}

Params file (frozen before runs; no defaults for E or B by design):
    {"version": "...", "E_c": <float>, "ectemp_B": {"3A": <float>, "3B": <float>},
     "required_cases": ["keep_going/KG-01", ..., "beat_ectemp/3B"]}

required_cases is the frozen list every model must cover (KG-03, the unscored
edge case, is deliberately left out). Cases outside it are scored and reported
but never rated and never exclude anyone. A missing list is an error; tests and
dev work may set "dev_allow_union_cases": true to require the union of observed
cases instead (one extra case anywhere then excludes every model lacking it).

Judge scores are integers 0-5. "not_scorable" or a missing judge score blocks
the case (it is not a zero); a blocked or missing case makes the model
ineligible for a rating.
"""
import argparse
import json
import math
import random
from pathlib import Path

WEIGHTS = {
    'keep_going': {'forecast': 0.30, 'decision': 0.40, 'reasoning': 0.30},
    'rulebook_vs_body': {'table_lookup': 0.30, 'override_decision': 0.40, 'reasoning': 0.30},
    'beat_ectemp': {'predictor': 0.60, 'research_explanation': 0.40},
}
JUDGED = {
    'keep_going': ('decision', 'reasoning'),
    'rulebook_vs_body': ('override_decision', 'reasoning'),
    'beat_ectemp': ('research_explanation',),
}
# Pinned fitting choices (recorded in every output).
FIT = {
    'tie_model': 'davidson',
    'optimizer': 'damped_newton',
    'theta_prior_precision': 0.1,   # Gaussian prior on log-strength; keeps perfect separation finite
    'log_nu_prior_precision': 0.01,  # weak prior on the Davidson tie parameter, centered at nu=1
    'tie_tolerance': 1e-9,           # |combined a - combined b| <= this is a tie (float noise only)
    'repeat_aggregation': 'mean_combined_score_per_case',
    'bootstrap': 'cases_resampled_within_task_matched_across_models',
}


class NotScorable(Exception):
    pass


def _judge(judge, name):
    value = (judge or {}).get(name)
    if value is None or value == 'not_scorable':
        raise NotScorable(f'judge score {name!r} not available')
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
        raise ValueError(f'judge score {name!r} must be an integer 0-5, got {value!r}')
    return value / 5


def components(task, case_id, grader, judge, params):
    """Normalized [0, 1] components for one case. Raises NotScorable if blocked."""
    if task not in WEIGHTS:
        raise ValueError(f'unknown task {task!r}')
    comp = {name: _judge(judge, name) for name in JUDGED[task]}
    flags = []
    if task == 'keep_going':
        E = params.get('E_c')
        if not isinstance(E, (int, float)) or not math.isfinite(E) or E <= 0:
            raise NotScorable('E_c not frozen in params')
        err = grader.get('core_abs_error_c')
        if err is None:  # rubric: missing or non-numeric forecast scores 0
            flags.append('missing_forecast')
            comp['forecast'] = 0.0
        else:
            comp['forecast'] = max(0.0, 1 - err / E)
    elif task == 'rulebook_vs_body':
        comp['table_lookup'] = float(grader['rulebook']['score'])
    else:
        # Per-person case "3A/<person>"; B is that person's baseline MAE on the same requests.
        variant, _, person = case_id.partition('/')
        B = ((params.get('ectemp_B') or {}).get(variant) or {}).get(person) if person else None
        if not isinstance(B, (int, float)) or not math.isfinite(B) or B <= 0:
            raise NotScorable(f'no valid ECTemp baseline B for {case_id!r}')
        if not grader.get('valid'):
            flags.append('invalid_artifact')
            comp['predictor'] = 0.0
        else:
            mae = grader.get('person_mae')
            if mae is None:
                raise NotScorable(f'grader output has no scored requests for {case_id!r}')
            comp['predictor'] = max(0.0, min(1.0, 1 - mae / B))
    return comp, flags


def expand_case(case, params):
    """Split a whole-variant beat_ectemp case ("3A", grader = benchmark.evaluate output) into one
    case per test person ("3A/<person>"), people taken from params ectemp_B[variant]. Each copy
    shares the judge scores and carries that person's MAE. Other cases pass through unchanged."""
    if case['task'] != 'beat_ectemp' or '/' in case['case_id']:
        return [case]
    people = (params.get('ectemp_B') or {}).get(case['case_id'])
    if not isinstance(people, dict) or not people:
        return [case]  # components() reports it as not scorable
    g = case['grader']
    return [{**case, 'case_id': f"{case['case_id']}/{p}",
             'grader': {'valid': g.get('valid'), 'person_mae': (g.get('person_mae') or {}).get(p)}}
            for p in sorted(people)]


def combined(task, comp):
    return sum(WEIGHTS[task][k] * comp[k] for k in WEIGHTS[task])


def _model_key(name):
    return str(name).strip().lower().rsplit('/', 1)[-1]  # 'openai/x' and 'x' are the same model


def check_judge_off_roster(runs):
    """The judge must not be any model being rated (self-preference bias)."""
    rated = {_model_key(r['model']) for r in runs}
    judges = {_model_key(m) for r in runs for c in r['cases']
              if (m := (c.get('judge_record') or {}).get('judge_model'))}
    clash = sorted(rated & judges)
    if clash:
        raise ValueError(f'judge model is also on the rated roster: {clash}')


def score_runs(runs, params):
    """runs: list of run dicts. Returns {model: {(task, case_id): case record}}."""
    check_judge_off_roster(runs)
    raw = {}
    for run in runs:
        for c in (x for case in run['cases'] for x in expand_case(case, params)):
            key = (c['task'], c['case_id'])
            rec = {'task': c['task'], 'case_id': c['case_id'], 'run': c.get('run', 0)}
            try:
                comp, flags = components(c['task'], c['case_id'], c['grader'], c.get('judge'), params)
                rec.update(status='scored', components=comp, flags=flags, combined=combined(c['task'], comp))
            except NotScorable as e:
                rec.update(status='not_scorable', reason=str(e))
            raw.setdefault(run['model'], {}).setdefault(key, []).append(rec)
    out = {}
    for model, cases in raw.items():
        for key, attempts in cases.items():
            scored = [a for a in attempts if a['status'] == 'scored']
            blocked = len(scored) != len(attempts)
            out.setdefault(model, {})[key] = {
                'task': key[0], 'case_id': key[1], 'n_runs': len(attempts),
                'status': 'not_scorable' if blocked else 'scored',
                'combined': None if blocked else sum(a['combined'] for a in scored) / len(scored),
                'attempts': attempts,
            }
    return out


def parse_required(required):
    """["task/case_id", ...] -> sorted [(task, case_id)]; None stays None."""
    if required is None:
        return None
    out = set()
    for item in required:
        task, sep, case = str(item).partition('/')
        if not sep or not case or task not in WEIGHTS:
            raise ValueError(f'required case {item!r} must be "<task>/<case_id>" with a known task')
        out.add((task, case))
    if not out:
        raise ValueError('required_cases is empty')
    return sorted(out)


def eligibility(scores, required=None):
    """Models need a scored value on every required case.

    required: frozen [(task, case_id)] list; None falls back to the union of
    every case anyone was run on. Returns (eligible, excluded, cases, extra)
    where extra maps model -> cases it ran outside the required list.
    """
    cases = sorted({k for m in scores.values() for k in m}) if required is None else list(required)
    need = set(cases)
    eligible, excluded, extra = [], {}, {}
    for model in sorted(scores):
        missing = [f'{t}/{c}' for t, c in cases if (t, c) not in scores[model]]
        blocked = [f'{t}/{c}' for (t, c), r in sorted(scores[model].items())
                   if (t, c) in need and r['status'] != 'scored']
        outside = [f'{t}/{c}' for t, c in sorted(scores[model]) if (t, c) not in need]
        if outside:
            extra[model] = outside
        if missing or blocked:
            excluded[model] = {'missing': missing, 'not_scorable': blocked}
        else:
            eligible.append(model)
    return eligible, excluded, cases, extra


def pairwise(scores, models, cases):
    """Weighted outcomes per ordered pair; every task type totals weight 1 per pair."""
    by_task = {}
    for t, c in cases:
        by_task.setdefault(t, []).append(c)
    tol = FIT['tie_tolerance']
    pairs = {}
    for a in range(len(models)):
        for b in range(a + 1, len(models)):
            w = {'wins_a': 0.0, 'wins_b': 0.0, 'ties': 0.0}
            for t, cs in by_task.items():
                for c in cs:
                    diff = scores[models[a]][(t, c)]['combined'] - scores[models[b]][(t, c)]['combined']
                    w['ties' if abs(diff) <= tol else 'wins_a' if diff > 0 else 'wins_b'] += 1 / len(cs)
            pairs[(a, b)] = w
    return pairs


def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        for r in range(i + 1, n):
            f = M[r][i] / M[i][i]
            for k in range(i, n + 1):
                M[r][k] -= f * M[i][k]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (M[i][n] - sum(M[i][k] * x[k] for k in range(i + 1, n))) / M[i][i]
    return x


def fit_davidson(n_models, pairs):
    """MAP fit of Davidson's Bradley-Terry-with-ties model. Returns (theta, nu)."""
    lam, lam_nu = FIT['theta_prior_precision'], FIT['log_nu_prior_precision']
    k = n_models + 1  # last variable is eta = log(nu)

    def evaluate(x):
        eta = x[-1]
        f = -0.5 * lam * sum(t * t for t in x[:-1]) - 0.5 * lam_nu * eta * eta
        g = [-lam * t for t in x[:-1]] + [-lam_nu * eta]
        H = [[0.0] * k for _ in range(k)]
        for i in range(n_models):
            H[i][i] -= lam
        H[-1][-1] -= lam_nu
        for (i, j), w in pairs.items():
            n = w['wins_a'] + w['wins_b'] + w['ties']
            if n == 0:
                continue
            u = [x[i], x[j], eta + (x[i] + x[j]) / 2]
            m = max(u)
            e = [math.exp(v - m) for v in u]
            s = sum(e)
            lse = m + math.log(s)
            p = [v / s for v in e]
            f += w['wins_a'] * u[0] + w['wins_b'] * u[1] + w['ties'] * u[2] - n * lse
            idx = [i, j, k - 1]
            vecs = [(1, 0, 0), (0, 1, 0), (0.5, 0.5, 1)]
            mean = [sum(p[o] * vecs[o][r] for o in range(3)) for r in range(3)]
            obs = [w['wins_a'] + w['ties'] / 2, w['wins_b'] + w['ties'] / 2, w['ties']]
            for r in range(3):
                g[idx[r]] += obs[r] - n * mean[r]
                for q in range(3):
                    cov = sum(p[o] * vecs[o][r] * vecs[o][q] for o in range(3)) - mean[r] * mean[q]
                    H[idx[r]][idx[q]] -= n * cov
        return f, g, H

    x = [0.0] * k
    f, g, H = evaluate(x)
    for _ in range(100):
        step = _solve([[-v for v in row] for row in H], g)
        t = 1.0
        while True:
            cand = [a + t * s for a, s in zip(x, step)]
            fc, gc, Hc = evaluate(cand)
            if fc >= f - 1e-12 or t < 1e-8:
                break
            t /= 2
        done = abs(fc - f) < 1e-12 and max(abs(s) for s in step) * t < 1e-9
        x, f, g, H = cand, fc, gc, Hc
        if done:
            break
    return x[:-1], math.exp(x[-1])


def to_elo(theta):
    mean = sum(theta) / len(theta)
    return [1500 + 400 * (t - mean) / math.log(10) for t in theta]


def percentile(xs, q):
    """Linearly interpolated quantile (numpy's default), 0 <= q <= 1."""
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


CI_NOTE = ('exploratory: case-resampling interval; in simulation it covers the true rating about 70% '
           'of the time, not 95%, because two tasks have very few cases (docs/SCORING_AND_ELO.md)')
PRIOR_GAP_NOTE = ('won or lost every matched comparison: the size of its rating gap is set by the '
                  'prior (theta_prior_precision), not by the data')


def separation_flags(models, pairs):
    """'wins_all' / 'loses_all' when a model never loses / never wins nor ties a matched comparison."""
    flags = {}
    for i, m in enumerate(models):
        won = lost = 0.0
        for (a, b), w in pairs.items():
            if i in (a, b):
                mine, theirs = ('wins_a', 'wins_b') if i == a else ('wins_b', 'wins_a')
                won += w[mine] + w['ties']
                lost += w[theirs] + w['ties']
        flags[m] = 'wins_all' if lost == 0 else 'loses_all' if won == 0 else None
    return flags


def rate(scores, n_boot=1000, seed=0, required_cases=None, dev_allow_union_cases=False):
    if required_cases is None and not dev_allow_union_cases:
        raise ValueError('params must freeze required_cases (set dev_allow_union_cases only for tests/dev)')
    required = parse_required(required_cases)
    models, excluded, cases, extra = eligibility(scores, required)
    result = {'fit': FIT, 'eligible': models, 'excluded': excluded,
              'cases': [f'{t}/{c}' for t, c in cases], 'extra_cases_not_rated': extra,
              'warnings': [], 'ratings': None}
    if required is None:
        result['warnings'].append('dev_allow_union_cases: union of observed cases is required, '
                                  'so one extra case anywhere excludes every model that lacks it; not official')
    if len(models) < 2:
        result['reason'] = 'fewer than two eligible models'
        return result
    pairs = pairwise(scores, models, cases)
    theta, nu = fit_davidson(len(models), pairs)
    elo = to_elo(theta)

    by_task = {}
    for t, c in cases:
        by_task.setdefault(t, []).append(c)
    rng = random.Random(seed)
    boots = [[] for _ in models]
    for _ in range(n_boot):
        sample = [(t, rng.choice(cs)) for t, cs in by_task.items() for _ in cs]
        # Duplicated cases are re-keyed so pairwise() treats them as separate draws.
        renamed = {m: {(t, f'{c}#{n}'): scores[m][(t, c)] for n, (t, c) in enumerate(sample)} for m in models}
        bt, _ = fit_davidson(len(models), pairwise(renamed, models, list(renamed[models[0]])))
        for i, e in enumerate(to_elo(bt)):
            boots[i].append(e)

    task_means = {m: {t: sum(scores[m][(t, c)]['combined'] for c in cs) / len(cs)
                      for t, cs in by_task.items()} for m in models}
    flags = separation_flags(models, pairs)
    result.update(
        nu=nu,
        ci95_note=CI_NOTE,
        n_boot=n_boot, seed=seed,
        pairwise=[{'a': models[a], 'b': models[b], **w} for (a, b), w in pairs.items()],
        ratings=sorted(({'model': m, 'elo': elo[i],
                         'ci95': [percentile(boots[i], 0.025), percentile(boots[i], 0.975)] if n_boot else None,
                         'separation': flags[m],
                         'separation_note': PRIOR_GAP_NOTE if flags[m] else None,
                         'task_mean_combined': task_means[m]}
                        for i, m in enumerate(models)), key=lambda r: -r['elo']),
    )
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('runs', nargs='+', type=Path, help='run JSON files')
    ap.add_argument('--params', type=Path, required=True, help='frozen params JSON (E_c, ectemp_B)')
    ap.add_argument('--n-boot', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    params = json.loads(a.params.read_text())
    scores = score_runs([json.loads(p.read_text()) for p in a.runs], params)
    result = rate(scores, a.n_boot, a.seed, params.get('required_cases'),
                  dev_allow_union_cases=params.get('dev_allow_union_cases') is True)
    result['params'] = params
    result['case_scores'] = {m: list(v.values()) for m, v in scores.items()}
    text = json.dumps(result, indent=2)
    if a.out:
        a.out.write_text(text)
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
