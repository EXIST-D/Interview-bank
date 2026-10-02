"""Replay host-reviewed visual extraction and semantic judgments end to end.

This is a reproducible integration fixture, NOT an automatic image/LLM extractor.
The 17 template images were inspected with native vision during development.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/interview-bank/scripts"))
from ibank_core.dedupe import candidate_task, exact_equivalent, stage_decisions
from ibank_core.ingestion import intake_images, stage_extraction
from ibank_core.storage import initialize, dumps, open_bank


def q(text, domain, technology=None, **extra):
    return {"original_text": text, "canonical_suggestion": text, "domains": [domain],
            "technologies": [technology] if technology else [], "role_tracks": [], "question_type": "concept",
            "confidence": {"is_question": 0.99, "classification": 0.95}, **extra}


# Manually selected visible questions and semantic labels after viewing the fixtures.
OBSERVED = {
    "single": [q("Redis 为什么快？", "backend.cache", "redis")],
    "many": [q("TCP 三次握手的过程？", "computer-science.network"), q("MySQL 索引是什么？", "backend.database", "mysql"),
             q("Redis 持久化有哪些方式？", "backend.cache", "redis"), q("线程和进程有什么区别？", "computer-science.operating-system"),
             q("HTTP 和 HTTPS 有什么区别？", "computer-science.network"), q("什么是死锁？", "computer-science.operating-system"),
             q("如何排查慢 SQL？", "backend.database", "mysql", question_type="debugging"), q("什么是缓存穿透？", "backend.cache"),
             q("B+ 树和 B 树的区别？", "computer-science.data-structure"), q("为什么需要连接池？", "backend.database"),
             q("项目里如何使用消息队列？", "backend.message-queue", question_type="project")],
    "followup": [q("那为什么使用单线程？", "backend.cache", "redis", canonical_suggestion="Redis 为什么使用单线程？"),
                 q("Redis 6 的多线程改了什么？", "backend.cache", "redis")],
    "sections": [q("MySQL 为什么使用 B+ 树？", "backend.database", "mysql", role_tracks=["backend"], round="technical-1"),
                 q("React 的 key 有什么作用？", "frontend.react", "react", role_tracks=["frontend"], round="technical-2")],
    "answer": [q("Redis 为什么快？", "backend.cache", "redis")],
    "comments": [q("Agent 的工具调用如何评估？", "ai.evaluation", role_tracks=["ai-agent"])],
    "ui": [q("闭包是什么？", "frontend.javascript", "javascript")],
    "company": [q("Redis 为什么性能高？", "backend.cache", "redis")],
    "unknown": [q("B+ 树有什么特点？", "computer-science.data-structure")],
    "role": [q("如何设计登录功能？", "backend.system-design", question_type="system-design")],
    "round": [q("MySQL 的 MVCC 是什么？", "backend.database", "mysql")],
    "chain": [q("Redis 为什么快？", "backend.cache", "redis"), q("为什么采用单线程？", "backend.cache", "redis", canonical_suggestion="Redis 为什么使用单线程？"),
              q("慢命令如何影响其他请求？", "backend.cache", "redis")],
    "code": [q("下面输出什么？\nconsole.log(1);\nPromise.resolve().then(() => console.log(2));\nconsole.log(3);", "frontend.javascript", "javascript", question_type="coding")],
    "mixed": [q("RAG 和 fine-tuning 有什么区别？", "ai.rag", role_tracks=["ai-agent"]),
              q("How do you evaluate tool calling?", "ai.evaluation", role_tracks=["ai-agent"], language="en")],
    "prompt_injection": [q("React 的 key 有什么作用？", "frontend.react", "react")],
    "empty": [], "blur": [],
}
META = {
    "single": {"company": {"name": "字节跳动", "aliases": ["字节", "ByteDance"], "industries": []}, "role_tracks": ["backend"], "round": "technical-2", "interview_type": "intern", "event_date": "2026-08"},
    "many": {"role_tracks": ["backend"], "round": "technical-1", "interview_type": "campus"},
    "sections": {"company": "美团", "interview_type": "campus"},
    "comments": {"interview_type": "campus"},
    "ui": {"role_tracks": ["frontend"], "interview_type": "intern", "round": "technical-1"},
    "company": {"company": "ByteDance", "role_tracks": ["backend"], "round": "technical-2", "event_date": "2026-08"},
    "role": {"role_tracks": ["fullstack"], "interview_type": "intern", "event_date": "2026-08"},
    "round": {"company": "字节", "role_tracks": ["backend"], "round": "technical-2"},
    "chain": {"role_tracks": ["backend"], "round": "technical-1"},
    "code": {"role_tracks": ["frontend"]},
    "mixed": {"role_tracks": ["ai-agent"], "interview_type": "intern", "round": "technical-1"},
    "prompt_injection": {"role_tracks": ["frontend"]},
}
META["followup"] = META["single"]


def equivalence(text):
    if text in ("Redis 为什么性能高？", "Redis 为什么快？"):
        return "redis-performance"
    if text in ("Agent 的工具调用如何评估？", "How do you evaluate tool calling?"):
        return "tool-evaluation"
    return text


def run_cli(bank, *arguments):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "skills/interview-bank/scripts/ibank.py"), *arguments,
                             "--bank", str(bank), "--json"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)["result"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=ROOT / "examples/acceptance-bank")
    bank = parser.parse_args().bank.resolve()
    if not bank.is_relative_to(ROOT):
        raise ValueError("Acceptance artifacts must stay in this repository")
    initialize(bank)
    with open_bank(bank) as (_, _, data):
        if data["questions"]:
            print("Acceptance bank already populated; use existing artifacts or a fresh named test bank.")
            return
    visual = ROOT / ".work/visual-evals"
    manifest = json.loads((visual / "manifest.json").read_text(encoding="utf-8"))
    intake = intake_images(bank, [visual / "batch50"], retention="copy")
    extraction = {"schema_version": 1, "sources": []}
    for item in intake["items"]:
        # copy retention uses bank media paths, so match source hashes to fixture paths.
        import hashlib
        match = next(m for m in manifest if hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest() == item["source"]["sha256"])
        case, index = match["case"], match["index"]
        questions = []
        for sequence, observed in enumerate(OBSERVED[case], 1):
            candidate = {**observed, "id": f"s{index}q{sequence}", "sequence": sequence}
            if not candidate["role_tracks"]:
                candidate["role_tracks"] = META.get(case, {}).get("role_tracks", [])
            if case in ("chain", "followup") and sequence > 1:
                candidate["parent_id"] = f"s{index}q{sequence - 1}"
            elif case == "followup":
                candidate["parent_id"] = f"s{index - 2}q1"
            questions.append(candidate)
        source = {"source_id": item["source"]["id"], "status": "extracted" if questions else "no_questions",
                  "metadata": META.get(case, {}), "questions": questions}
        if case == "empty":
            source["reason"] = "Visible daily-life note and app UI; no interview questions"
        if case == "blur":
            source.update(status="skip", reviewed=True, reason="Reviewed synthetic blur fixture; illegible text deliberately excluded")
        extraction["sources"].append(source)
    (bank / "extraction-response.json").write_text(dumps(extraction), encoding="utf-8")
    stage = stage_extraction(bank, intake["id"], extraction)
    task = candidate_task(bank, stage["run_id"], top_k=30)
    decisions = []
    for item in task["items"]:
        incoming = item["incoming"]
        same = next((m for m in item["matches"] if equivalence(m["question"]["canonical"]) == equivalence(incoming["canonical"])), None)
        action, target, reason = "KEEP_DISTINCT", None, "Different core knowledge or no equivalent earlier question"
        if same:
            action = "MERGE_EXACT" if exact_equivalent(incoming, same["question"]) else "MERGE_VARIANT"
            target, reason = same["question"]["id"], "Host-reviewed equivalent wording; one complete answer covers both"
        elif incoming["canonical"] == "Redis 为什么使用单线程？":
            related = next((m for m in item["matches"] if equivalence(m["question"]["canonical"]) == "redis-performance"), None)
            if related:
                action, target, reason = "KEEP_RELATED", related["question"]["id"], "Execution model explains only part of performance; keep distinct"
        decisions.append({"question_id": incoming["id"], "action": action, "target_id": target, "confidence": 0.99, "reason": reason})
    response = {"schema_version": 1, "task_id": task["id"], "decisions": decisions}
    (bank / "dedupe-response.json").write_text(dumps(response), encoding="utf-8")
    run = stage_decisions(bank, response)
    committed = run_cli(bank, "commit", "--run", run["run_id"])
    exports = [run_cli(bank, "export", "--output", f"all-questions.{fmt}", "--format", fmt) for fmt in ("markdown", "json", "jsonl", "csv", "viewer")]
    report = {"input_files": 50, "unique_images": len(intake["items"]), "duplicate_images": len(intake["duplicates"]),
              "commit": committed, "stats": run_cli(bank, "stats"), "doctor": run_cli(bank, "doctor"),
              "validate": run_cli(bank, "validate"), "exports": exports,
              "evaluation_boundary": "17 synthetic templates visually inspected by host; 40 rendered images + 10 byte-identical duplicates replay stored extraction/judgments. Not a real-world screenshot accuracy benchmark."}
    (bank / "acceptance-results.json").write_text(dumps(report), encoding="utf-8")
    print(dumps({"bank": str(bank), "input_files": 50, "unique_images": len(intake["items"]), "duplicate_images": len(intake["duplicates"]),
                 "question_candidates": stage["summary"]["question_candidates"], "active_questions": report["stats"]["questions"],
                 "occurrences": report["stats"]["occurrences"], "dedupe": committed["summary"]["dedupe"]}))


if __name__ == "__main__":
    main()
