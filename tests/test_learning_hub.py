"""The learning hub is a disjoint projection, with stable original records and deep links."""
import hashlib
import unittest

from support import Bank
from ibank_core.web import WebApp
from ibank_core.note_organization import LEARNING_KINDS


class LearningHub(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        source = self.bank.root / 'source'
        source.mkdir()
        self.kinds = ('qa', 'knowledge', 'exercise', 'case', 'collection', *LEARNING_KINDS, 'info')
        text = '# 材料\n\n' + '\n\n'.join('## 条目 ' + kind + '\n\n独立原文 ' + kind for kind in self.kinds)
        (source / '01.md').write_text(text, encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(source), '--name', 'first')
        self.ids = {}
        self.organize()

    def organize(self, experiences=None):
        catalog = self.bank.result('notes', 'catalog', '--name', 'first')
        self.ids = {kind: n['id'] for kind, n in zip(self.kinds, catalog['notes'])}
        payload = {'schema_version': 1, 'collection': 'first', 'source_digest': catalog['source_digest'],
                   'organization_digest': catalog['organization_digest'],
                   'notes': {self.ids[k]: {'kind': k} for k in self.kinds}}
        if experiences is not None:
            payload['experiences'] = experiences
        self.bank.result('notes', 'organize', '--name', 'first', payload=payload)

    def test_disjoint_sections_and_legacy_all_preserve_sources(self):
        source = self.bank.path / 'collections/first.json'
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        app = WebApp(self.bank.path, read_only=True)
        knowledge = app.notes({'section': 'knowledge', 'kind': 'study'})
        learning = app.notes({'section': 'learning'})
        self.assertEqual(set(knowledge['ids']), {self.ids[k] for k in self.kinds[:5]})
        self.assertEqual(set(learning['ids']), {self.ids[k] for k in LEARNING_KINDS})
        self.assertFalse(set(knowledge['ids']) & set(learning['ids']))
        self.assertEqual(learning['section_counts'], {'knowledge': 5, 'learning': 5, 'experiences': 0})
        self.assertEqual(app.notes({'kind': 'study'})['total'], 10)
        card = learning['collections'][0]
        self.assertEqual((card['content_total'], card['knowledge_total'], card['learning_total']), (5, 5, 5))
        self.assertEqual(set(card['content_ids']), set(learning['ids']))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original)

    def test_category_source_search_and_deep_link(self):
        app = WebApp(self.bank.path, read_only=True)
        for kind in LEARNING_KINDS:
            with self.subTest(kind=kind):
                found = app.notes({'section': 'learning', 'kind': kind, 'collection': 'first', 'query': '独立原文'})
                self.assertEqual(found['ids'], [self.ids[kind]])
                self.assertEqual(app.notes({'section': 'knowledge', 'kind': kind})['total'], 0)
                self.assertEqual(app.note(self.ids[kind])['section'], 'learning')
                self.assertEqual(app.note(self.ids[kind])['body'], '独立原文 ' + kind)
        self.assertEqual(app.note(self.ids['qa'])['section'], 'knowledge')
        self.assertEqual(app.notes({'section': 'learning', 'kind': 'info'})['total'], 0)
        self.assertEqual([c['kind'] for c in found['learning_categories']], list(LEARNING_KINDS))
        self.assertTrue(all(c['count'] == c['sources'] == 1 for c in found['learning_categories']))
        cli = self.bank.result('notes', 'search', '--query', '独立原文', '--section', 'learning')
        self.assertEqual(cli['total'], 5)

    def test_public_career_members_never_leak_into_learning(self):
        self.organize({'article': {'title': '公开求职经验', 'kind': 'career', 'note_ids': [self.ids['career']]}})
        app = WebApp(self.bank.path, read_only=True)
        learning = app.notes({'section': 'learning'})
        experiences = app.notes({'section': 'experiences'})
        self.assertEqual((learning['total'], experiences['total']), (4, 1))
        self.assertNotIn(self.ids['career'], learning['ids'])
        self.assertEqual(app.note(experiences['ids'][0])['section'], 'experiences')
        self.assertEqual(next(c for c in learning['learning_categories'] if c['kind'] == 'career')['count'], 0)

    def test_directory_counts_kinds_and_retains_scoped_deep_links(self):
        catalog = self.bank.result('notes', 'catalog', '--name', 'first')
        self.bank.result('notes', 'organize', '--name', 'first', payload={
            'schema_version': 1, 'collection': 'first', 'source_digest': catalog['source_digest'],
            'organization_digest': catalog['organization_digest'],
            'areas': [{'id': 'course', 'title': '课程', 'topics': [
                {'id': 'setup', 'title': '环境与准备'}, {'id': 'unused', 'title': '空目录'}]}],
            'chapters': {'01.md': {'area': 'course', 'topic': 'setup'}}})
        app = WebApp(self.bank.path, read_only=True)
        card = app.notes({'section': 'learning'})['collections'][0]
        area = card['areas'][0]
        self.assertEqual(area['count'], 5)
        self.assertEqual(area['kinds'], dict.fromkeys(LEARNING_KINDS, 1))
        self.assertEqual(area['topics'][0]['kinds']['tutorial'], 1)
        self.assertEqual(area['topics'][1]['kinds'], {})
        found = app.notes({'section': 'learning', 'collection': 'first', 'area': 'course',
                           'topic': 'setup', 'kind': 'tutorial', 'meta': '0'})
        self.assertEqual(found['ids'], [self.ids['tutorial']])
        self.assertEqual(app.note(found['ids'][0])['body'], '独立原文 tutorial')
        self.assertNotIn('collections', found)
        self.assertNotIn('kinds', app.notes({'section': 'knowledge'})['collections'][0]['areas'][0])

    def test_empty_hub_keeps_five_categories(self):
        self.organize({'article': {'title': '公开材料汇总', 'kind': 'career',
                                  'note_ids': [self.ids[k] for k in LEARNING_KINDS]}})
        value = WebApp(self.bank.path, read_only=True).notes({'section': 'learning'})
        self.assertEqual(value['total'], 0)
        self.assertTrue(all(c['count'] == c['sources'] == 0 for c in value['learning_categories']))
