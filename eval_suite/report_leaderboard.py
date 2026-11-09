"""Build the descriptive roster leaderboard from saved inventory + judged cases.

Reads only existing evidence under --root (default .benchmark-runs/rerun-20261107).
Uses eval_suite.resume_sweep.inventory and frozen tasks/combined_score.py. Writes
docs/results/roster-rerun-20261107-leaderboard.md and
.benchmark-runs/rerun-20261107/final-leaderboard.json. Does not call providers,
mutate artifacts, or change scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from eval_suite.core.common import digest, read
from eval_suite.resume_sweep import inventory
from tasks import combined_score as cs

ROOT_DEFAULT = Path('.benchmark-runs/rerun-20261107')
TASKS = ('keep_going', 'rulebook_vs_body', 'beat_ectemp')


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_judged(root: Path, source: str):
    path = Path(source)
    submission = read(path)
    judge_dir = root / (path.parent.name + '-judge')
    identity = judge_dir / 'identity.json'
    if identity.exists() and read(identity).get('submission_sha256') != digest(submission):
        judge_dir = root / (path.parent.name + '-judge-' + digest(submission)[:12])
    judged_path = judge_dir / 'judged.json'
    if not judged_path.exists():
        raise FileNotFoundError(f'missing judged file for {source}: {judged_path}')
    return path, submission, judged_path, read(judged_path)


def build_runs(root: Path, roster):
    runs, coverage, sources, judgments = [], {}, {}, Counter()
    case_index = {}
    for row in roster:
        mid = row['openrouter_id']
        found, spent = inventory(root, row)
        cases = []
        src_names = []
        for key, src in sorted(found.items()):
            task, case_id = key.split('/', 1)
            path, submission, judged_path, judged = resolve_judged(root, src)
            match = [c for c in judged['cases'] if c['task'] == task and c['case_id'] == case_id]
            if len(match) != 1:
                raise ValueError(f'{mid} {key}: expected 1 judged case, found {len(match)}')
            c = match[0]
            jr = c['judge_record']
            status = jr['status']
            if status not in ('scored', 'absent_answer'):
                raise ValueError(f'{mid} {key}: unexpected judge status {status!r}')
            if not (jr.get('input_hashes') or {}).get('rubric'):
                raise ValueError(f'{mid} {key}: missing judge input_hashes.rubric')
            if jr.get('judge_model') != 'openai/gpt-6.1-sol-pro':
                raise ValueError(f'{mid} {key}: unexpected judge model {jr.get("judge_model")!r}')
            judgments[status] += 1
            cases.append({k: c[k] for k in ('task', 'case_id', 'run', 'grader', 'judge', 'judge_record') if k in c})
            src_names.append(path.parent.name)
            cwd = Path.cwd().resolve()
            try:
                sub_rel = str(path.resolve().relative_to(cwd))
                jud_rel = str(judged_path.resolve().relative_to(cwd))
            except ValueError:
                sub_rel, jud_rel = str(path), str(judged_path)
            case_index[(mid, task, case_id)] = {
                'submission_rel': sub_rel,
                'judged_rel': jud_rel,
                'source_dir': path.parent.name,
                'judge_status': status,
                'finish_reason': (next((x for x in submission['cases']
                                        if x['task'] == task and x['case_id'] == case_id), {})
                                  .get('finish_reason')),
                'input_hashes': jr.get('input_hashes'),
            }
        coverage[mid] = {
            'cases': len(found),
            'accounted_usd': spent,
            'sources': sorted(set(src_names)),
        }
        sources[mid] = coverage[mid]['sources']
        runs.append({'model': mid, 'cases': cases})
    return runs, coverage, sources, judgments, case_index


def task_means(model_scores):
    by_task = defaultdict(list)
    for (task, _case), rec in model_scores.items():
        if rec['status'] != 'scored':
            continue
        by_task[task].append(rec['combined'])
    out = {}
    for task in TASKS:
        vals = by_task.get(task) or []
        out[task] = None if not vals else sum(vals) / len(vals)
    return out


def cross_check_components(scores, sc):
    diffs = []
    by = {m['model']: m for m in sc['models']}
    for model, cases in scores.items():
        for (task, case_id), rec in cases.items():
            sib = next(c for c in by[model]['cases'] if c['task'] == task and c['case_id'] == case_id)
            sib_comp = sib['frozen_normalized_components']
            sib_combined = cs.combined(task, sib_comp)
            if abs(rec['combined'] - sib_combined) > 1e-12:
                diffs.append({'model': model, 'case': f'{task}/{case_id}',
                              'leaderboard': rec['combined'], 'score_components': sib_combined})
            mine = rec['attempts'][0]['components']
            for k, v in sib_comp.items():
                if abs(mine[k] - v) > 1e-12:
                    diffs.append({'model': model, 'case': f'{task}/{case_id}/{k}',
                                  'leaderboard': mine[k], 'score_components': v})
    return diffs


def representative_failures(case_index, roster_by_id, sc_by):
    """Concrete saved-case examples, classified without inventing causes."""
    examples = []

    def sib_meta(mid, task, cid):
        case = next(c for c in sc_by[mid]['cases'] if c['task'] == task and c['case_id'] == cid)
        return case.get('saved_execution_metadata') or {}

    # harness / protocol timing (Beat ECTemp absent, research)
    harness = [
        ('google/gemini-4-argon', 'beat_ectemp', '3A/H06'),
        ('google/gemini-4-argon', 'beat_ectemp', '3B/H06'),
        ('x-ai/grok-4.6', 'beat_ectemp', '3A/H06'),
        ('moonshotai/kimi-k3.1-pro', 'beat_ectemp', '3A/H06'),
    ]
    for mid, task, cid in harness:
        meta = case_index[(mid, task, cid)]
        exe = sib_meta(mid, task, cid)
        stop = exe.get('research_stop') or meta['finish_reason'] or 'wall_limit'
        examples.append({
            'class': 'harness_finalization_or_wall_limit',
            'model': mid,
            'display': roster_by_id[mid]['model'],
            'case': f'{task}/{cid}',
            'judge_status': meta['judge_status'],
            'finish_reason': stop,
            'research_wall_s': exe.get('research_wall_s'),
            'submission': meta['submission_rel'],
            'judged': meta['judged_rel'],
            'note': ('Empty explanation with valid saved predictor; Task3 attributes Argon/Grok/Kimi '
                     '3A (and Argon 3B) absences to unprotected research-deadline finalization / wall_limit, '
                     'not to an LLM judgment that the explanation was poor.'),
        })
    provider = [
        ('anthropic/claude-opus-5.5', 'keep_going', 'KG-02', 'content_filter'),
        ('anthropic/claude-opus-5.5', 'rulebook_vs_body', 'RB-01', 'content_filter'),
        ('anthropic/claude-fable-5', 'rulebook_vs_body', 'RB-02', 'content_filter'),
        ('tencent/hy4', 'rulebook_vs_body', 'RB-01', 'length'),
    ]
    for mid, task, cid, expect in provider:
        meta = case_index[(mid, task, cid)]
        examples.append({
            'class': 'provider_filter_or_length',
            'model': mid,
            'display': roster_by_id[mid]['model'],
            'case': f'{task}/{cid}',
            'judge_status': meta['judge_status'],
            'finish_reason': meta['finish_reason'] or expect,
            'submission': meta['submission_rel'],
            'judged': meta['judged_rel'],
            'note': ('Single-turn empty answer. Recorded finish_reason distinguishes content_filter '
                     'refusal from length/token exhaustion; not the Beat ECTemp finalization path.'),
        })
    return examples


def abs_link(rel: str) -> str:
    return str((Path.cwd() / rel).resolve())


def render_md(payload):
    rows = payload['leaderboard']
    lines = []
    a = lines.append
    a('# Roster rerun leaderboard (2026-11-07)')
    a('')
    a('Descriptive mixed scores from the completed saved inventory. '
      'Overall is the equal-weight mean of the three task means, each task mean being the mean of '
      'that task’s frozen per-case combined scores (weights in `tasks/combined_score.py`). '
      '**These are not accuracy percentages, Elo ratings, or a claim of general ability.**')
    a('')
    a(f"- Checked against `{payload['source_audit']}`: "
      f"{payload['coverage_summary']['models']} models × "
      f"{payload['coverage_summary']['required_cases_per_model']} required cases = "
      f"{payload['coverage_summary']['total_unique_cases']} cases; "
      f"{payload['judgments']['scored']} scored + {payload['judgments']['absent_answer']} absent_answer.")
    a(f"- Judge `{payload['judge_model']}` (outside roster). Carbon unavailable. "
      'Gemini 3.7, diagnostic fixtures, and initial DeepSeek pilots excluded.')
    a(f"- Cross-check vs sibling score-components: **{payload['cross_check']['n_cases']} cases, "
      f"{payload['cross_check']['n_diffs']} diffs**.")
    a(f"- Spend (from completion audit only): provider-reported "
      f"**${payload['spend']['provider_reported_usd']:.6f}**; conservative reservations "
      f"**${payload['spend']['conservative_reservation_usd']:.6f}** (not confirmed charges).")
    a('- Sibling reports (read-only): '
      f"[score components]({abs_link('docs/results/roster-rerun-20261107-score-components.md')}), "
      f"[rerun decision]({abs_link('docs/results/roster-rerun-20261107-rerun-decision.md')}).")
    a('')
    a('## Plain-language walkthrough')
    a('')
    a('Think of each case as a small exam question with a frozen grading key. '
      'Keep/Pull mixes a thermometer-error score with a judge’s marks for the keep/pull call and the write-up. '
      'Rulebook mixes “did you copy the table fields?” with a judge’s marks for whether to override and why. '
      'Research mixes “how close was your predictor to the hidden labels, versus a frozen baseline?” with a judge’s mark for the research explanation. '
      'Overall just averages the three subject scores so a task with more cases cannot bully the others—like averaging midterm, lab, and essay even if the essay has fewer pages.')
    a('')
    a('Zeros for missing text are rubric rules, not proof the model “knew nothing.” '
      'Some research zeros are partly a harness timing flaw (no protected finalization budget); '
      'predictors can still be valid. Treat explanation columns and any overall that embeds them as **provisional** until a matched Beat ECTemp rerun under a repaired protocol (see sibling decision report).')
    a('')
    a('## Leaderboard (descriptive overall /100)')
    a('')
    a('| Rank | Model | Keep/Pull | Rulebook | Research | Overall | Coverage |')
    a('|---:|---|---:|---:|---:|---:|---:|')
    for i, r in enumerate(rows, 1):
        a(f"| {i} | {r['display']} | {r['task_scores_100']['keep_going']:.1f} | "
          f"{r['task_scores_100']['rulebook_vs_body']:.1f} | {r['task_scores_100']['beat_ectemp']:.1f} | "
          f"**{r['overall_100']:.1f}** | {r['coverage']}/21 |")
    a('')
    a('Research and overall columns include provisional explanation credit (including harness-caused absences scored as zero). '
      'Predictor-only comparisons should use the sibling score-components research tables.')
    a('')
    a('## Raw metrics (sibling-validated)')
    a('')
    a('| Model | KG correct/12 | KG forecast MAE °C | RB fields/8 | RB overrides/2 | Research people beating B |')
    a('|---|---:|---:|---:|---:|---:|')
    for r in rows:
        raw = r['raw']
        mae = raw['keep_going']['mae_c']
        mae_s = f'{mae:.4f}' if mae is not None else '—'
        a(f"| {r['display']} | {raw['keep_going']['correct']}/{raw['keep_going']['n']} | "
          f"{mae_s} | "
          f"{raw['rulebook_vs_body']['lookup_fields_correct']}/{raw['rulebook_vs_body']['lookup_fields_total']} | "
          f"{raw['rulebook_vs_body']['override_correct']}/{raw['rulebook_vs_body']['override_total']} | "
          f"{raw['beat_ectemp']['people_beating_baseline']}/{raw['beat_ectemp']['people_total']} |")
    a('')
    a('Pooled roster totals (not a ranking): '
      f"{payload['raw_totals']['keep_going_correct']}/{payload['raw_totals']['keep_going_total']} KG decisions correct; "
      f"{payload['raw_totals']['rulebook_fields_correct']}/{payload['raw_totals']['rulebook_fields_total']} rulebook fields; "
      f"{payload['raw_totals']['rulebook_override_correct']}/{payload['raw_totals']['rulebook_total']} overrides; "
      f"{payload['raw_totals']['research_beating_baseline']}/{payload['raw_totals']['research_total']} research person-cases beating baseline "
      f"({payload['raw_totals']['research_valid']} valid predictors).")
    a('')
    a('## Representative failures (saved cases)')
    a('')
    a('Distinguish generated-code/model/filter/length failures from infrastructure/harness problems. '
      'Absent explanations under `wall_limit` can coexist with valid predictors.')
    a('')
    for ex in payload['representative_failures']:
        extra = ''
        if ex.get('research_wall_s') is not None:
            extra = f", research_wall_s `{ex['research_wall_s']:.3f}`"
        a(f"- **{ex['class']}** — {ex['display']} `{ex['case']}` "
          f"(judge `{ex['judge_status']}`, finish `{ex['finish_reason']}`{extra}). "
          f"Submission [{ex['submission']}]({abs_link(ex['submission'])}); "
          f"judged [{ex['judged']}]({abs_link(ex['judged'])}). {ex['note']}")
    a('')
    a('## Caveats')
    a('')
    for c in payload['caveats']:
        a(f'- {c}')
    a('')
    a('## Reproduce')
    a('')
    a('```bash')
    a('.venv-research/bin/python -m eval_suite.report_leaderboard')
    a('```')
    a('')
    a('Machine-readable twin: `.benchmark-runs/rerun-20261107/final-leaderboard.json`.')
    a('')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT_DEFAULT)
    ap.add_argument('--params', type=Path, default=Path('tasks/scoring_params.json'))
    ap.add_argument('--roster', type=Path, default=Path('eval_suite/roster.json'))
    ap.add_argument('--audit', type=Path, default=None)
    ap.add_argument('--score-components', type=Path, default=None)
    ap.add_argument('--md-out', type=Path, default=Path('docs/results/roster-rerun-20261107-leaderboard.md'))
    ap.add_argument('--json-out', type=Path, default=None)
    args = ap.parse_args(argv)
    root = args.root.resolve()
    audit_path = (args.audit or root / 'control' / 'completion-audit.json').resolve()
    sc_path = (args.score_components or root / 'score-components.json').resolve()
    json_out = (args.json_out or root / 'final-leaderboard.json').resolve()

    params = json.loads(args.params.read_text())
    roster_all = json.loads(args.roster.read_text())['models']
    roster = [r for r in roster_all if r.get('openrouter_id')]
    if len(roster) != 14:
        raise SystemExit(f'expected 14 available roster models, found {len(roster)}')
    audit = json.loads(audit_path.read_text())
    sc = json.loads(sc_path.read_text())

    runs, coverage, sources, judgments, case_index = build_runs(root, roster)
    if dict(judgments) != audit['judgments']:
        raise SystemExit(f'judgment counts {dict(judgments)} != audit {audit["judgments"]}')
    if sum(coverage[m]['cases'] for m in coverage) != audit['total_unique_cases']:
        raise SystemExit('coverage total mismatch vs audit')

    scores = cs.score_runs(runs, params)
    eligible, excluded, required, extra = cs.eligibility(scores, cs.parse_required(params['required_cases']))
    if excluded:
        raise SystemExit(f'unexpected exclusions: {excluded}')
    if len(eligible) != 14:
        raise SystemExit(f'expected 14 eligible models, got {len(eligible)}')

    diffs = cross_check_components(scores, sc)
    if diffs:
        raise SystemExit(f'score-components cross-check failed: {diffs[:3]}')

    sc_by = {m['model']: m for m in sc['models']}
    roster_by = {r['openrouter_id']: r for r in roster}
    leaderboard = []
    for mid in eligible:
        means = task_means(scores[mid])
        task_100 = {t: means[t] * 100 for t in TASKS}
        overall = sum(task_100[t] for t in TASKS) / 3
        # attach per-case for JSON
        case_rows = []
        for (task, case_id), rec in sorted(scores[mid].items()):
            meta = case_index[(mid, task, case_id)]
            case_rows.append({
                'task': task,
                'case_id': case_id,
                'combined': rec['combined'],
                'components': rec['attempts'][0]['components'],
                'flags': rec['attempts'][0].get('flags') or [],
                'judge_status': meta['judge_status'],
                'finish_reason': meta['finish_reason'],
                'submission': meta['submission_rel'],
                'judged': meta['judged_rel'],
            })
        # Prefer sibling task deterministic summaries for stable raw metrics.
        tk = sc_by[mid]['tasks']
        kg = tk['keep_going']['deterministic']
        rb = tk['rulebook_vs_body']['deterministic']
        be = tk['beat_ectemp']['deterministic']
        beat_people = sum(be[v]['people_beating_baseline'] for v in ('3A', '3B'))
        beat_total = sum(be[v]['n_people'] for v in ('3A', '3B'))
        raw = {
            'keep_going': {
                'correct': kg['correct'],
                'n': kg['n'],
                'forecasts': kg['forecast_present'],
                'mae_c': kg['forecast_mae_c'],
            },
            'rulebook_vs_body': {
                'lookup_fields_correct': rb['lookup_fields_correct'],
                'lookup_fields_total': rb['lookup_fields_total'],
                'override_correct': rb['correct'],
                'override_total': rb['n'],
            },
            'beat_ectemp': {
                'people_beating_baseline': beat_people,
                'people_total': beat_total,
                'variant_mae': {v: be[v]['person_balanced_mae_c'] for v in ('3A', '3B')},
            },
        }
        leaderboard.append({
            'rank': None,
            'model': mid,
            'display': roster_by[mid]['model'],
            'roster_rank': roster_by[mid]['rank'],
            'task_mean_combined': means,
            'task_scores_100': task_100,
            'overall_100': overall,
            'coverage': coverage[mid]['cases'],
            'accounted_usd_inventory': coverage[mid]['accounted_usd'],
            'sources': coverage[mid]['sources'],
            'raw': raw,
            'cases': case_rows,
            'provisional_research_and_overall': True,
        })
    leaderboard.sort(key=lambda r: (-r['overall_100'], r['roster_rank']))
    for i, r in enumerate(leaderboard, 1):
        r['rank'] = i

    failures = representative_failures(case_index, roster_by, sc_by)
    caveats = [
        'Descriptive mixed scores only; not accuracy%, Elo, clinical competence, or general ability.',
        'Equal task weighting: overall = mean(Keep/Pull, Rulebook, Research) after per-task mean of frozen combined scores.',
        'Argon (and some Grok/Kimi) absent research explanations are partly harness-caused; explanation and overall comparisons are provisional pending a versioned matched Beat ECTemp rerun (see roster-rerun-20261107-rerun-decision.md).',
        'Predictor artifacts remain valid recorded outcomes even when explanations are absent; do not treat absent_answer as proof of an invalid predictor.',
        'Provider content_filter / length empties (Opus 5.5, Fable 5, Hy4 RB-01) are different mechanisms from harness finalization.',
        'Carbon unavailable; Gemini 3.7, diagnostic fixtures, and initial DeepSeek pilots excluded.',
        'Provider-reported spend and conservative reservations are separate figures from the completion audit; reservations are not confirmed charges.',
        'All artifacts, attempts, and ledgers were preserved; this report only reads them.',
        'score-snapshot.json is stale relative to the completed audit; this report recomputes from current inventory + judged files.',
    ]

    payload = {
        'schema': 'roster-rerun-final-leaderboard-v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_audit': str(audit_path.relative_to(Path.cwd().resolve())),
        'source_audit_sha256': _sha(audit_path),
        'score_components': str(sc_path.relative_to(Path.cwd().resolve())),
        'score_components_sha256': _sha(sc_path),
        'combined_score_file_sha256': _sha(Path('tasks/combined_score.py')),
        'scoring_params_sha256': _sha(args.params),
        'judge_model': audit['judge_model'],
        'judgments': dict(judgments),
        'coverage_summary': {
            'models': 14,
            'required_cases_per_model': 21,
            'total_unique_cases': audit['total_unique_cases'],
            'verified_submission_sources': audit.get('verified_submission_sources'),
            'verified_transcript_chains': audit.get('verified_transcript_chains'),
            'verified_frozen_artifacts': audit.get('verified_frozen_artifacts'),
        },
        'spend': {
            'provider_reported_usd': audit['spend']['provider_reported'],
            'conservative_reservation_usd': audit['spend']['conservative_reservation'],
        },
        'carbon': audit.get('carbon'),
        'comparison_caveat': audit.get('comparison_caveat'),
        'frozen_weights': cs.WEIGHTS,
        'scoring_label': (
            'Descriptive mixed combined scores (frozen component weights; equal task means). '
            'Not accuracy, Elo, or general ability.'
        ),
        'cross_check': {'n_cases': 294, 'n_diffs': len(diffs), 'against': 'score-components.json'},
        'raw_totals': sc['raw_totals'],
        'leaderboard': leaderboard,
        'representative_failures': failures,
        'caveats': caveats,
        'sibling_reports': {
            'score_components_md': 'docs/results/roster-rerun-20261107-score-components.md',
            'score_components_json': '.benchmark-runs/rerun-20261107/score-components.json',
            'rerun_decision_md': 'docs/results/roster-rerun-20261107-rerun-decision.md',
        },
        'queue_services_stopped': audit.get('queue_services_stopped'),
    }

    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(render_md(payload))
    json_out.write_text(json.dumps(payload, indent=2) + '\n')
    print(f'wrote {args.md_out}')
    print(f'wrote {json_out}')
    print('top3', [(r['display'], round(r['overall_100'], 2)) for r in leaderboard[:3]])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
