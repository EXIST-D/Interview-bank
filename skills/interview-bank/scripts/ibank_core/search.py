from collections import Counter, defaultdict

from .index import connect_index, rows
from .normalize import normalize_company_alias, normalize_question_text, normalize_technology
from .storage import open_bank
from .dates import bounds, interval, effective_answer
from .schema import require
from .catalog import matches, company_matches


def select_questions(conn, *, query=None, company=None, role=None, technology=None, domain=None,
                     round_name=None, industry=None, interview_type=None, difficulty=None,
                     date_from=None, date_to=None, recent_days=None, as_of=None, answer_status=None,
                     question_type=None, stale_days=180, company_type=None, ownership=None, business_model=None,
                     question_ids=None, expression=None, occurrence_ids=None):
    """Context filters must match ONE occurrence, never independent joins."""
    companies = {c["id"]: c for c in rows(conn, "companies")}
    start, end = bounds(date_from, date_to, recent_days, as_of)
    require(answer_status in (None, "missing", "ai_draft", "source_backed", "reviewed", "stale"), "Invalid answer status filter")
    answers = defaultdict(list)
    for answer in rows(conn, "answers"):
        answers[answer["question_id"]].append(answer)
    by_question = defaultdict(list)
    for occ in rows(conn, "occurrences"):
        by_question[occ["question_id"]].append(occ)
    company_key = normalize_company_alias(company) if company else None
    terms = [normalize_question_text(term) for term in (query or "").split()]
    result = []
    for question in rows(conn, "questions"):
        if question_ids is not None and question["id"] not in question_ids:
            continue
        if question["status"] != "active":
            continue
        if technology and normalize_technology(technology) not in {normalize_technology(t) for t in question["technologies"]}:
            continue
        if domain and not any(matches("domains", d, domain) for d in question["domains"]):
            continue
        if difficulty and difficulty != question["difficulty"]:
            continue
        if question_type and question_type != question["question_type"]:
            continue
        versions = sorted(answers[question["id"]], key=lambda a: a["version"])
        latest = versions[-1] if versions else None
        status = effective_answer(latest, as_of, stale_days)
        if latest and "question_revision" in latest:
            from .state import revision
            if latest["question_revision"] != revision(question):
                status = "stale"
        if answer_status and answer_status != status:
            continue
        occurrences = by_question[question["id"]]
        matching = []
        for occ in occurrences:
            if occurrence_ids is not None and occ["id"] not in occurrence_ids:
                continue
            entity = companies.get(occ["company_id"], {})
            if company_key and company_key not in {normalize_company_alias(a) for a in [entity.get("id", ""), entity.get("name", ""), *entity.get("aliases", [])]}:
                continue
            if role and not any(matches("role_tracks", value, role) for value in occ["role_tracks"]):
                continue
            if round_name and round_name != occ["round"]:
                continue
            if not company_matches(entity, industry=industry, company_type=company_type, ownership=ownership, business_model=business_model):
                continue
            if interview_type and interview_type != occ["interview_type"]:
                continue
            span = interval(occ["event_date"])
            if (start or end) and (span is None or (start and span[1] < start) or (end and span[0] > end)):
                continue
            matching.append(occ)
        if not matching:
            continue
        searchable = [question["normalized"], *(normalize_question_text(o["original_text"]) for o in matching)]
        if terms and not any(all(term in text for term in terms) for text in searchable):
            continue
        company_counts = Counter(o["company_id"] for o in matching)
        result.append({**question, "frequency": len(matching), "total_frequency": len(occurrences),
                       "companies": [{"id": key, "name": companies.get(key, {}).get("name", "unknown"), "frequency": count}
                                     for key, count in sorted(company_counts.items(), key=lambda item: (-item[1], item[0] or ""))],
                       "occurrences": matching, "answer_status": status, "answer": latest, "answer_versions": versions})
    if expression is not None:
        from .selection import apply_expression
        result = apply_expression(result, list(companies.values()), expression)
    return sorted(result, key=lambda q: (-q["frequency"], q["canonical"], q["id"]))


def search(bank, *, limit=50, offset=0, **filters):
    require(type(limit) is int and limit > 0 and type(offset) is int and offset >= 0, "Invalid pagination")
    with open_bank(bank) as (_, config, data):
        conn = connect_index(bank, data)
        try:
            found = select_questions(conn, stale_days=config.get("answer_stale_days", 180), **filters)
            return {"total": len(found), "offset": offset, "questions": found[offset:offset + limit]}
        finally:
            conn.close()


def detail(bank, question_id):
    with open_bank(bank) as (_, config, data):
        q = next((q for q in data["questions"] if q["id"] == question_id), None)
        require(q is not None, "Question not found")
        resolved_id = q["merged_into"] if q["status"] == "merged" else question_id
        conn = connect_index(bank, data)
        try:
            selected = next(q for q in select_questions(conn, stale_days=config.get("answer_stale_days", 180)) if q["id"] == resolved_id)
        finally:
            conn.close()
        source_ids = {o["source_id"] for o in selected["occurrences"]}
        return {"requested_id": question_id, "resolved_id": resolved_id, "question": selected,
                "sources": [s for s in data["sources"] if s["id"] in source_ids],
                "relations": [r for r in data["relations"] if resolved_id in (r["from_question_id"], r["to_question_id"])],
                "merged_variants": [q for q in data["questions"] if q["merged_into"] == resolved_id]}
