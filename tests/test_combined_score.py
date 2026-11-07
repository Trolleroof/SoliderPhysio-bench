"""Tests for combined per-case scores and matched Davidson/Elo ratings."""
import json
import math
import unittest

from tasks import combined_score as cs
from tasks.beat_ectemp import benchmark
from tasks.keep_going import evaluator as kg
from tasks.rulebook_vs_body import evaluator as rb

PARAMS = {'E_c': 1.0, 'ectemp_B': {'3A': {'H13': 0.5}, '3B': {'H13': 0.5}}}


def kg_case(core, judge=(5, 5), case='KG-01'):
    truth = kg.load_ground_truth()[case]['core_at_cutoff_plus_15_c']
    text = json.dumps({'decision': 'PULL', 'core_c_in_15_min': None if core is None else truth + core})
    return {'task': 'keep_going', 'case_id': case, 'grader': kg.grade(case, text),
            'judge': {'decision': judge[0], 'reasoning': judge[1]}}


def ec_case(mae, judge=5, case='3A', valid=True):
    """Whole-variant run case as written by a runner; score_runs expands it per person."""
    return {'task': 'beat_ectemp', 'case_id': case,
            'grader': {'valid': valid, 'person_mae': None if mae is None else {'H13': mae}},
            'judge': {'research_explanation': judge}}


def ec_person(mae, valid=True):
    return {'valid': valid, 'person_mae': mae}


class Components(unittest.TestCase):
    def test_keep_going_forecast_uses_E(self):
        comp, _ = cs.components('keep_going', 'KG-01', kg_case(0.25)['grader'], {'decision': 5, 'reasoning': 0}, PARAMS)
        self.assertAlmostEqual(comp['forecast'], 0.75)
        self.assertAlmostEqual(cs.combined('keep_going', comp), 0.3 * 0.75 + 0.4)

    def test_missing_forecast_scores_zero_not_blocked(self):
        comp, flags = cs.components('keep_going', 'KG-01', kg_case(None)['grader'], {'decision': 5, 'reasoning': 5}, PARAMS)
        self.assertEqual(comp['forecast'], 0)
        self.assertIn('missing_forecast', flags)

    def test_error_beyond_E_floors_at_zero(self):
        comp, _ = cs.components('keep_going', 'KG-01', kg_case(3.0)['grader'], {'decision': 5, 'reasoning': 5}, PARAMS)
        self.assertEqual(comp['forecast'], 0)

    def test_unfrozen_E_or_B_blocks(self):
        with self.assertRaises(cs.NotScorable):
            cs.components('keep_going', 'KG-01', kg_case(0)['grader'], {'decision': 5, 'reasoning': 5}, {})
        with self.assertRaises(cs.NotScorable):
            cs.components('beat_ectemp', '3A/H13', ec_person(0.3), {'research_explanation': 5}, {'ectemp_B': {'3A': {'H13': 0}}})

    def test_judge_failure_blocks_bad_judge_errors(self):
        with self.assertRaises(cs.NotScorable):
            cs.components('keep_going', 'KG-01', kg_case(0)['grader'], {'decision': 'not_scorable', 'reasoning': 5}, PARAMS)
        with self.assertRaises(ValueError):
            cs.components('keep_going', 'KG-01', kg_case(0)['grader'], {'decision': 6, 'reasoning': 5}, PARAMS)

    def test_rulebook_uses_field_fraction(self):
        task = rb.load_tasks()['RB-01']
        table = rb.load_json(rb.TABLE_PATH)
        exp = rb.lookup(table, task['inputs']['heat_category'], task['inputs']['work_category'])
        reply = {'rulebook': {f: exp[f] for f in rb.RULEBOOK_FIELDS}, 'decision': 'OVERRIDE'}
        reply['rulebook'][rb.RULEBOOK_FIELDS[0]] = 'wrong'
        g = rb.grade('RB-01', json.dumps(reply))
        comp, _ = cs.components('rulebook_vs_body', 'RB-01', g, {'override_decision': 5, 'reasoning': 5}, PARAMS)
        self.assertAlmostEqual(comp['table_lookup'], 1 - 1 / len(rb.RULEBOOK_FIELDS))

    def test_ectemp_mapping_and_invalid_artifact(self):
        comp, _ = cs.components('beat_ectemp', '3A/H13', ec_person(0.25), {'research_explanation': 5}, PARAMS)
        self.assertAlmostEqual(comp['predictor'], 0.5)
        comp, _ = cs.components('beat_ectemp', '3A/H13', ec_person(0.9), {'research_explanation': 5}, PARAMS)
        self.assertEqual(comp['predictor'], 0)  # worse than ECTemp gets no credit
        comp, flags = cs.components('beat_ectemp', '3A/H13', ec_person(None, valid=False), {'research_explanation': 5}, PARAMS)
        self.assertEqual((comp['predictor'], flags), (0, ['invalid_artifact']))


class PersonBalancedMAE(unittest.TestCase):
    def test_people_weighted_equally(self):
        # Person A: 3 requests error 1; person B: 1 request error 0 -> 0.5, not 0.75.
        self.assertAlmostEqual(benchmark.person_balanced_mae([1, 1, 1, 0], 'AAAB'), 0.5)

    def test_metrics_reports_it_over_primary_mask(self):
        out = [{'lower': 37, 'mean': 38, 'upper': 39}] * 3
        m = benchmark.metrics(out, [38, 39, 40], [True, True, False], ['A', 'B', 'B'])
        self.assertAlmostEqual(m['person_balanced_mae'], 0.5)
        self.assertEqual(m['person_mae'], {'A': 0, 'B': 1})

    def test_hot_slice_reported_separately(self):
        out = [{'lower': 37, 'mean': 38, 'upper': 39}] * 3
        m = benchmark.metrics(out, [38, 39, 40], [True, True, True], ['A', 'B', 'B'], [False, False, True])
        self.assertAlmostEqual(m['primary_mae'], 1)
        self.assertEqual((m['hot_count'], m['hot_mae'], m['hot_person_balanced_mae']), (1, 2, 2))


class Ratings(unittest.TestCase):
    def run_for(self, model, kg_err, ec_mae, judge=5):
        return {'model': model, 'cases': [kg_case(kg_err, (judge, judge)), ec_case(ec_mae, judge)]}

    def test_better_model_rates_higher_and_mean_is_1500(self):
        runs = [self.run_for('good', 0.1, 0.1), self.run_for('mid', 0.4, 0.3), self.run_for('bad', 0.8, 0.45)]
        r = cs.rate(cs.score_runs(runs, PARAMS), n_boot=50, dev_allow_union_cases=True)
        self.assertEqual([x['model'] for x in r['ratings']], ['good', 'mid', 'bad'])
        self.assertAlmostEqual(sum(x['elo'] for x in r['ratings']) / 3, 1500)
        for x in r['ratings']:
            self.assertLessEqual(x['ci95'][0], x['ci95'][1])
            self.assertTrue(math.isfinite(x['elo']))

    def test_identical_models_tie_at_1500(self):
        r = cs.rate(cs.score_runs([self.run_for('a', 0.2, 0.2), self.run_for('b', 0.2, 0.2)], PARAMS), n_boot=0, dev_allow_union_cases=True)
        self.assertEqual(r['pairwise'][0]['ties'], 2.0)
        for x in r['ratings']:
            self.assertAlmostEqual(x['elo'], 1500, places=6)

    def test_tasks_weighted_equally_regardless_of_case_count(self):
        # 'a' wins all 3 KG cases, 'b' wins the single ECTemp case -> even split.
        kg_cases = ['KG-01', 'KG-02', 'KG-03']
        a = {'model': 'a', 'cases': [kg_case(0.0, case=c) for c in kg_cases] + [ec_case(0.4)]}
        b = {'model': 'b', 'cases': [kg_case(0.5, case=c) for c in kg_cases] + [ec_case(0.1)]}
        r = cs.rate(cs.score_runs([a, b], PARAMS), n_boot=0, dev_allow_union_cases=True)
        p = r['pairwise'][0]
        self.assertAlmostEqual(p['wins_a'], 1.0)
        self.assertAlmostEqual(p['wins_b'], 1.0)
        self.assertAlmostEqual(r['ratings'][0]['elo'], 1500, places=6)

    def test_blocked_or_incomplete_model_not_rated(self):
        blocked = self.run_for('blocked', 0.1, 0.1)
        blocked['cases'][0]['judge']['decision'] = 'not_scorable'
        partial = {'model': 'partial', 'cases': [kg_case(0.1)]}
        runs = [self.run_for('a', 0.1, 0.1), self.run_for('b', 0.3, 0.3), blocked, partial]
        r = cs.rate(cs.score_runs(runs, PARAMS), n_boot=0, dev_allow_union_cases=True)
        self.assertEqual(r['eligible'], ['a', 'b'])
        self.assertEqual(r['excluded']['blocked']['not_scorable'], ['keep_going/KG-01'])
        self.assertEqual(r['excluded']['partial']['missing'], ['beat_ectemp/3A/H13'])

    def test_repeated_runs_are_averaged_not_new_cases(self):
        runs = [self.run_for('a', 0.0, 0.2), self.run_for('a', 0.4, 0.2), self.run_for('b', 0.2, 0.2)]
        s = cs.score_runs(runs, PARAMS)
        self.assertEqual(s['a'][('keep_going', 'KG-01')]['n_runs'], 2)
        self.assertAlmostEqual(s['a'][('keep_going', 'KG-01')]['combined'], s['b'][('keep_going', 'KG-01')]['combined'])

    def test_judge_on_roster_is_rejected(self):
        a, b = self.run_for('openai/model-x', 0.1, 0.1), self.run_for('model-y', 0.3, 0.3)
        b['cases'][0]['judge_record'] = {'judge_model': 'model-x'}
        with self.assertRaisesRegex(ValueError, 'model-x'):
            cs.score_runs([a, b], PARAMS)
        b['cases'][0]['judge_record'] = {'judge_model': 'judge-z'}
        cs.score_runs([a, b], PARAMS)

    def test_required_cases_ignore_extra_case(self):
        # One model also ran KG-02. Under the union rule that excluded everyone else.
        extra = self.run_for('a', 0.1, 0.1)
        extra['cases'].append(kg_case(0.1, case='KG-02'))
        runs = [extra, self.run_for('b', 0.3, 0.3), self.run_for('c', 0.5, 0.4)]
        scores = cs.score_runs(runs, PARAMS)
        union = cs.rate(scores, n_boot=0, dev_allow_union_cases=True)
        self.assertEqual(union['eligible'], ['a'])
        self.assertTrue(union['warnings'])
        r = cs.rate(scores, n_boot=0, required_cases=['keep_going/KG-01', 'beat_ectemp/3A/H13'])
        self.assertEqual(r['eligible'], ['a', 'b', 'c'])
        self.assertEqual(r['extra_cases_not_rated'], {'a': ['keep_going/KG-02']})
        self.assertEqual(r['cases'], ['beat_ectemp/3A/H13', 'keep_going/KG-01'])
        self.assertEqual(r['warnings'], [])
        # The extra case must not change the comparison at all.
        base = cs.rate(cs.score_runs(runs[1:] + [self.run_for('a', 0.1, 0.1)], PARAMS), n_boot=0, dev_allow_union_cases=True)
        self.assertEqual([x['elo'] for x in r['ratings']], [x['elo'] for x in base['ratings']])

    def test_required_cases_blocked_extra_does_not_exclude_but_required_does(self):
        a = self.run_for('a', 0.1, 0.1)
        bad = kg_case(0.1, case='KG-02')
        bad['judge']['decision'] = 'not_scorable'
        a['cases'].append(bad)
        req = ['keep_going/KG-01', 'beat_ectemp/3A/H13', 'beat_ectemp/3B/H13']
        r = cs.rate(cs.score_runs([a, self.run_for('b', 0.3, 0.3)], PARAMS), n_boot=0, required_cases=req)
        self.assertEqual(r['eligible'], [])
        self.assertEqual(r['excluded']['a'], {'missing': ['beat_ectemp/3B/H13'], 'not_scorable': []})
        with self.assertRaises(ValueError):
            cs.parse_required(['KG-01'])
        with self.assertRaises(ValueError):
            cs.parse_required(['nope/KG-01'])

    def test_missing_required_cases_is_an_error(self):
        scores = cs.score_runs([self.run_for('a', 0.1, 0.1), self.run_for('b', 0.3, 0.3)], PARAMS)
        with self.assertRaises(ValueError):
            cs.rate(scores, n_boot=0)
        self.assertEqual(cs.rate(scores, n_boot=0, dev_allow_union_cases=True)['eligible'], ['a', 'b'])

    def test_cli_reads_required_cases_and_dev_flag(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            runs = []
            for m, e in (('a', 0.1), ('b', 0.4)):
                p = Path(d) / f'{m}.json'
                p.write_text(json.dumps(self.run_for(m, e, e)))
                runs.append(str(p))
            params = Path(d) / 'params.json'
            out = Path(d) / 'out.json'
            params.write_text(json.dumps(PARAMS))
            with self.assertRaises(ValueError):
                cs.main(runs + ['--params', str(params), '--n-boot', '0', '--out', str(out)])
            for extra in ({'dev_allow_union_cases': True}, {'required_cases': ['keep_going/KG-01', 'beat_ectemp/3A/H13']}):
                params.write_text(json.dumps({**PARAMS, **extra}))
                import contextlib, io
                with contextlib.redirect_stdout(io.StringIO()):
                    cs.main(runs + ['--params', str(params), '--n-boot', '0', '--out', str(out)])
                self.assertEqual(json.loads(out.read_text())['eligible'], ['a', 'b'])

    def test_kg03_edge_case_outside_required_list_is_reported_not_rated(self):
        req = ['keep_going/KG-01', 'beat_ectemp/3A/H13']
        runs = [self.run_for('a', 0.1, 0.1), self.run_for('b', 0.3, 0.3)]
        runs[0]['cases'].append(kg_case(0.0, case='KG-03'))
        runs[1]['cases'].append(kg_case(2.0, (0, 0), case='KG-03'))
        r = cs.rate(cs.score_runs(runs, PARAMS), n_boot=0, required_cases=req)
        self.assertNotIn('keep_going/KG-03', r['cases'])
        self.assertEqual(r['extra_cases_not_rated'], {'a': ['keep_going/KG-03'], 'b': ['keep_going/KG-03']})
        base = cs.rate(cs.score_runs([self.run_for('a', 0.1, 0.1), self.run_for('b', 0.3, 0.3)], PARAMS),
                       n_boot=0, required_cases=req)
        self.assertEqual([x['elo'] for x in r['ratings']], [x['elo'] for x in base['ratings']])

    def test_required_case_ids_may_contain_slashes(self):
        # Per-person beat_ectemp ids such as "3A/H04" split on the first slash only.
        self.assertEqual(cs.parse_required(['beat_ectemp/3A/H04', 'keep_going/KG-01']),
                         [('beat_ectemp', '3A/H04'), ('keep_going', 'KG-01')])

    def test_separation_flag_and_ci_note(self):
        runs = [self.run_for('top', 0.0, 0.05), self.run_for('mid', 0.3, 0.3), self.run_for('low', 0.9, 0.49, judge=1)]
        req = ['keep_going/KG-01', 'beat_ectemp/3A/H13']
        r = cs.rate(cs.score_runs(runs, PARAMS), n_boot=10, required_cases=req)
        flags = {x['model']: x['separation'] for x in r['ratings']}
        self.assertEqual(flags, {'top': 'wins_all', 'mid': None, 'low': 'loses_all'})
        self.assertIn('prior', [x for x in r['ratings'] if x['model'] == 'top'][0]['separation_note'])
        self.assertIsNone([x for x in r['ratings'] if x['model'] == 'mid'][0]['separation_note'])
        self.assertIn('70%', r['ci95_note'])
        self.assertIn('exploratory', r['ci95_note'])
        # A tie with a winner means "did not win every comparison".
        tied = [self.run_for('a', 0.1, 0.1), self.run_for('b', 0.1, 0.1), self.run_for('c', 0.5, 0.4)]
        r = cs.rate(cs.score_runs(tied, PARAMS), n_boot=0, required_cases=req)
        self.assertEqual({x['model']: x['separation'] for x in r['ratings']}, {'a': None, 'b': None, 'c': 'loses_all'})

    def test_ties_use_tolerance_not_rounding(self):
        # These differ by ~4e-19 but round(., 9) puts them on opposite sides of a boundary.
        x, y = math.nextafter(0.0010000005, 0), math.nextafter(0.0010000005, 1)
        self.assertNotEqual(round(x, 9), round(y, 9))
        scores = {m: {('keep_going', 'KG-01'): {'status': 'scored', 'combined': v}}
                  for m, v in (('a', x), ('b', y))}
        self.assertEqual(cs.pairwise(scores, ['a', 'b'], [('keep_going', 'KG-01')])[(0, 1)]['ties'], 1)

    def test_percentile_interpolates_symmetrically(self):
        xs = list(range(1000))
        self.assertAlmostEqual(cs.percentile(xs, 0.025), 24.975)
        self.assertAlmostEqual(cs.percentile(xs, 0.975), 974.025)
        self.assertEqual(cs.percentile([7], 0.975), 7)

    def test_perfect_separation_finite_and_all_ties_flat(self):
        ids = [('keep_going', f'KG-{i:02d}') for i in range(1, 14)] + [
            ('rulebook_vs_body', 'RB-01'), ('rulebook_vs_body', 'RB-02'), ('beat_ectemp', '3A'), ('beat_ectemp', '3B')]
        sep = {f'm{i}': {k: {'status': 'scored', 'combined': 1 - i / 4} for k in ids} for i in range(4)}
        r = cs.rate(sep, n_boot=20, dev_allow_union_cases=True)
        elos = [x['elo'] for x in r['ratings']]
        self.assertEqual([x['model'] for x in r['ratings']], ['m0', 'm1', 'm2', 'm3'])
        self.assertTrue(all(math.isfinite(e) for e in elos))
        self.assertLess(max(elos) - min(elos), 2000)
        tie = {f'm{i}': {k: {'status': 'scored', 'combined': 0.5} for k in ids} for i in range(4)}
        r = cs.rate(tie, n_boot=20, dev_allow_union_cases=True)
        for x in r['ratings']:
            self.assertAlmostEqual(x['elo'], 1500, places=6)
            self.assertAlmostEqual(x['ci95'][0], 1500, places=6)
            self.assertAlmostEqual(x['ci95'][1], 1500, places=6)

    def test_too_few_models(self):
        r = cs.rate(cs.score_runs([self.run_for('a', 0.1, 0.1)], PARAMS), dev_allow_union_cases=True)
        self.assertIsNone(r['ratings'])



class StressHarness(unittest.TestCase):
    def test_elo_order_is_total_pairwise_score_order(self):
        # Complete matched design: every fit variant ranks by total (task-averaged) pairwise score.
        import random
        from tasks import elo_stress as es
        rng = random.Random(3)
        for _ in range(5):
            scores = es.to_scores(es.benchmark(es.roster(6, es.SCENARIOS['typical'], rng), es.SCENARIOS['typical'], rng))
            ts = es.total_score(scores)
            if len({round(x, 9) for x in ts}) < len(ts):
                continue
            for tm, over in (('davidson', {}), ('half_win', {}), ('davidson', {'theta_prior_precision': 1.0})):
                self.assertEqual(es.ranks(es.elo_of(scores, tm, **over)[0]), es.ranks(ts))


class ECTempPerPerson(unittest.TestCase):
    P = {'E_c': 1.0, 'ectemp_B': {'3A': {'H06': 0.2, 'H13': 0.8}}}

    def test_run_case_expands_per_person_with_shared_judge(self):
        case = {'task': 'beat_ectemp', 'case_id': '3A', 'judge': {'research_explanation': 5},
                'grader': {'valid': True, 'person_mae': {'H06': 0.1, 'H13': 0.2}}}
        s = cs.score_runs([{'model': 'm', 'cases': [case]}], self.P)['m']
        self.assertEqual(sorted(s), [('beat_ectemp', '3A/H06'), ('beat_ectemp', '3A/H13')])
        a, b = (s[('beat_ectemp', c)]['attempts'][0]['components'] for c in ('3A/H06', '3A/H13'))
        self.assertAlmostEqual(a['predictor'], 0.5)    # 1 - 0.1/0.2, per-person B
        self.assertAlmostEqual(b['predictor'], 0.75)   # 1 - 0.2/0.8
        self.assertEqual(a['research_explanation'], b['research_explanation'])

    def test_invalid_artifact_zeroes_every_person_and_missing_person_blocks(self):
        bad = {'task': 'beat_ectemp', 'case_id': '3A', 'judge': {'research_explanation': 5},
               'grader': {'valid': False, 'person_mae': None}}
        s = cs.score_runs([{'model': 'm', 'cases': [bad]}], self.P)['m']
        self.assertEqual([r['attempts'][0]['components']['predictor'] for r in s.values()], [0.0, 0.0])
        partial = {**bad, 'grader': {'valid': True, 'person_mae': {'H06': 0.1}}}
        s = cs.score_runs([{'model': 'm', 'cases': [partial]}], self.P)['m']
        self.assertEqual(s[('beat_ectemp', '3A/H13')]['status'], 'not_scorable')

    def test_flat_B_is_not_scorable(self):
        s = cs.score_runs([{'model': 'm', 'cases': [ec_case(0.1)]}], {'E_c': 1.0, 'ectemp_B': {'3A': 0.5}})['m']
        self.assertEqual(s[('beat_ectemp', '3A')]['status'], 'not_scorable')


class FrozenParams(unittest.TestCase):
    def test_frozen_params_are_valid_and_scorable(self):
        from pathlib import Path
        params = json.loads((Path(cs.__file__).parent / 'scoring_params.json').read_text())
        self.assertAlmostEqual(params['E_c'], 0.1712)
        self.assertEqual(sorted(params['ectemp_B']), ['3A', '3B'])
        expected_ec = []
        for variant, people in params['ectemp_B'].items():
            for person, B in people.items():
                self.assertTrue(math.isfinite(B) and B > 0)
                expected_ec.append(f'beat_ectemp/{variant}/{person}')
        req = params['required_cases']
        self.assertEqual(len(req), len(set(req)))
        self.assertEqual([c for c in req if c.startswith('beat_ectemp/')], expected_ec)
        kg_scored = sorted(t for t, g in kg.load_ground_truth().items() if g['role'] == 'primary')
        self.assertEqual([c for c in req if c.startswith('keep_going/')], [f'keep_going/{t}' for t in kg_scored])
        self.assertNotIn('keep_going/KG-03', req)
        self.assertIn('rulebook_vs_body/RB-01', req)
        self.assertIn('rulebook_vs_body/RB-02', req)
        comp, _ = cs.components('keep_going', 'KG-01', {'core_abs_error_c': params['E_c'] / 2},
                                {'decision': 5, 'reasoning': 5}, params)
        self.assertAlmostEqual(comp['forecast'], 0.5)


if __name__ == '__main__':
    unittest.main()
