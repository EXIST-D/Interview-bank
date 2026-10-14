"""Public interview views preserve provenance and private question frequency."""
import unittest

from support import Bank
from ibank_core.web import WebApp


class PublicExperienceTests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        self.source = self.bank.root / 'public'
        self.source.mkdir()
        (self.source / '01.md').write_text(
            '# 示例公司面试\n\n## 示例公司 后端一面（2026-02-10）\n\n缓存穿透如何处理？\n\n'
            '## 复盘\n\n布隆过滤器有假阳性。\n\n## Redis 知识\n\nRedis 是内存数据库。\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'public')
        catalog = self.bank.result('notes', 'catalog', '--name', 'public')
        self.ids = [n['id'] for n in catalog['notes']]
        self.article = {'title': '示例公司后端一面与复盘', 'kind': 'interview',
                        'note_ids': self.ids[:2], 'company': '示例公司', 'role': '后端', 'round': '一面',
                        'interview_time': '2026-02-10', 'summary': '缓存问题与复盘。',
                        'facts': [{'field': field, 'quote': '示例公司 后端一面（2026-02-10）', 'note_id': self.ids[0]}
                                  for field in ('company', 'role', 'round', 'interview_time')]}

    def payload(self, experiences=None):
        catalog = self.bank.result('notes', 'catalog', '--name', 'public')
        return {'schema_version': 1, 'collection': 'public', 'source_digest': catalog['source_digest'],
                'organization_digest': catalog['organization_digest'],
                'experiences': {'first': self.article} if experiences is None else experiences}

    def apply(self, payload=None):
        return self.bank.result('notes', 'organize', '--name', 'public', payload=payload or self.payload())

    def test_article_projection_excludes_fragments_from_knowledge_and_preserves_originals(self):
        original = (self.bank.path / 'collections/public.json').read_bytes()
        self.apply()
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.notes({})['total'], 3)
        self.assertEqual(app.notes({'section': 'knowledge'})['ids'], self.ids[2:])
        result = app.notes({'section': 'experiences', 'company': '示例公司', 'year': '2026'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['collections'][0]['experience_member_total'], 2)
        self.assertEqual(result['collections'][0]['knowledge_total'], 1)
        note = app.note(result['ids'][0])
        self.assertIn('缓存穿透如何处理', note['body'])
        self.assertIn('布隆过滤器有假阳性', note['body'])
        self.assertEqual(note['experience']['year'], '2026')
        self.assertEqual(self.bank.result('notes', 'show', result['ids'][0])['body'], note['body'])
        self.assertEqual(original, (self.bank.path / 'collections/public.json').read_bytes())
        self.assertEqual(app.note(self.ids[0])['title'], '示例公司 后端一面（2026-02-10）')

    def test_invalid_fields_evidence_and_cross_source_ids_leave_no_partial_write(self):
        self.apply()
        path = self.bank.path / 'collections/_organization.json'
        original = path.read_bytes()
        invalid = [
            {'company': '伪造公司'}, {'facts': []}, {'note_ids': ['missing']}, {'kind': 'qa'},
            {'extra': 'no'}, {'note_ids': [self.ids[0], self.ids[0]]},
            {'facts': [{'field': 'company', 'quote': '伪造公司', 'note_id': self.ids[0]}]},
            {'kind': 'company_questions'},
            {'facts': [{'field': 'company', 'quote': '示例公司', 'url': 'javascript:alert(1)'}]},
        ]
        for change in invalid:
            with self.subTest(change=change):
                bad = self.payload({'first': {**self.article, **change}})
                result = self.bank.cli('notes', 'organize', '--name', 'public', payload=bad, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(original, path.read_bytes())
        result = self.bank.cli('notes', 'organize', '--name', 'public',
                               payload=self.payload({'first': self.article, 'duplicate': self.article}), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(original, path.read_bytes())

    def test_missing_year_is_not_fabricated_and_publication_is_separate(self):
        self.article.update(interview_time='', published_time='2026-10-13')
        self.article['facts'] = [f for f in self.article['facts'] if f['field'] != 'interview_time'] + [
            {'field': 'published_time', 'quote': '发布时间：2026-10-13', 'url': 'https://example.org/post'}]
        self.apply()
        app = WebApp(self.bank.path, read_only=True)
        result = app.notes({'section': 'experiences', 'year': 'unknown'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['notes'][0]['experience']['year'], '')
        self.assertEqual(app.notes({'section': 'experiences', 'year': '2026'})['total'], 0)
        self.assertEqual(result['facets']['years'], [])

    def test_search_scope_source_isolation_idempotence_and_removal(self):
        self.apply()
        first_id = WebApp(self.bank.path).notes({'section': 'experiences'})['ids'][0]
        self.assertFalse(self.apply()['changed'])
        result = self.bank.result('notes', 'search', '--query', '假阳性', '--section', 'experiences')
        self.assertEqual(result['notes'][0]['id'], first_id)
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'second')
        second = self.bank.result('notes', 'catalog', '--name', 'second')
        bad = {'schema_version': 1, 'collection': 'second', 'source_digest': second['source_digest'],
               'organization_digest': second['organization_digest'], 'experiences': {'bad': self.article}}
        self.assertNotEqual(self.bank.cli('notes', 'organize', '--name', 'second', payload=bad, check=False).returncode, 0)
        self.apply(self.payload({'first': None}))
        self.assertEqual(WebApp(self.bank.path).notes({'section': 'knowledge'})['total'], 6)
        self.assertEqual(WebApp(self.bank.path).notes({'section': 'experiences'})['total'], 0)

    def test_legacy_and_backup_round_trip(self):
        self.assertEqual(WebApp(self.bank.path).notes({'section': 'experiences'})['total'], 0)
        self.apply()
        backup = self.bank.result('backup', 'create')['archive']
        restored = self.bank.root / 'restored'
        self.bank.result('backup', 'restore', '--archive', backup, '--destination', str(restored))
        before = WebApp(self.bank.path).notes({'section': 'experiences'})
        after = WebApp(restored).notes({'section': 'experiences'})
        self.assertEqual(before, after)

    def test_aggregate_links_deduplicate_without_changing_frequency(self):
        from ibank_core.note_experiences import linked
        question = {'id': 'q', 'frequency': 9}
        links = {self.ids[0]: [(question, {'relation': 'covers'})],
                 self.ids[1]: [(question, {'relation': 'answers'})]}
        result = linked({'experience': {'note_ids': self.ids[:2]}}, links)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0]['frequency'], 9)
        self.assertEqual(result[0][1]['relation'], 'answers')

    def test_changed_source_marks_incomplete_article(self):
        self.apply()
        (self.source / '01.md').write_text('# 示例公司面试\n\n## 示例公司 后端一面（2026-02-10）\n\n缓存问题。\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'public')
        result = WebApp(self.bank.path).notes({'section': 'experiences'})
        self.assertTrue(result['collections'][0]['organization_stale'])
        self.assertTrue(result['notes'][0]['experience']['incomplete'])
        self.assertEqual(result['notes'][0]['verification'], 'needs_review')

    def test_reject_invalid_section_year_and_company_scope(self):
        self.apply()
        app = WebApp(self.bank.path)
        for params in ({'section': 'private'}, {'year': '2026'}, {'company': '示例公司'},
                       {'section': 'experiences', 'year': '26'}, {'sort': 'recent'},
                       {'experience_domain': 'backend'}, {'section': 'experiences', 'experience_domain': 'missing'},
                       {'sort': 'domain'}):
            with self.subTest(params=params), self.assertRaises(Exception):
                app.notes(params)
        self.assertEqual(app.notes({'section': 'experiences', 'sort': 'recent'})['total'], 1)

    def test_global_domain_and_year_catalogue_preserves_source_and_article_ids(self):
        self.apply()
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'second')
        catalog = self.bank.result('notes', 'catalog', '--name', 'second')
        ids = [n['id'] for n in catalog['notes']]
        article = {**self.article, 'note_ids': ids[:2], 'facts': [
            {**fact, 'note_id': ids[0]} for fact in self.article['facts']]}
        self.bank.result('notes', 'organize', '--name', 'second', payload={
            'schema_version': 1, 'collection': 'second', 'source_digest': catalog['source_digest'],
            'organization_digest': catalog['organization_digest'], 'experiences': {'first': article}})
        app = WebApp(self.bank.path, read_only=True)
        data = app.notes({'section': 'experiences', 'experience_domain': 'backend', 'year': '2026', 'sort': 'domain'})
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['facets']['experience_domains'], {'backend': 2})
        self.assertEqual(data['facets']['experience_years'], {'2026': 2})
        self.assertEqual({n['collection'] for n in data['notes']}, {'public', 'second'})
        self.assertEqual(len(set(data['ids'])), 2)
        self.assertTrue(all(n['experience']['domain_basis'] == 'title_role' for n in data['notes']))
        self.assertEqual(app.notes({'section': 'experiences', 'collection': 'public'})['total'], 1)
        self.assertEqual(app.note(data['ids'][0])['source']['collection'], data['notes'][0]['collection_title'])


class ExperienceNavigationTests(unittest.TestCase):
    def test_topics_prefer_headings_and_do_not_guess_from_one_keyword(self):
        from ibank_core.note_experiences import domain
        cases = [
            ('Agent开发一面', '', 'Redis MySQL JVM', 'agent', 'title_role'),
            ('Java后端一面', '后端', 'LangGraph RAG MCP', 'backend', 'title_role'),
            ('多模态大模型算法', '', '', 'multimodal', 'title_role'),
            ('AI 全栈实习', '', '', 'fullstack', 'title_role'),
            ('某公司一面', '', 'Redis 缓存 MySQL', 'backend', 'body'),
            ('某公司一面', '', '聊了一次 Redis。', 'other', 'unspecified'),
            ('某公司一面', '', '候选人谈了自己的经历。', 'other', 'unspecified'),
        ]
        for title, role, body, expected, basis in cases:
            with self.subTest(title=title):
                self.assertEqual(domain(title, role, body), (expected, basis))
        self.assertEqual(domain('Java备考经验', '', '', 'career'), ('career', 'kind'))

    def test_partial_dates_and_unknown_year_keep_original_precision(self):
        from ibank_core.note_experiences import date_key
        def key(value, year):
            return date_key({'experience': {'interview_time': value, 'year': year}})
        self.assertEqual(key('26年2月初', '2026'), ('2026', 2, 0))
        self.assertEqual(key('2026 年 8 月 22 日', '2026'), ('2026', 8, 22))
        self.assertEqual(key('2026-09-01', '2026'), ('2026', 9, 1))
        self.assertEqual(key('7.6', ''), ('', 0, 0))
        self.assertGreater(key('2026-09-01', '2026'), key('2026 年 8 月 22 日', '2026'))


if __name__ == '__main__':
    unittest.main()
