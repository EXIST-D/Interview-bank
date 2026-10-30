"""Preparation views of the Web reader: the most-asked ranking with recency weighting, the company view and saved
job-description lists. Pure functions over the bank's rows, plus the one write (a list is a saved `studyset`)."""
from collections import Counter, defaultdict
from datetime import date, timedelta

from .errors import BankError
from .flows import commit_unless_review
from .runs import abandon_run
from .schema import require
from .studysets import studyset

# A date the person did not record says nothing about age: it counts, but less than a recent one.
UNKNOWN_WEIGHT = 0.3
HALF_LIVES = (180, 365, 730)
WINDOWS = {"all": None, "3y": 3 * 365, "1y": 365}
SORTS = ("weighted", "count")
PRIORITIES = ("must", "nice", "unspecified")
COVERAGES = ("direct", "partial", "uncertain")


def occurrence_day(value):
    """YYYY, YYYY-MM or YYYY-MM-DD as a date (the middle of a partial period); None when unknown or unreadable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parts = [int(p) for p in value.split("-")]
        if len(parts) == 1:
            return date(parts[0], 7, 1)
        if len(parts) == 2:
            return date(parts[0], parts[1], 15)
        return date(*parts[:3])
    except (ValueError, TypeError):
        return None


def weight(day, today, half_life):
    """1 for today, one half after `half_life` days, and so on; a future date counts as today."""
    if day is None:
        return UNKNOWN_WEIGHT
    return 0.5 ** (max(0, (today - day).days) / half_life)


def rank(rows, today, half_life=365, window="all", order="weighted"):
    """Questions with their occurrences inside the window, most asked first.

    count is how many times the question was asked; score weighs each time by how recent it is. A window other than
    "all" keeps only dated occurrences inside it (an undated one cannot be placed in time)."""
    require(half_life in HALF_LIVES and window in WINDOWS and order in SORTS, "Unknown ranking option")
    cutoff = today - timedelta(days=WINDOWS[window]) if WINDOWS[window] else None
    ranked = []
    for q in rows:
        kept = []
        for occurrence in q["occurrences"]:
            day = occurrence_day(occurrence.get("event_date"))
            if cutoff is None or (day is not None and day >= cutoff):
                kept.append((day, occurrence))
        if not kept:
            continue
        dated = [day for day, _ in kept if day]
        ranked.append({"q": q, "count": len(kept), "score": round(sum(weight(day, today, half_life) for day, _ in kept), 3),
                       "companies": len({o["company_id"] for _, o in kept if o.get("company_id")}),
                       "last_year": max(dated).year if dated else None, "undated": len(kept) - len(dated)})
    key = (lambda r: (-r["score"], -r["count"], r["q"]["canonical"], r["q"]["id"])) if order == "weighted" else \
        (lambda r: (-r["count"], -r["score"], r["q"]["canonical"], r["q"]["id"]))
    return sorted(ranked, key=key)


def company_index(rows, companies):
    """Every company that asked something, with how much and when; most occurrences first."""
    names = {c["id"]: c["name"] for c in companies}
    seen = defaultdict(lambda: {"questions": set(), "occurrences": 0, "years": set(), "domains": Counter(), "rounds": Counter()})
    for q in rows:
        for o in q["occurrences"]:
            if not o.get("company_id") or o["company_id"] not in names:
                continue
            entry = seen[o["company_id"]]
            if q["id"] not in entry["questions"]:
                entry["domains"].update(d.split(".")[0] for d in q["domains"][:1])
            entry["questions"].add(q["id"])
            entry["occurrences"] += 1
            if o.get("event_date"):
                entry["years"].add(o["event_date"][:4])
            if o.get("round"):
                entry["rounds"][o["round"]] += 1
    result = [{"id": cid, "name": names[cid], "questions": len(e["questions"]), "occurrences": e["occurrences"],
               "years": sorted(e["years"], reverse=True), "rounds": dict(e["rounds"]),
               "domains": [{"id": d, "count": n} for d, n in e["domains"].most_common(3)]} for cid, e in seen.items()]
    return sorted(result, key=lambda c: (-c["occurrences"], -c["questions"], c["name"], c["id"]))


def company_questions(rows, company_id, today, half_life=365):
    """The company's questions, each with how often this company asked it, in which rounds and years."""
    result = []
    for q in rows:
        mine = [o for o in q["occurrences"] if o.get("company_id") == company_id]
        if not mine:
            continue
        days = [occurrence_day(o.get("event_date")) for o in mine]
        result.append({"q": q, "count": len(mine), "score": round(sum(weight(d, today, half_life) for d in days), 3),
                       "rounds": sorted({o["round"] for o in mine if o.get("round")}),
                       "years": sorted({o["event_date"][:4] for o in mine if o.get("event_date")}, reverse=True)})
    return sorted(result, key=lambda r: (-r["score"], -r["count"], r["q"]["canonical"], r["q"]["id"]))


def requirements(jd, picks, uncovered):
    """The picks as the studyset's JD mapping: one requirement per excerpt of the job description, with its questions.

    Excerpts that do not occur in the text are dropped by the caller's source (the plan), but are checked here too:
    a mapping must quote the job description word for word."""
    found = {}
    for pick in picks:
        quote = pick.get("quote")
        if not quote or quote not in jd:
            continue
        entry = found.setdefault(quote, {"id": f"r{len(found) + 1}", "quote": quote, "priority": "unspecified",
                                         "reason": "岗位描述原文里的要求", "matches": []})
        if entry["priority"] == "unspecified" and pick.get("priority") in PRIORITIES:
            entry["priority"] = pick["priority"]
        entry["matches"].append({"question_id": pick["id"], "coverage": pick.get("coverage") if pick.get("coverage") in COVERAGES else "uncertain",
                                 "reason": pick.get("reason") or "AI 认为相关"})
    for quote in uncovered:
        if quote in jd and quote not in found:
            found[quote] = {"id": f"r{len(found) + 1}", "quote": quote, "priority": "unspecified",
                            "reason": "当前题库里没有直接考察这一项的题", "matches": []}
    return list(found.values())


def save_list(bank, mutation, name, jd, picks, uncovered):
    """Save the chosen questions and their JD mapping as a snapshot study set (`studyset create`); returns its ID."""
    require(bool(picks), "没有可保存的题")
    payload = {"name": name, "mode": "snapshot", "source_intent": "JD 备考：" + " ".join(jd.split())[:60], "expression": {},
               "selected_ids": [p["id"] for p in picks], "jd_text": jd, "requirements": requirements(jd, picks, uncovered)}
    with mutation:
        staged = studyset(bank, "create", payload)
        try:
            receipt = commit_unless_review(bank, staged)
        except BankError:
            abandon_run(bank, staged["run_id"])
            raise
    require(receipt.get("committed"), "无法保存这份备考清单，请重试")
    return receipt["receipt"]["summary"]["studyset_id"]
