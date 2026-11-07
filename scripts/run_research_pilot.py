"""One-model interactive diagnostic; never publishes a leaderboard entry."""
import argparse
import fcntl
from pathlib import Path

from research_env.core.common import digest, file_hash, read, write
from research_env.core.spend import SpendLedger
from research_env.judging.judge import OpenAICompatibleJudge, judge_packet, summarize
from research_env.leaderboard import check_suite, freeze, verify
from research_env.run_model import run
from research_env.sweep import credential


def review_selection(root, config, key, spend):
    receipt = verify(read(root/'receipt.json'))
    packets = read(root/'judge-packets.json')
    if digest(packets) != receipt['judge_packets_sha256']:
        raise ValueError('Sealed judge evidence changed')
    if file_hash(root/'trajectory.jsonl') != receipt['trajectory_sha256']:
        raise ValueError('Sealed trajectory changed')
    final = [p for p in packets if p['kind'] == 'final_selection']
    if len(final) != 1:
        raise ValueError('Pilot review requires one actual final submission')
    out = root/'selection-review'
    out.mkdir(exist_ok=True)
    if (out/'config.json').exists() and read(out/'config.json') != config:
        raise ValueError('Cannot change resumed reviewer settings')
    write(out/'config.json', config)
    provider = OpenAICompatibleJudge(api_key=key, spend=spend, **config)
    result = judge_packet(final[0], provider, out/'attempts.json')
    verdicts = [result['verdict']] if result['verdict'] is not None else []
    report = {**summarize(final, verdicts), 'scope':'final-selection packet with preceding public evidence',
              'all_decision_packets':len(packets), 'verdicts':verdicts}
    write(out/'report.json', report)
    return report


def execute(output, config_path, judge_path, key, *, cap=1, seed=0,
            data='.leaderboard-data', image=None, spend_path=None, tasks=('load','heat','pulse')):
    tasks=tuple(tasks)
    if not tasks or len(set(tasks)) != len(tasks) or any(t not in ('load','heat','pulse') for t in tasks):
        raise ValueError('Select distinct pilot tasks from load, heat and pulse')
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    with (root/'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config, judge = read(config_path), read(judge_path)
        for name, value in [('participant.json', config), ('judge.json', judge)]:
            if (root/name).exists() and read(root/name) != value:
                raise ValueError('Cannot change pilot settings on resume')
            write(root/name, value)
        suite = root/'suite.json'
        if not suite.exists():
            freeze(data, image, suite)
        check_suite(read(suite))
        spend_path = Path(spend_path or root/'spend.sqlite').resolve()
        identity = digest({'suite':read(suite)['sha256'], 'config':config, 'judge':judge, 'seed':seed,
                           'spend_path':str(spend_path), 'cap':cap, 'tasks':list(tasks)})
        status_path = root/'pilot-status.json'
        if status_path.exists() and read(status_path)['identity'] != identity:
            raise ValueError('Cannot change pilot identity on resume')
        spend = SpendLedger(spend_path, cap)
        status = {'identity':identity, 'scope':'interactive diagnostic; no leaderboard entry',
                  'requested_tasks':list(tasks), 'tasks':{}}
        try:
            for task in tasks:
                p = root/task
                status['active_task'] = task
                write(status_path, {**status, 'spend':spend.summary()})
                print('Running', task, flush=True)
                if not (p/'receipt.json').exists():
                    run(suite, task, root/'participant.json', seed, p, key, spend)
                receipt = verify(read(p/'receipt.json'))
                meta = verify(receipt['run'])
                if (meta['suite_sha256'] != read(suite)['sha256'] or
                        meta['configuration_sha256'] != digest(config) or meta['seed'] != seed or meta['task'] != task):
                    raise ValueError('Pilot receipt identity mismatch')
                valid = receipt['score']['execution_valid']
                review = review_selection(p, judge, key, spend) if valid else None
                status['tasks'][task] = {'valid':valid, 'review':review['llm_judge_status'] if review else 'no_submission'}
                print(task, status['tasks'][task], flush=True)
            status['status'] = 'complete' if all(v['valid'] and v['review'] == 'complete' for v in status['tasks'].values()) else 'needs_attention'
        except BaseException as exc:
            status.update(status='needs_attention', error=type(exc).__name__)
            raise
        finally:
            write(status_path, {**status, 'spend':spend.summary()})
            spend.close()
    return read(status_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--config', default='leaderboard/pilots/deepseek-interactive/participant.json')
    parser.add_argument('--judge', default='leaderboard/pilots/deepseek-interactive/judge.json')
    parser.add_argument('--image', default='sha256:7751f6262d2768889bebc8b567c771af0dae369db54ef79b208db155ebae9314')
    parser.add_argument('--cap', type=float, default=1)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--key-env', default='OPENROUTER_API_KEY')
    parser.add_argument('--env-file')
    parser.add_argument('--spend-path')
    parser.add_argument('--tasks', nargs='+', choices=('load','heat','pulse'), default=['load','heat','pulse'])
    args = parser.parse_args()
    print(execute(args.output, args.config, args.judge, credential(args.key_env, args.env_file),
                  cap=args.cap, seed=args.seed, image=args.image, spend_path=args.spend_path, tasks=args.tasks))
