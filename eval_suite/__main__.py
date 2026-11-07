"""List intended tasks; block inference until their implementations are ready."""
import argparse
import json
from eval_suite.registry import ACTIVE_TASK_IDS, TaskNotReadyError, preflight, run_task, tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    sub.add_parser('preflight')
    run = sub.add_parser('run')
    run.add_argument('task', choices=ACTIVE_TASK_IDS)
    args = parser.parse_args()
    if args.command == 'list':
        print(json.dumps({'tasks':tasks()}, indent=2))
    elif args.command == 'preflight':
        print(json.dumps(preflight(), indent=2))
        return 2
    else:
        try:
            run_task(args.task)
        except TaskNotReadyError as exc:
            parser.exit(2, str(exc)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
