from collections import Counter

from .index import connect_index
from .search import select_questions
from .storage import open_bank
from .catalog import normalize_labels


def stats(bank, *, limit=10, **filters):
    with open_bank(bank) as (_, config, data):
        conn = connect_index(bank, data)
        try:
            found = select_questions(conn, stale_days=config.get("answer_stale_days", 180), **filters)
        finally:
            conn.close()
        companies, roles, domains, technologies = (Counter() for _ in range(4))
        months, rounds, interviews, statuses = (Counter() for _ in range(4))
        unique_sources, imprecise_dates, unknown_dates = set(), 0, 0
        entities = {c["id"]: c for c in data["companies"]}
        industries, company_types, ownerships, business_models = (Counter() for _ in range(4))
        for q in found:
            statuses[q["answer_status"]] += 1
            for occ in q["occurrences"]:
                unique_sources.add(occ["source_id"])
                months[(occ["event_date"] or "unknown")[:7]] += 1
                rounds[occ["round"]] += 1
                interviews[occ["interview_type"]] += 1
                unknown_dates += occ["event_date"] is None
                imprecise_dates += occ["event_date"] is not None and len(occ["event_date"]) < 10
                companies[occ["company_id"] or "unknown"] += 1
                entity = entities.get(occ["company_id"], {})
                industries.update(normalize_labels("industries", entity.get("industries", [])))
                company_types[entity.get("company_type", "unknown")] += 1
                ownerships[entity.get("ownership", "unknown")] += 1
                business_models.update(entity.get("business_models", []))
                roles.update(normalize_labels("role_tracks", occ["role_tracks"]))
                domains.update(normalize_labels("domains", q["domains"]))
                technologies.update(normalize_labels("technologies", q["technologies"]))
        return {"questions": len(found), "occurrences": sum(q["frequency"] for q in found),
                "top_questions": [{"id": q["id"], "canonical": q["canonical"], "frequency": q["frequency"],
                                   "total_frequency": q["total_frequency"]} for q in found[:limit]],
                "companies": dict(companies.most_common()), "roles": dict(roles.most_common()),
                "domains": dict(domains.most_common()), "technologies": dict(technologies.most_common()),
                "industries": dict(industries.most_common()), "company_types": dict(company_types.most_common()),
                "ownerships": dict(ownerships.most_common()), "business_models": dict(business_models.most_common()),
                "by_month": dict(sorted(months.items())), "by_round": dict(rounds.most_common()),
                "by_interview_type": dict(interviews.most_common()), "answer_status": dict(statuses),
                "unique_sources": len(unique_sources), "unknown_dates": unknown_dates, "imprecise_dates": imprecise_dates,
                "date_policy": "Partial dates match by interval overlap; unknown dates are excluded only when date filtering is requested"}
