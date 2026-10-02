"""More ways in: a web page the host read, Bilibili subtitle JSON and rolling auto-captions."""
import json
import unittest
from pathlib import Path

from support import Bank
from ibank_core.media import merge_rolling, parse_transcript

URL = "https://example.org/posts/backend-interview"


class Parsers(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="ibank-sources-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_bilibili_body(self):
        path = self.root / "bili.json"
        path.write_text(json.dumps({"font_size": 0.4, "body": [
            {"from": 1.2, "to": 3.4, "content": "面试官问 Redis 为什么快"}, {"from": 3.4, "to": 5.0, "content": " "},
            {"from": 5.0, "to": 7.5, "content": "然后问了持久化"}]}, ensure_ascii=False), encoding="utf-8")
        segments = parse_transcript(path)
        self.assertEqual([(s["start"], s["text"]) for s in segments], [(1.2, "面试官问 Redis 为什么快"), (5.0, "然后问了持久化")])

    def test_rolling_captions_are_merged_with_cue_numbers(self):
        path = self.root / "auto.vtt"
        path.write_text("WEBVTT\n\n"
                        "00:00:01.000 --> 00:00:03.000\nredis <00:00:01.500><c>why is it fast</c>\n\n"
                        "00:00:03.000 --> 00:00:03.010\nredis why is it fast\n\n"
                        "00:00:03.010 --> 00:00:05.000\nredis why is it fast\nand what about persistence\n\n"
                        "00:00:05.000 --> 00:00:07.000\nand what about persistence\nnext question\n", encoding="utf-8")
        segments = parse_transcript(path)
        self.assertEqual([s["text"] for s in segments], ["redis why is it fast", "and what about persistence", "next question"])
        self.assertEqual(segments[0]["source_cues"], [1, 2])
        self.assertEqual(segments[1]["source_cues"], [3])

    def test_plain_subtitles_are_untouched(self):
        cues = [{"id": 1, "start": 0, "end": 1, "text": "第一句"}, {"id": 2, "start": 1, "end": 2, "text": "第二句"}]
        self.assertIs(merge_rolling(cues), cues)


class WebIntake(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.page = self.bank.root / "page.txt"
        self.page.write_text("后端一面面经\n\n1. Redis 为什么快？\n\n2. MySQL 索引为什么用 B+ 树？\n\n楼主最后拿到了 offer。\n", encoding="utf-8")

    def tearDown(self):
        self.bank.close()

    def test_page_to_questions_with_paragraph_provenance(self):
        intake = self.bank.result("web-intake", "--url", URL, "--text", str(self.page))
        self.assertEqual((intake["items"][0]["type"], intake["items"][0]["segment_count"]), ("web", 4))
        task = self.bank.result("media-task", "--run", intake["id"], "--source", intake["items"][0]["source_id"])
        self.assertEqual(task["segments"][1]["text"], "1. Redis 为什么快？")
        sid = intake["items"][0]["source_id"]
        extraction = {"schema_version": 1, "sources": [{"source_id": sid, "status": "extracted", "reviewed_segment_ids": [1, 2, 3, 4],
            "questions": [{"id": "w1", "sequence": 1, "original_text": "Redis 为什么快？", "segment_ids": [2], "reviewed": True, "correction": "去掉列表序号",
                           "domains": ["backend.cache"], "confidence": {"is_question": 1, "classification": 0.9}}]}]}
        path = self.bank.root / "extraction.json"
        path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
        submitted = self.bank.result("ingest", "submit", "--intake", intake["id"], "--extraction", str(path))
        final = self.bank.result("ingest", "finalize", "--task", submitted["dedupe"]["task_id"])
        self.assertTrue(final["committed"])
        question = self.bank.result("search", "--detail")["questions"][0]
        self.assertEqual(question["occurrences"][0]["locator"]["segment_ids"], [2])
        source = self.bank.result("show", question["id"])["sources"][0]
        self.assertEqual((source["type"], source["source_url"], source["platform"]), ("web", URL, "example.org"))

    def test_same_page_twice_and_bad_url(self):
        self.bank.result("web-intake", "--url", URL, "--text", str(self.page))
        bad = self.bank.cli("web-intake", "--url", "file:///etc/passwd", "--text", str(self.page), check=False)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
