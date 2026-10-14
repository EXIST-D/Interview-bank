"""Candidate retrieval stays bounded on a large library and preserves study matches."""
import unittest
import json
from unittest.mock import patch

import support  # noqa: F401 -- establishes the installed Skill import path
from ibank_core.notes import _profile, _rank_candidates


class CandidateScaleTests(unittest.TestCase):
    def test_large_source_reads_only_shortlisted_bodies_and_ranks_core_question(self):
        notes = [{'id': str(i), 'title': 'unrelated topic ' + str(i), 'order': i} for i in range(2000)]
        target = {'id': 'redis', 'title': 'Redis 缓存与数据库双写一致性如何保证？', 'order': 2001}
        notes.append(target)
        reads = []
        def body(note_id):
            reads.append(note_id)
            return _profile('先更新数据库再删除缓存，失败需重试与补偿。')
        result = _rank_candidates(_profile('Redis 缓存和数据库双写一致性如何保证？'),
                                  [(n, _profile(n['title'])) for n in notes], 6, body)
        self.assertEqual(result[0][1]['id'], 'redis')
        self.assertLessEqual(len(reads), 72)
        self.assertEqual(len(result), 6)

    def test_small_source_includes_body_signal_and_stable_order(self):
        notes = [{'id': str(i), 'title': '缓存处理策略', 'order': i} for i in range(5)]
        profiles = [(n, _profile(n['title'])) for n in notes]
        body = lambda nid: _profile('缓存穿透布隆过滤器' if nid == '3' else '缓存失效')
        result = _rank_candidates(_profile('缓存穿透与布隆过滤器'), profiles, 3, body)
        self.assertEqual(result[0][1]['id'], '3')
        self.assertEqual([n['id'] for _, n in result[1:]], ['0', '1'])

    def test_concurrent_metadata_update_is_not_blocked_and_rejects_stale_task(self):
        from support import Bank
        from ibank_core import notes, note_organization
        bank = Bank()
        self.addCleanup(bank.close)
        folder = bank.root / 'source'
        folder.mkdir()
        (folder / 'notes.md').write_text('# Redis\n\n## 缓存穿透是什么？\n\n布隆过滤器拦截不存在的键。\n', encoding='utf-8')
        bank.result('notes', 'import', '--source', str(folder), '--name', 'public')
        bank.add_questions('database', 'Redis 缓存穿透怎么处理？')
        def concurrent_update(*args):
            catalog = note_organization.catalog(bank.path, 'public')
            note_organization.organize(bank.path, 'public', {'schema_version': 1, 'collection': 'public',
                'source_digest': catalog['source_digest'], 'organization_digest': catalog['organization_digest'],
                'metadata': {'description': 'Changed while retrieval runs'}})
            return _rank_candidates(*args)
        before = set((bank.path / 'runs').iterdir())
        with patch('ibank_core.notes._rank_candidates', side_effect=concurrent_update), self.assertRaisesRegex(Exception, 'retry'):
            notes.link_candidates(bank.path)
        self.assertEqual(before, set((bank.path / 'runs').iterdir()))
        self.assertIn('Changed', note_organization.catalog(bank.path, 'public')['metadata']['description'])

    def test_changed_body_with_same_note_id_invalidates_new_link_tasks(self):
        from support import Bank
        bank = Bank()
        self.addCleanup(bank.close)
        folder = bank.root / 'source'
        folder.mkdir()
        path = folder / 'notes.md'
        path.write_text('# Redis\n\n## 缓存穿透是什么？\n\n布隆过滤器拦截不存在的键。\n', encoding='utf-8')
        bank.result('notes', 'import', '--source', str(folder), '--name', 'public')
        bank.add_questions('database', 'Redis 缓存穿透怎么处理？')
        task = bank.result('notes', 'link-candidates')
        packet = json.loads((bank.path / 'runs' / task['task_id'] / 'task.json').read_text(encoding='utf-8'))
        qid = packet['items'][0]['question']['id']
        nid = packet['items'][0]['candidates'][0]['note_id']
        path.write_text('# Redis\n\n## 缓存穿透是什么？\n\n更新后的解释。\n', encoding='utf-8')
        bank.result('notes', 'import', '--source', str(folder), '--name', 'public')
        result = bank.cli('notes', 'link', payload={'task_id': task['task_id'], 'links': [
            {'question_id': qid, 'note_id': nid, 'relation': 'covers'}]}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('note content changed', result.stderr)
        self.assertEqual(bank.result('notes', 'list')['links'], 0)
        fresh = bank.result('notes', 'link-candidates')
        response = {'task_id': fresh['task_id'], 'links': [{'question_id': qid, 'note_id': nid, 'relation': 'covers'}]}
        self.assertFalse(bank.result('notes', 'link', payload=response)['already_applied'])
        original = (bank.path / 'collections/links.jsonl').read_bytes()
        self.assertTrue(bank.result('notes', 'link', payload=response)['already_applied'])
        self.assertEqual(original, (bank.path / 'collections/links.jsonl').read_bytes())

    def test_fresh_task_after_question_merge_preserves_links_without_duplicates(self):
        import copy
        from support import Bank
        from ibank_core.dedupe import merge_questions
        from ibank_core.runs import stage_snapshot, commit_run
        from ibank_core.storage import open_bank
        from ibank_core.web import WebApp
        bank = Bank()
        self.addCleanup(bank.close)
        folder = bank.root / 'source'
        folder.mkdir()
        (folder / 'notes.md').write_text('# Redis\n\n## 缓存穿透\n\n布隆过滤器拦截不存在的键。\n\n## 过滤器\n\n过滤器的误判率需要控制。\n', encoding='utf-8')
        bank.result('notes', 'import', '--source', str(folder), '--name', 'public')
        bank.add_questions('database', 'Redis 缓存穿透如何处理？', '布隆过滤器怎样处理缓存穿透？')
        initial = bank.result('notes', 'link-candidates')
        packet = json.loads((bank.path / 'runs' / initial['task_id'] / 'task.json').read_text(encoding='utf-8'))
        source, target = [i['question']['id'] for i in packet['items']]
        note1, note2 = [n['id'] for n in bank.result('notes', 'search', '--query', '过滤器')['notes']]
        bank.result('notes', 'link', payload={'task_id': initial['task_id'], 'links': [
            {'question_id': source, 'note_id': note1, 'relation': 'covers', 'reason': 'Fixture source link'}]})
        with open_bank(bank.path) as (_, config, data):
            final = copy.deepcopy(data)
            audit = merge_questions(final, source, target, 'MERGE_VARIANT', 0.99, 'Synthetic same-topic merge')
            staged = stage_snapshot(bank.path, data, final, config, operation='dedupe', audit=[audit])
        commit_run(bank.path, staged['run_id'])
        fresh = bank.result('notes', 'link-candidates')
        response = {'task_id': fresh['task_id'], 'links': [
            {'question_id': target, 'note_id': note1, 'relation': 'covers', 'reason': 'Fixture source link'},
            {'question_id': target, 'note_id': note2, 'relation': 'covers', 'reason': 'Fixture extra mechanism'}]}
        bank.result('notes', 'link', payload=response)
        stored = [json.loads(s) for s in (bank.path / 'collections/links.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(stored), 2)
        self.assertEqual({r['question_id'] for r in stored}, {target})
        self.assertTrue(bank.result('notes', 'link', payload=response)['already_applied'])
        self.assertEqual([q['id'] for q in WebApp(bank.path, read_only=True).note(note1)['questions']], [target])


if __name__ == '__main__':
    unittest.main()
