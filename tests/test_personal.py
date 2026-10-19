"""The person's own layer: notes on collection entries, favourite folders, learning state and hosted write switches."""
import json
import unittest

from support import Bank

from ibank_core import my_answers, personal
from ibank_core.errors import BankError
from ibank_core.migrations import migrate
from ibank_core.storage import open_bank
from ibank_core.web import WebApp

NOTES = "# Redis\n\n## 1. 缓存穿透怎么处理？\n\n布隆过滤器或缓存空值。\n\n## 2. 缓存雪崩怎么处理？\n\n过期时间加随机值。\n"


class PersonalLayer(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.addCleanup(self.bank.close)
        source = self.bank.root / "java"
        source.mkdir()
        (source / "01-Redis.md").write_text(NOTES, encoding="utf-8")
        self.bank.add_questions("backend.cache", "如何防止缓存穿透？")
        self.bank.result("notes", "import", "--source", str(source), "--name", "java", "--title", "Java 八股", "--origin", "测试")
        with open_bank(self.bank.path, shared=True) as (_, _c, data):
            self.qid = next(q["id"] for q in data["questions"] if q["status"] == "active")
        self.note = WebApp(self.bank.path).notes({"limit": "5"})["notes"][0]["id"]

    def test_note_on_a_collection_entry_lists_with_question_notes(self):
        saved = my_answers.save(self.bank.path, self.note, "穿透：查不到的 key 每次都打到数据库。", "")
        my_answers.save(self.bank.path, self.qid, "先讲布隆过滤器。", "")
        app = WebApp(self.bank.path, read_only=True)
        self.assertEqual(app.note(self.note)["my_answer"]["text"], saved["my_answer"]["text"])
        self.assertTrue(next(n for n in app.notes({"limit": "5"})["notes"] if n["id"] == self.note)["has_my_answer"])
        self.assertEqual(self.bank.result("notes", "show", self.note)["my_answer"]["text"], saved["my_answer"]["text"])
        rows = app.my_notes({})["notes"]
        self.assertEqual({r["section"] for r in rows}, {"bank", "knowledge"})
        self.assertEqual(app.my_notes({"section": "knowledge"})["notes"][0]["where"], "Java 八股")
        self.assertEqual([r["id"] for r in app.my_notes({"query": "布隆"})["notes"]], [self.qid])
        with self.assertRaises(BankError):
            my_answers.save(self.bank.path, "note_doesnotexist", "x", "")

    def test_a_note_survives_its_entry_being_removed(self):
        my_answers.save(self.bank.path, self.note, "这段不能丢", "")
        self.bank.result("notes", "remove", "--name", "java")
        row = WebApp(self.bank.path).my_notes({})["notes"][0]
        self.assertEqual((row["text"], row["missing"], row["title"]), ("这段不能丢", True, "缓存穿透怎么处理？"))

    def test_favourite_folders(self):
        app = WebApp(self.bank.path, read_only=True, allow_my_answers=True)
        folders = app.change_favorites({"action": "create", "name": "  字节二面  "})["folders"]
        fid = folders[0]["id"]
        self.assertEqual(folders[0]["name"], "字节二面")
        for item in (self.qid, self.note, self.qid):
            folders = app.change_favorites({"action": "add", "folder": fid, "item": item})["folders"]
        self.assertEqual([i["id"] for i in folders[0]["items"]], [self.note, self.qid])
        self.assertEqual([i["section"] for i in folders[0]["items"]], ["knowledge", "bank"])
        app.change_favorites({"action": "create", "name": "RAG 重点"})
        folders = app.change_favorites({"action": "move", "folder": fid, "position": 1})["folders"]
        self.assertEqual([f["name"] for f in folders], ["RAG 重点", "字节二面"])
        folders = app.change_favorites({"action": "remove", "folder": fid, "item": self.qid})["folders"]
        self.assertEqual([i["id"] for i in folders[1]["items"]], [self.note])
        app.change_favorites({"action": "rename", "folder": fid, "name": "字节"})
        self.assertEqual(app.favorites()["folders"][1]["name"], "字节")
        app.change_favorites({"action": "delete", "folder": fid})
        self.assertEqual([f["name"] for f in app.favorites()["folders"]], ["RAG 重点"])
        for bad in ({"action": "create", "name": ""}, {"action": "create", "name": "x" * 61},
                    {"action": "add", "folder": "fav_missing", "item": self.qid}, {"action": "drop"},
                    {"action": "add", "folder": folders[0]["id"], "item": "../etc"}, {"action": "create", "name": "a", "extra": 1}):
            with self.assertRaises(BankError, msg=bad):
                app.change_favorites(bad)

    def test_learning_state_merges_devices(self):
        app = WebApp(self.bank.path, read_only=True, allow_my_answers=True)
        app.change_learning({"read": {self.qid: "2026-10-19T01:00:00Z"}, "states": {self.note: {"state": "review", "at": "2026-10-19T01:00:00Z"}}})
        # The other device is older for the state and newer for the shelf.
        merged = app.change_learning({"read": {self.qid: "2026-10-19T03:00:00Z", self.note: "2026-10-19T02:00:00Z"},
                                      "states": {self.note: {"state": "read", "at": "2026-10-19T00:30:00Z"}},
                                      "shelf": {"order": ["java"], "at": "2026-10-19T02:00:00Z"}})
        self.assertEqual(merged["read"], {self.qid: "2026-10-19T01:00:00Z", self.note: "2026-10-19T02:00:00Z"})
        self.assertEqual(merged["states"][self.note]["state"], "review")
        self.assertEqual(merged["shelf"]["order"], ["java"])
        later = app.change_learning({"states": {self.note: {"state": "mastered", "at": "2026-10-19T05:00:00Z"}}})
        self.assertEqual(later["states"][self.note]["state"], "mastered")
        self.assertEqual(personal.learning(self.bank.path)["states"][self.note]["state"], "mastered")
        for bad in ({"states": {self.note: {"state": "done", "at": "x"}}}, {"read": {"bad id": "x"}}, {"other": 1},
                    {"shelf": {"order": "java", "at": "x"}}):
            with self.assertRaises(BankError, msg=bad):
                app.change_learning(bad)

    def test_hosted_switches(self):
        locked = WebApp(self.bank.path, read_only=True)
        with self.assertRaises(BankError):
            locked.change_favorites({"action": "create", "name": "x"})
        with self.assertRaises(BankError):
            locked.change_learning({"read": {self.qid: "2026-10-19T01:00:00Z"}})
        self.assertFalse(locked.learning()["can_write"])
        migrate(self.bank.path, "apply")
        self.assertFalse(locked.library({"limit": "1"})["can_record"])
        practise = WebApp(self.bank.path, read_only=True, allow_practice=True)
        library = practise.library({"limit": "1"})
        self.assertTrue(library["can_record"])
        self.assertFalse(library["can_review"] or library["can_write_answer"])
        question = practise.question(self.qid)
        saved = practise.record({"question_id": self.qid, "revision": question["revision"], "rating": "good",
                                 "request_id": "r-1", "note": "", "timezone": "Asia/Shanghai"})
        self.assertTrue(saved["saved"])

    def test_backups_carry_personal_files(self):
        app = WebApp(self.bank.path, read_only=True, allow_my_answers=True)
        app.change_favorites({"action": "create", "name": "收藏"})
        app.change_learning({"read": {self.qid: "2026-10-19T01:00:00Z"}})
        archive = self.bank.result("backup", "create")["archive"]
        import zipfile
        with zipfile.ZipFile(archive) as handle:
            names = set(handle.namelist())
        self.assertTrue({"personal/favorites.json", "personal/learning.json"} <= names)
        self.assertFalse(any(name.endswith(".bank.lock") for name in names), names)
        json.loads((self.bank.path / "personal" / "favorites.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
