"""Navigation overlays must preserve source content, links and protected human choices."""
import hashlib
import json
import unittest

from support import Bank
from ibank_core.web import WebApp


class NotesOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        self.source = self.bank.root / 'source'
        self.source.mkdir()
        (self.source / '01.md').write_text('# Redis\n\n## 缓存穿透？\n\n布隆过滤器。\n\n## TTL 是什么？\n\n过期时间。\n', encoding='utf-8')
        (self.source / '02.md').write_text('# 资料信息\n\n## 来源说明\n\nExample reference.\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'first')

    def payload(self, **extra):
        catalog = self.bank.result('notes', 'catalog', '--name', 'first')
        return {'schema_version': 1, 'collection': 'first', 'source_digest': catalog['source_digest'],
                'organization_digest': catalog['organization_digest'],
                'areas': [{'id': 'storage', 'title': '数据存储', 'topics': [{'id': 'redis', 'title': 'Redis'}]}],
                'metadata': {'description': 'Redis 学习资料', 'homepage': 'https://example.org/guide', 'language': 'zh-CN'},
                'chapters': {'01.md': {'area': 'storage', 'topic': 'redis', 'kind': 'qa', 'tags': ['Redis']},
                             '02.md': {'kind': 'info'}}, **extra}

    def apply(self, payload=None, *args):
        return self.bank.result('notes', 'organize', '--name', 'first', *args, payload=payload or self.payload())

    def test_preview_and_apply_preserve_source_and_ids(self):
        original = (self.bank.path / 'collections/first.json').read_bytes()
        before = self.bank.result('notes', 'catalog', '--name', 'first')
        value = self.payload()
        self.assertTrue(self.apply(value, '--preview')['preview'])
        self.assertFalse((self.bank.path / 'collections/_organization.json').exists())
        self.assertTrue(self.apply(value)['changed'])
        after = self.bank.result('notes', 'catalog', '--name', 'first')
        self.assertEqual(before['source_digest'], after['source_digest'])
        self.assertEqual([n['id'] for n in before['notes']], [n['id'] for n in after['notes']])
        self.assertEqual((self.bank.path / 'collections/first.json').read_bytes(), original)
        self.assertEqual(after['notes'][0]['classification']['topic'], 'redis')
        self.assertEqual(after['notes'][0]['classification']['verification'], 'reference')

    def test_stale_metadata_and_source_are_rejected(self):
        old = self.payload()
        self.apply(old)
        failed = self.bank.cli('notes', 'organize', '--name', 'first', payload=old, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('Organization changed', failed.stdout + failed.stderr)
        latest = self.payload()
        (self.source / '01.md').write_text('# Redis\n\n## 新问题\n\n新的正文。\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'first')
        failed = self.bank.cli('notes', 'organize', '--name', 'first', payload=latest, check=False)
        self.assertIn('Source changed', failed.stdout + failed.stderr)

    def test_idempotence_and_update_history(self):
        self.apply()
        path = self.bank.path / 'collections/_organization.json'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertFalse(self.apply()['changed'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        catalog = self.bank.result('notes', 'catalog', '--name', 'first')
        change = self.payload(notes={catalog['notes'][0]['id']: {'tags': ['Redis', '缓存']}})
        self.apply(change)
        self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['collections']['first']['history']), 2)

    def test_source_isolation_and_scoped_search(self):
        self.apply()
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'second')
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.notes({'query': '布隆'})['total'], 2)
        result = app.notes({'collection': 'first', 'area': 'storage', 'topic': 'redis', 'query': '布隆'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['notes'][0]['collection'], 'first')
        self.assertEqual(app.notes({'tag': 'Redis', 'kind': 'study'})['total'], 2)
        self.assertEqual(app.notes({'kind': 'info'})['total'], 1)
        self.assertEqual(app.notes({'collection': 'first', 'verification': 'verified'})['total'], 0)
        self.assertEqual(app.notes({'collection': 'first', 'view': 'knowledge'})['notes'][0]['area_title'], '数据存储')
        source = next(c for c in result['collections'] if c['name'] == 'first')
        self.assertEqual((source['content_total'], source['information_total']), (2, 1))
        self.assertEqual(source['areas'][0]['topics'][0]['count'], 2)
        self.assertEqual(source['metadata']['language'], 'zh-CN')

    def test_invalid_input_has_no_partial_write(self):
        self.apply()
        path = self.bank.path / 'collections/_organization.json'
        original = path.read_bytes()
        catalog = self.bank.result('notes', 'catalog', '--name', 'first')
        note = catalog['notes'][0]['id']
        bad_changes = [
            {'metadata': {'homepage': 'javascript:alert(1)'}},
            {'metadata': {'homepage': 'https://user:password@example.org/'}},
            {'metadata': {'invented': 'unknown'}},
            {'chapters': {'missing.md': {}}},
            {'chapters': {'01.md': {'area': 'unknown'}}},
            {'chapters': {'01.md': {'area': '', 'topic': 'redis'}}},
            {'notes': {'missing_note': {'kind': 'qa'}}},
            {'notes': {note: {'verification': 'verified'}}},
            {'notes': {note: {'tags': ['Redis', 'Redis']}}},
            {'notes': {note: {'locked': True}}},
        ]
        for extra in bad_changes:
            with self.subTest(extra=extra):
                failed = self.bank.cli('notes', 'organize', '--name', 'first', payload=self.payload(**extra), check=False)
                self.assertNotEqual(failed.returncode, 0)
                self.assertEqual(path.read_bytes(), original)

    def test_learning_content_kinds_are_explicit_and_do_not_change_source(self):
        original = (self.bank.path / 'collections/first.json').read_bytes()
        note = self.bank.result('notes', 'catalog', '--name', 'first')['notes'][0]['id']
        for kind in ('roadmap', 'tutorial', 'exercise', 'resource', 'career', 'news', 'collection'):
            with self.subTest(kind=kind):
                self.apply(self.payload(notes={note: {'kind': kind, 'question_type': 'reference'}}))
                app = WebApp(self.bank.path, read_only=True)
                value = app.notes({'collection': 'first', 'section': 'knowledge', 'kind': kind})
                self.assertEqual(value['total'], 1)
                self.assertEqual(value['notes'][0]['id'], note)
                self.assertEqual(value['notes'][0]['kind'], kind)
                self.assertEqual(app.notes({'collection': 'first', 'kind': 'qa'})['total'], 1)
                self.assertEqual(app.notes({'collection': 'first', 'kind': 'study'})['total'], 2)
                self.assertEqual(value['facets']['kinds'][kind], 1)
                self.assertEqual((self.bank.path / 'collections/first.json').read_bytes(), original)

    def test_protected_choice_requires_explicit_user_words(self):
        note = self.bank.result('notes', 'catalog', '--name', 'first')['notes'][0]['id']
        self.apply(self.payload(notes={note: {'tags': ['我选的标签'], 'locked': True, 'user_quote': '请保留这个分类。'}}))
        bad = self.payload(notes={note: {'tags': ['自动替换']}})
        result = self.bank.cli('notes', 'organize', '--name', 'first', payload=bad, check=False)
        self.assertIn('protected', result.stdout + result.stderr)
        good = self.payload(notes={note: {'tags': ['新标签'], 'user_quote': '请将标签改为新标签。'}})
        self.apply(good)
        self.assertEqual(self.bank.result('notes', 'show', note)['tags'], ['新标签'])

    def test_verification_evidence_and_backup_roundtrip(self):
        note = self.bank.result('notes', 'catalog', '--name', 'first')['notes'][0]['id']
        self.apply(self.payload(notes={note: {'verification': 'verified', 'evidence': ['https://redis.io/docs/']}}))
        archive = self.bank.result('backup', 'create')['archive']
        restored = self.bank.root / 'restored'
        self.bank.result('backup', 'restore', '--archive', archive, '--destination', str(restored))
        self.assertEqual((restored / 'collections/_organization.json').read_bytes(),
                         (self.bank.path / 'collections/_organization.json').read_bytes())
        self.assertEqual(WebApp(restored, read_only=True).notes({'verification': 'verified'})['total'], 1)

    def test_protected_chapter_cannot_be_bypassed_by_a_note_override(self):
        value = self.payload()
        value['chapters']['01.md'].update(locked=True, user_quote='请保留本章的分类。')
        self.apply(value)
        note = self.bank.result('notes', 'catalog', '--name', 'first')['notes'][0]['id']
        for change in ({'tags': ['绕过章节']}, {'locked': False}):
            value = self.payload(notes={note: change})
            value.pop('chapters')
            result = self.bank.cli('notes', 'organize', '--name', 'first', payload=value, check=False)
            self.assertIn('protected', result.stdout + result.stderr)
        value['notes'][note]['user_quote'] = '请解除这条资料的分类保护。'
        self.apply(value)
        self.assertFalse(self.bank.result('notes', 'show', note)['locked'])

    def test_reimport_retains_metadata_and_marks_changed_source(self):
        self.apply()
        note = self.bank.result('notes', 'catalog', '--name', 'first')['notes'][0]['id']
        (self.source / '01.md').write_text('# Redis\n\n## 缓存穿透？\n\n修改后的正文。\n', encoding='utf-8')
        self.bank.result('notes', 'import', '--source', str(self.source), '--name', 'first')
        card = WebApp(self.bank.path, read_only=True).notes({})['collections'][0]
        self.assertTrue(card['organization_stale'])
        self.assertEqual(self.bank.result('notes', 'show', note)['area'], 'storage')
        self.apply()
        self.assertFalse(WebApp(self.bank.path, read_only=True).notes({})['collections'][0]['organization_stale'])


if __name__ == '__main__':
    unittest.main()
