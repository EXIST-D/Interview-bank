"""Note search: every term must appear, titles rank first, short terms work, and the index follows the collections."""
import unittest
from unittest import mock

from support import Bank

from ibank_core import fulltext
from ibank_core.backups import bank_files
from ibank_core.web import WebApp

FILES = {
    "01-Redis.md": "# Redis\n\n## Redis 持久化有哪些方式？\n\nRDB 快照与 AOF 日志。\n\n## 缓存穿透怎么处理？\n\n布隆过滤器；"
                   "也要考虑 Redis 宕机后的持久化恢复。\n\n## 缓存一致性\n\n先更新数据库再删缓存。\n",
    "02-Go.md": "# Go\n\n## Go 的 GMP 模型\n\nG、M、P 三者协作调度。\n",
}


class NoteSearch(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        source = self.bank.root / "java"
        source.mkdir()
        for name, text in FILES.items():
            (source / name).write_text(text, encoding="utf-8")
        self.bank.result("notes", "import", "--source", str(source), "--name", "java", "--title", "八股", "--origin", "测试")

    def titles(self, query, scan=False):
        with mock.patch.object(fulltext, "SUPPORTED", fulltext.SUPPORTED and not scan):
            return [n["title"] for n in WebApp(self.bank.path).notes({"query": query, "limit": "20"})["notes"]]

    def test_terms_must_all_appear_and_titles_rank_first(self):
        for scan in (False, True):
            with self.subTest(scan=scan):
                self.assertEqual(self.titles("redis 持久化", scan), ["Redis 持久化有哪些方式？", "缓存穿透怎么处理？"])
                self.assertEqual(self.titles("缓存", scan)[:2], ["缓存穿透怎么处理？", "缓存一致性"])
                self.assertEqual(self.titles("go gmp", scan), ["Go 的 GMP 模型"])
                self.assertEqual(self.titles("持久化 不存在的词", scan), [])

    def test_cli_search_uses_the_same_ranking(self):
        hits = self.bank.result("notes", "search", "--query", "持久化 Redis")["notes"]
        self.assertEqual([n["title"] for n in hits], ["Redis 持久化有哪些方式？", "缓存穿透怎么处理？"])

    @unittest.skipUnless(fulltext.SUPPORTED, "SQLite here has no FTS5 trigram tokenizer")
    def test_index_is_rebuilt_when_a_collection_changes_and_never_backed_up(self):
        self.titles("redis")
        index = self.bank.path / "cache" / fulltext.NAME
        self.assertTrue(index.exists())
        self.assertNotIn(index, bank_files(self.bank.path))
        source = self.bank.root / "java"
        (source / "03-MQ.md").write_text("# MQ\n\n## Kafka 如何保证持久化？\n\n副本与刷盘。\n", encoding="utf-8")
        self.bank.result("notes", "import", "--source", str(source), "--name", "java", "--title", "八股", "--origin", "测试")
        self.assertIn("Kafka 如何保证持久化？", self.titles("持久化"))

    def test_odd_input_is_searched_literally(self):
        self.assertEqual(self.titles('"'), [])
        self.assertEqual(self.titles("100%"), [])
        self.assertEqual(self.titles("_"), [])


if __name__ == "__main__":
    unittest.main()
