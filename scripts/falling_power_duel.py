"""Baseline duel: elapsed-time vs wearable(+workload) forecasters on falling-power episodes.

Reads the original Figshare CORE cycling workbook (not the prepared leaderboard data,
which strips wattage). Leave-one-person-out across all 24 people.

Usage: python -I scripts/falling_power_duel.py /path/to/core_cycling_2025.xlsx
"""
import sys
import json
import numpy as np
import openpyxl
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

HORIZONS = (5, 10, 15)
DROP_W = 10          # a fall is >= 10 W below the max power seen in the prior 10 min
LOOKBACK = 10


def minute(v):
    if isinstance(v, str) and '-' in v:
        return int(v.split('-')[1])
    return int(v)


def load(path):
    w = openpyxl.load_workbook(path, data_only=True)
    core, skin, ex, env = (w[n] for n in ('Core Temp', 'Skin Temp', 'Exercise Data', 'Environmental Conditions'))
    cols = lambda sh, lo, hi: {int(sh.cell(2, c).value): c for c in range(lo, hi) if sh.cell(2, c).value is not None}
    core_c, skin_c, hr_c, pw_c, env_c = cols(core, 3, 27), cols(skin, 3, 27), cols(ex, 28, 52), cols(ex, 78, 102), cols(env, 3, 27)
    people = {}
    for drow in range(2, w['Demographics'].max_row + 1):
        d = [w['Demographics'].cell(drow, c).value for c in range(1, 6)]
        if not isinstance(d[0], int):
            continue
        s = d[0]
        demo = dict(zip(('age', 'height', 'mass'), map(float, d[2:])))
        series = {}
        for name, sh, col, lo, hi in (('core', core, core_c[s], 30, 45), ('skin', skin, skin_c[s], 20, 45),
                                       ('hr', ex, hr_c[s], 30, 240), ('power', ex, pw_c[s], 0, 600)):
            out = {}
            for r in range(3, sh.max_row + 1):
                t, v = sh.cell(r, 2).value, sh.cell(r, col).value
                if t is None or v is None or not isinstance(v, (int, float)) or not lo <= v <= hi:
                    continue
                out[minute(t)] = float(v)
            series[name] = out
        envd = {}
        for r in range(3, env.max_row + 1):
            t = env.cell(r, 2).value
            if t is None:
                continue
            a, rh = env.cell(r, env_c[s]).value, env.cell(r, env_c[s] + 25).value
            if isinstance(a, (int, float)) and isinstance(rh, (int, float)):
                envd[minute(t)] = (float(a), float(rh))
        series['env'] = envd
        people[s] = (demo, series)
    return people


def carry(d, t):
    ks = [k for k in d if k <= t]
    return d[max(ks)] if ks else None


def episodes(people):
    eps = []
    for s, (demo, se) in people.items():
        core, power = se['core'], se['power']
        tmax = max(core)
        for t in range(10, tmax + 1):
            if any(t + h not in core for h in HORIZONS) or t not in se['skin']:
                continue
            p_now = carry(power, t)
            hist_p = [carry(power, u) for u in range(t - LOOKBACK, t + 1)]
            hist_p = [p for p in hist_p if p is not None]
            if p_now is None or not hist_p:
                continue
            fut_p = [carry(power, u) for u in range(t, t + max(HORIZONS) + 1)]
            falling = max(hist_p) - p_now >= DROP_W
            steady = (max(hist_p) - min(hist_p) < DROP_W) and (max(fut_p) - min(fut_p) < DROP_W)
            hr_hist = [carry(se['hr'], u) for u in range(0, t + 1)]
            hr_hist = [h for h in hr_hist if h is not None]
            if not hr_hist:
                continue
            a, rh = carry(se['env'], t) or (np.nan, np.nan)
            skin_first = se['skin'][min(se['skin'])]
            feats = {
                't': t, 'skin_first': skin_first, 'skin_last': se['skin'][t], 'skin_delta': se['skin'][t] - skin_first,
                'hr_last': hr_hist[-1], 'hr_mean': float(np.mean(hr_hist)), 'ambient': a, 'rh': rh,
                'age': demo['age'], 'mass': demo['mass'], 'height': demo['height'],
                'p_now': p_now, 'p_max10': max(hist_p), 'p_drop10': max(hist_p) - p_now, 'p_mean': float(np.mean(hist_p)),
            }
            eps.append({'person': s, 't': t, 'falling': falling, 'steady': steady, 'feats': feats,
                        'targets': {h: core[t + h] for h in HORIZONS}, 'core_now': core[t]})
    return eps


ELAPSED = lambda f, h: [f['t'] + h, (f['t'] + h) ** 2 / 100, (f['t'] + h) ** 3 / 1e4]
WEAR = lambda f, h: [f['t'], h, f['t'] + h, f['skin_first'], f['skin_last'], f['skin_delta'], f['hr_last'], f['hr_mean'],
                     f['ambient'], f['rh'], f['age'], f['mass'], f['height']]
WEAR_W = lambda f, h: WEAR(f, h) + [f['p_now'], f['p_max10'], f['p_drop10'], f['p_mean'], f['p_now'] / f['mass']]

MODELS = {
    'elapsed_ridge': (ELAPSED, lambda: make_pipeline(StandardScaler(), Ridge(alpha=10))),
    'wearable_ridge': (WEAR, lambda: make_pipeline(StandardScaler(), Ridge(alpha=10))),
    'wearable+watts_ridge': (WEAR_W, lambda: make_pipeline(StandardScaler(), Ridge(alpha=10))),
    'wearable_gbm': (WEAR, lambda: HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=7, l2_regularization=10, random_state=0)),
    'wearable+watts_gbm': (WEAR_W, lambda: HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=7, l2_regularization=10, random_state=0)),
}


def lopo(eps):
    persons = sorted({e['person'] for e in eps})
    preds = {m: {} for m in MODELS}
    for m, (fx, mk) in MODELS.items():
        for p in persons:
            tr = [e for e in eps if e['person'] != p]
            te = [e for e in eps if e['person'] == p]
            x = np.array([fx(e['feats'], h) for e in tr for h in HORIZONS])
            y = np.array([e['targets'][h] for e in tr for h in HORIZONS])
            model = mk().fit(x, y)
            for e in te:
                preds[m][(p, e['t'])] = {h: float(model.predict([fx(e['feats'], h)])[0]) for h in HORIZONS}
    return preds


def score(eps, preds, mask):
    sub = [e for e in eps if mask(e)]
    rows = {}
    for m in MODELS:
        mae = {h: np.mean([abs(preds[m][(e['person'], e['t'])][h] - e['targets'][h]) for e in sub]) for h in HORIZONS}
        # direction: does forecast rise from +5 to +15 when measured core rose from +5 to +15?
        meas_up = [e['targets'][15] > e['targets'][5] for e in sub]
        pred_up = [preds[m][(e['person'], e['t'])][15] > preds[m][(e['person'], e['t'])][5] for e in sub]
        # bias at +15: negative means the model under-forecasts the measured temperature
        bias15 = np.mean([preds[m][(e['person'], e['t'])][15] - e['targets'][15] for e in sub])
        rows[m] = {'n': len(sub), 'people': len({e['person'] for e in sub}),
                   **{f'mae+{h}': round(float(mae[h]), 3) for h in HORIZONS},
                   'dir_acc': round(float(np.mean([a == b for a, b in zip(meas_up, pred_up)])), 3),
                   'meas_rising_frac': round(float(np.mean(meas_up)), 3), 'bias+15': round(float(bias15), 3)}
    return rows


def main(path):
    people = load(path)
    varied = {s for s, (_, se) in people.items() if len(set(se['power'].values())) > 1}
    print(f'people={len(people)} with_power_variation={len(varied)}')
    for s in sorted(people):
        se = people[s][1]
        changes = sorted({t: v for t, v in se['power'].items()}.items())
        steps = [(t, v) for i, (t, v) in enumerate(changes) if i == 0 or v != changes[i - 1][1]]
        print(f'  S{s:02} core_minutes={len(se["core"])} skin={len(se["skin"])} hr_obs={len(se["hr"])} power_steps={steps}')
    eps = episodes(people)
    print(f'\nepisodes={len(eps)} falling={sum(e["falling"] for e in eps)} steady={sum(e["steady"] for e in eps)}')
    print('falling episodes by person:', {s: sum(1 for e in eps if e['falling'] and e['person'] == s) for s in sorted(varied)})
    fall = [e for e in eps if e['falling']]
    rise15 = [e['targets'][15] - e['core_now'] for e in fall]
    print(f'measured core change over +15 after a fall: mean={np.mean(rise15):.2f}C  min={min(rise15):.2f}  frac_rising={np.mean([r > 0 for r in rise15]):.2f}')
    preds = lopo(eps)
    for name, mask in (('ALL', lambda e: True), ('FALLING', lambda e: e['falling']), ('STEADY', lambda e: e['steady'])):
        print(f'\n== {name} ==')
        rows = score(eps, preds, mask)
        keys = list(next(iter(rows.values())).keys())
        print(f'{"model":24}' + ''.join(f'{k:>18}' for k in keys))
        for m, r in rows.items():
            print(f'{m:24}' + ''.join(f'{r[k]:>18}' for k in keys))
    # The demo moment: subject 1 at minute 40 forecasting minute 55
    e = next((e for e in eps if e['person'] == 1 and e['t'] == 40), None)
    if e:
        print('\nSubject 1, cutoff minute 40 -> minute 55: measured', e['targets'][15], 'core_now', e['core_now'])
        for m in MODELS:
            print(f'  {m:24} pred+15={preds[m][(1, 40)][15]:.2f}')
    json.dump({'episodes': len(eps), 'falling': sum(e['falling'] for e in eps)}, open('/tmp/core_dl/duel_summary.json', 'w'))


if __name__ == '__main__':
    main(sys.argv[1])
