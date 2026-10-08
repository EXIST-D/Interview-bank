import copy
import http.client
import json
import threading
from unittest.mock import patch

from test_foundation import BankFixture
from ibank_core.web import LocalServer, WebApp
from ibank_core.storage import load_data, fingerprint, open_bank
from ibank_core.migrations import migrate
from ibank_core.errors import ValidationError, LockConflict
from ibank_core.normalize import normalize_question_text
from ibank_core.runs import stage_snapshot, commit_run


class WebTests(BankFixture):
    def start(self, v2=False, read_only=False, seed=True):
        if seed:self.seed()
        if v2:migrate(self.bank, 'apply')
        self.app=WebApp(self.bank,read_only)
        self.server=LocalServer(self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def request(self,path,body=None,headers=None,method=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        sent={'X-Interview-Token':self.server.token,'Content-Type':'application/json',**(headers or {})}
        raw=json.dumps(body) if body is not None else None
        conn.request(method or ('POST' if body is not None else 'GET'),path,raw,sent)
        response=conn.getresponse();result=(response.status,dict(response.getheaders()),response.read());conn.close();return result

    def get(self,path):
        code,_,raw=self.request(path);self.assertEqual(code,200,raw);return json.loads(raw)

    def payload(self,rating='good',key='web-fixture'):
        q=self.app.question('q_demo0')
        return {'question_id':q['id'],'revision':q['revision'],'rating':rating,'request_id':key,'note':'My actual fixture response','timezone':'Asia/Shanghai'}

    def test_v1_browse_and_filters_preserve_canonical_data(self):
        self.start();before=fingerprint(load_data(self.bank));manifest=(self.bank/'manifest.json').read_bytes()
        lib=self.get('/api/library');self.assertEqual(lib['total'],3);self.assertFalse(lib['can_record'])
        found=self.get('/api/library?company=company_meituan&technology=redis');self.assertEqual(found['total'],1);self.assertEqual(found['questions'][0]['frequency'],1)
        self.assertEqual(self.get('/api/library?query=MySQL')['total'],1)
        self.assertEqual(self.get('/api/library?role=frontend&company=company_meituan')['total'],0)
        self.assertEqual(self.get('/api/library?limit=1&offset=1')['questions'][0]['id'],'q_demo0')
        detail=self.get('/api/question?id=q_demo0');self.assertEqual(detail['occurrences'][0]['text'],self.bundle['questions'][0]['canonical'])
        self.assertNotIn(str(self.base),json.dumps(detail))
        self.assertEqual(fingerprint(load_data(self.bank)),before);self.assertEqual((self.bank/'manifest.json').read_bytes(),manifest)

    def test_excluded_questions_are_not_exposed(self):
        q=self.bundle['questions'][0];q.update(canonical='请自我介绍',normalized=normalize_question_text('请自我介绍'))
        self.start();self.assertEqual(self.get('/api/library')['total'],2)
        self.assertEqual(self.request('/api/question?id=q_demo0')[0],400)

    def test_empty_bank_and_invalid_queries(self):
        self.start(seed=False);self.assertEqual(self.get('/api/library')['total'],0)
        for p in ('limit=0','limit=101','offset=-1','sort=invalid','view=bad','unknown=x','limit=1&limit=2'):
            self.assertEqual(self.request('/api/library?'+p)[0],400,p)

    def test_origin_token_and_host_enforcement(self):
        self.start()
        for headers in ({'X-Interview-Token':''},{'X-Interview-Token':'wrong'},{'Origin':'https://evil.example'},{'Origin':'null'},{'Host':'evil.example'}):
            status,_,body=self.request('/api/library',headers=headers);self.assertIn(status,(401,403));self.assertNotIn(b'q_demo',body)
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        self.assertEqual(self.request('/api/library',headers={'Origin':self.server.origin})[0],200)

    def test_hosting_behind_a_proxy_uses_a_fixed_token_and_named_origin(self):
        self.seed()
        token = 'proxy-token-' + 'x' * 40
        self.app = WebApp(self.bank, True)
        self.server = LocalServer(self.app, 0, token, ['https://exist.example'])
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        self.assertEqual(self.request('/api/library', headers={'Origin': 'https://exist.example'})[0], 200)
        for headers in ({'Origin': 'https://other.example'}, {'X-Interview-Token': 'wrong'}):
            self.assertIn(self.request('/api/library', headers=headers)[0], (401, 403))

    def test_serve_validates_hosting_options(self):
        from ibank_core.web import serve
        with self.assertRaises(ValidationError):
            serve(self.bank, 0, True, False, None, ['https://exist.example'])
        with self.assertRaises(ValidationError):
            serve(self.bank, 0, True, False, None, ['http://exist.example/ibank'])
        short = self.bank.parent / 'short-token'
        short.write_text('short', encoding='utf-8')
        with self.assertRaises(ValidationError):
            serve(self.bank, 0, True, False, str(short), ['https://exist.example'])

    def test_static_assets_and_no_arbitrary_file_server(self):
        self.start()
        for path,mime in (('/','text/html'),('/app.js','text/javascript'),('/app.css','text/css')):
            status,headers,body=self.request(path);self.assertEqual(status,200);self.assertIn(mime,headers['Content-Type']);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy']);self.assertNotIn(self.server.token.encode(),body)
        for path in ('/../manifest.json','/data/questions.jsonl','/assets/../../SKILL.md','/api/migrate'):
            self.assertEqual(self.request(path)[0],404)

    def test_v1_and_read_only_refuse_writes(self):
        self.start();self.assertEqual(self.request('/api/practice',self.payload())[0],400)
        migrate(self.bank,'apply');self.app.read_only=True;before=fingerprint(load_data(self.bank))
        self.assertEqual(self.request('/api/practice',self.payload())[0],400);self.assertEqual(fingerprint(load_data(self.bank)),before)

    def test_rating_is_persistent_idempotent_and_updates_queue(self):
        self.start(v2=True);p=self.payload()
        self.assertEqual(self.get('/api/library?view=due')['total'],3)
        result=json.loads(self.request('/api/practice',p)[2]);self.assertTrue(result['saved'])
        again=json.loads(self.request('/api/practice',p)[2]);self.assertTrue(again['already_recorded'])
        self.assertEqual(len(load_data(self.bank)['_state']['events']),1)
        self.assertEqual(self.get('/api/library?view=due')['total'],2)
        self.assertEqual(self.get('/api/library?view=unseen')['total'],2)
        self.assertEqual(WebApp(self.bank).question('q_demo0')['history'][0]['note'],p['note'])
        self.assertEqual(self.request('/api/practice',{**p,'rating':'easy'})[0],400)

    def test_weak_queue_and_revision_change(self):
        self.start(v2=True);p=self.payload('hard');self.assertEqual(self.request('/api/practice',p)[0],200)
        self.assertEqual(self.get('/api/library?view=weak')['total'],1)
        with open_bank(self.bank) as (_,config,data):
            final=copy.deepcopy(data);final['questions'][0]['canonical']+=' 请举例。';final['questions'][0]['normalized']=normalize_question_text(final['questions'][0]['canonical'])
            staged=stage_snapshot(self.bank,data,final,config,operation='curate')
        commit_run(self.bank,staged['run_id'])
        self.assertEqual(self.request('/api/practice',{**p,'request_id':'new-old-revision'})[0],400)
        self.assertEqual(self.get('/api/library?view=due')['total'],3)
        self.assertEqual(self.app.question('q_demo0')['progress']['state'],'changed')

    def test_request_validation_no_fake_dates_or_scores(self):
        self.start(v2=True)
        for change in ({'occurred_at':'2020-01-01'},{'interval_days':10},{'note':'x'*10001},{'rating':'passed'},{'request_id':''},{'timezone':4}):
            self.assertEqual(self.request('/api/practice',{**self.payload(),**change})[0],400)
        self.assertFalse(load_data(self.bank)['_state']['events'])

    def test_busy_bank_has_actionable_error(self):
        self.start()
        with patch.object(self.app,'library',side_effect=LockConflict('private path')):
            status,_,body=self.request('/api/library');self.assertEqual(status,409);self.assertNotIn(b'private path',body)

    def test_commit_conflict_does_not_save_or_leave_pending_stage(self):
        self.start(v2=True)
        with patch('ibank_core.web.commit_run',side_effect=ValidationError('Bank changed since staging')):
            self.assertEqual(self.request('/api/practice',self.payload())[0],400)
        self.assertFalse(load_data(self.bank)['_state']['events'])
        from ibank_core.doctor import doctor
        self.assertFalse(doctor(self.bank)['pending_runs'])

    def test_practice_matches_selection_and_page(self):
        self.start(v2=True)
        rows=self.get('/api/practice?technology=redis&limit=10')['questions']
        self.assertEqual([q['id'] for q in rows],['q_demo1'])
        self.assertNotIn('answer',rows[0])

    def test_concurrent_retry_records_only_once(self):
        self.start(v2=True)
        from concurrent.futures import ThreadPoolExecutor
        p=self.payload()
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses=list(executor.map(lambda _:self.request('/api/practice',p),range(2)))
        self.assertTrue(all(r[0]==200 for r in responses))
        self.assertEqual(len(load_data(self.bank)['_state']['events']),1)
