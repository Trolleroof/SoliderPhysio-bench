import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'tasks/beat_ectemp'
spec = importlib.util.spec_from_file_location('beat', BASE/'benchmark.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
spec = importlib.util.spec_from_file_location('ectemp', BASE/'ectemp_baseline.py')
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)


def rows():
    return [dict(time_min=i+1, watts=200 if i<10 else 50, hr=140,
                 skin_temp=35, core_temp=38.5 if i>=10 else 38,
                 ambient_temp=35, humidity=40, age=25, mass=70,height=175) for i in range(40)]


class BeatECTempTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=BASE)
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.public=self.root/'public'; self.private=self.root/'private'
        self.private.mkdir()
        (self.private/'labels.json').write_text(json.dumps({p:rows() for p in b.TRAIN+b.DEV+b.TEST}))

    def test_workbook_and_frozen_split(self):
        data=b.read_workbook(ROOT/'sources/figshare-heat/core_cycling_2025.xlsx')
        self.assertEqual(set(data),set(b.TRAIN+b.DEV+b.TEST))
        self.assertEqual([len(x) for x in (b.TRAIN,b.DEV,b.TEST)],[14,5,5])
        self.assertTrue(all(len(r)==60 for r in data.values()))
        self.assertTrue(all(any(r[k] is not None for r in data['H01']) for k in rows()[0]))
        self.assertTrue(all(30 <= r['hr'] <= 240 for rows_p in data.values() for r in rows_p if r['hr'] is not None))
        split=self.root/'splits.json'; split.write_text(json.dumps(b.SPLITS))
        b.build(ROOT/'sources/figshare-heat/core_cycling_2025.xlsx',split,self.public,self.private)
        train=json.loads((self.public/'train.json').read_text())
        self.assertEqual(set(train),set(b.TRAIN))
        dev=json.loads((self.public/'dev_requests.json').read_text())
        self.assertTrue(dev['3A']); self.assertTrue(dev['3B'])
        for task in dev.values():
            for request in task:
                self.assertTrue(all('core_temp' not in row for row in request['history']))
        public_text=''.join(p.read_text() for p in self.public.iterdir())
        for person in b.TEST+b.DEV:
            self.assertNotIn(person,public_text)
        self.assertNotIn('labels.json',[p.name for p in self.public.iterdir()])
        split.write_text('{}')
        with self.assertRaises(ValueError): b.build('unused',split,self.public,self.private)
        bad_wb=self.root/'bad.xlsx'; bad_wb.write_bytes(b'bad')
        with self.assertRaises(ValueError): b.read_workbook(bad_wb)

    def test_causal_forecast_and_online(self):
        a=list(b.requests(rows(),'3A')); c=list(b.requests(rows(),'3B'))
        self.assertEqual(len(a),1); self.assertEqual(len(a[0][0]['history']),11)
        self.assertEqual(a[0][1],rows()[25]['core_temp'])
        self.assertEqual(len(c),40)
        self.assertEqual([len(x[0]['history']) for x in c],list(range(1,41)))

    def test_baseline_and_clock_shift(self):
        a=list(b.requests(rows(),'3B',0)); c=list(b.requests(rows(),'3B',12345))
        self.assertEqual([e.predict(r) for r,_,_ in a],[e.predict(r) for r,_,_ in c])
        self.assertTrue(all(b.valid(e.predict(r)) for r,_,_ in a))
        cold=rows(); cold[-1]['hr']=60; cold[-1]['skin_temp']=30; cold[-1]['watts']=0
        self.assertLess(e.predict(list(b.requests(cold,'3B'))[-1][0])['mean'],e.predict(a[-1][0])['mean'])
        seen=[]
        b.evaluate(self.public,self.private,'3B',True,lambda _,rs: seen.extend(rs) or [e.predict(r) for r in rs])
        self.assertTrue(any(r['history'][0]['time_min']!=1 for r in seen))
        self.assertTrue(all('core_temp' not in x for r in seen for x in r['history']))

    def test_invalid_intervals_zero_entire_call(self):
        for output in ({}, {'mean':float('nan'),'lower':37,'upper':39},
                       {'mean':38,'lower':39,'upper':40}, {'mean':38,'lower':37,'upper':float('inf')},
                       {'mean':38,'lower':20,'upper':50}, {'mean':38,'lower':38,'upper':38}):
            self.assertEqual(b.metrics([output],[38],[True])['score'],0)
        self.assertEqual(b.metrics([],[38],[True])['score'],0)

    def test_worker_ignores_submission_prints(self):
        import subprocess, sys
        self.public.mkdir()
        (self.public/'submission.py').write_text(
            'print("import noise")\ndef predict(r):\n    print("debug")\n    return {"mean":38,"lower":37.5,"upper":38.5}\n')
        r=subprocess.run([sys.executable,'-I','-c',b.WORKER,str(self.public)],input='[{}, {}]',
                         text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(r.stdout),[{'mean':38,'lower':37.5,'upper':38.5}]*2)
        self.assertIn('debug',r.stderr)

    def test_hidden_hot_after_drop_and_gap_and_spam(self):
        runner=lambda _,rs:[{'mean':38,'lower':37.5,'upper':38.5} for r in rs]
        for _ in range(3): public=b.evaluate(self.public,self.private,'3B',False,runner)
        hidden=b.evaluate(self.public,self.private,'3B',True,runner)
        self.assertEqual(hidden['public_call_count'],3)
        self.assertEqual(hidden['primary_count'],150)
        self.assertEqual(hidden['primary_mae'],.5)
        self.assertEqual(hidden['mae'],.375)
        self.assertEqual(hidden['public_to_hidden_gap'],.125)
        self.assertEqual(len((self.private/'calls.jsonl').read_text().splitlines()),4)
        self.assertEqual(public['primary_count'],200)
        no_drop=rows()
        for r in no_drop:r['watts']=200
        self.assertFalse(any(m for _,_,m in b.requests(no_drop,'3B')))
        self.assertEqual(b.metrics([runner(None,[{}])[0]],[38],[False])['score'],0)

    @unittest.skipUnless(b.sys.platform=='darwin' and b.shutil.which('sandbox-exec'),'macOS sandbox required')
    def test_real_sandbox_blocks_labels_network_and_budget(self):
        self.public.mkdir()
        source='''import socket\ndef predict(r):\n    try:\n        open(%r).read()\n        raise AssertionError('label leak')\n    except PermissionError: pass\n    try:\n        socket.create_connection(('1.1.1.1',80),timeout=1)\n        raise AssertionError('network leak')\n    except OSError: pass\n    import resource\n    assert resource.getrlimit(resource.RLIMIT_CPU)[0]==1200\n    return {'mean':38,'lower':37,'upper':39}\n''' % str(self.private/'labels.json')
        (self.public/'submission.py').write_text(source)
        self.assertTrue(b.valid(b.run_submission(self.public,[{}])[0]))


if __name__=='__main__': unittest.main()
