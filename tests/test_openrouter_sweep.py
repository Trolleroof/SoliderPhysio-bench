"""OpenRouter compatibility, explicit credential loading and shared spend safety."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research_env.core.common import canonical, read, write, digest
from research_env.core.spend import SpendLedger, SpendLimitReached
from research_env.run_model import ModelProvider
from research_env.sweep import credential, load_plan, validate_catalog, execute, check_resume_window
from research_env.leaderboard import seal
from research_env.judging.judge import OpenAICompatibleJudge, judge_packet, packet


class Sweep(unittest.TestCase):
    def test_expired_infrastructure_pause_is_not_silently_scored(self):
        from research_env.core.session import Session
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            session=Session(root/'private',wall_s=1,clock=lambda:0)
            session.db.close()
            write(root/'run-status.json',{'status':'paused','resumable':True})
            with self.assertRaises(RuntimeError):check_resume_window(root)
            self.assertFalse((root/'receipt.json').exists())

    def test_exact_screenshot_roster_and_supported_controls(self):
        repo,manifest,configs,judge=load_plan('leaderboard/sweeps/openrouter-frontier-10/manifest.json')
        self.assertEqual(len(configs),10)
        self.assertEqual(manifest['participant_runs'],90)
        catalog={m['catalog']['id']:m['catalog'] for m in read(repo/'leaderboard/sweeps/openrouter-frontier-10/catalog-snapshot.json')['models']}
        for entry,path,config in configs:
            validate_catalog(config,catalog)
            self.assertEqual(config['decoding']['reasoning']['effort'],entry['effort'])
            self.assertNotIn('temperature',config['decoding'])
            self.assertEqual(config['seed_mode'],'omit' if config['model'].startswith('anthropic/') else 'send')
        self.assertNotIn(read(judge)['model'],[c['model'] for _,_,c in configs])

    def test_explicit_env_file_is_data_not_executable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{},clear=True):
            path=Path(tmp)/'.env'
            path.write_text('UNRELATED=secret\nexport OPENROUTER_API_KEY="value-123" # comment\n')
            self.assertEqual(credential('OPENROUTER_API_KEY',path),'value-123')
            path.write_text('OPENROUTER_API_KEY="$(touch /tmp/should-never-execute)"\n')
            self.assertEqual(credential('OPENROUTER_API_KEY',path),'$(touch /tmp/should-never-execute)')
            with self.assertRaises(ValueError):credential('MISSING_KEY',path)

    def test_shared_spend_reservation_settlement_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'spend.sqlite';ledger=SpendLedger(path,1)
            body={'model':'model','max_tokens':100,'messages':[]}
            prices={'prompt':'0','completion':'0.001'}
            charge=ledger.reserve(body,prices)
            self.assertAlmostEqual(ledger.summary()['accounted_usd'],.1)
            ledger.settle(charge,{'cost':.02})
            ledger.close()
            ledger=SpendLedger(path,1)
            self.assertAlmostEqual(ledger.summary()['accounted_usd'],.02)
            self.assertEqual(ledger.summary()['requests_with_reserved_cost'],0)
            with self.assertRaises(SpendLimitReached):ledger.reserve({**body,'max_tokens':1000},prices)
            ledger.close()
            with self.assertRaises(ValueError):SpendLedger(path,2)

    def test_failed_call_keeps_reservation_and_cap_blocks_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            spend=SpendLedger(root/'spend.sqlite',.15)
            config={'endpoint':'https://example.invalid','model':'mock','prompt':'task',
                    'max_calls':3,'max_total_tokens':100000,'decoding':{'max_tokens':100},
                    'pricing_ceiling':{'prompt':'0','completion':'0.001'}}
            provider=ModelProvider(config,'SECRET',root,spend)
            with patch('urllib.request.urlopen',side_effect=OSError('offline')) as network:
                with self.assertRaises(OSError):provider({},0)
                with self.assertRaises(SpendLimitReached):provider({},1)
                self.assertEqual(network.call_count,1)
            self.assertAlmostEqual(spend.summary()['accounted_usd'],.1)
            self.assertEqual(provider.usage['calls'],1)
            spend.close()

    def test_anthropic_seed_is_omitted_and_actual_cost_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spend=SpendLedger(root/'spend.sqlite',1)
            cfg={'endpoint':'https://example.invalid','model':'anthropic/mock','prompt':'task','seed_mode':'omit',
                 'max_calls':2,'max_total_tokens':100000,'request_timeout_s':600,
                 'decoding':{'max_tokens':100,'reasoning':{'effort':'max'},'verbosity':'max'},
                 'pricing_ceiling':{'prompt':'0','completion':'0.001'}}
            payload={'provider':'Anthropic','usage':{'total_tokens':20,'cost':.01},'choices':[{'message':{'content':'{"ok":true}'}}]}
            def call(req,timeout):
                self.assertNotIn('seed',json.loads(req.data));self.assertNotIn('temperature',json.loads(req.data))
                self.assertEqual(timeout,200)
                return io.BytesIO(canonical(payload))
            with patch('urllib.request.urlopen',side_effect=call):ModelProvider(cfg,'SECRET',root,spend)({'remaining_wall_s':200},2)
            self.assertAlmostEqual(spend.summary()['accounted_usd'],.01)
            self.assertEqual(read(root/'provider-call-0001.json')['response_provider'],'Anthropic')
            spend.close()

    def test_judge_native_controls_and_cost_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            spend=SpendLedger(Path(tmp)/'spend.sqlite',1)
            provider=OpenAICompatibleJudge(endpoint='https://example.invalid',api_key='SECRET',model='judge',temperature=None,
                max_tokens=100,max_calls=1,max_total_tokens=100000,request_options={'reasoning':{'effort':'high'}},
                pricing_ceiling={'prompt':'0','completion':'0.001'},spend=spend)
            def call(req,**kwargs):
                body=json.loads(req.data);self.assertNotIn('temperature',body)
                self.assertEqual(body['reasoning']['effort'],'high')
                return io.BytesIO(canonical({'usage':{'total_tokens':10,'cost':.01},'choices':[{'message':{'content':'{}'}}]}))
            with patch('urllib.request.urlopen',side_effect=call):provider({'evidence':[]})
            self.assertAlmostEqual(spend.summary()['accounted_usd'],.01)
            spend.close()

    def test_judge_resume_does_not_repeat_exhausted_repairs(self):
        class Bad:
            config={'model':'mock'}
            calls=0
            def __call__(self,p):self.calls+=1;return {},{}
        with tempfile.TemporaryDirectory() as tmp:
            p=packet('e00001','decision',{},[{'id':'e0','available_before':'e00000','content':'evidence'}])
            provider=Bad();path=Path(tmp)/'attempts.json'
            self.assertIsNone(judge_packet(p,provider,path)['verdict'])
            self.assertEqual(provider.calls,3)
            self.assertIsNone(judge_packet(p,provider,path)['verdict'])
            self.assertEqual(provider.calls,3)

    def test_sweep_orchestrates_all_ninety_without_network_or_real_scores(self):
        manifest='leaderboard/sweeps/openrouter-frontier-10/manifest.json'
        repo,plan,configs,judge=load_plan(manifest)
        catalog={'data':[x['catalog'] for x in read(repo/'leaderboard/sweeps/openrouter-frontier-10/catalog-snapshot.json')['models']]}
        suite=read(repo/plan['suite'])
        class Probe:
            def __init__(self,*args):pass
            def __call__(self,*args):return {'operation':'probe','ok':True}
        def fake_run(suite_path,task,config_path,seed,root,key,spend):
            config=read(config_path)
            meta=seal({'suite_sha256':suite['sha256'],'task':task,'seed':seed,'competitor':config['competitor'],
                       'configuration':config,'configuration_sha256':digest(config)})
            write(root/'run.json',meta)
            write(root/'judge-packets.json',[])
            write(root/'receipt.json',seal({'run':meta,'score':{'execution_valid':True,'primary_loss':1,
                                        'uncertainty':{'interval_score_90':2}}}))
        with tempfile.TemporaryDirectory() as tmp, \
             patch('research_env.sweep.check_suite'), \
             patch('research_env.sweep.check_access',return_value={'limit_remaining':100}), \
             patch('research_env.sweep.ModelProvider',Probe), \
             patch('research_env.sweep.run',side_effect=fake_run) as runner, \
             patch('urllib.request.urlopen',return_value=io.BytesIO(canonical(catalog))) as network:
            result=execute(manifest,tmp,'SECRET',10)
            self.assertEqual(runner.call_count,90)
            self.assertEqual(network.call_count,1)  # Catalog only; all provider calls are mocked.
            self.assertEqual(result['completed_runs'],90)
            self.assertEqual(result['status'],'complete_with_missing_judgments')
            self.assertEqual(len(read(Path(tmp)/'leaderboard.json')['models']),10)
            self.assertNotIn('SECRET',(Path(tmp)/'status.json').read_text())

    def test_invalid_probe_does_not_launch_benchmark(self):
        manifest='leaderboard/sweeps/openrouter-frontier-10/manifest.json'
        repo,plan,configs,judge=load_plan(manifest)
        catalog={'data':[x['catalog'] for x in read(repo/'leaderboard/sweeps/openrouter-frontier-10/catalog-snapshot.json')['models']]}
        class Probe:
            def __init__(self,*args):pass
            def __call__(self,*args):return {'operation':'command'}
        with tempfile.TemporaryDirectory() as tmp, patch('research_env.sweep.check_suite'), \
             patch('research_env.sweep.check_access',return_value={}), \
             patch('research_env.sweep.ModelProvider',Probe), patch('research_env.sweep.run') as runner, \
             patch('urllib.request.urlopen',return_value=io.BytesIO(canonical(catalog))):
            with self.assertRaises(ValueError):execute(manifest,tmp,'SECRET',10)
            runner.assert_not_called()
            self.assertEqual(read(Path(tmp)/'status.json')['status'],'needs_attention')


if __name__=='__main__':unittest.main()
