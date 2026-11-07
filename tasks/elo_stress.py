"""Stress test of the pinned Elo fitting choices in tasks/combined_score.py.

Synthetic rosters only: no model outputs exist yet. Case counts match the real
suite (13 keep_going incl. the KG-03 edge case, 2 rulebook_vs_body, 2
beat_ectemp). Raw measurements are simulated per model and case, then pushed
through the same normalization, pairwise and Davidson code as real runs.

    python3 -m tasks.elo_stress            # all checks, ~12 min serial
    python3 -m tasks.elo_stress --only rmse   # one section (each is reproducible alone)
    python3 -m tasks.elo_stress --quick    # fewer replicates

Results are summarised in docs/SCORING_AND_ELO.md ("Fit stress test").
"""
import argparse
import contextlib
import math
import random
import statistics
import time

from tasks import combined_score as cs

CASES = {'keep_going': [f'KG-{i:02d}' for i in range(1, 14)],
         'rulebook_vs_body': ['RB-01', 'RB-02'],
         'beat_ectemp': ['3A', '3B']}
N_FIELDS = 4  # rulebook_vs_body.RULEBOOK_FIELDS

SCENARIOS = {
    # spread: between-model skill sd; base: judge latent mean; ec_shift: log MAE/B at skill 0
    'typical': dict(spread=0.7, base=3.0, ec_shift=0.0),
    'close': dict(spread=0.25, base=3.0, ec_shift=0.0),
    'ceiling': dict(spread=0.5, base=4.6, ec_shift=0.05),  # judges near the top, few beat ECTemp
    'tie_heavy': dict(spread=0.5, base=5.8, ec_shift=0.4),  # judges saturate, nobody beats ECTemp
}


@contextlib.contextmanager
def fit(**over):
    old = dict(cs.FIT)
    cs.FIT.update(over)
    try:
        yield
    finally:
        cs.FIT.clear()
        cs.FIT.update(old)


def clip(x, lo=0, hi=5):
    return max(lo, min(hi, x))


def roster(n, sc, rng):
    """Latent per-model, per-task skill."""
    out = []
    for _ in range(n):
        s = rng.gauss(0, sc['spread'])
        out.append({t: s + rng.gauss(0, 0.4 * sc['spread'] / 0.7) for t in CASES})
    return out


def draw_case(task, sc, rng):
    return {'d': rng.gauss(0, 0.7), 'task': task}


def measure(skill, case, sc, rng):
    """Raw measurements for one model on one case."""
    t, a = case['task'], skill[case['task']] - case['d']
    lat = sc['base'] + a + rng.gauss(0, 0.8)
    j1, j2 = round(clip(lat)), round(clip(lat + rng.gauss(0, 0.6)))
    if t == 'keep_going':
        err = round(abs(rng.gauss(0, 0.35 * math.exp(-0.4 * a))), 2)
        return {'err': err, 'j1': j1, 'j2': j2}
    if t == 'rulebook_vs_body':
        p = 1 / (1 + math.exp(-(1.5 + a)))
        return {'frac': sum(rng.random() < p for _ in range(N_FIELDS)) / N_FIELDS, 'j1': j1, 'j2': j2}
    ratio = math.exp(sc['ec_shift'] - 0.15 * a + rng.gauss(0, 0.08))
    return {'ratio': ratio, 'j1': j1}


BASE_MAP = {'E': 1.0, 'B_scale': 1.0, 'weights': cs.WEIGHTS}


def combine(task, m, mp=BASE_MAP):
    w = mp['weights'][task]
    if task == 'keep_going':
        comp = {'forecast': max(0.0, 1 - m['err'] / mp['E']), 'decision': m['j1'] / 5, 'reasoning': m['j2'] / 5}
    elif task == 'rulebook_vs_body':
        comp = {'table_lookup': m['frac'], 'override_decision': m['j1'] / 5, 'reasoning': m['j2'] / 5}
    else:
        comp = {'predictor': clip(1 - m['ratio'] / mp['B_scale'], 0, 1), 'research_explanation': m['j1'] / 5}
    return sum(w[k] * comp[k] for k in w)


def benchmark(skills, sc, rng, counts=None):
    """One simulated benchmark: raw measurements[model][(task, case)]."""
    raw = [{} for _ in skills]
    for t, ids in CASES.items():
        n = (counts or {}).get(t, len(ids))
        for k in range(n):
            case = draw_case(t, sc, rng)
            cid = ids[k] if k < len(ids) else f'{t}-{k}'
            for i, s in enumerate(skills):
                raw[i][(t, cid)] = measure(s, case, sc, rng)
    return raw


def to_scores(raw, mp=BASE_MAP):
    return {f'm{i}': {k: {'status': 'scored', 'combined': combine(k[0], v, mp)} for k, v in r.items()}
            for i, r in enumerate(raw)}


def models_of(scores):
    return sorted(scores, key=lambda m: int(m[1:]))


def pairs_of(scores):
    models = models_of(scores)
    return models, cs.pairwise(scores, models, sorted(scores[models[0]]))


def fit_bt_halfwin(n, pairs, lam):
    """Plain Bradley-Terry with ties counted as half a win each, same prior and optimizer style."""
    x = [0.0] * n
    for _ in range(100):
        g = [-lam * v for v in x]
        H = [[-lam if i == j else 0.0 for j in range(n)] for i in range(n)]
        for (i, j), w in pairs.items():
            tot = w['wins_a'] + w['wins_b'] + w['ties']
            p = 1 / (1 + math.exp(x[j] - x[i]))
            r = w['wins_a'] + w['ties'] / 2 - tot * p
            g[i] += r
            g[j] -= r
            c = tot * p * (1 - p)
            H[i][i] -= c
            H[j][j] -= c
            H[i][j] += c
            H[j][i] += c
        step = cs._solve([[-v for v in row] for row in H], g)
        x = [a + s for a, s in zip(x, step)]
        if max(abs(s) for s in step) < 1e-10:
            break
    return x


def elo_of(scores, tie_model='davidson', **over):
    models, pairs = pairs_of(scores)
    with fit(**over):
        if tie_model == 'davidson':
            theta, nu = cs.fit_davidson(len(models), pairs)
        else:
            theta, nu = fit_bt_halfwin(len(models), pairs, cs.FIT['theta_prior_precision']), None
    return cs.to_elo(theta), nu


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: -v[i])
    r = [0] * len(v)
    for k, i in enumerate(order):
        r[i] = k
    return r


def kendall(a, b):
    n, conc, disc = len(a), 0, 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            conc += s > 0
            disc += s < 0
    return (conc - disc) / (n * (n - 1) / 2)


def total_score(scores):
    models, pairs = pairs_of(scores)
    s = [0.0] * len(models)
    for (a, b), w in pairs.items():
        s[a] += w['wins_a'] + w['ties'] / 2
        s[b] += w['wins_b'] + w['ties'] / 2
    return s


def tie_fraction(scores):
    _, pairs = pairs_of(scores)
    tot = sum(w['ties'] + w['wins_a'] + w['wins_b'] for w in pairs.values())
    return sum(w['ties'] for w in pairs.values()) / tot


def spread(e):
    return max(e) - min(e)


# ---------------------------------------------------------------- checks

def check_tie_model_and_priors(reps, rng):
    print('\n## 1-2. Tie model and prior sensitivity (point estimates)')
    print('Elo spread = max-min; |dElo| vs pinned fit (davidson, theta 0.1, log_nu 0.01); '
          'rank_changes = rosters whose order changed (exact score ties excluded).')
    variants = [('davidson', {}), ('half_win', {})]
    variants += [('davidson', {'theta_prior_precision': v}) for v in (0.01, 0.03, 0.3, 1.0)]
    variants += [('davidson', {'log_nu_prior_precision': v}) for v in (0.001, 0.1, 1.0)]
    for name, sc in SCENARIOS.items():
        for n in (3, 5, 10):
            stats = {i: {'d': [], 'sp': [], 'rk': 0} for i in range(len(variants))}
            ties, rank_vs_score, nus = [], 0, []
            for _ in range(reps):
                scores = to_scores(benchmark(roster(n, sc, rng), sc, rng))
                ties.append(tie_fraction(scores))
                base, nu = elo_of(scores)
                nus.append(nu)
                ts = total_score(scores)
                distinct = len({round(x, 9) for x in ts}) == n
                rank_vs_score += distinct and ranks(base) != ranks(ts)
                for i, (tm, over) in enumerate(variants):
                    e, _ = elo_of(scores, tm, **over)
                    stats[i]['d'].append(max(abs(x - y) for x, y in zip(e, base)))
                    stats[i]['sp'].append(spread(e))
                    stats[i]['rk'] += distinct and ranks(e) != ranks(base)
            print(f'\n{name}, n={n}: pair-weighted tie share {statistics.mean(ties):.2f}, '
                  f'median nu {statistics.median(nus):.2f}, Elo order != total-score order in {rank_vs_score}/{reps}')
            print('| variant | median spread | median max |dElo| | 95th pct max |dElo| | rank changes |')
            print('|---|---:|---:|---:|---:|')
            for i, (tm, over) in enumerate(variants):
                d = sorted(stats[i]['d'])
                lab = tm + ''.join(f' {k.split("_")[0]}={v}' for k, v in over.items())
                print(f'| {lab} | {statistics.median(stats[i]["sp"]):.0f} | {statistics.median(d):.0f} | '
                      f'{d[int(0.95 * (len(d) - 1))]:.0f} | {stats[i]["rk"]}/{reps} |')


def check_extremes():
    print('\n## 4. Perfect separation and all ties')
    for n in (2, 3, 5, 10):
        raw = [{(t, c): None for t, ids in CASES.items() for c in ids} for _ in range(n)]
        sep = {f'm{i}': {k: {'status': 'scored', 'combined': 1 - i / n} for k in raw[i]} for i in range(n)}
        tie = {f'm{i}': {k: {'status': 'scored', 'combined': 0.5} for k in raw[i]} for i in range(n)}
        row = []
        for lam in (0.01, 0.1, 1.0):
            e, nu = elo_of(sep, theta_prior_precision=lam)
            eh, _ = elo_of(sep, 'half_win', theta_prior_precision=lam)
            row.append(f'lam={lam}: davidson spread {spread(e):.0f} (nu={nu:.1e}), half-win {spread(eh):.0f}')
        et, nut = elo_of(tie)
        r = cs.rate(tie, n_boot=50, dev_allow_union_cases=True)
        cis = {tuple(round(v, 6) for v in x['ci95']) for x in r['ratings']}
        print(f'n={n} separation: ' + '; '.join(row))
        print(f'n={n} all ties: Elo {sorted({round(x, 6) for x in et})}, nu={nut:.0f}, CIs {cis}')


def population_elo(skills, sc, rng, mp=BASE_MAP, k=400):
    return elo_of(to_scores(benchmark(skills, sc, rng, {t: k for t in CASES}), mp))[0]


def bootstrap_ci(scores, n_boot, seed, minus_one=False):
    """Pinned method via cs.rate(); minus_one draws n-1 cases per task (n-1 bootstrap)."""
    if not minus_one:
        r = cs.rate(scores, n_boot=n_boot, seed=seed, dev_allow_union_cases=True)
        return {x['model']: (x['elo'], x['ci95']) for x in r['ratings']}
    models = models_of(scores)
    by_task = {}
    for t, c in sorted(scores[models[0]]):
        by_task.setdefault(t, []).append(c)
    point, _ = elo_of(scores)
    rng = random.Random(seed)
    boots = [[] for _ in models]
    for _ in range(n_boot):
        sample = [(t, rng.choice(c)) for t, c in by_task.items() for _ in range(max(1, len(c) - 1))]
        renamed = {m: {(t, f'{c}#{k}'): scores[m][(t, c)] for k, (t, c) in enumerate(sample)} for m in models}
        bt, _ = cs.fit_davidson(len(models), cs.pairwise(renamed, models, list(renamed[models[0]])))
        for i, e in enumerate(cs.to_elo(bt)):
            boots[i].append(e)
    out = {}
    for i, m in enumerate(models):
        out[m] = (point[i], [cs.percentile(boots[i], 0.025), cs.percentile(boots[i], 0.975)])
    return out


def check_bootstrap(reps, n_boot, rng):
    print('\n## 3. Within-task case bootstrap')
    # Degeneracy: with 2 cases a task has 3 distinct resamples (AA 1/4, AB 1/2, BB 1/4).
    print('Two-case task resamples: P(both draws same case) = 0.5; the task contributes only '
          '3 distinct outcome sets, so both 2-case tasks together give at most 9 configurations.')
    print('Estimand: the same fit applied to 400 cases per task from the same case distribution.')
    print('| scenario | n | method | coverage | median CI width | point outside CI | '
          'median spread: sample / population |')
    print('|---|---:|---|---:|---:|---:|---:|')
    for name in ('typical', 'close'):
        sc = SCENARIOS[name]
        for n in (3, 5, 8):
            acc = {mo: {'cover': 0, 'out': 0, 'w': []} for mo in (False, True)}
            total, ratio = 0, []
            for rep in range(reps):
                skills = roster(n, sc, rng)
                truth = population_elo(skills, sc, rng)
                scores = to_scores(benchmark(skills, sc, rng))
                for mo in (False, True):
                    ci = bootstrap_ci(scores, n_boot, rep, mo)
                    for i in range(n):
                        e, (lo, hi) = ci[f'm{i}']
                        acc[mo]['cover'] += lo <= truth[i] <= hi
                        acc[mo]['out'] += not lo <= e <= hi
                        acc[mo]['w'].append(hi - lo)
                ratio.append(spread(elo_of(scores)[0]) / spread(truth))
                total += n
            for mo in (False, True):
                a = acc[mo]
                print(f'| {name} | {n} | {"n-1 draws" if mo else "pinned (n draws)"} | {a["cover"] / total:.2f} | '
                      f'{statistics.median(a["w"]):.0f} | {a["out"] / total:.3f} | {statistics.median(ratio):.2f} |')


def check_bootstrap_by_task(reps, n_boot, rng):
    """Coverage when the benchmark is a single task at its real case count."""
    print('\nSingle-task benchmarks (typical, n=5): each task alone at its real case count vs the '
          'same task with 400 cases.')
    sc = SCENARIOS['typical']
    n = 5
    for t, k in (('keep_going', 13), ('rulebook_vs_body', 2), ('beat_ectemp', 2)):
        cover = {False: 0, True: 0}
        total = 0
        for rep in range(reps):
            skills = roster(n, sc, rng)
            pop = benchmark(skills, sc, rng, {u: (400 if u == t else 0) for u in CASES})
            truth = elo_of(to_scores(pop))[0]
            scores = to_scores(benchmark(skills, sc, rng, {u: (k if u == t else 0) for u in CASES}))
            for mo in (False, True):
                ci = bootstrap_ci(scores, n_boot, rep, mo)
                cover[mo] += sum(ci[f'm{i}'][1][0] <= truth[i] <= ci[f'm{i}'][1][1] for i in range(n))
            total += n
        print(f'- {t} alone ({k} cases): coverage pinned {cover[False] / total:.2f}, n-1 draws {cover[True] / total:.2f}')


def check_prior_rmse(reps, rng):
    """Which theta prior makes the 17-case Elo closest to the infinite-case (unpenalised) Elo?"""
    print('\n## 2b. Theta prior vs accuracy and coverage against the population rating')
    print('Truth: near-unpenalised fit (theta precision 1e-6) to 400 cases per task. Estimate: '
          'the fit on one 13/2/2 benchmark. CI: pinned bootstrap (200 draws) under the same prior.')
    lams = (0.01, 0.03, 0.1, 0.3, 1.0)
    for name in ('typical', 'close'):
        sc = SCENARIOS[name]
        for n in (3, 5, 8):
            err = {l: [] for l in lams}
            cover = {l: 0 for l in lams}
            sp = {l: [] for l in lams}
            total, tsp = 0, []
            for rep in range(reps):
                skills = roster(n, sc, rng)
                truth = elo_of(to_scores(benchmark(skills, sc, rng, {t: 400 for t in CASES})),
                               theta_prior_precision=1e-6)[0]
                tsp.append(spread(truth))
                scores = to_scores(benchmark(skills, sc, rng))
                for l in lams:
                    with fit(theta_prior_precision=l):
                        ci = bootstrap_ci(scores, 200, rep)
                    est = [ci[f'm{i}'][0] for i in range(n)]
                    err[l] += [(a - b) ** 2 for a, b in zip(est, truth)]
                    cover[l] += sum(ci[f'm{i}'][1][0] <= truth[i] <= ci[f'm{i}'][1][1] for i in range(n))
                    sp[l].append(spread(est))
                total += n
            print(f'\n{name}, n={n}, {reps} rosters, median true spread {statistics.median(tsp):.0f}')
            print('| theta_prior_precision | RMSE (Elo) | 95% CI coverage | median spread |')
            print('|---:|---:|---:|---:|')
            for l in lams:
                print(f'| {l} | {math.sqrt(statistics.mean(err[l])):.0f} | {cover[l] / total:.2f} | '
                      f'{statistics.median(sp[l]):.0f} |')


ALT_MAPS = {
    'equal component weights': {'weights': {t: {c: 1 / len(w) for c in w} for t, w in cs.WEIGHTS.items()}},
    'deterministic-heavy': {'weights': {
        'keep_going': {'forecast': 0.5, 'decision': 0.3, 'reasoning': 0.2},
        'rulebook_vs_body': {'table_lookup': 0.5, 'override_decision': 0.3, 'reasoning': 0.2},
        'beat_ectemp': {'predictor': 0.8, 'research_explanation': 0.2}}},
    'judge-heavy': {'weights': {
        'keep_going': {'forecast': 0.2, 'decision': 0.5, 'reasoning': 0.3},
        'rulebook_vs_body': {'table_lookup': 0.2, 'override_decision': 0.5, 'reasoning': 0.3},
        'beat_ectemp': {'predictor': 0.4, 'research_explanation': 0.6}}},
    'E = 0.5 C': {'E': 0.5},
    'E = 2.0 C': {'E': 2.0},
    'ECTemp B x2 (parity = 0.5 credit)': {'B_scale': 2.0},
}


def check_mapping(reps, rng):
    print('\n## 6. Weight and mapping rank sensitivity')
    print('Same simulated answers re-scored under each alternative; Elo order compared with the '
          'pinned weights, E = 1.0 C, B = ECTemp MAE. Also: case-proportional task weighting.')
    for name in ('typical', 'close'):
        sc = SCENARIOS[name]
        n = 6
        res = {k: {'tau': [], 'top': 0, 'any': 0} for k in list(ALT_MAPS) + ['case-proportional tasks']}
        for _ in range(reps):
            raw = benchmark(roster(n, sc, rng), sc, rng)
            base = elo_of(to_scores(raw))[0]
            for k, over in ALT_MAPS.items():
                e = elo_of(to_scores(raw, {**BASE_MAP, **over}))[0]
                res[k]['tau'].append(kendall(e, base))
                res[k]['top'] += ranks(e).index(0) != ranks(base).index(0)
                res[k]['any'] += ranks(e) != ranks(base)
            # case-proportional: every case one comparison, no per-task averaging
            sc_ = to_scores(raw)
            models = models_of(sc_)
            pairs = {}
            for a in range(n):
                for b in range(a + 1, n):
                    w = {'wins_a': 0.0, 'wins_b': 0.0, 'ties': 0.0}
                    for key in sc_[models[0]]:
                        x, y = sc_[models[a]][key]['combined'], sc_[models[b]][key]['combined']
                        w['wins_a' if x > y + 1e-9 else 'wins_b' if y > x + 1e-9 else 'ties'] += 3 / 17
                    pairs[(a, b)] = w
            e = cs.to_elo(cs.fit_davidson(n, pairs)[0])
            k = 'case-proportional tasks'
            res[k]['tau'].append(kendall(e, base))
            res[k]['top'] += ranks(e).index(0) != ranks(base).index(0)
            res[k]['any'] += ranks(e) != ranks(base)
        print(f'\n{name}, n={n}, {reps} rosters')
        print('| alternative | median Kendall tau | mean tau | top model changes | any order change |')
        print('|---|---:|---:|---:|---:|')
        for k, v in res.items():
            print(f'| {k} | {statistics.median(v["tau"]):.2f} | {statistics.mean(v["tau"]):.2f} | '
                  f'{v["top"] / reps:.0%} | {v["any"] / reps:.0%} |')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--seed', type=int, default=20261107)
    ap.add_argument('--only', choices=['priors', 'extremes', 'bootstrap', 'rmse', 'mapping'])
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    q = a.quick
    t0 = time.time()
    if a.only in (None, 'extremes'):
        check_extremes()
    if a.only in (None, 'priors'):
        check_tie_model_and_priors(40 if q else 200, rng)
    if a.only in (None, 'rmse'):
        check_prior_rmse(15 if q else 60, rng)
    if a.only in (None, 'bootstrap'):
        check_bootstrap(20 if q else 100, 100 if q else 300, rng)
        check_bootstrap_by_task(20 if q else 80, 100 if q else 300, rng)
    if a.only in (None, 'mapping'):
        check_mapping(50 if q else 300, rng)
    print(f'\n({time.time() - t0:.0f}s, seed {a.seed})')


if __name__ == '__main__':
    main()
