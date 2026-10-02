"""Shared helpers: temporary banks and a CLI runner. Tests never write into the installed skill."""
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "interview-bank"
CLI = SKILL / "scripts" / "ibank.py"
sys.path.insert(0, str(SKILL / "scripts"))

REDIS_FAQ = "https://redis.io/docs/latest/develop/get-started/faq/"


class Bank:
    """A throwaway bank driven through the real CLI, exactly as a host agent would."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ibank-test-")
        self.root = Path(self._tmp.name)
        self.path = self.root / "bank"
        self.cli("init")

    def close(self):
        self._tmp.cleanup()

    def cli(self, *args, payload=None, check=True, env=None):
        argv = [sys.executable, "-B", str(CLI), *args, "--bank", str(self.path), "--json"]
        if payload is not None:
            source = self.root / f"payload-{uuid.uuid4().hex}.json"
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            argv += ["--input", str(source)]
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=env)
        if check and proc.returncode != 0:
            raise AssertionError(f"{args} exited {proc.returncode}: {proc.stderr or proc.stdout}")
        return proc

    def result(self, *args, payload=None):
        return json.loads(self.cli(*args, payload=payload).stdout)["result"]

    def stage_commit(self, *args, payload=None):
        run_id = self.result(*args, payload=payload)["run_id"]
        return self.result("commit", "--run", run_id)

    def add_questions(self, domain, *questions):
        source = self.root / f"questions-{uuid.uuid4().hex}.txt"
        source.write_text("\n".join(questions) + "\n", encoding="utf-8")
        return self.stage_commit("stage", "--text", str(source), "--domain", domain)

    def answer_all(self, accessed_at=None):
        """Attach one source-backed answer to every question in a fresh research task."""
        task = self.result("research", "--limit", "50")
        accessed_at = accessed_at or datetime.now(timezone.utc).date().isoformat()
        answers = [sourced_answer(item["question"]["id"], accessed_at) for item in task["items"]]
        return self.cli("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": answers}, check=False)


def sourced_answer(question_id, accessed_at):
    return {"question_id": question_id, "status": "source_backed",
            "short_answer": "基于内存、事件循环与高效数据结构。", "spoken_answer": "口述版本",
            "key_points": ["数据主要在内存中"], "deep_dive": "展开说明", "interviewer_intent": "考察架构理解",
            "common_mistakes": ["误以为完全单线程"], "follow_up_questions": ["Redis 6 的 I/O 线程是什么？"],
            "code_example": None,
            "sources": [{"title": "Redis FAQ", "url": REDIS_FAQ, "publisher": "Redis", "type": "official_doc",
                         "accessed_at": accessed_at, "evidence_note": "FAQ 说明 Redis 为内存数据库"}],
            "evidence": [{"key_point": 0, "source_urls": [REDIS_FAQ]}]}
