import copy
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from test_foundation import BankFixture
from ibank_core.storage import open_bank, load_data, fingerprint, read_json, atomic_write, dumps
from ibank_core.runs import commit_run, stage_text, undo_run, stage_snapshot
from ibank_core.migrations import migrate, restore_backup
from ibank_core.state import policy
from ibank_core.curation import stage_curate
from ibank_core.answers import stage_answers
from ibank_core.workflows import workflow, next_batch, workflow_summary
from ibank_core.studysets import studyset, export_set
from ibank_core.study import study
from ibank_core.interview import interview
from ibank_core.search import search
from ibank_core.errors import ValidationError
from ibank_core.dedupe import merge_questions


class MaintenanceTests(BankFixture):
    def ready(self):
        self.seed()
        return migrate(self.bank, 'apply')

    def commit(self, result):
        if 'run_id' in result:
            commit_run(self.bank, result['run_id'])
        return result.get('summary', result)

    def flow(self, **extra):
        result = workflow(self.bank,'create',{'name':'Research','question_ids':['q_demo0','q_demo1'], **extra})
        self.commit(result)
        return result['summary']['workflow_id']

    def answer(self, task, qid=None, skip=False):
        from ibank_core.dates import today
        rows=[]
        for item in task['items']:
            key=item['question']['id']
            if skip or (qid and key!=qid):
                rows.append({'question_id':key,'skip':True,'reason':'Fixture missing evidence'})
                continue
            url='https://redis.io/docs/latest/develop/data-types/'
            rows.append({'question_id':key,'status':'source_backed','short_answer':'测试机制与边界。','spoken_answer':'测试口述。',
                'deep_dive':'Fixture only, no live research.','interviewer_intent':'核对机制','key_points':['测试要点'],
                'common_mistakes':['忽略边界'],'follow_up_questions':['如何验证？'],'code_example':None,
                'sources':[{'url':url,'title':'Fixture documentation','publisher':'Redis','type':'official_doc','accessed_at':today().isoformat(),'evidence_note':'Synthetic test citation, not a real research claim'}],
                'evidence':[{'key_point':0,'source_urls':[url]}], 'checks':['Synthetic fixture validation'], 'version_scope':'fixture'})
        return stage_answers(self.bank,{'schema_version':1,'task_id':task['id'],'answers':rows})

    def test_migration_plan_read_only_and_legacy_rejection(self):
        self.seed()
        before=(self.bank/'manifest.json').read_bytes()
        self.assertEqual(migrate(self.bank)['from_version'],1)
        self.assertEqual(before,(self.bank/'manifest.json').read_bytes())
        with self.assertRaises(ValidationError):self.flow()
        result=migrate(self.bank,'apply')
        self.assertTrue(result['upgraded'])
        self.assertEqual(len(load_data(self.bank)['questions']),3)
        legacy = read_json(self.bank/'manifest.json')
        from ibank_core.schema import require
        def legacy_manifest_guard(value):
            require(type(value.get('schema_version')) is int and value['schema_version'] == 1, 'V1 runtime refuses new format')
        with self.assertRaises(ValidationError):legacy_manifest_guard(legacy)

    def test_backup_restore_and_never_overwrite(self):
        result=self.ready()
        restored=restore_backup(self.bank,result['backup'].split('\\')[-1],'baseline')
        from pathlib import Path
        self.assertEqual(read_json(Path(restored['restored_bank'])/'manifest.json')['schema_version'],1)
        with self.assertRaises(ValidationError):restore_backup(self.bank,Path(result['backup']).name,'baseline')
        with self.assertRaises(ValidationError):restore_backup(self.bank,Path(result['backup']).name,'../../escape')

    def test_migration_pending_stage_rejected(self):
        self.seed()
        p=self.base/'more.txt';p.write_text('New question',encoding='utf-8')
        stage_text(self.bank,p)
        with self.assertRaisesRegex(ValidationError,'pending'):migrate(self.bank,'apply')

    def test_migration_transaction_recovers_after_interruption(self):
        self.seed()
        from ibank_core import storage
        real=storage.atomic_write
        def failing(path,content):
            if Path(path).parts[-2:] == ('data', 'state.json'):raise OSError('Injected disk fault')
            real(path,content)
        with patch.object(storage,'atomic_write',side_effect=failing):
            with self.assertRaises(OSError):migrate(self.bank,'apply')
        with open_bank(self.bank) as (manifest,_,data):
            self.assertEqual(manifest['schema_version'],2)
            self.assertIn('_state',data)

    def test_policy_protection_and_explicit_override(self):
        self.ready()
        self.commit(policy(self.bank,'add',{'kind':'protect','question_id':'q_demo1','field':'canonical','reason':'Keep my wording','user_requested':True,'user_quote':'这题保持我的写法'}))
        change={'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'canonical':'Redis 为什么快，有哪些边界？'},'reason':'User refinement'}]}
        with self.assertRaisesRegex(ValidationError,'Protected field'):stage_curate(self.bank,change)
        self.commit(stage_curate(self.bank,{**change,'override_protection':True,'user_requested':True,'user_quote':'这题保持我的写法'}))
        self.assertIn('边界',search(self.bank,technology='redis')['questions'][0]['canonical'])

    def test_forbidden_merge_transitive_cluster(self):
        self.ready()
        self.commit(policy(self.bank,'add',{'kind':'never_merge','question_ids':['q_demo0','q_demo2'],'reason':'Distinct','user_requested':True,'user_quote':'这题保持我的写法'}))
        with open_bank(self.bank) as (_,config,data):
            final=copy.deepcopy(data)
            merge_questions(final,'q_demo0','q_demo1','MERGE_VARIANT',.99,'fixture')
            merge_questions(final,'q_demo2','q_demo1','MERGE_VARIANT',.99,'fixture')
            with self.assertRaisesRegex(ValidationError,'Protected pair'):stage_snapshot(self.bank,data,final,config,operation='dedupe')

    def test_state_snapshot_undo_and_append_preserve_state(self):
        self.ready()
        result=policy(self.bank,'add',{'kind':'protect','question_id':'q_demo1','field':'canonical','reason':'Keep','user_requested':True,'user_quote':'这题保持我的写法'})
        self.commit(result)
        self.commit(undo_run(self.bank,result['run_id']))
        self.assertEqual(policy(self.bank,'list')['policies'],[])
        key=self.flow()
        p=self.base/'new.txt';p.write_text('如何保证事务恢复？',encoding='utf-8')
        self.commit(stage_text(self.bank,p))
        self.assertEqual(workflow(self.bank,'show',key=key)['total'],2)

    def test_workflow_resume_skip_and_commit_reconciliation(self):
        self.ready();key=self.flow(batch_size=1)
        first=next_batch(self.bank,key)['task']
        self.assertEqual(first['id'],next_batch(self.bank,key)['task']['id'])
        run=self.answer(first);self.commit(run)
        commit_run(self.bank,run['run_id'])
        self.assertEqual(workflow(self.bank,'show',key=key)['answered'],1)
        second=next_batch(self.bank,key)['task'];self.commit(self.answer(second,skip=True))
        self.assertEqual(workflow(self.bank,'show',key=key)['status'],'blocked')
        self.commit(workflow(self.bank,'resume',{'retry_blocked':True},key))
        self.commit(self.answer(next_batch(self.bank,key)['task']))
        self.assertEqual(workflow(self.bank,'show',key=key)['status'],'completed')
        self.assertEqual(len(load_data(self.bank)['answers']),2)

    def test_workflow_budget_does_not_shrink_scope(self):
        self.ready();key=self.flow(limits={'max_questions':1},batch_size=2)
        self.commit(self.answer(next_batch(self.bank,key)['task']))
        result=next_batch(self.bank,key)
        self.assertIsNone(result['task']);self.assertEqual(result['reason'],'max_questions reached')
        self.assertEqual(result['workflow']['remaining'],1)
        self.assertEqual(result['workflow']['total'],2)
        self.assertNotIn('items',result['workflow'])
        self.assertNotIn('question_ids',result['workflow'])

    def test_answer_revision_stales_only_content(self):
        self.ready();key=self.flow(question_ids=['q_demo1'])
        self.commit(self.answer(next_batch(self.bank,key)['task']))
        self.assertEqual(search(self.bank,answer_status='source_backed')['total'],1)
        self.commit(stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'difficulty':'hard'},'reason':'difficulty fix'}]}))
        self.assertEqual(search(self.bank,answer_status='source_backed')['total'],1)
        self.commit(stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'canonical':'Redis 性能与慢命令的边界？'},'reason':'new constraint'}]}))
        self.assertEqual(search(self.bank,answer_status='stale')['total'],1)
        self.assertEqual(workflow(self.bank,'show',key=key)['remaining'],1)
        self.commit(workflow(self.bank,'block',{'question_id':'q_demo1','reason':'Old missing-evidence blocker'},key))
        from ibank_core.answers import research_task
        self.commit(self.answer(research_task(self.bank,['q_demo1'])))
        view=workflow(self.bank,'show',key=key)
        self.assertEqual(view['answered'],1)
        self.assertIsNone(view['items']['q_demo1']['reason'])

    def test_workflow_empty_scope_and_explicit_required(self):
        self.ready()
        with self.assertRaises(ValidationError):workflow(self.bank,'create',{'name':'ambiguous'})
        key=self.flow(question_ids=[])
        self.assertEqual(workflow(self.bank,'show',key=key)['total'],0)
        self.assertIsNone(workflow(self.bank,'show',key=key)['coverage'])

    def test_studyset_ast_context_and_jd_quotes(self):
        self.ready()
        expression={'all':[{'field':'company','values':['美团']},{'field':'round','values':['technical-2']}]}
        result=studyset(self.bank,'create',{'name':'No cross occurrence','expression':expression})
        self.commit(result);key=result['summary']['studyset_id']
        self.assertEqual(studyset(self.bank,'show',key=key)['question_ids'],[])
        with self.assertRaises(ValidationError):studyset(self.bank,'create',{'name':'Bad JD','jd_text':'Redis','requirements':[{'id':'r1','quote':'Java','priority':'must','reason':'invented'}]})

    def test_studyset_dynamic_refresh_and_double_exports(self):
        self.ready()
        result=studyset(self.bank,'create',{'name':'Backend','mode':'dynamic','expression':{'field':'role','scope':'suitability','values':['backend']}})
        self.commit(result);key=result['summary']['studyset_id']
        self.commit(studyset(self.bank,'refresh',key=key))
        self.assertEqual(studyset(self.bank,'show',key=key)['selection_revision'],2)
        exported=export_set(self.bank,key,'topic.md')
        self.assertEqual(exported['questions'],2)
        from pathlib import Path
        text=Path(exported['question_output']).read_text(encoding='utf-8')
        self.assertNotIn('答案（参考）',text)
        self.assertIn('Backend',text)

    def test_invalid_ast_and_path_escape_rejected(self):
        self.ready()
        with self.assertRaises(ValidationError):studyset(self.bank,'create',{'name':'x','expression':{'field':'sql','values':['drop table']}})
        key=self.flow()
        with self.assertRaises(ValidationError):workflow_summary(self.bank,key,'../../escape.md')

    def test_practice_idempotency_timezone_and_changed_wording(self):
        self.ready()
        payload={'request_id':'practice-1','question_id':'q_demo1','rating':'good','timezone':'Asia/Shanghai','user_quote':'这题我基本会了'}
        self.commit(study(self.bank,'record',payload))
        self.assertTrue(study(self.bank,'record',payload)['already_recorded'])
        history=study(self.bank,'history')['events'];self.assertEqual(len(history),1)
        self.assertEqual(history[0]['interval_days'],3)
        queued=study(self.bank,'queue',{'include_future':True})['questions']
        self.assertTrue(next(q for q in queued if q['question_id']=='q_demo1')['next_review_at'].endswith('+08:00'))
        self.commit(stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'canonical':'Redis 慢查询如何诊断？'},'reason':'changed'}]}))
        queued=study(self.bank,'queue')['questions']
        self.assertEqual(next(q for q in queued if q['question_id']=='q_demo1')['state'],'needs_repractice')

    def test_interview_one_at_a_time_feedback_and_resume(self):
        self.ready()
        result=interview(self.bank,'start',{'name':'Mock','question_ids':['q_demo1']});self.commit(result);key=result['summary']['session_id']
        prompt=interview(self.bank,'next',key=key)
        self.assertNotIn('answer',prompt)
        self.commit(interview(self.bank,'answer',{'question_id':'q_demo1','request_id':'answer-1','text':'Redis 使用内存。'},key))
        pending=interview(self.bank,'next',key=key)
        self.assertEqual(pending['status'],'awaiting_feedback')
        feedback={'response_id':pending['response']['id'],'observations':[{'dimension':'coverage','quote':'内存','note':'需要补充操作复杂度与边界。'}],'review_topics':['Redis 复杂度']}
        with self.assertRaises(ValidationError):interview(self.bank,'feedback',feedback,key)
        self.commit(interview(self.bank,'feedback',{**feedback,'limited_basis':True},key))
        self.commit(interview(self.bank,'follow-up',{'prompt':'是否所有命令都是常数时间？','reason':'检查边界'},key))
        self.assertTrue(interview(self.bank,'next',key=key)['follow_up'])
        self.commit(interview(self.bank,'answer',{'question_id':'q_demo1','request_id':'answer-2','text':'不是，复杂度取决于命令。'},key))
        pending=interview(self.bank,'next',key=key)
        self.commit(interview(self.bank,'feedback',{'response_id':pending['response']['id'],'limited_basis':True,'observations':[{'dimension':'clarity','quote':'取决于命令','note':'明确指出差异。'}]},key))
        self.commit(interview(self.bank,'end',key=key))
        summary=interview(self.bank,'summary',key=key)
        self.assertEqual(summary['status'],'completed');self.assertEqual(summary['ungraded'],0)

    def test_interview_rejects_wrong_question_and_fake_quote(self):
        self.ready();r=interview(self.bank,'start',{'name':'Mock','question_ids':['q_demo0']});self.commit(r);key=r['summary']['session_id']
        with self.assertRaises(ValidationError):interview(self.bank,'answer',{'question_id':'q_demo1','request_id':'x','text':'wrong'},key)
        self.commit(interview(self.bank,'answer',{'question_id':'q_demo0','request_id':'x','text':'树索引'},key))
        pending=interview(self.bank,'next',key=key)
        with self.assertRaises(ValidationError):interview(self.bank,'feedback',{'response_id':pending['response']['id'],'limited_basis':True,'observations':[{'dimension':'clarity','quote':'内存','note':'fake'}]},key)

    def test_new_cli_validation_envelope(self):
        self.ready()
        result=self.cli('workflow','list')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        result=self.cli('studyset','show','--id','missing')
        self.assertEqual(result.returncode,2)
        self.assertFalse(json.loads(result.stderr)['ok'])

    def add_occurrence(self):
        import hashlib
        from ibank_core.runs import stage_bundle
        p=self.base/'new-occurrence.txt';p.write_text('Redis 为什么性能高？ 新收集记录',encoding='utf-8')
        source={**self.bundle['sources'][0],'id':'src_new','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        occ={**self.bundle['occurrences'][1],'id':'occ_new','source_id':'src_new','sequence':1}
        run=stage_bundle(self.bank,{'schema_version':1,'sources':[source],'occurrences':[occ]})
        self.commit(run)
        return run['run_id']

    def test_frozen_occurrences_and_incremental_workflow_scope(self):
        self.ready()
        r=studyset(self.bank,'create',{'name':'Frozen','selected_ids':['q_demo1']});self.commit(r);key=r['summary']['studyset_id']
        run_id=self.add_occurrence()
        exported=export_set(self.bank,key,'frozen.md')
        side=read_json(__import__('pathlib').Path(exported['details_output']))
        self.assertEqual(side['questions'][0]['frequency'],2)
        self.assertEqual(search(self.bank,technology='redis')['questions'][0]['frequency'],3)
        r=workflow(self.bank,'create',{'name':'Increment','from_run':run_id});self.commit(r)
        v=workflow(self.bank,'show',key=r['summary']['workflow_id'])
        self.assertEqual(v['question_ids'],['q_demo1']);self.assertEqual(v['occurrence_ids'],['occ_new'])
        self.assertEqual(v['intake_receipt']['counts']['occurrences'],1)

    def test_jd_must_coverage_precedes_frequency_limit(self):
        self.ready()
        r=studyset(self.bank,'create',{'name':'JD priority','jd_text':'必须熟悉 React','requirements':[
            {'id':'r1','quote':'必须熟悉 React','priority':'must','reason':'Explicit requirement',
             'matches':[{'question_id':'q_demo2','coverage':'direct','reason':'React question'}]}],'limit':1})
        self.commit(r)
        v=studyset(self.bank,'show',key=r['summary']['studyset_id'])
        self.assertEqual(v['question_ids'],['q_demo2'])
        self.assertEqual(v['jd_coverage']['directly_covered'],1)

    def test_workflow_revision_and_deadline(self):
        self.ready();key=self.flow(limits={'deadline':'2020-01-01T00:00:00+00:00'})
        self.assertEqual(next_batch(self.bank,key)['reason'],'deadline reached')
        self.commit(workflow(self.bank,'revise',{'question_ids':['q_demo2'],'reason':'User narrows scope'},key))
        v=workflow(self.bank,'show',key=key)
        self.assertEqual(v['scope_revision'],2);self.assertEqual(len(v['scope_history']),1)
        self.commit(workflow(self.bank,'resume',{'limits':{}},key))
        self.assertEqual(next_batch(self.bank,key)['task']['items'][0]['question']['id'],'q_demo2')

    def test_v2_snapshot_dedupe_candidates_and_undo(self):
        self.ready()
        from ibank_core.dedupe import candidate_task,stage_decisions
        r=stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'difficulty':'hard'},'reason':'User fix'}]})
        task=candidate_task(self.bank,r['run_id'])
        final=stage_decisions(self.bank,{'schema_version':1,'task_id':task['id'],'decisions':[]})
        self.commit(final)
        self.assertIn('_state',load_data(self.bank))
        self.commit(undo_run(self.bank,final['run_id']))

    def test_existing_answer_migration_binds_answers_of_unchanged_questions(self):
        # The question was not edited after its answer was written, so the answer keeps covering it.
        self.seed()
        from ibank_core.answers import research_task
        self.commit(self.answer(research_task(self.bank,['q_demo1'])))
        self.assertEqual(search(self.bank,answer_status='source_backed')['total'],1)
        result=migrate(self.bank,'apply')
        self.assertEqual((result['answers_bound'],result['answers_need_recheck']),(1,0))
        self.assertEqual(search(self.bank,answer_status='source_backed')['total'],1)
        self.assertEqual(len(load_data(self.bank)['answers']),1)

    def test_existing_answer_migration_marks_edited_questions_for_recheck(self):
        self.seed()
        from ibank_core.answers import research_task
        self.commit(self.answer(research_task(self.bank,['q_demo1'])))
        change={'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'canonical':'Redis 为什么快，有哪些边界？'},'reason':'Edited after answering'}]}
        self.commit(stage_curate(self.bank,change))
        result=migrate(self.bank,'apply')
        self.assertEqual((result['answers_bound'],result['answers_need_recheck']),(0,1))
        self.assertEqual(search(self.bank,answer_status='stale')['total'],1)

    def test_restore_tamper_and_state_corruption_rejected(self):
        result=self.ready()
        from pathlib import Path
        backup=Path(result['backup'])
        with zipfile.ZipFile(backup,'a') as z:z.writestr('unlisted.txt','unexpected')
        with self.assertRaisesRegex(ValidationError,'entry mismatch'):restore_backup(self.bank,backup.name,'invalid')
        self.assertFalse((self.bank/'restored/invalid').exists())
        state=read_json(self.bank/'data/state.json');state['workflows']=[]
        atomic_write(self.bank/'data/state.json',dumps(state))
        with self.assertRaises(ValidationError):
            with open_bank(self.bank):pass

    def test_practice_retry_conflict_and_time_validation(self):
        self.ready();p={'request_id':'once','question_id':'q_demo1','rating':'good','note':'original','user_quote':'这题我基本会了'}
        self.commit(study(self.bank,'record',p))
        with self.assertRaises(ValidationError):study(self.bank,'record',{**p,'note':'changed'})
        with self.assertRaises(ValidationError):study(self.bank,'record',{'request_id':'next','question_id':'q_demo1','rating':'good','occurred_at':'2099-01-01T00:00:00+00:00','user_quote':'会了'})
        with self.assertRaises(ValidationError):study(self.bank,'queue',{'as_of':'2026-09-07T12:00:00'})

    def test_task_staleness_and_budget_batch_count(self):
        self.ready();key=self.flow(limits={'max_batches':1})
        task=next_batch(self.bank,key)['task']
        self.commit(stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo2','set':{'difficulty':'hard'},'reason':'concurrent edit'}]}))
        with self.assertRaisesRegex(ValidationError,'stale'):self.answer(task)
        self.assertEqual(next_batch(self.bank,key)['reason'],'max_batches reached')

    def test_conflicting_scopes_and_stale_jd_coverage(self):
        self.ready()
        with self.assertRaises(ValidationError):
            workflow(self.bank,'create',{'name':'Conflicting','question_ids':['q_demo1'],'expression':{}})
        r=studyset(self.bank,'create',{'name':'JD','jd_text':'Redis','requirements':[{'id':'r1','quote':'Redis','priority':'must','reason':'Explicit','matches':[{'question_id':'q_demo1','coverage':'direct','reason':'Redis question'}]}]})
        self.commit(r);key=r['summary']['studyset_id']
        self.commit(stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'canonical':'Redis 持久化的失败边界？'},'reason':'Different coverage'}]}))
        v=studyset(self.bank,'show',key=key)
        self.assertEqual(v['jd_coverage']['directly_covered'],0)
        self.assertTrue(v['requirements'][0]['matches'][0]['needs_recheck'])

    def test_interview_receipt_retry_after_end(self):
        self.ready()
        r=interview(self.bank,'start',{'name':'Retry','question_ids':['q_demo1']});self.commit(r);key=r['summary']['session_id']
        answer={'request_id':'lost-receipt','question_id':'q_demo1','text':'内存'}
        self.commit(interview(self.bank,'answer',answer,key))
        pending=interview(self.bank,'next',key=key)
        feedback={'response_id':pending['response']['id'],'limited_basis':True,'observations':[{'dimension':'clarity','note':'Synthetic feedback','quote':'内存'}]}
        self.commit(interview(self.bank,'feedback',feedback,key))
        self.commit(interview(self.bank,'end',key=key))
        self.assertTrue(interview(self.bank,'answer',answer,key)['already_recorded'])
        self.assertTrue(interview(self.bank,'feedback',feedback,key)['already_recorded'])
        self.assertTrue(interview(self.bank,'end',key=key)['already_ended'])
        with self.assertRaises(ValidationError):interview(self.bank,'answer',{**answer,'question_id':'q_demo2'},key)
        with self.assertRaises(ValidationError):interview(self.bank,'feedback',{**feedback,'review_topics':['different']},key)

    def test_migration_disk_full_preflight_preserves_v1(self):
        self.seed()
        from collections import namedtuple
        Usage=namedtuple('Usage','total used free')
        before=fingerprint(load_data(self.bank))
        with patch('ibank_core.migrations.shutil.disk_usage',return_value=Usage(100,100,0)):
            with self.assertRaisesRegex(ValidationError,'Insufficient free space'):migrate(self.bank,'apply')
        self.assertEqual(read_json(self.bank/'manifest.json')['schema_version'],1)
        self.assertEqual(fingerprint(load_data(self.bank)),before)

