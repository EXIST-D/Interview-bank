"""Source-local semantic associations have evidence, stale handling and independent counts."""
import copy
import json
import unittest

from support import Bank
from ibank_core import note_organization as organization
from ibank_core.web import WebApp


class NoteRelationTests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        self.source = self.bank.root / 'public'
        self.source.mkdir()
        self.path = self.source / '01.md'
        self.path.write_text('# 来源\n\n## 某公司后端一面\n\n缓存穿透如何防止？\n\n'
                             '## 布隆过滤器\n\n用布隆过滤器拦截不存在的键，但须处理误判与更新。\n\n'
                             '## 来源信息\n\n仅用于来源说明。\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'first')
        self.ids = [n['id'] for n in organization.catalog(self.bank.path, 'first')['notes']]
        self.edge = {'from_note': self.ids[0], 'to_note': self.ids[1], 'relation': 'covers',
                     'question_quote': '缓存穿透如何防止？', 'answer_quote': '用布隆过滤器拦截不存在的键，但须处理误判与更新。',
                     'reason': '解释拦截不存在的键这一措施及误判边界。'}

    def payload(self, **extra):
        catalog = organization.catalog(self.bank.path, 'first')
        return {'schema_version': 1, 'collection': 'first', 'source_digest': catalog['source_digest'],
                'organization_digest': catalog['organization_digest'],
                'notes': {self.ids[1]: {'kind': 'knowledge', 'question_type': 'concept'},
                          self.ids[2]: {'kind': 'info', 'question_type': 'reference'}},
                'experiences': {'interview': {'title': '某公司后端一面', 'kind': 'interview',
                                             'note_ids': [self.ids[0]]}},
                'study_links': {'bloom': self.edge}, **extra}

    def apply(self, payload=None, preview=False):
        return organization.organize(self.bank.path, 'first', payload or self.payload(), preview)

    def test_preview_projection_bidirectional_links_and_immutable_source_digest(self):
        raw = (self.bank.path / 'collections/first.json').read_bytes()
        digest = self.payload()['source_digest']
        self.assertTrue(self.apply(preview=True)['changed'])
        self.assertFalse((self.bank.path / 'collections/_organization.json').exists())
        self.apply()
        app = WebApp(self.bank.path, read_only=True)
        article = app.notes({'section': 'experiences'})['notes'][0]
        note = app.note(self.ids[1])
        self.assertEqual(article['study_note_count'], 1)
        self.assertEqual(app.note(article['id'])['study_notes'][0]['id'], self.ids[1])
        self.assertEqual(note['public_experiences'][0]['id'], article['id'])
        self.assertEqual(note['public_experiences'][0]['question_quote'], self.edge['question_quote'])
        self.assertEqual(app.notes({'section': 'knowledge', 'kind': 'study'})['ids'], self.ids[1:2])
        self.assertEqual(app.notes({})['summary'], {'notes': 3, 'marked': 0, 'asked': 0})
        self.assertEqual(organization.catalog(self.bank.path, 'first')['source_digest'], digest)
        self.assertEqual(raw, (self.bank.path / 'collections/first.json').read_bytes())
        self.assertFalse(self.apply()['changed'])

    def test_invalid_quotes_targets_fields_types_and_duplicate_edges_are_atomic(self):
        self.apply()
        path = self.bank.path / 'collections/_organization.json'
        before = path.read_bytes()
        invalid = [{'to_note': self.ids[0]}, {'to_note': self.ids[2]}, {'to_note': 'unknown'},
                   {'from_note': self.ids[1]}, {'relation': 'similar'}, {'question_quote': '缓存'},
                   {'answer_quote': '这是不存在于原文中的语句'}, {'reason': ''}, {'extra': 'unknown'},
                   {'from_note': []}, {'answer_quote': 12}]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(Exception):
                self.apply(self.payload(study_links={'bloom': {**self.edge, **change}}))
            self.assertEqual(path.read_bytes(), before)
        for patch in ({'another': self.edge}, {'BAD KEY': self.edge}):
            with self.assertRaises(Exception):
                self.apply(self.payload(study_links=patch))
            self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(Exception):
            self.apply(self.payload(notes={self.ids[1]: {'question_type': 'guessed'}}))
        self.assertEqual(path.read_bytes(), before)

    def test_filters_have_independent_personal_and_public_meanings(self):
        self.apply()
        self.bank.add_questions('database', '如何防止缓存穿透？')
        task = self.bank.result('notes', 'link-candidates')
        packet = json.loads(__import__('pathlib').Path(task['task_file']).read_text(encoding='utf-8'))
        qid = packet['items'][0]['question']['id']
        self.bank.result('notes', 'link', payload={'task_id': task['task_id'], 'links': [
            {'question_id': qid, 'note_id': self.ids[1], 'relation': 'covers', 'reason': '缓存措施'}]})
        app = WebApp(self.bank.path, read_only=True)
        notes = app.notes({'section': 'knowledge', 'kind': 'study', 'question_type': 'concept', 'connection': 'public'})
        self.assertEqual(notes['ids'], self.ids[1:2])
        self.assertEqual(notes['notes'][0]['asked'], 1)
        self.assertEqual(notes['collections'][0]['study_links'], 1)
        self.assertEqual(notes['collections'][0]['linked'], 1)
        self.assertEqual(notes['collections'][0]['public_linked'], 1)
        self.assertEqual(app.notes({'section': 'experiences', 'connection': 'public'})['total'], 1)
        self.assertEqual(app.notes({'section': 'experiences', 'connection': 'personal'})['total'], 0)
        self.assertEqual(app.notes({'section': 'knowledge', 'connection': 'none', 'kind': 'study'})['total'], 0)
        self.assertEqual(app.note(self.ids[1])['questions'][0]['frequency'], 1)
        self.assertEqual(app.notes({'section': 'experiences', 'question_type': 'concept'})['total'], 0)
        for params in ({'question_type': 'unknown'}, {'connection': 'unknown'}):
            with self.assertRaises(Exception):
                app.notes(params)

    def test_source_changes_hide_stale_evidence_and_require_explicit_reconciliation(self):
        self.apply()
        self.path.write_text(self.path.read_text(encoding='utf-8').replace('用布隆过滤器拦截不存在的键，但须处理误判与更新。',
                                                                            '更新后的正文。'), encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'first')
        app = WebApp(self.bank.path)
        self.assertEqual(app.note(self.ids[1])['public_experiences'], [])
        self.assertEqual(app.note(self.ids[1])['study_links_incomplete'], 1)
        self.assertTrue(app.notes({})['collections'][0]['organization_stale'])
        self.assertEqual(app.notes({'connection': 'public'})['total'], 0)
        with self.assertRaises(Exception):
            self.apply(self.payload())
        self.apply(self.payload(study_links={'bloom': None}))
        self.assertEqual(app.notes({})['collections'][0]['study_links_incomplete'], 0)

    def test_no_cross_source_links_and_article_removal_requires_unlink(self):
        self.apply()
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'second')
        other = organization.catalog(self.bank.path, 'second')['notes'][1]['id']
        with self.assertRaises(Exception):
            self.apply(self.payload(study_links={'bloom': {**self.edge, 'to_note': other}}))
        with self.assertRaises(Exception):
            self.apply(self.payload(experiences={'interview': None}))
        self.apply(self.payload(experiences={'interview': None}, study_links={'bloom': None}))
        self.assertEqual(WebApp(self.bank.path).notes({'section': 'experiences'})['total'], 0)

    def test_cli_backup_round_trip_and_optimistic_concurrency(self):
        payload = self.payload()
        self.bank.result('notes', 'organize', '--name', 'first', payload=payload)
        with self.assertRaises(Exception):
            self.apply(payload)
        expected = self.bank.result('notes', 'show', self.ids[1])
        backup = self.bank.result('backup', 'create')['archive']
        destination = self.bank.root / 'restored'
        self.bank.result('backup', 'restore', '--archive', backup, '--destination', str(destination))
        self.assertEqual(WebApp(destination).note(self.ids[1])['public_experiences'], expected['public_experiences'])
        self.assertEqual(organization.catalog(destination, 'first')['study_links'], {'bloom': self.edge})

    def test_legacy_banks_have_empty_typed_and_relationship_fields(self):
        note = WebApp(self.bank.path).note(self.ids[1])
        self.assertEqual(note['question_type'], '')
        self.assertEqual(note['public_experiences'], [])
        self.assertEqual(note['study_notes'], [])
        self.assertEqual(note['study_links_incomplete'], 0)
        self.assertEqual(WebApp(self.bank.path).notes({'connection': 'none'})['total'], 3)

    def test_chapter_inheritance_and_study_link_patch_preserve_other_edges(self):
        self.apply()
        extra = {**self.edge, 'question_quote': '缓存穿透如何防止？', 'relation': 'answers'}
        payload = self.payload(study_links={'bloom': extra}, notes={self.ids[1]: {'question_type': ''}},
                               chapters={'01.md': {'question_type': 'implementation'}})
        self.apply(payload)
        catalog = organization.catalog(self.bank.path, 'first')
        self.assertEqual(catalog['notes'][0]['classification']['question_type'], 'implementation')
        self.assertEqual(catalog['notes'][1]['classification']['question_type'], '')
        original = copy.deepcopy(catalog['study_links'])
        self.apply(self.payload(study_links={}, notes={}))
        self.assertEqual(organization.catalog(self.bank.path, 'first')['study_links'], original)


if __name__ == '__main__':
    unittest.main()
