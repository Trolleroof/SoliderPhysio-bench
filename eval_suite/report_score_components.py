"""Offline report of saved deterministic outcomes and separate judge assessments."""
from collections import Counter
from pathlib import Path
from statistics import mean, median
import hashlib
import json

from eval_suite.core.common import digest, file_hash, read, write
from eval_suite.resume_sweep import inventory
from eval_suite.runner import select_cases
from tasks.combined_score import JUDGED, WEIGHTS, check_judge_model, components
from tasks.judge import answer_text, case_materials, load_rubric, outcome_block, render_prompt

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / '.benchmark-runs/rerun-20261107'
REPORT = ROOT / 'docs/results/roster-rerun-20261107-score-components.md'


def average(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def sha(text):
    return None if text is None else hashlib.sha256(text.encode()).hexdigest()


def decisions(graders):
    errors = [g['core_abs_error_c'] for g in graders if g['core_abs_error_c'] is not None]
    return {'n': len(graders), 'correct': sum(g['decision_correct'] for g in graders),
            'accuracy': average([int(g['decision_correct']) for g in graders]),
            'errors': dict(Counter(g['error_type'] or 'correct' for g in graders)),
            'forecast_present': len(errors), 'forecast_missing': len(graders) - len(errors),
            'forecast_mae_c': average(errors), 'forecast_median_abs_error_c': median(errors) if errors else None,
            'forecast_max_abs_error_c': max(errors) if errors else None}


def judge_summary(cases, task):
    status = Counter(c['judge']['status'] for c in cases)
    out = {'n': len(cases), 'status': dict(status), 'dimensions': {}}
    for dim in JUDGED[task]:
        values = [c['judge']['scores'][dim] for c in cases]
        present = [c['judge']['scores'][dim] for c in cases if c['judge']['status'] == 'scored']
        out['dimensions'][dim] = {'mean_including_absent_zero': average(values),
                                  'mean_scored_answers_only': average(present),
                                  'scored_answer_n': len(present),
                                  'distribution_including_absent_zero': dict(Counter(values))}
    if task == 'beat_ectemp':
        # The same explanation is judged separately against each person's outcome.
        out['unique_research_artifacts'] = len({(c['submission'], c['case_id'].split('/')[0]) for c in cases})
        out['unique_nonempty_explanations'] = len({(c['submission'], c['case_id'].split('/')[0])
                                                 for c in cases if c['judge']['status'] == 'scored'})
    return out


def build():
    audit = read(RUN / 'control/completion-audit.json')
    params = read(ROOT / 'tasks/scoring_params.json')
    required = select_cases()
    roster = read(ROOT / 'eval_suite/roster.json')['models']
    rows = [r for r in roster if r.get('openrouter_id') in audit['coverage']]
    assert len(rows) == 14 and len(required) == 21
    check_judge_model(audit['judge_model'])
    rubric = load_rubric()
    saved_judges = [(p, read(p)) for p in sorted(RUN.glob('*/judged.json'))]
    checks = Counter()
    sources, models, all_cases, discrepancies = {}, [], [], []
    for row in rows:
        found, _ = inventory(RUN, row)
        assert set(found) == set(required), (row['openrouter_id'], set(found) ^ set(required))
        assert len(found) == audit['coverage'][row['openrouter_id']] == 21
        cases = []
        for source in sorted(set(found.values())):
            p = Path(source)
            submission = read(p)
            assert not submission.get('fake_model')
            assert submission['scoring_params_sha256'] == digest(params)
            matches = [(jp, j) for jp, j in saved_judges
                       if j.get('identity', {}).get('submission_sha256') == digest(submission)]
            assert len(matches) == 1, (source, len(matches))
            jp, judged = matches[0]
            assert judged['model'] == submission['model'] == row['openrouter_id']
            assert read(jp.parent / 'identity.json') == judged['identity']
            assert judged['identity']['rubric_sha256'] == rubric['sha256']
            assert judged['identity']['judge_model'] == audit['judge_model']
            assert len(submission['cases']) == len(judged['cases'])
            sources[str(p.relative_to(ROOT))] = {'submission_sha256': digest(submission),
                                                'judged': str(jp.relative_to(ROOT)),
                                                'judged_file_sha256': file_hash(jp)}
            checks['submission_identity'] += 1
            for i, (c, j) in enumerate(zip(submission['cases'], judged['cases'])):
                key = c['task'] + '/' + c['case_id']
                assert found[key] == source
                assert (c['task'], c['case_id'], c.get('run', 0), c['grader']) == (
                    j['task'], j['case_id'], j['run'], j['grader'])
                checkpoint = read(jp.parent / f'case-{i:02d}.json')
                assert checkpoint['input_sha256'] == digest(c)
                assert checkpoint['attempts'][-1] == j
                checks['case_checkpoint'] += 1
                rec = j['judge_record']
                assert rec['status'] in ('scored', 'absent_answer')
                assert rec['judge_model'] == audit['judge_model']
                assert rec['scores'] == j['judge']
                assert set(j['judge']) == set(JUDGED[c['task']])
                assert all(type(v) is int and 0 <= v <= 5 for v in j['judge'].values())
                text = answer_text(c.get('answer'))
                assert rec['input_hashes']['answer'] == sha(text)
                assert rec['input_hashes']['rubric'] == rubric['sha256']
                checks['answer_and_rubric'] += 1
                if text is None:
                    assert rec['status'] == 'absent_answer' and not rec['attempts']
                    assert rec['prompt'] is None and all(v == 0 for v in j['judge'].values())
                    checks['absent_without_provider_judgment'] += 1
                else:
                    mats = case_materials(c['task'], c['case_id'], c.get('materials'))
                    outcome = outcome_block(c['task'], c['case_id'], c['grader'])
                    prompt = render_prompt(c['task'], rubric, mats, text, JUDGED[c['task']], outcome=outcome)
                    assert rec['input_hashes'] == {'answer': sha(text), 'rubric': rubric['sha256'],
                                                  'materials': digest(mats), 'extra': None,
                                                  'outcome': sha(outcome), 'prompt': sha(prompt)}
                    assert rec['prompt'] == prompt
                    for attempt in rec['attempts']:
                        assert attempt['prompt_sha256'] == sha(prompt)
                        assert attempt['request_sha256'] == digest(attempt['request_body'])
                        assert attempt['request_body']['model'] == audit['judge_model']
                        assert attempt['request_body']['messages'] == [{'role': 'user', 'content': prompt}]
                        checks['judge_request'] += 1
                    checks['rendered_judge_inputs'] += 1
                deterministic = dict(c['grader'])
                if c['task'] == 'beat_ectemp':
                    variant, person = c['case_id'].split('/')
                    baseline = params['ectemp_B'][variant][person]
                    mae = c['grader']['person_mae']
                    report_path = p.parent / c['grader_report']
                    hidden = read(report_path)
                    assert hidden['valid'] == c['grader']['valid']
                    assert (hidden.get('person_mae') or {}).get(person) == mae
                    deterministic.update(baseline_mae_c=baseline,
                                         improvement_c=None if mae is None else baseline - mae,
                                         relative_improvement=None if mae is None else 1 - mae / baseline,
                                         beats_baseline=None if mae is None else mae < baseline,
                                         grader_report=str(report_path.relative_to(ROOT)))
                    checks['research_grader_crosscheck'] += 1
                normalized, flags = components(c['task'], c['case_id'], c['grader'], j['judge'], params)
                case = {'model': row['openrouter_id'], 'task': c['task'], 'case_id': c['case_id'],
                        'submission': str(p.relative_to(ROOT)), 'judge_file': str(jp.relative_to(ROOT)),
                        'deterministic': deterministic,
                        'saved_execution_metadata': {k: c[k] for k in ('finish_reason', 'research_stop', 'research_wall_s') if k in c},
                        'frozen_normalized_components': normalized, 'frozen_flags': flags,
                        'judge': {'status': rec['status'], 'scores': j['judge'],
                                  'judgment': rec['judgment'], 'input_hashes': rec['input_hashes']}}
                if c['task'] != 'beat_ectemp':
                    g = c['grader'] if c['task'] == 'keep_going' else c['grader']['body']
                    dim = 'decision' if c['task'] == 'keep_going' else 'override_decision'
                    for name, cap in ((dim, 1), ('reasoning', 2)):
                        if not g['decision_correct'] and j['judge'][name] > cap:
                            discrepancies.append({'model': row['openrouter_id'], 'case': key,
                                                  'dimension': name, 'score': j['judge'][name],
                                                  'issue': f'wrong deterministic decision exceeds frozen rubric cap {cap}'})
                cases.append(case)
        cases.sort(key=lambda c: required.index(c['task'] + '/' + c['case_id']))
        assert len(cases) == 21
        tasks = {}
        for task in WEIGHTS:
            group = [c for c in cases if c['task'] == task]
            if task == 'keep_going':
                det = decisions([c['deterministic'] for c in group])
            elif task == 'rulebook_vs_body':
                det = decisions([c['deterministic']['body'] for c in group])
                det.update(lookup_fields_correct=sum(sum(c['deterministic']['rulebook']['matches'].values()) for c in group),
                           lookup_fields_total=4 * len(group),
                           lookup_all_fields_correct=sum(c['deterministic']['rulebook']['pass'] for c in group),
                           lookup_field_correct_counts=dict(Counter(k for c in group for k, v in c['deterministic']['rulebook']['matches'].items() if v)))
            else:
                det = {}
                for variant in ('3A', '3B'):
                    people = [c for c in group if c['case_id'].startswith(variant + '/')]
                    graded = [c for c in people if c['deterministic']['valid'] and c['deterministic']['person_mae'] is not None]
                    reports = {c['deterministic']['grader_report'] for c in people}
                    assert len(reports) == 1
                    hidden = read(ROOT / next(iter(reports)))
                    assert {c['case_id'].split('/')[1] for c in people} == set(params['ectemp_B'][variant])
                    assert abs(average([c['deterministic']['person_mae'] for c in graded]) - hidden['person_balanced_mae']) < 1e-12
                    assert hidden['primary_count'] == (57 if variant == '3A' else 300)
                    det[variant] = {'n_people': len(people), 'valid_people': len(graded),
                                    'person_balanced_mae_c': average([c['deterministic']['person_mae'] for c in graded]),
                                    'person_balanced_baseline_mae_c': average([c['deterministic']['baseline_mae_c'] for c in graded]),
                                    'person_balanced_improvement_c': average([c['deterministic']['improvement_c'] for c in graded]),
                                    'people_beating_baseline': sum(c['deterministic']['beats_baseline'] for c in graded),
                                    'saved_variant_grader': hidden,
                                    'selected_person_cases': [c['case_id'] for c in people]}
            tasks[task] = {'deterministic': det, 'judge': judge_summary(group, task)}
        models.append({'roster_rank': row['rank'], 'model': row['openrouter_id'], 'tasks': tasks, 'cases': cases})
        all_cases.extend(cases)
    statuses = dict(Counter(c['judge']['status'] for c in all_cases))
    assert len(all_cases) == audit['total_unique_cases'] == 294
    assert statuses == audit['judgments'] == {'scored': 276, 'absent_answer': 18}
    assert len(sources) == audit['verified_submission_sources'] == 24
    kg = [c['deterministic'] for c in all_cases if c['task'] == 'keep_going']
    rb = [c['deterministic'] for c in all_cases if c['task'] == 'rulebook_vs_body']
    research = [c['deterministic'] for c in all_cases if c['task'] == 'beat_ectemp']
    raw_totals = {'keep_going_correct': sum(g['decision_correct'] for g in kg), 'keep_going_total': len(kg),
                  'rulebook_fields_correct': sum(sum(g['rulebook']['matches'].values()) for g in rb),
                  'rulebook_fields_total': 4 * len(rb),
                  'rulebook_full_lookup_cases': sum(g['rulebook']['pass'] for g in rb),
                  'rulebook_override_correct': sum(g['body']['decision_correct'] for g in rb),
                  'rulebook_total': len(rb), 'research_valid': sum(g['valid'] for g in research),
                  'research_beating_baseline': sum(g['beats_baseline'] for g in research),
                  'research_total': len(research),
                  'absent_by_task': dict(Counter(c['task'] for c in all_cases if c['judge']['status'] == 'absent_answer'))}
    result = {'schema': 'saved-score-components-v1', 'source_audit': str((RUN / 'control/completion-audit.json').relative_to(ROOT)),
              'source_audit_sha256': file_hash(RUN / 'control/completion-audit.json'),
              'scoring_params_sha256': digest(params), 'combined_score_file_sha256': file_hash(ROOT / 'tasks/combined_score.py'),
              'rubric_sha256': rubric['sha256'], 'judge_model': audit['judge_model'],
              'required_cases': required, 'frozen_weights': WEIGHTS, 'frozen_E_c': params['E_c'],
              'coverage': {m['model']: len(m['cases']) for m in models}, 'total_cases': len(all_cases),
              'judge_status': statuses, 'raw_totals': raw_totals, 'checks': dict(checks), 'sources': sources, 'models': models,
              'discrepancies': discrepancies,
              'spend_from_completion_audit_only': {'provider_reported_usd': audit['spend']['provider_reported'],
                                                   'conservative_reservations_usd': audit['spend']['conservative_reservation']},
              'limitations': ['Saved-data audit only; no inference, research execution, or rescoring of predictions.',
                              'Argon absent explanations are partly harness-caused (30-second finalization reserve); explanation comparisons are provisional.',
                              'Absent_answer is a deterministic rubric zero without an LLM judge request, not an evaluated explanation.',
                              'Per-person research judgments share artifacts/explanations and are not independent research experiments.',
                              'Finish/stop metadata describes execution boundaries, not causal failure attribution.',
                              'Carbon unavailable; Gemini 3.7, diagnostic fixtures and initial DeepSeek pilots excluded.']}
    return result


def fmt(value):
    return '—' if value is None else f'{value:.4f}'


def markdown(result):
    models = result['models']
    all_cases = [c for m in models for c in m['cases']]
    totals = result['raw_totals']
    lines = ['# Saved score components: roster rerun 2026-11-07', '',
             'This report separates deterministic ground-truth outcomes from LLM judge assessments. '
             'Rows follow frozen roster order, not a new ranking. Machine-readable case details, '
             'judge explanations, hashes and saved variant metrics are in '
             '`.benchmark-runs/rerun-20261107/score-components.json`.', '',
             '## Scope and checks', '',
             '- Coverage: **14 models × 21 required cases = 294** (168 Keep going, 28 Rulebook, 98 research person-cases). '
             'Every model covers the same 12 KG, 2 RB and 7 research cases; KG-03 is excluded.',
             '- Reused `eval_suite.resume_sweep.inventory`; all 24 source submissions have a unique canonical-hash-matching judge file. '
             'Verified 294 case checkpoint hashes and matching graders, 294 answer/rubric hashes, '
             '276 reconstructed materials/outcome/prompt hashes and request-body hashes. '
             'The 18 absent answers have no judge prompt/request and receive deterministic rubric zeros.',
             '- Judge: `openai/gpt-6.1-sol-pro`, verified outside the frozen roster. '
             '276 scored + 18 absent answers; no remaining not-scorable records in this selection.',
             '- Carbon unavailable. Gemini 3.7, diagnostic fixtures and initial DeepSeek pilots are outside this inventory. '
             'All saved artifacts, attempts and ledgers remain untouched.', '',
             '## Raw deterministic outcomes', '',
             'Accuracy uses all required cases, including absent/unparsed decisions as incorrect. '
             'Temperature error summaries use available numeric forecasts only; missing counts are explicit. '
             'These are saved deterministic grader results, not judge opinions.', '',
             f"Across the roster: **{totals['keep_going_correct']}/{totals['keep_going_total']} correct KG decisions**, "
             f"**{totals['rulebook_fields_correct']}/{totals['rulebook_fields_total']} rulebook fields**, "
             f"**{totals['rulebook_override_correct']}/{totals['rulebook_total']} correct overrides**, and "
             f"**{totals['research_beating_baseline']}/{totals['research_total']} research person-cases beating baseline**. "
             f"No rulebook case matched all four lookup fields ({totals['rulebook_full_lookup_cases']}/{totals['rulebook_total']}). "
             'These pooled counts describe this case set; they are not a model ranking.', '',
             '### Keep going', '',
             '| Model | Correct /12 | Missed pull | False pull | Unparsed | Forecasts /12 | MAE °C | Median °C | Max °C |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in models:
        d = m['tasks']['keep_going']['deterministic']; e = d['errors']
        lines.append(f"| {m['model']} | {d['correct']} | {e.get('missed_pull', 0)} | {e.get('false_pull', 0)} | {e.get('unparsed', 0)} | {d['forecast_present']} | {fmt(d['forecast_mae_c'])} | {fmt(d['forecast_median_abs_error_c'])} | {fmt(d['forecast_max_abs_error_c'])} |")
    lines += ['', '### Rulebook versus body', '',
              'Lookup is exact match on four fields per case; a case passes lookup only at 4/4. '
              'Override correctness is independently compared with the saved FOLLOW/OVERRIDE ground truth. '
              'The evaluator’s legacy 50/50 `total` is retained per case in JSON but is not the frozen mixed score.', '',
              '| Model | Lookup fields /8 | Full lookup cases /2 | Override correct /2 | Missed override | False override | Unparsed | Forecasts /2 | MAE °C |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in models:
        d = m['tasks']['rulebook_vs_body']['deterministic']; e = d['errors']
        lines.append(f"| {m['model']} | {d['lookup_fields_correct']} | {d['lookup_all_fields_correct']} | {d['correct']} | {e.get('missed_override', 0)} | {e.get('false_override', 0)} | {e.get('unparsed', 0)} | {d['forecast_present']} | {fmt(d['forecast_mae_c'])} |")
    lines += ['', '### Research predictors', '',
              'All 98 person-cases have valid saved predictors and numeric MAE. '
              'There are 28 distinct variant artifacts (one 3A and one 3B per model), not 98 independent research runs. '
              '3A covers H06/H13 (57 scored requests after watts drop); 3B covers five people (300 requests). '
              'MAE below is the equal-person mean. Improvement is baseline MAE minus model MAE in °C, so negative values are worse. '
              'No clipping is applied to these raw improvements. The comparator is ECTemp-style, not a validated reproduction of published ECTemp.', '',
              '| Model | Variant | Valid people | MAE °C | Baseline °C | Improvement °C | People beating baseline | Interval coverage | Interval score |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in models:
        for variant, d in m['tasks']['beat_ectemp']['deterministic'].items():
            g = d['saved_variant_grader']
            lines.append(f"| {m['model']} | {variant} | {d['valid_people']}/{d['n_people']} | {fmt(d['person_balanced_mae_c'])} | {fmt(d['person_balanced_baseline_mae_c'])} | {fmt(d['person_balanced_improvement_c'])} | {d['people_beating_baseline']}/{d['n_people']} | {fmt(g.get('coverage_90'))} | {fmt(g.get('interval_score_90'))} |")
    lines += ['', 'Interval coverage/score are the saved variant-wide metrics over all prediction requests, '
              'not equal-person or exclusively post-drop aggregates. They do not enter the frozen predictor score. '
              'Saved request-weighted MAE, primary MAE, hot-slice metrics and public-to-hidden gaps are preserved in JSON.', '',
              '#### Raw MAE for every held-out person', '',
              '| Model | 3A H06 | 3A H13 | 3B H06 | 3B H13 | 3B H18 | 3B H22 | 3B H25 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    research_keys = [k.split('/', 1)[1] for k in result['required_cases'] if k.startswith('beat_ectemp/')]
    baseline = {c['case_id']: c['deterministic']['baseline_mae_c'] for c in models[0]['cases'] if c['task'] == 'beat_ectemp'}
    lines.append('| Frozen baseline | ' + ' | '.join(fmt(baseline[k]) for k in research_keys) + ' |')
    for m in models:
        values = {c['case_id']: c['deterministic']['person_mae'] for c in m['cases'] if c['task'] == 'beat_ectemp'}
        lines.append('| ' + m['model'] + ' | ' + ' | '.join(fmt(values[k]) for k in research_keys) + ' |')
    lines += ['', '## Separate judge summaries', '',
              'Means are on the original 0–5 scale. “All” includes deterministic zeros for absent answers; '
              '“scored only” excludes those absent answers. Missing explanations are not evidence of invalid predictors. '
              'The JSON contains per-case scores, score distributions, explanations, quoted answer evidence, references and uncertainties. '
              'Scores describe this frozen judge’s assessment, not an additional ground-truth measurement.', '']
    for task in WEIGHTS:
        dims = JUDGED[task]
        lines += [f'### {task}', '', '| Model | Scored | Absent | ' + ' | '.join(f'{d} all / scored only' for d in dims) + ' |',
                  '|---|---:|---:|' + '---:|' * len(dims)]
        for m in models:
            s = m['tasks'][task]['judge']
            vals = [f"{fmt(s['dimensions'][d]['mean_including_absent_zero'])} / {fmt(s['dimensions'][d]['mean_scored_answers_only'])}" for d in dims]
            lines.append(f"| {m['model']} | {s['status'].get('scored', 0)} | {s['status'].get('absent_answer', 0)} | " + ' | '.join(vals) + ' |')
        lines.append('')
    absent = [c for c in all_cases if c['judge']['status'] == 'absent_answer']
    lines += ['Research explanations are shared across person-cases within an artifact, but the judge sees each person’s verified outcome. '
              'Those scores can differ and are correlated. Unique nonempty explanation counts per model are available in JSON. '
              '**Argon’s missing research explanations are partly harness-caused by the 30-second finalization reserve. '
              'Explanation comparisons are provisional and need a versioned matched rerun.**', '',
              'Absent-answer cases: ' + '; '.join(f"{model}: " + ', '.join(c['task'] + '/' + c['case_id'] for c in absent if c['model'] == model)
                                                  for model in dict.fromkeys(c['model'] for c in absent)) + '.', '',
              '## Frozen weighting and interpretation', '',
              '- Keep going: 30% deterministic forecast `max(0, 1 − absolute_error / 0.1712)` + '
              '40% judge decision/5 + 30% judge reasoning/5. Missing forecasts receive zero forecast credit. '
              'Raw binary decision correctness is reported above; it is not itself a separate weighted component.',
              '- Rulebook: 30% deterministic four-field lookup fraction + 40% judge override/5 + 30% judge reasoning/5. '
              'Raw override correctness and body forecast error remain separately visible; body forecast error has no direct mixed-score weight.',
              '- Research: 60% deterministic per-person `clip(1 − MAE/B, 0, 1)` + 40% judge research explanation/5. '
              '`B` is the frozen baseline for that variant/person. Invalid artifacts get zero predictor credit; none of the 98 selected person-cases are invalid. '
              'Worse-than-baseline predictors all get zero normalized predictor credit even when their raw errors differ.',
              '- Judge zeros for absent answers do not erase valid deterministic forecast/lookup/predictor outcomes. '
              'A missing/not-scorable judge dimension would block a mixed case instead of becoming zero; no such records remain here.',
              '- These formulas are read from frozen `tasks/combined_score.py`; no scoring or protocol changes, '
              'new ranking, Elo fit or mixed leaderboard were produced by this report.', '',
              '## Discrepancies and limits', '']
    if result['discrepancies']:
        lines += [f"- {d['model']} {d['case']} {d['dimension']}={d['score']}: {d['issue']}." for d in result['discrepancies']]
    else:
        lines.append('- No coverage/hash discrepancies or wrong-decision rubric-cap violations were found.')
    lines += ['- Provider/filter/length failures, generated-code problems and infrastructure/harness interruptions are different causes. '
              'This report preserves saved finish/stop metadata but does not infer cause from absent text or an error metric; '
              'the companion failure audit owns that attribution. In particular, a research wall-limit can leave a valid predictor.',
              f"- Completion-audit spend is **${result['spend_from_completion_audit_only']['provider_reported_usd']:.9f} provider-reported** and "
              f"**${result['spend_from_completion_audit_only']['conservative_reservations_usd']:.9f} conservative reservations**. "
              'Reservations are not confirmed provider charges; these numbers are carried from the source audit, not independently reconciled here.',
              '- Checks are entirely offline: inventory, canonical input hashes, saved grader/report consistency, '
              'frozen rubric caps and report arithmetic. Predictions and historical execution were not rerun. '
              'No provider requests, new dependencies, queue changes, automations, commits or pushes.', '',
              '## Reproduce this saved-data report', '',
              'Run `.venv-research/bin/python -m eval_suite.report_score_components` from the repository root. '
              'This only reads existing evidence and writes these two owned reports. '
              'The script asserts 14×21 coverage, audit status counts, unique source matches, grader consistency and judge input hashes before writing.', '']
    return '\n'.join(lines)


def main():
    result = build()
    text = markdown(result)
    write(RUN / 'score-components.json', result)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text)
    print(json.dumps({'cases': result['total_cases'], 'judge_status': result['judge_status'],
                      'checks': result['checks'], 'discrepancies': result['discrepancies'],
                      'reports': [str(REPORT), str(RUN / 'score-components.json')]}, indent=2))


if __name__ == '__main__':
    main()
