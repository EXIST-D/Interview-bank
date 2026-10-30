"""Read-only list of the bank's imported sources: which screenshots, pages and recordings it already holds."""
from collections import Counter, defaultdict

from .schema import require
from .storage import open_bank


def list_sources(bank, query=None, url=None, platform=None, source_type=None, limit=50, offset=0):
    """Sources newest first, each with the number of occurrences and distinct questions extracted from it.

    A source with no occurrences was registered but nothing is committed from it yet (a recording still to be
    transcribed or read, or a page that held no questions). `url` matches a source URL exactly; `query` matches
    case-insensitively inside the URL or platform. Paths of the stored files are left out on purpose.
    """
    require(type(limit) is int and limit > 0 and type(offset) is int and offset >= 0, "Invalid source pagination")
    with open_bank(bank, shared=True) as (_, _, data):
        occurrences, questions = Counter(), defaultdict(set)
        for occurrence in data["occurrences"]:
            occurrences[occurrence["source_id"]] += 1
            questions[occurrence["source_id"]].add(occurrence["question_id"])
        rows = []
        for source in data["sources"]:
            source_url = source.get("source_url")
            if url and source_url != url:
                continue
            if platform and source.get("platform") != platform:
                continue
            if source_type and source["type"] != source_type:
                continue
            if query and query.lower() not in f"{source_url or ''} {source.get('platform') or ''}".lower():
                continue
            transcription = source.get("transcription") or {}
            rows.append({
                "id": source["id"], "type": source["type"], "platform": source.get("platform"),
                "source_url": source_url, "source_date": source.get("source_date"),
                "imported_at": source.get("imported_at"), "retention": source.get("retention"),
                "engine": transcription.get("engine"), "model": transcription.get("model"),
                "segments": transcription.get("segment_count"),
                "occurrences": occurrences[source["id"]], "questions": len(questions[source["id"]]),
            })
        rows.sort(key=lambda row: (row["imported_at"] or "", row["id"]), reverse=True)
        return {"total": len(rows), "offset": offset, "sources": rows[offset:offset + limit]}
