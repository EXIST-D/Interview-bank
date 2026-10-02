"""Deterministic synthetic data for the M0 demo and 1,000-question acceptance."""
import hashlib


def make_bundle(folder, count=3):
    from ibank_core.normalize import normalize_question_text
    from ibank_core.schema import TABLES

    bundle = {"schema_version": 1, **{table: [] for table in TABLES}}
    now = "2026-09-05T00:00:00+00:00"
    titles = ["MySQL 为什么使用 B+ 树索引？", "Redis 为什么性能高？", "React 中 key 有什么作用？"]
    for i in range(count):
        title = titles[i] if i < 3 else f"示例题 {i + 1}：如何定位服务延迟？"
        role = "frontend" if i == 2 else "backend"
        domain = "frontend.react" if i == 2 else "backend.cache" if i == 1 else "backend.database"
        technology = "react" if i == 2 else "redis" if i == 1 else "mysql"
        bundle["questions"].append({"schema_version": 1, "id": f"q_demo{i}", "canonical": title,
            "normalized": normalize_question_text(title), "language": "zh-CN", "question_type": "concept",
            "role_tracks": [role], "domains": [domain], "technologies": [technology], "difficulty": "medium",
            "status": "active", "merged_into": None, "created_at": now, "updated_at": now})
        bundle["occurrences"].append({"schema_version": 1, "id": f"occ_demo{i}", "question_id": f"q_demo{i}",
            "source_id": "src_demo", "original_text": title, "company_id": "company_bytedance", "role_tracks": [role],
            "interview_type": "campus", "round": "technical-2", "event_date": "2026-08", "sequence": i + 1,
            "parent_occurrence_id": None, "extraction_confidence": 1.0, "classification_confidence": 1.0, "created_at": now})
    if count >= 2:
        bundle["occurrences"].append({**bundle["occurrences"][1], "id": "occ_repeat", "company_id": "company_meituan",
                                      "round": "technical-1", "sequence": count + 1, "event_date": "2026-07"})
    source = folder / "mock-source.txt"
    source.write_text("\n".join(o["original_text"] for o in bundle["occurrences"]) + "\n", encoding="utf-8")
    bundle["sources"].append({"schema_version": 1, "id": "src_demo", "type": "text", "path": str(source.resolve()),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "platform": "synthetic-fixture", "source_url": None,
        "source_date": None, "imported_at": now, "retention": "reference"})
    bundle["companies"] = [
        {"schema_version": 1, "id": "company_bytedance", "name": "字节跳动", "aliases": ["字节", "ByteDance", "bytedance"], "industries": ["internet", "ai"]},
        {"schema_version": 1, "id": "company_meituan", "name": "美团", "aliases": ["Meituan"], "industries": ["internet"]},
    ]
    return bundle
