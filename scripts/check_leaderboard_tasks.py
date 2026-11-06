"""Development-only Docker wiring checks; never enters official leaderboard."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_env.core.agent import ResearchEnvironment
from research_env.core.common import write
from research_env.staging import stage
from research_env.judging.judge import build_packets, summarize


def check(data_root,output_root,task,image):
    root, data=Path(output_root),Path(data_root)/task
    workspace=stage(data/'public',root/'workspace')
    env=ResearchEnvironment(root/'private',workspace,data/'private/development/manifest.json',image=image)
    kind={'pulse':'median','heat':'ridge','load':'ridge'}[task]
    decision={'hypothesis':'Verify isolated command-to-submission wiring with an unchanged reference model',
              'expected_result':'Finite predictions on every eligible development request',
              'evidence_ids':['e00000'],'code_diff':'Use the provided reference training implementation'}
    command=['python','-m','research_env','baseline','data/train/manifest.json','artifact','--task',task,'--kind',kind]
    trained=env.act({'operation':'command','argv':command,'decision':decision,'seed':0})
    if not trained['execution_valid']:
        write(root/'training-failure.json',trained)
        raise RuntimeError(trained)
    result=env.act({'operation':'evaluate','decision':decision})
    if not result['execution_valid']:
        write(root/'evaluation-failure.json',result)
        raise RuntimeError(result)
    evidence=[e['event_id'] for e in env.session.events() if e['kind']=='development_result']
    env.act({'operation':'select','candidate_id':result['candidate_id'],'reason':'Reference wiring check only','evidence_ids':evidence})
    env.act({'operation':'submit','candidate_id':result['candidate_id'],'reason':'Complete development-only wiring verification','evidence_ids':evidence})
    packets=build_packets(env.session.events())
    write(root/'judge-packets.json',packets)
    write(root/'judging.json',summarize(packets,[]))
    env.session.export(root/'trajectory.jsonl','agent_development')
    write(root/'check.json',{'task':task,'closed':env.session.get('closed'),'development_score':result,
                            'llm_judge_status':'pending','official_leaderboard_entry':False,'private_test_scored':False})
    with env.session.db:
        env.session.transcript.append('run_status',{'status':'completed','fault':None,
            'final_answer':'Complete development-only wiring verification',
            'source':'development_wiring_check','official_leaderboard_entry':False})
    from research_env.trace import export
    export(root)
    env.session.db.close()
    print(task,'PASS',result.get('n_windows',result.get('n_records')),'development requests',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('task',choices=('pulse','heat','load'));p.add_argument('data_root');p.add_argument('output_root');p.add_argument('--image',required=True)
    a=p.parse_args();check(a.data_root,a.output_root,a.task,a.image)
