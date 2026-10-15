"""Reading continuity is an overlay, never a rewrite of original notes or evidence."""
import copy
import json
import unittest

from support import Bank
from ibank_core import note_organization as organization, note_readings, notes
from ibank_core.errors import BankError
from ibank_core.web import WebApp


class ReadingGroups(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        self.source = self.bank.root / 'source'
        self.source.mkdir()
        self.url = 'https://example.org/guide.md'
        self.text = ('# 缓存学习路线\n\n## 缓存学习路线 · 导读\n\n先读原理。\n\n'
                     '原文：[查看来源](' + self.url + '#L1) · 固定版本：123\n\n'
                     '## 第一步\n\n```python\n# preserve code\nprint(1)\n```\n\n'
                     '原文：[查看来源](' + self.url + '#L10) · 固定版本：123\n\n'
                     '## 第二步\n\n比较 TTL 与失效策略。\n\n'
                     '原文：[查看来源](' + self.url + '#L20) · 固定版本：123\n')
        (self.source / '01.md').write_text(self.text, encoding='utf-8')
        notes.import_collection(self.bank.path, self.source, 'first')
        self.ns = notes.load_notes(self.bank.path)['notes']
        self.ids = [n['id'] for n in self.ns]
        self.original = (self.bank.path / 'collections/first.json').read_bytes()

    def payload(self, **extra):
        catalog = organization.catalog(self.bank.path, 'first')
        return {'schema_version': 1, 'collection': 'first', 'source_digest': catalog['source_digest'],
                'organization_digest': catalog['organization_digest'],
                'chapters': {'01.md': {'kind': 'roadmap'}},
                'reading_groups': {'guide': {'title': '缓存学习路线', 'note_ids': self.ids,
                    'source_url': self.url, 'content_digest': note_readings.digest(self.ns),
                    'reason': '同一原文的导读和两个依次进行的步骤。'}}, **extra}

    def apply(self, payload=None, preview=False):
        return organization.organize(self.bank.path, 'first', payload or self.payload(), preview)

    def test_preview_apply_idempotence_and_original_access(self):
        before = organization.catalog(self.bank.path, 'first')['source_digest']
        self.assertTrue(self.apply(preview=True)['changed'])
        self.assertFalse((self.bank.path / organization.PATH).exists())
        self.assertTrue(self.apply()['changed'])
        saved = (self.bank.path / organization.PATH).read_bytes()
        self.assertFalse(self.apply()['changed'])
        self.assertEqual((self.bank.path / organization.PATH).read_bytes(), saved)
        self.assertEqual(organization.catalog(self.bank.path, 'first')['source_digest'], before)
        self.assertEqual((self.bank.path / 'collections/first.json').read_bytes(), self.original)
        app = WebApp(self.bank.path, read_only=True)
        value = app.notes({'section': 'learning'})
        self.assertEqual(value['ids'], self.ids[:1])
        self.assertEqual(value['section_counts']['learning'], 1)
        self.assertEqual(value['collections'][0]['total'], 3)
        self.assertEqual(value['collections'][0]['learning_total'], 1)
        self.assertEqual(app.notes({})['total'], 3)  # Legacy raw catalog stays intact.
        detail = app.note(self.ids[-1])  # Old bookmarks resolve to the coherent article.
        self.assertEqual(detail['id'], self.ids[0])
        self.assertEqual(detail['title'], '缓存学习路线')
        self.assertLess(detail['body'].index('第一步'), detail['body'].index('第二步'))
        self.assertIn('```python\n# preserve code\nprint(1)\n```', detail['body'])
        self.assertEqual(detail['body'].count('原文：'), 1)
        self.assertEqual(notes.show_note(self.bank.path, self.ids[-1], original=True)['body'], self.ns[-1]['body'])
        cli = self.bank.result('notes', 'show', self.ids[1], '--original')
        self.assertEqual(cli['id'], self.ids[1])

    def test_query_matches_member_body_but_returns_one_reading_unit(self):
        self.apply()
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.notes({'section': 'learning', 'query': '失效策略'})['ids'], self.ids[:1])
        self.assertEqual(notes.search_notes(self.bank.path, '失效策略', section='learning')['notes'][0]['id'], self.ids[0])
        self.assertEqual(app.notes({'section': 'knowledge'})['total'], 0)

    def test_invalid_group_does_not_partially_write(self):
        self.apply()
        path = self.bank.path / organization.PATH
        before = path.read_bytes()
        for field, value in [('source_url', 'https://other.org/page'), ('note_ids', [self.ids[0]]),
                             ('note_ids', [*self.ids, self.ids[0]]), ('note_ids', ['missing', self.ids[0]]),
                             ('content_digest', 'stale'), ('reason', '')]:
            payload = self.payload()
            payload['reading_groups']['guide'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(BankError):
                self.apply(payload)
            self.assertEqual(path.read_bytes(), before)
        payload = self.payload()
        payload['reading_groups']['duplicate'] = copy.deepcopy(payload['reading_groups']['guide'])
        with self.assertRaises(BankError):
            self.apply(payload)
        self.assertEqual(path.read_bytes(), before)

    def test_info_mixed_classification_protected_and_public_members_are_rejected(self):
        for patch in ({'kind': 'info'}, {'kind': 'qa'}, {'locked': True, 'user_quote': '保留原分类'}):
            with self.subTest(patch=patch), self.assertRaises(BankError):
                self.apply(self.payload(notes={self.ids[-1]: patch}))
        with self.assertRaises(BankError):
            self.apply(self.payload(experiences={'public': {'title': '公开面经', 'kind': 'career', 'note_ids': self.ids[:1]}}))
        notes.import_collection(self.bank.path, self.source, 'second')
        other = next(c for c in notes.load_notes(self.bank.path)['collections'] if c['name'] == 'second')['notes'][0]['id']
        payload = self.payload()
        payload['reading_groups']['guide']['note_ids'][1] = other
        with self.assertRaises(BankError):
            self.apply(payload)

    def test_stale_group_fails_open_and_uncovered_source_segments_are_visible(self):
        self.apply()
        (self.source / '01.md').write_text(self.text.replace('先读原理。', '新的导读。'), encoding='utf-8')
        notes.import_collection(self.bank.path, self.source, 'first')
        app = WebApp(self.bank.path, read_only=True)
        value = app.notes({'section': 'learning'})
        self.assertEqual(value['total'], 3)
        self.assertEqual(value['reading_groups_incomplete'], 1)
        self.assertNotIn('reading', app.note(self.ids[0]))
        payload = self.payload()
        payload['reading_groups'] = {'guide': None}
        self.apply(payload)
        self.assertEqual(WebApp(self.bank.path, read_only=True).notes({'section': 'learning'})['reading_groups_incomplete'], 0)

    def test_weakest_verification_is_retained_and_does_not_promote_content(self):
        self.apply(self.payload(notes={self.ids[0]: {'verification': 'verified', 'evidence': ['https://example.org/proof']},
                                     self.ids[2]: {'verification': 'needs_review'}}))
        detail = WebApp(self.bank.path, read_only=True).note(self.ids[0])
        self.assertEqual(detail['verification'], 'needs_review')
        self.assertEqual(detail['evidence'], ['https://example.org/proof'])

    def test_removing_group_restores_all_individual_entries(self):
        self.apply()
        self.apply(self.payload(reading_groups={'guide': None}))
        self.assertEqual(WebApp(self.bank.path, read_only=True).notes({'section': 'learning'})['ids'], self.ids)
        self.assertEqual((self.bank.path / 'collections/first.json').read_bytes(), self.original)

    def test_backup_restores_group_and_source(self):
        self.apply()
        archive = self.bank.result('backup', 'create')['archive']
        target = self.bank.root / 'restored'
        self.bank.result('backup', 'restore', '--archive', archive, '--destination', str(target))
        self.assertEqual(WebApp(target, read_only=True).notes({'section': 'learning'})['ids'], self.ids[:1])
        self.assertEqual((target / 'collections/first.json').read_bytes(), self.original)
        self.assertEqual(json.loads((target / organization.PATH).read_text(encoding='utf-8'))['collections']['first']['reading_groups'],
                         organization.catalog(self.bank.path, 'first')['reading_groups'])

    def test_display_title_is_an_overlay_with_verbatim_cli_access(self):
        self.apply(self.payload(reading_groups={}, notes={self.ids[1]: {'display_title': '缓存路线 · 第一步'}}))
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.note(self.ids[1])['title'], '缓存路线 · 第一步')
        self.assertEqual(app.notes({'section': 'learning', 'query': '缓存路线'})['ids'], self.ids[1:2])
        self.assertEqual(notes.show_note(self.bank.path, self.ids[1], original=True)['title'], '第一步')
        self.assertEqual((self.bank.path / 'collections/first.json').read_bytes(), self.original)

    def test_personal_and_public_evidence_aggregate_without_rewriting_edges(self):
        (self.source / '01.md').write_text(self.text + '\n## 公开面试\n\n比较 TTL 与失效策略。\n', encoding='utf-8')
        notes.import_collection(self.bank.path, self.source, 'first')
        public = notes.load_notes(self.bank.path)['notes'][-1]['id']
        quote = '比较 TTL 与失效策略。'
        edges = {'one': {'from_note': public, 'to_note': self.ids[-1], 'relation': 'covers',
                         'question_quote': quote, 'answer_quote': quote, 'reason': '同一问题的原文说明。'}}
        self.apply(self.payload(experiences={'interview': {'title': '公开面试', 'kind': 'interview', 'note_ids': [public]}},
                                study_links=edges))
        self.bank.add_questions('database', '缓存 TTL 与失效策略如何选择？')
        task = self.bank.result('notes', 'link-candidates')
        qid = json.loads(__import__('pathlib').Path(task['task_file']).read_text(encoding='utf-8'))['items'][0]['question']['id']
        self.bank.result('notes', 'link', payload={'task_id': task['task_id'], 'links': [
            {'question_id': qid, 'note_id': i, 'relation': 'covers', 'reason': '原文解释失效策略。'} for i in self.ids[1:]]})
        before = (self.bank.path / 'collections/links.jsonl').read_bytes()
        app = WebApp(self.bank.path, read_only=True)
        article = app.notes({'section': 'experiences'})['ids'][0]
        self.assertEqual(app.note(article)['study_notes'][0]['id'], self.ids[0])
        self.assertEqual(app.note(self.ids[1])['public_experiences'][0]['id'], article)
        self.assertEqual(len(app.note(self.ids[2])['questions']), 1)
        self.assertEqual(app.notes({'section': 'learning'})['collections'][0]['linked'], 1)
        self.assertEqual([n['id'] for n in app.question(qid)['notes']], self.ids[:1])
        self.assertEqual((self.bank.path / 'collections/links.jsonl').read_bytes(), before)
        self.assertEqual(organization.catalog(self.bank.path, 'first')['study_links'], edges)
