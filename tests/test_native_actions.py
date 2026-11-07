"""Native actions execute once; malformed replies recover within fixed paid budgets."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research_env.core.common import canonical,read,write
from research_env.run_model import ACTION_TOOL,ActionProtocolError,ModelProvider,run
from research_env.sweep import load_plan,validate_catalog,execute
from test_transcript import config,make_suite


def native_config():
    c=config();c.update(action_transport='tools',max_consecutive_protocol_errors=3)
    c['decoding'].update(tools=[ACTION_TOOL],tool_choice='auto')
    return c


def reply(action=None,*,calls=None):
    if calls is None:
        calls=[{'id':'call1','type':'function','function':{'name':'take_action','arguments':json.dumps(action)}}]
    return io.BytesIO(canonical({'usage':{'total_tokens':20},'choices':[{'message':{'content':None,'tool_calls':calls}}]}))


class NativeActions(unittest.TestCase):
    def test_early_evaluation_gate_leaves_calls_for_repairs_and_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=native_config();c.update(max_calls=32,evaluation_after_calls=12)
            provider=ModelProvider(c,'SECRET',tmp)
            provider.usage['calls']=12
            observation={'history':[{'kind':'initial_evidence','event_id':'e00000'}]}
            decision={'hypothesis':'Test fitted predictor','expected_result':'Valid outputs',
                      'code_diff':'Baseline fit','evidence_ids':['e00000']}
            def evaluate(request,**kwargs):
                body=json.loads(request.data)
                schema=body['tools'][0]['function']['parameters']
                self.assertEqual(schema['properties']['operation']['enum'],['evaluate'])
                self.assertIn('decision',schema['required'])
                return reply({'operation':'evaluate','decision':decision})
            with patch('urllib.request.urlopen',side_effect=evaluate):
                self.assertEqual(provider(observation,0)['operation'],'evaluate')
            observation['history'].append({'kind':'development_result','result':{'execution_valid':False}})
            def repair(request,**kwargs):
                self.assertEqual(json.loads(request.data)['tools'],[ACTION_TOOL])
                return reply({'operation':'edit','path':'artifact/inference.py','text':'repair'})
            with patch('urllib.request.urlopen',side_effect=repair):
                self.assertEqual(provider(observation,0)['operation'],'edit')

    def test_tool_conversation_preserves_code_reasoning_and_actual_results_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=native_config();c.update(conversation_mode='tools',max_total_tokens=1000000)
            provider=ModelProvider(c,'SECRET',tmp)
            initial={'history':[{'event_id':'e00000','kind':'initial_evidence','content':'Public task'}]}
            action={'operation':'edit','path':'train.py','text':'print("remember this code")'}
            block={'type':'reasoning.text','text':'fixture reasoning','signature':'opaque'}
            raw={'usage':{'total_tokens':20},'choices':[{'message':{'content':None,
                'reasoning_details':[block], 'tool_calls':[{'id':'call1','type':'function',
                'function':{'name':'take_action','arguments':json.dumps(action)}}]}}]}
            with patch('urllib.request.urlopen',return_value=io.BytesIO(canonical(raw))):
                self.assertEqual(provider(initial,0),action)
            resumed=ModelProvider(c,'SECRET',tmp)
            result={'event_id':'e00001','kind':'edit','content_sha256':'public hash'}
            observation={'history':[*initial['history'],result]}
            def next_turn(request,**kwargs):
                messages=json.loads(request.data)['messages']
                self.assertEqual([m['role'] for m in messages],['system','user','assistant','tool'])
                self.assertEqual(messages[2]['reasoning_details'],[block])
                self.assertEqual(json.loads(messages[2]['tool_calls'][0]['function']['arguments']),action)
                self.assertEqual(messages[3]['tool_call_id'],'call1')
                self.assertEqual(json.loads(messages[3]['content'])['new_events'],[result])
                self.assertNotIn('history',json.loads(messages[3]['content']))
                return reply({'operation':'command','argv':['python','train.py']})
            with patch('urllib.request.urlopen',side_effect=next_turn):
                resumed(observation,0)
            state=read(Path(tmp)/'participant-history.json')
            self.assertNotIn('SECRET',canonical(state).decode())
            changed={'history':[{'event_id':'changed'}]}
            with patch('urllib.request.urlopen') as network:
                with self.assertRaisesRegex(ValueError,'public ledger changed'):resumed(changed,0)
                network.assert_not_called()

    def test_submission_phase_requires_model_choice_and_blocks_more_research(self):
        observation={'history':[{'kind':'development_result','result':{
            'execution_valid':True,'candidate_id':'good','primary_loss':2}},
            {'kind':'development_result','result':{'execution_valid':False,'candidate_id':'bad'}}]}
        with tempfile.TemporaryDirectory() as tmp:
            c=native_config();c['max_calls']=4
            provider=ModelProvider(c,'SECRET',tmp)
            def respond(request,**kwargs):
                body=json.loads(request.data)
                schema=body['tools'][0]['function']['parameters']
                self.assertEqual(schema['properties']['operation']['enum'],['submit'])
                self.assertEqual(schema['properties']['candidate_id']['enum'],['good'])
                self.assertIn('SUBMISSION PHASE',body['messages'][0]['content'])
                return reply({'operation':'edit','path':'x.py','text':'more research'})
            with patch('urllib.request.urlopen',side_effect=respond):
                with self.assertRaisesRegex(ActionProtocolError,'Research is closed'):
                    provider(observation,0)
            with patch('urllib.request.urlopen',return_value=reply({'operation':'submit','candidate_id':'bad'})):
                with self.assertRaisesRegex(ActionProtocolError,'Research is closed'):
                    provider(observation,0)
            choice={'operation':'submit','candidate_id':'good','reason':'Lowest public loss','evidence_ids':['e00001']}
            with patch('urllib.request.urlopen',return_value=reply(choice)):
                self.assertEqual(provider(observation,0),choice)
            self.assertEqual(provider.usage['calls'],3)
            self.assertEqual(ACTION_TOOL['function']['parameters']['properties']['operation']['enum'],
                             ['edit','command','evaluate','select','submit'])

    def test_cap_cannot_exceed_recorded_user_authorization(self):
        with tempfile.TemporaryDirectory() as tmp,patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError,'authorization'):
                execute('leaderboard/sweeps/openrouter-frontier-10-tools/manifest.json',tmp,'SECRET',11)
            network.assert_not_called()

    def test_native_preflight_requires_tool_edit_and_executes_nothing(self):
        manifest='leaderboard/sweeps/openrouter-frontier-10-tools/manifest.json'
        repo,_,configs,_=load_plan(manifest)
        catalog={'data':[m['catalog'] for m in read(repo/'leaderboard/sweeps/openrouter-frontier-10-tools/catalog-snapshot.json')['models']]}
        class Probe:
            count=0
            def __init__(self,config,*args):
                if config.get('action_transport')!='tools':raise AssertionError('Native config required')
            def __call__(self,observation,seed):
                if 'take_action' not in observation['task']:raise AssertionError('Native probe instruction required')
                Probe.count+=1
                return {'operation':'edit','path':'probe.txt','text':'ok'}
        with tempfile.TemporaryDirectory() as tmp,patch('research_env.sweep.check_suite'),patch('research_env.sweep.check_access',return_value={}),patch('research_env.sweep.ModelProvider',Probe),patch('urllib.request.urlopen',return_value=io.BytesIO(canonical(catalog))):
            status=execute(manifest,tmp,'SECRET',10,probes_only=True)
            self.assertEqual(status['status'],'preflight_passed')
            self.assertEqual(Probe.count,10)
            self.assertFalse(list(Path(tmp).rglob('probe.txt')))

    def test_exact_native_request_and_response_are_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=ModelProvider(native_config(),'SECRET',tmp)
            action={'operation':'edit','path':'x.py','text':'print("ok")'}
            def call(request,**kwargs):
                body=json.loads(request.data)
                self.assertEqual(body['tool_choice'],'auto')
                self.assertEqual(body['tools'],[ACTION_TOOL])
                self.assertIn('Call take_action exactly once',body['messages'][0]['content'])
                return reply(action)
            with patch('urllib.request.urlopen',side_effect=call):self.assertEqual(provider({},0),action)
            record=read(Path(tmp)/'provider-call-0001.json')
            self.assertEqual(json.loads(record['tool_calls'][0]['function']['arguments']),action)
            self.assertNotIn('SECRET',json.dumps(record))

    def test_multiple_missing_or_wrong_tools_never_become_actions(self):
        valid={'id':'c','type':'function','function':{'name':'take_action','arguments':'{"operation":"submit"}'}}
        wrong={'id':'c','type':'function','function':{'name':'other','arguments':'{}'}}
        for calls in ([],[valid,valid],[wrong],[{'type':'function','function':None}]):
            with self.subTest(calls=calls),tempfile.TemporaryDirectory() as tmp:
                provider=ModelProvider(native_config(),'SECRET',tmp)
                with patch('urllib.request.urlopen',return_value=reply(calls=calls)):
                    with self.assertRaises(ActionProtocolError):provider({},0)
                self.assertEqual(read(Path(tmp)/'provider-usage.json')['calls'],1)

    def test_malformed_arguments_are_retained_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=ModelProvider(native_config(),'SECRET',tmp)
            calls=[{'type':'function','function':{'name':'take_action','arguments':'{bad'}}]
            with patch('urllib.request.urlopen',return_value=reply(calls=calls)):
                with self.assertRaises(json.JSONDecodeError):provider({},0)
            r=read(Path(tmp)/'provider-call-0001.json')
            self.assertEqual(r['tool_calls'],calls)
            self.assertEqual(r['fault']['kind'],'invalid_response_json')

    def test_recovery_preserves_work_and_executes_only_valid_actions(self):
        with tempfile.TemporaryDirectory() as tmp,patch('research_env.leaderboard.resource_limits',return_value={'cpus':1,'memory_bytes':1024**3}):
            root=Path(tmp);make_suite(root);write(root/'config.json',native_config());requests=[]
            def provider(request,**kwargs):
                observation=json.loads(json.loads(request.data)['messages'][1]['content']);requests.append(observation)
                ids=[e['event_id'] for e in observation['history']]
                if len(requests)==1:return reply(calls=[])
                if len(requests)==2:return reply({'operation':'edit','path':'artifact/inference.py','text':'def predict(a,r):return {}\n'})
                decision={'hypothesis':'Test recovery','expected_result':'Valid artifact','code_diff':'Fixture','evidence_ids':ids}
                if len(requests)==3:return reply({'operation':'evaluate','decision':decision})
                if len(requests)==4:return reply(calls=[])
                candidate=[e['candidate_id'] for e in observation['history'] if e['kind']=='candidate'][-1]
                return reply({'operation':'submit','candidate_id':candidate,'reason':'Observed valid development result','evidence_ids':ids})
            score={'execution_valid':True,'primary_loss':1,'uncertainty':{'interval_score_90':2}}
            with patch('urllib.request.urlopen',side_effect=provider),patch('research_env.core.agent.evaluate',return_value=(score,{})),patch('research_env.core.evaluation.evaluate',return_value=(score,{})):
                receipt=run(root/'suite.json','load',root/'config.json',0,root/'run','SECRET')
            self.assertTrue(receipt['score']['execution_valid'])
            self.assertEqual(len(requests),5)
            self.assertTrue(any(e.get('layer')=='model_response' for e in requests[1]['history']))
            trace=[json.loads(x) for x in (root/'run/transcript.jsonl').read_text().splitlines()]
            self.assertEqual([e['data']['call_id'] for e in trace if e['kind']=='action_result'],[2,3,5])
            self.assertEqual(read(root/'run/provider-usage.json'),{'calls':5,'tokens':100})

    def test_protocol_error_limit_survives_interruption_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp,patch('research_env.leaderboard.resource_limits',return_value={'cpus':1,'memory_bytes':1024**3}):
            root=Path(tmp);make_suite(root);write(root/'config.json',native_config())
            with patch('urllib.request.urlopen',side_effect=[reply(calls=[]),reply(calls=[]),KeyboardInterrupt]):
                with self.assertRaises(KeyboardInterrupt):run(root/'suite.json','load',root/'config.json',0,root/'run','SECRET')
            self.assertFalse((root/'run/receipt.json').exists())
            with patch('urllib.request.urlopen',return_value=reply(calls=[])) as network:
                receipt=run(root/'suite.json','load',root/'config.json',0,root/'run','SECRET')
            self.assertFalse(receipt['score']['execution_valid'])
            self.assertEqual(network.call_count,1)
            self.assertEqual(read(root/'run/provider-usage.json')['calls'],4)
            self.assertEqual(read(root/'run/run-status.json')['fault']['kind'],'invalid_action_response')

    def test_all_ten_native_configs_keep_medium_and_supported_auto_tools(self):
        repo,manifest,configs,judge=load_plan('leaderboard/sweeps/openrouter-frontier-10-tools/manifest.json')
        catalog={m['catalog']['id']:m['catalog'] for m in read(repo/'leaderboard/sweeps/openrouter-frontier-10-tools/catalog-snapshot.json')['models']}
        for _,_,c in configs:
            validate_catalog(c,catalog)
            self.assertEqual(c['decoding']['reasoning']['effort'],'medium')
            self.assertEqual(c['decoding']['tool_choice'],'auto')
            self.assertNotIn('response_format',c['decoding'])
            self.assertEqual(c['max_consecutive_protocol_errors'],3)


if __name__=='__main__':unittest.main()
