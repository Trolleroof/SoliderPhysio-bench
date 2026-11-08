"""Run the frozen physiology suite on one roster model with an explicit budget."""
import argparse
import json
from eval_suite.registry import ACTIVE_TASK_IDS, preflight, tasks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    check = sub.add_parser('preflight')
    run = sub.add_parser('run')
    run.add_argument('task', nargs='?', choices=ACTIVE_TASK_IDS)
    run.add_argument('--model', required=True, help='roster rank, apex id, or OpenRouter id')
    run.add_argument('--tasks', default='all', help='all or comma-separated task names')
    run.add_argument('--cases', help='comma-separated frozen case ids, e.g. KG-01,RB-01,3A/H06')
    run.add_argument('--spend-cap-usd', required=True, type=float)
    run.add_argument('--out', required=True)
    run.add_argument('--research-seconds', type=float, default=1200)
    run.add_argument('--max-steps', type=int, default=64)
    run.add_argument('--max-tokens', type=int, default=32768)
    for p in (run, check):
        p.add_argument('--backend', choices=['docker', 'local', 'macos-development'], default='docker')
        p.add_argument('--image', help='digest-pinned, already installed Docker image')
    args = parser.parse_args(argv)
    if args.command == 'list':
        print(json.dumps({'tasks': tasks()}, indent=2))
    elif args.command == 'preflight':
        report = preflight(backend=args.backend, image=args.image)
        print(json.dumps(report, indent=2))
        return 0 if report['status'] == 'ready' else 2
    else:
        from eval_suite.runner import run as run_model
        try:
            result = run_model(args.model, args.out, args.spend_cap_usd, task_ids=args.task or args.tasks,
                               cases=args.cases, backend=args.backend, image=args.image,
                               research_seconds=args.research_seconds, max_steps=args.max_steps,
                               max_tokens=args.max_tokens)
        except Exception as exc:
            parser.exit(2, f'{type(exc).__name__}: {exc}\n')
        print(json.dumps({'status': result['status'], 'cases': len(result['cases']),
                          'official': result['official'], 'spend': result['spend'],
                          'submissions': args.out+'/submissions.json'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
