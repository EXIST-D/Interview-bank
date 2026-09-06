"""Read-only discovery of the bank's actual employer entities, not a seed list."""
from .catalog import company_matches
from .normalize import normalize_company_alias
from .schema import require
from .storage import open_bank


def list_companies(bank, query=None, industry=None, company_type=None, ownership=None, business_model=None, limit=50, offset=0):
    require(type(limit) is int and limit > 0 and type(offset) is int and offset >= 0, "Invalid company pagination")
    with open_bank(bank) as (_, _, data):
        result = []
        for company in data["companies"]:
            searchable = normalize_company_alias(" ".join([company["id"], company["name"], *company["aliases"]]))
            if query and not all(normalize_company_alias(word) in searchable for word in query.split()):
                continue
            if not company_matches(company, industry=industry, company_type=company_type, ownership=ownership, business_model=business_model):
                continue
            occurrences = [o for o in data["occurrences"] if o["company_id"] == company["id"]]
            result.append({**company, "questions": len({o["question_id"] for o in occurrences}), "occurrences": len(occurrences)})
        result.sort(key=lambda c: (-c["occurrences"], c["name"], c["id"]))
        return {"total": len(result), "offset": offset, "companies": result[offset:offset + limit]}
