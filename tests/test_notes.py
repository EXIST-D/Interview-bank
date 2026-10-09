"""八股 collections: Markdown parsing, import, links to interview questions, backups and the reader API."""
import http.client
import json
import threading
import unittest
from pathlib import Path

from support import Bank
from ibank_core.notes import parse_markdown
from ibank_core.web import LocalServer, WebApp

CACHE = """# Redis

> 先看这一章的总述。

## 1. 缓存与数据库双写一致性怎么保证？🔴

- 先更新数据库，再删除缓存
  - 删除失败时重试

```python
# 这一行不是标题
cache.delete(key)
```

## 2、缓存穿透是什么 ⭐

| 问题 | 方案 |
| --- | --- |
| 穿透 | 布隆过滤器 |

## 高频面试题

### 1. 缓存雪崩怎么处理？

加随机过期时间。

### 2. 热点 key 怎么办？
"""

JVM = """# JVM

## 1. 垃圾回收算法有哪些？

标记清除、标记复制、标记整理。
"""


class ParseTests(unittest.TestCase):
    def test_headings_marks_groups_and_code(self):
        chapter = parse_markdown(CACHE)
        self.assertEqual(chapter["title"], "Redis")
        self.assertEqual(chapter["intro"], "> 先看这一章的总述。")
        titles = [n["title"] for n in chapter["notes"]]
        self.assertEqual(titles, ["缓存与数据库双写一致性怎么保证？", "缓存穿透是什么", "缓存雪崩怎么处理？", "热点 key 怎么办？"])
        first, second, third, fourth = chapter["notes"]
        self.assertEqual((first["marks"], second["marks"]), (["red"], ["star"]))
        self.assertIn("# 这一行不是标题", first["body"])  # a '#' inside code is not a heading
        self.assertEqual((third["group"], fourth["group"]), ("高频面试题", "高频面试题"))
        self.assertEqual(fourth["body"], "")
        self.assertEqual(first["line"], 5)

    def test_long_opening_becomes_a_note_and_headless_file_is_one_note(self):
        long = "# 记忆\n\n" + "记忆分为四类。" * 40 + "\n\n## 1. 短期记忆\n\n上下文。\n"
        notes = parse_markdown(long)["notes"]
        self.assertEqual([n["title"] for n in notes], ["记忆 · 导读", "短期记忆"])
        self.assertEqual(parse_markdown("# 心得\n\n多复盘。\n")["notes"][0]["title"], "心得")


class NotesCliTests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        self.source = self.bank.root / "java"
        self.source.mkdir()
        (self.source / "01-Redis.md").write_text(CACHE, encoding="utf-8")
        (self.source / "02-JVM.md").write_text(JVM, encoding="utf-8")
        self.bank.add_questions("backend.cache", "Redis 缓存和数据库双写一致性如何保证？", "说说 JVM 的垃圾回收算法")

    def import_java(self, **extra):
        args = ["notes", "import", "--source", str(self.source), "--name", "java", "--title", "Java 八股", "--origin", "网络整理"]
        for key, value in extra.items():
            args += [f"--{key}", value]
        return self.bank.result(*args)

    def test_import_list_search_and_show(self):
        result = self.import_java()
        self.assertEqual((result["chapters"], result["notes"], result["marked"]), (2, 5, 2))
        listed = self.bank.result("notes", "list")["collections"][0]
        self.assertEqual([c["title"] for c in listed["chapters"]], ["Redis", "JVM"])
        hits = self.bank.result("notes", "search", "--query", "布隆")
        self.assertEqual([n["title"] for n in hits["notes"]], ["缓存穿透是什么"])
        shown = self.bank.result("notes", "show", hits["notes"][0]["id"])
        self.assertEqual(shown["source"]["file"], "01-Redis.md")
        self.assertEqual(shown["source"]["origin"], "网络整理")
        # The source folder is only read.
        self.assertEqual(sorted(p.name for p in self.source.iterdir()), ["01-Redis.md", "02-JVM.md"])

    def test_link_task_links_and_reimport_keeps_them(self):
        self.import_java()
        task = self.bank.result("notes", "link-candidates", "--top-k", "3")
        stored = json.loads(Path(task["task_file"]).read_text(encoding="utf-8"))
        items = {i["question"]["canonical"]: i for i in stored["items"]}
        self.assertEqual(len(stored["catalog"]), 5)
        self.assertTrue(all(line.count("\t") == 2 for line in stored["catalog"]))
        redis = items["Redis 缓存和数据库双写一致性如何保证？"]
        self.assertEqual(redis["candidates"][0]["title"], "缓存与数据库双写一致性怎么保证？")
        jvm = items["说说 JVM 的垃圾回收算法"]
        self.assertEqual(jvm["candidates"][0]["title"], "垃圾回收算法有哪些？")
        links = {"task_id": task["task_id"], "links": [
            {"question_id": redis["question"]["id"], "note_id": redis["candidates"][0]["note_id"], "relation": "answers", "reason": "同一题"}]}
        result = self.bank.result("notes", "link", payload=links)
        self.assertEqual((result["links"], result["without_links"]), (1, 1))
        # The JVM question was judged without links, so only nothing is left for --unlinked.
        self.assertIn("No questions selected", self.bank.cli("notes", "link-candidates", "--unlinked", check=False).stderr)
        # Unchanged headings keep their IDs and links; a removed heading drops its links.
        self.assertEqual(self.import_java()["links_kept"], 1)
        (self.source / "01-Redis.md").write_text(CACHE.replace("双写一致性怎么保证", "一致性"), encoding="utf-8")
        self.assertEqual(self.import_java()["links_dropped"], 1)

    def test_link_validation(self):
        self.import_java()
        task = self.bank.result("notes", "link-candidates")
        stored = json.loads(Path(task["task_file"]).read_text(encoding="utf-8"))
        item = stored["items"][0]
        good = {"question_id": item["question"]["id"], "note_id": item["candidates"][0]["note_id"], "relation": "covers"}
        for bad, message in (({**good, "note_id": "note_missing"}, "Unknown note"),
                             ({**good, "question_id": "q_missing"}, "Question not in this task"),
                             ({**good, "relation": "same"}, "relation must be")):
            proc = self.bank.cli("notes", "link", payload={"task_id": task["task_id"], "links": [bad]}, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(message, proc.stderr)
        proc = self.bank.cli("notes", "link", payload={"task_id": task["task_id"], "links": [good, good]}, check=False)
        self.assertIn("Duplicate link", proc.stderr)
        # A new import makes the old task stale.
        (self.source / "02-JVM.md").write_text(JVM + "\n## 2. 类加载过程？\n\n加载、链接、初始化。\n", encoding="utf-8")
        self.import_java()
        proc = self.bank.cli("notes", "link", payload={"task_id": task["task_id"], "links": [good]}, check=False)
        self.assertIn("stale", proc.stderr)

    def test_backup_carries_collections_and_remove(self):
        self.import_java()
        archive = self.bank.result("backup", "create")["archive"]
        restored = self.bank.root / "restored"
        self.bank.result("backup", "restore", "--archive", archive, "--destination", str(restored))
        self.assertTrue((restored / "collections" / "java.json").is_file())
        self.assertEqual(self.bank.result("notes", "remove", "--name", "java")["notes"], 5)
        self.assertEqual(self.bank.result("notes", "list")["collections"], [])

    def test_reader_api(self):
        self.import_java()
        task = self.bank.result("notes", "link-candidates")
        stored = json.loads(Path(task["task_file"]).read_text(encoding="utf-8"))
        redis = next(i for i in stored["items"] if "Redis" in i["question"]["canonical"])
        self.bank.result("notes", "link", payload={"task_id": task["task_id"], "links": [
            {"question_id": redis["question"]["id"], "note_id": redis["candidates"][0]["note_id"], "relation": "answers"}]})
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.library({})["notes"], {"total": 5, "collections": 1})
        everything = app.notes({})
        self.assertEqual((everything["total"], everything["summary"]), (5, {"notes": 5, "marked": 2, "asked": 1}))
        self.assertEqual(app.notes({"collection": "java", "chapter": "1"})["total"], 1)
        self.assertEqual(app.notes({"marked": "1"})["total"], 2)
        self.assertEqual(app.notes({"query": "布隆"})["notes"][0]["title"], "缓存穿透是什么")
        self.assertEqual(app.notes({"collection": "gone"})["total"], 5)  # a remembered collection that was removed
        self.assertEqual(app.notes({"sort": "asked"})["notes"][0]["asked"], 1)
        note = app.note(redis["candidates"][0]["note_id"])
        self.assertEqual([q["relation"] for q in note["questions"]], ["answers"])
        self.assertIn("先更新数据库", note["body"])
        question = app.question(redis["question"]["id"])
        self.assertEqual([n["title"] for n in question["notes"]], ["缓存与数据库双写一致性怎么保证？"])
        with self.assertRaises(Exception):
            app.notes({"unknown": "1"})
        server = LocalServer(app)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        for token, status in ((server.token, 200), ("wrong", 401)):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("GET", "/api/notes?collection=java", headers={"X-Interview-Token": token})
            response = conn.getresponse()
            self.assertEqual(response.status, status)
            response.read()
            conn.close()


if __name__ == "__main__":
    unittest.main()
