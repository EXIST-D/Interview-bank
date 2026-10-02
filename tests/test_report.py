import json
import re
from pathlib import Path
from test_foundation import BankFixture
from ibank_core.export import export_bank, report_group, answer_section
from ibank_core.answers import research_task
from ibank_core.editorial import is_self_introduction
from ibank_core.normalize import normalize_question_text
from ibank_core.curation import stage_curate
from ibank_core.dedupe import candidate_task, stage_decisions
from ibank_core.ingestion import intake_images, stage_extraction
from ibank_core.runs import commit_run
from ibank_core.storage import load_data
from ibank_core.errors import ValidationError


class ReportTests(BankFixture):
    def test_default_two_editions_share_question_order(self):
        self.seed()
        result = export_bank(self.bank, 'both.md')
        full = Path(result['answer_output']).read_text(encoding='utf-8')
        questions = Path(result['question_output']).read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'^### .*', full, re.M), re.findall(r'^### .*', questions, re.M))
        self.assertIn('答案（参考）', full)
        self.assertNotIn('答案', questions)
        self.assertNotIn('参考资料', questions)
        self.assertEqual(result['pending_answers'], 3)
        self.assertEqual(result['answered_questions'], 0)
        self.assertEqual(result['output'], result['answer_output'])

    def test_single_edition_and_cli_option(self):
        self.seed()
        result = export_bank(self.bank, 'questions.md', answer_mode='without')
        self.assertIsNone(result['answer_output'])
        self.assertEqual(result['question_output'], result['output'])
        self.assertNotIn('答案', Path(result['output']).read_text(encoding='utf-8'))
        result = self.cli('export', '--output', 'answers.md', '--answers', 'with')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)['result']['question_output'])
        with self.assertRaises(ValidationError):
            export_bank(self.bank, 'bad.json', format='json', answer_mode='without')

    def test_second_report_escape_is_rejected_before_any_writes(self):
        self.seed()
        exports = self.bank / 'exports'
        outside = self.base / 'outside.md'
        outside.write_text('keep', encoding='utf-8')
        try: (exports / 'r（题目版）.md').symlink_to(outside)
        except OSError: self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValidationError): export_bank(self.bank, 'r.md')
        self.assertEqual(outside.read_text(encoding='utf-8'), 'keep')
        self.assertFalse((exports / 'r.md.details.json').exists())

    def test_research_packet_omits_unneeded_provenance(self):
        self.seed()
        task = research_task(self.bank, ['q_demo1'])
        question = task['items'][0]['question']
        self.assertEqual(question['canonical'], 'Redis 为什么性能高？')
        self.assertNotIn('occurrences', question)
        self.assertNotIn('answer_versions', question)

    def test_headings_counts_numbering_and_answer_slots(self):
        for q in self.bundle['questions'][:2]:
            q['domains'] = ['backend.cache']
        self.seed()
        result = export_bank(self.bank, 'outline.md')
        text = Path(result['output']).read_text(encoding='utf-8')
        detail = json.loads(Path(result['details_output']).read_text(encoding='utf-8'))
        self.assertTrue(text.startswith('# 面试题整理报告\n'))
        self.assertIn('| 缓存 | 2 |', text)
        self.assertIn('## 缓存（2 题）', text)
        self.assertLess(text.index('### 1. Redis'), text.index('### 2. MySQL'))
        self.assertIn('### 1. React', text)
        self.assertEqual(text.count('答案（参考）：待检索与核验。'), 3)
        self.assertEqual(sum(g['count'] for g in detail['report']['groups']), 3)
        self.assertIn('已核验来源 0 道', text)

    def test_reference_answers_show_verified_content_and_hide_drafts(self):
        answer = {'short_answer':'结论。\n- 要点一。\n2. 要点二。', 'sources':[
            {'title':'Official [reference]', 'url':'https://example.org/doc(v1)'}]}
        for status in ['source_backed', 'reviewed']:
            text = '\n\n'.join(answer_section({'answer':answer, 'answer_status':status}))
            self.assertIn('答案（参考）', text)
            self.assertIn('- 要点一。\n- 要点二。', text)
            self.assertIn('https://example.org/doc%28v1%29', text)
        for status in ['ai_draft', 'stale']:
            text = '\n'.join(answer_section({'answer':answer, 'answer_status':status}))
            self.assertNotIn('要点一', text)
            self.assertIn('核验', text)
        answer['sources'] = []
        self.assertIn('待补充来源', answer_section({'answer':answer, 'answer_status':'reviewed'})[0])

    def test_default_research_omits_report_exclusions(self):
        self.bundle['questions'][0]['report_exclusion'] = '个人情况'
        q = self.bundle['questions'][2]
        q.update(canonical='自我介绍', normalized=normalize_question_text('自我介绍'))
        self.seed()
        task = research_task(self.bank, limit=100)
        self.assertEqual([i['question']['id'] for i in task['items']], ['q_demo1'])
        # An explicit selection remains available for unusual user-authorized scopes.
        self.assertEqual(len(research_task(self.bank, ['q_demo0'])['items']), 1)

    def test_plain_markdown_and_primary_domain(self):
        q = self.bundle['questions'][0]
        q.update(canonical='# Redis [cache](https://example.com) 与 *Memory*',
                 normalized=normalize_question_text('# Redis [cache](https://example.com) 与 *Memory*'))
        self.seed()
        text = Path(export_bank(self.bank, 'plain.md')['output']).read_text(encoding='utf-8')
        self.assertIn(r'\# Redis \[cache\]', text)
        self.assertIn(r'\*Memory\*', text)
        self.assertNotIn('\x01', text)
        self.assertEqual(report_group({'domains':['ai.agent.memory','ai.rag.retrieval']}), '记忆与上下文')

    def test_legacy_intro_cannot_merge_into_knowledge_question(self):
        q = self.bundle['questions'][2]
        q.update(canonical='自我介绍', normalized=normalize_question_text('自我介绍'),
                 domains=['backend.cache'], technologies=['redis'])
        self.seed()
        task = candidate_task(self.bank, question_ids=['q_demo2'])
        with self.assertRaisesRegex(ValidationError, 'excluded and included'):
            stage_decisions(self.bank, {'schema_version':1,'task_id':task['id'],'decisions':[
                {'question_id':'q_demo2','target_id':'q_demo1','action':'MERGE_VARIANT',
                 'confidence':0.99,'reason':'Invalid merge despite host confidence'}]})

    def test_reader_excludes_introduction_but_sidecar_retains_every_occurrence(self):
        q=self.bundle['questions'][0]
        q.update(canonical='请做一个简短的自我介绍，重点突出项目。', normalized=normalize_question_text('请做一个简短的自我介绍，重点突出项目。'))
        self.seed()
        before=load_data(self.bank)
        result=export_bank(self.bank,'report.md',include_paths=True)
        text=Path(result['output']).read_text(encoding='utf-8')
        data=json.loads(Path(result['details_output']).read_text(encoding='utf-8'))
        self.assertEqual(result['questions'],2)
        self.assertEqual(len(data['questions']),3)
        self.assertEqual(sum(len(q['occurrences']) for q in data['questions']),4)
        self.assertNotIn('自我介绍',text)
        self.assertNotRegex(text,r'q_demo|src_|technical-|2026-\d')
        self.assertIn('2026',text)
        self.assertNotIn(str(self.base),text)
        self.assertEqual(before,load_data(self.bank))

    def test_exclusion_is_audited_reversible_and_structured_exports_stay_complete(self):
        self.seed()
        def exclude(value):
            run=stage_curate(self.bank,{'schema_version':1,'changes':[{'table':'questions','id':'q_demo1','set':{'report_exclusion':value},'reason':'User selection'}]})
            commit_run(self.bank,run['run_id'])
        exclude('个人情况，不进入知识题报告')
        self.assertEqual(export_bank(self.bank,'r.md')['questions'],2)
        self.assertEqual(export_bank(self.bank,'r.json','json')['questions'],3)
        exclude(None)
        self.assertEqual(export_bank(self.bank,'r.md')['questions'],3)
        with self.assertRaises(ValidationError): exclude('')

    def test_intro_guard_does_not_drop_technical_topic_mentioning_intro(self):
        for text in ['自我介绍','先做下自我介绍','介绍一下你自己','Please introduce yourself','做一个针对性的自我介绍，侧重架构']:
            self.assertTrue(is_self_introduction(text),text)
        for text in ['如何设计自动生成自我介绍的Agent？','自我介绍生成系统如何设计？','介绍一下 Redis 持久化','你项目中为什么用 LangGraph？']:
            self.assertFalse(is_self_introduction(text),text)
        image=self.base/'fixture.png'; image.write_bytes(b'fixture')
        intake=intake_images(self.bank,[image])
        response={'schema_version':1,'sources':[{'source_id':intake['items'][0]['source']['id'],'status':'extracted','questions':[{'id':'intro','original_text':'自我介绍','sequence':1,'confidence':{'is_question':1,'classification':1}}]}]}
        with self.assertRaisesRegex(ValidationError,'self-introduction'):
            stage_extraction(self.bank,intake['id'],response)
        self.assertFalse(load_data(self.bank)['questions'])

    def test_canonical_merge_rewrites_target_and_preserves_originals(self):
        q=self.bundle['questions'][2]; q.update(canonical='Redis 快的原因有哪些？',normalized=normalize_question_text('Redis 快的原因有哪些？'),domains=['backend.cache'],technologies=['redis'])
        self.seed(); before={o['id']:o['original_text'] for o in load_data(self.bank)['occurrences']}
        task=candidate_task(self.bank,question_ids=['q_demo2'])
        response={'schema_version':1,'task_id':task['id'],'decisions':[{'question_id':'q_demo2','target_id':'q_demo1','action':'MERGE_VARIANT','canonical':'Redis 为什么快？内存访问和数据结构如何影响性能？','confidence':0.97,'reason':'同一性能考点，保留说明要点'}]}
        run=stage_decisions(self.bank,response); commit_run(self.bank,run['run_id'])
        data=load_data(self.bank); target=next(q for q in data['questions'] if q['id']=='q_demo1')
        self.assertEqual(target['canonical'],response['decisions'][0]['canonical'])
        self.assertEqual(before,{o['id']:o['original_text'] for o in data['occurrences']})
        audit=json.loads((self.bank/'runs'/run['run_id']/'run.json').read_text(encoding='utf-8'))['audit']
        self.assertTrue(any(a['action']=='EDIT' and a['id']=='q_demo1' for a in audit))

    def test_canonical_rewrite_cannot_bypass_merge_review(self):
        self.seed(); task=candidate_task(self.bank,question_ids=['q_demo2'])
        with self.assertRaisesRegex(ValidationError,'only allowed'):
            stage_decisions(self.bank,{'schema_version':1,'task_id':task['id'],'decisions':[{'question_id':'q_demo2','action':'KEEP_DISTINCT','canonical':'changed','confidence':1,'reason':'bad'}]})

    def test_filtered_metadata_and_years_are_from_matching_occurrences(self):
        self.seed(); result=export_bank(self.bank,'filtered.md',company='字节',technology='redis')
        text=Path(result['output']).read_text(encoding='utf-8')
        sidecar=json.loads(Path(result['details_output']).read_text(encoding='utf-8'))
        self.assertEqual(result['questions'],1)
        self.assertIn('出现 1 次',text)
        self.assertNotIn('2026-08',text)
        self.assertEqual(len(sidecar['questions'][0]['occurrences']),1)

    def test_sidecar_escape_is_rejected(self):
        self.seed(); exports=self.bank/'exports'; exports.mkdir(exist_ok=True)
        outside=self.base/'outside.json'; outside.write_text('keep',encoding='utf-8')
        try: (exports/'r.md.details.json').symlink_to(outside)
        except OSError: self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValidationError): export_bank(self.bank,'r.md')
        self.assertEqual(outside.read_text(encoding='utf-8'),'keep')
