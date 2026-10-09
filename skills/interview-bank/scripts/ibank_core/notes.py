"""Reference notes (八股文): published question collections kept beside the bank's own interview questions.

A collection is imported from a folder of Markdown files: one file per chapter, its ``##`` headings are the
questions and the text under each heading is the collection's own answer, kept verbatim with where it came from.
Notes never count as interview occurrences: they do not change frequency, dedupe or the bank's sourced answers.
Links join a bank question to the notes that answer or cover it; the agent judges them from a candidate task.

Layout inside the bank: ``collections/<name>.json`` (one file per collection, replaced atomically) and
``collections/links.jsonl``. Both are read and written under the bank lock.
"""
import hashlib
import re
from pathlib import Path

from .dedupe import grams, retrieval_text
from .ids import utc_now
from .normalize import normalize_question_text
from .schema import require
from .storage import atomic_write, bank_file, dumps, fingerprint, jsonl_text, open_bank, read_json, read_jsonl
from .tasks import read_task, write_task

NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
MARKS = {"🔴": "red", "⭐": "star"}
NUMBER = re.compile(r"^(?:\d+|[一二三四五六七八九十]+)\s*[.、．)）]\s*")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
RELATIONS = ("answers", "covers")
TOP_K = 6
EXCERPT = 160
CATALOG_LIMIT = 3000  # up to this many notes, a link task lists every note so the agent can look past the candidates
INTRO_NOTE = 200  # characters: a longer chapter opening becomes a note


# ---------------------------------------------------------------- parsing

def _title(raw):
    marks = [mark for symbol, mark in MARKS.items() if symbol in raw]
    for symbol in MARKS:
        raw = raw.replace(symbol, " ")
    return re.sub(r"\s+", " ", NUMBER.sub("", raw.strip())).strip(), marks


def _sections(lines, level):
    """Split lines at headings of exactly ``level`` outside code fences: (intro, [(heading, line_no, body_lines)])."""
    intro, sections, fenced = [], [], False
    for number, line in lines:
        if FENCE.match(line):
            fenced = not fenced
        match = None if fenced else HEADING.match(line)
        if match and len(match.group(1)) == level:
            sections.append((match.group(2), number, []))
        elif sections:
            sections[-1][2].append((number, line))
        else:
            intro.append((number, line))
    return intro, sections


def _text(lines):
    return "\n".join(line for _, line in lines).strip("\n").rstrip()


def parse_markdown(text):
    """One chapter: its title, intro and questions. ``##`` headings are questions; an ``##`` that only groups
    several ``###`` headings (e.g. 高频面试题) becomes a group whose ``###`` headings are the questions."""
    lines = list(enumerate(text.replace("\r\n", "\n").split("\n"), 1))
    head, chapters = _sections(lines, 1)
    title = _title(chapters[0][0])[0] if chapters else ""
    intro, sections = _sections(chapters[0][2] if chapters else head, 2)
    notes = []
    for heading, number, section in sections:
        name, marks = _title(heading)
        lead, children = _sections(section, 3)
        if len(children) >= 2:
            if _text(lead).strip():
                notes.append({"title": name, "heading": heading, "group": None, "marks": marks, "line": number, "body": _text(lead)})
            for child, child_number, child_body in children:
                child_name, child_marks = _title(child)
                notes.append({"title": child_name, "heading": child, "group": name, "marks": child_marks,
                              "line": child_number, "body": _text(child_body)})
        else:
            notes.append({"title": name, "heading": heading, "group": None, "marks": marks, "line": number, "body": _text(section)})
    if not sections and _text(intro).strip():
        notes.append({"title": title, "heading": title, "group": None, "marks": [], "line": 1, "body": _text(intro)})
        intro = []
    elif len(_text(intro).strip()) >= INTRO_NOTE:
        # A long chapter opening is content of its own (e.g. the kinds of memory); read and link it like a question.
        notes.insert(0, {"title": f"{title} · 导读" if title else "导读", "heading": "", "group": None, "marks": [],
                         "line": intro[0][0], "body": _text(intro)})
        intro = []
    return {"title": title, "intro": _text(intro), "notes": [n for n in notes if n["title"]]}


# ---------------------------------------------------------------- storage

def _collections_dir(bank):
    return bank_file(bank, "collections")


def _collection_path(bank, name):
    require(isinstance(name, str) and NAME.fullmatch(name), "Collection name: lowercase letters, digits, '_' or '-', at most 40")
    return bank_file(bank, f"collections/{name}.json")


def load_notes(bank):
    """Every collection, note and link of a bank. The caller holds the bank lock."""
    directory = _collections_dir(bank)
    collections = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            if NAME.fullmatch(path.stem):
                value = read_json(path)
                require(value.get("schema_version") == 1 and value.get("name") == path.stem, f"Invalid collection file: {path.name}")
                collections.append(value)
    collections.sort(key=lambda c: (c.get("order", 0), c["name"]))
    notes = [n for c in collections for n in c["notes"]]
    known = {n["id"] for n in notes}
    links_path = bank_file(bank, "collections/links.jsonl")
    links = [link for link in (read_jsonl(links_path) if links_path.is_file() else []) if link["note_id"] in known]
    return {"collections": collections, "notes": notes, "links": links}


def signature(bank):
    """Changes whenever a collection or the links change; lets the reader cache parsed notes."""
    directory = _collections_dir(bank)
    if not directory.is_dir():
        return ()
    return tuple(sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in directory.iterdir() if p.is_file()))


def _note_id(collection, file, group, title, seen):
    key = f"{collection}\n{file}\n{group or ''}\n{title}"
    seen[key] = seen.get(key, 0) + 1
    return "note_" + hashlib.sha256(f"{key}\n{seen[key]}".encode("utf-8")).hexdigest()[:20]


def import_collection(bank, source, name, title=None, origin=None, order=None):
    """Read every .md file of ``source`` (sorted by file name, one chapter each) into collection ``name``.

    Re-importing the same name replaces the collection; notes whose file, group and title are unchanged keep their
    IDs, so their links survive. The source folder is only read."""
    source = Path(source).expanduser().resolve()
    require(source.is_dir(), f"Not a folder: {source}")
    files = sorted(p for p in source.glob("*.md") if p.is_file() and not p.name.startswith("."))
    require(bool(files), f"No Markdown files in {source}")
    path = _collection_path(bank, name)
    chapters, notes, seen = [], [], {}
    for index, file in enumerate(files):
        raw = file.read_bytes()
        parsed = parse_markdown(raw.decode("utf-8-sig"))
        chapter_title = parsed["title"] or file.stem
        chapters.append({"index": index, "file": file.name, "title": chapter_title, "intro": parsed["intro"],
                         "sha256": hashlib.sha256(raw).hexdigest(), "notes": len(parsed["notes"])})
        for note in parsed["notes"]:
            notes.append({"id": _note_id(name, file.name, note["group"], note["title"], seen), "collection": name,
                          "chapter": index, "order": len(notes), **note, "file": file.name})
    require(bool(notes), "No questions found: expected '## ' headings")
    with open_bank(bank):
        previous = read_json(path) if path.is_file() else None
        value = {"schema_version": 1, "name": name, "title": title or (previous or {}).get("title") or source.name,
                 "origin": origin if origin is not None else (previous or {}).get("origin", ""),
                 "order": order if order is not None else (previous or {}).get("order", 0),
                 "source_folder": source.name, "imported_at": utc_now(), "chapters": chapters, "notes": notes}
        atomic_write(path, dumps(value) + "\n")
        kept, dropped = _prune_links(bank)
    old = {n["id"] for n in previous["notes"]} if previous else set()
    new = {n["id"] for n in notes}
    return {"collection": name, "title": value["title"], "chapters": len(chapters), "notes": len(notes),
            "marked": sum(bool(n["marks"]) for n in notes), "added": len(new - old), "removed": len(old - new),
            "unchanged": len(new & old), "links_kept": kept, "links_dropped": dropped,
            "next": "notes link-candidates, then notes link, to join your interview questions to these notes"}


def _prune_links(bank):
    links_path = bank_file(bank, "collections/links.jsonl")
    if not links_path.is_file():
        return 0, 0
    rows = read_jsonl(links_path)
    known = {n["id"] for n in load_notes(bank)["notes"]}
    kept = [row for row in rows if row["note_id"] in known]
    if len(kept) != len(rows):
        atomic_write(links_path, jsonl_text(kept))
    return len(kept), len(rows) - len(kept)


def remove_collection(bank, name):
    path = _collection_path(bank, name)
    with open_bank(bank):
        require(path.is_file(), f"No collection named {name}")
        count = len(read_json(path)["notes"])
        path.unlink()
        kept, dropped = _prune_links(bank)
    return {"removed": name, "notes": count, "links_dropped": dropped}


# ---------------------------------------------------------------- views

def chapter_title(collection, note):
    return collection["chapters"][note["chapter"]]["title"]


def note_card(note, collection, linked=()):
    return {"id": note["id"], "title": note["title"], "collection": collection["name"], "collection_title": collection["title"],
            "chapter": note["chapter"], "chapter_title": chapter_title(collection, note), "group": note["group"],
            "marked": bool(note["marks"]), "linked": len(linked), "asked": sum(q["frequency"] for q in linked)}


def source_of(note, collection):
    """Where the collection's own answer came from, shown beside it."""
    return {"collection": collection["title"], "origin": collection.get("origin", ""), "file": note["file"],
            "chapter": chapter_title(collection, note), "heading": note["heading"], "line": note["line"],
            "imported_at": collection["imported_at"]}


def linked_questions(bundle, rows):
    """note_id -> active bank questions linked to it (merged IDs follow their target)."""
    by_id = {q["id"]: q for q in rows}
    result = {}
    for link in bundle["links"]:
        q = by_id.get(link["question_id"])
        if q:
            result.setdefault(link["note_id"], []).append((q, link))
    return result


def resolve_links(bundle, data):
    targets = {q["id"]: q["merged_into"] or q["id"] for q in data["questions"]}
    return {**bundle, "links": [{**link, "question_id": targets.get(link["question_id"], link["question_id"])} for link in bundle["links"]]}


def summary(bank):
    with open_bank(bank, shared=True) as (_, config, data):
        bundle = load_notes(bank)
    linked = {link["note_id"] for link in bundle["links"]}
    return {"collections": [{"name": c["name"], "title": c["title"], "origin": c.get("origin", ""), "imported_at": c["imported_at"],
                             "chapters": [{"index": ch["index"], "title": ch["title"], "notes": ch["notes"]} for ch in c["chapters"]],
                             "notes": len(c["notes"]), "marked": sum(bool(n["marks"]) for n in c["notes"]),
                             "linked": sum(n["id"] in linked for n in c["notes"])} for c in bundle["collections"]],
            "links": len(bundle["links"]), "linked_questions": len({link["question_id"] for link in bundle["links"]})}


def search_notes(bank, query, limit=20):
    require(isinstance(query, str) and query.strip(), "Give --query")
    needle = query.strip().casefold()
    with open_bank(bank, shared=True):
        bundle = load_notes(bank)
    by_name = {c["name"]: c for c in bundle["collections"]}
    hits = [n for n in bundle["notes"] if needle in n["title"].casefold()] + \
           [n for n in bundle["notes"] if needle not in n["title"].casefold() and needle in n["body"].casefold()]
    return {"total": len(hits), "notes": [note_card(n, by_name[n["collection"]]) | {"excerpt": _excerpt(n)} for n in hits[:limit]]}


def show_note(bank, note_id):
    from .studysets import select
    with open_bank(bank, shared=True) as (_, config, data):
        bundle = resolve_links(load_notes(bank), data)
        rows = select(data, config, bank)
    note = next((n for n in bundle["notes"] if n["id"] == note_id), None)
    require(note is not None, f"Unknown note: {note_id}")
    collection = next(c for c in bundle["collections"] if c["name"] == note["collection"])
    linked = linked_questions(bundle, rows).get(note_id, [])
    return {**note_card(note, collection, [q for q, _ in linked]), "body": note["body"], "source": source_of(note, collection),
            "questions": [{"id": q["id"], "canonical": q["canonical"], "frequency": q["frequency"], "relation": link["relation"]}
                          for q, link in linked]}


def _excerpt(note):
    text = re.sub(r"\s+", " ", re.sub(r"[#>*`|]", " ", note["body"])).strip()
    return text[:EXCERPT] + ("…" if len(text) > EXCERPT else "")


# ---------------------------------------------------------------- linking

def _profile(text):
    return grams(retrieval_text(normalize_question_text(text)))


def _score(question, note, body):
    """How likely a note answers the question: its title inside the question counts most, then shared wording."""
    if not question or not note:
        return 0.0
    shared = len(question & note)
    contained = shared / len(note)
    jaccard = shared / len(question | note)
    covered = len(question & body) / len(question) if body else 0.0
    return round(0.5 * contained + 0.3 * jaccard + 0.2 * covered, 6)


def link_candidates(bank, question_ids=None, top_k=TOP_K, unlinked=False):
    """A task with the closest notes for each active question. The agent returns links with notes link."""
    from .studysets import select
    require(1 <= top_k <= 20, "top-k must be 1..20")
    with open_bank(bank) as (_, config, data):
        bundle = resolve_links(load_notes(bank), data)
        require(bool(bundle["notes"]), "No notes yet: import a collection first (notes import)")
        rows = select(data, config, bank, ids=question_ids) if question_ids else select(data, config, bank)
        if unlinked:
            judged = {link["question_id"] for link in bundle["links"]} | set(_judged_without_links(bank))
            rows = [q for q in rows if q["id"] not in judged]
        require(bool(rows), "No questions selected")
        by_name = {c["name"]: c for c in bundle["collections"]}
        profiles = [(n, _profile(n["title"]), _profile(n["body"][:800])) for n in bundle["notes"]]
        items = []
        for q in rows:
            mine = _profile(q["canonical"])
            ranked = sorted(((_score(mine, title, body), n) for n, title, body in profiles), key=lambda x: (-x[0], x[1]["order"]))
            current = {link["note_id"]: link["relation"] for link in bundle["links"] if link["question_id"] == q["id"]}
            candidates = [{"note_id": n["id"], "title": n["title"],
                           "where": f"{by_name[n['collection']]['title']} › {chapter_title(by_name[n['collection']], n)}",
                           "score": score, "excerpt": _excerpt(n), **({"current": current[n["id"]]} if n["id"] in current else {})}
                          for score, n in ranked[:top_k]]
            for note_id, relation in current.items():
                if all(c["note_id"] != note_id for c in candidates):
                    n = next(n for n in bundle["notes"] if n["id"] == note_id)
                    candidates.append({"note_id": note_id, "title": n["title"], "where": chapter_title(by_name[n["collection"]], n),
                                       "score": None, "excerpt": _excerpt(n), "current": relation})
            items.append({"question": {"id": q["id"], "canonical": q["canonical"], "frequency": q["frequency"]}, "candidates": candidates})
        # Word overlap misses paraphrases: in a real bank about half of the judged links were outside the candidates.
        catalog = [f"{n['id']}\t{by_name[n['collection']]['title']} › {chapter_title(by_name[n['collection']], n)}"
                   f"{' › ' + n['group'] if n['group'] else ''}\t{n['title']}"
                   for n in bundle["notes"]] if len(bundle["notes"]) <= CATALOG_LIMIT else None
        task = write_task(bank, "notes-link", data, config, items, notes_digest=fingerprint(sorted(n["id"] for n in bundle["notes"])),
                          catalog=catalog,
                          instruction="For each question, link the notes that a candidate could study to answer it. relation "
                                      "'answers': the note is about the same question; 'covers': the note explains a core part "
                                      "of it. Skip notes that only share a word or a broad topic. Any note ID is allowed: scan "
                                      "`catalog` (note_id, collection › chapter, title) or use notes search, because the "
                                      "candidates only share words. Questions you return no links for are recorded as having none.",
                          response_shape={"task_id": "<this task id>", "links": [{"question_id": "q_…", "note_id": "note_…",
                                                                                 "relation": "answers|covers", "reason": "short"}]})
    from .runs import run_path
    return {"task_id": task["id"], "task_file": str(run_path(bank, task["id"]) / "task.json"), "questions": len(items),
            "notes": len(bundle["notes"]), "catalog_in_task": catalog is not None, "preview": [{"question": i["question"]["canonical"][:60],
                                                        "best": i["candidates"][0]["title"] if i["candidates"] else None}
                                                       for i in items[:10]],
            "next": "Read task_file, judge each question's candidates, write {task_id, links} and run: notes link --input <response.json>"}


def _judged_path(bank):
    return bank_file(bank, "collections/_judged.json")


def _judged_without_links(bank):
    path = _judged_path(bank)
    return read_json(path).get("questions", []) if path.is_file() else []


def stage_links(bank, response):
    """Record the agent's links for every question of a link task; the task's questions get exactly these links."""
    require(isinstance(response, dict) and set(response) <= {"task_id", "links"} and isinstance(response.get("links"), list),
            "Expected {task_id, links: [...]}")
    with open_bank(bank) as (_, config, data):
        task = read_task(bank, response["task_id"], "notes-link", data, config)
        bundle = load_notes(bank)
        require(task["notes_digest"] == fingerprint(sorted(n["id"] for n in bundle["notes"])),
                "Task is stale: the notes changed; create a new link task")
        questions = {item["question"]["id"] for item in task["items"]}
        notes = {n["id"] for n in bundle["notes"]}
        offered = {(item["question"]["id"], c["note_id"]) for item in task["items"] for c in item["candidates"]}
        now, seen, rows = utc_now(), set(), []
        for link in response["links"]:
            require(isinstance(link, dict) and set(link) <= {"question_id", "note_id", "relation", "reason"}, "Invalid link")
            require(link.get("question_id") in questions, f"Question not in this task: {link.get('question_id')}")
            require(link.get("note_id") in notes, f"Unknown note: {link.get('note_id')}")
            require(link.get("relation") in RELATIONS, "relation must be answers or covers")
            require(isinstance(link.get("reason", ""), str) and len(link.get("reason", "")) <= 300, "reason: at most 300 characters")
            key = (link["question_id"], link["note_id"])
            require(key not in seen, f"Duplicate link: {key}")
            seen.add(key)
            rows.append({"question_id": link["question_id"], "note_id": link["note_id"], "relation": link["relation"],
                         "reason": link.get("reason", ""), "task_id": task["id"], "judged_by": "agent",
                         "outside_candidates": key not in offered, "created_at": now})
        links_path = bank_file(bank, "collections/links.jsonl")
        existing = read_jsonl(links_path) if links_path.is_file() else []
        kept = [row for row in existing if row["question_id"] not in questions]
        atomic_write(links_path, jsonl_text(kept + rows))
        linked = {row["question_id"] for row in rows}
        judged = (set(_judged_without_links(bank)) - linked) | (questions - linked)
        atomic_write(_judged_path(bank), dumps({"schema_version": 1, "questions": sorted(judged)}) + "\n")
    return {"task_id": task["id"], "questions": len(questions), "linked_questions": len(linked), "links": len(rows),
            "answers": sum(r["relation"] == "answers" for r in rows), "covers": sum(r["relation"] == "covers" for r in rows),
            "outside_candidates": sum(r["outside_candidates"] for r in rows), "without_links": len(questions - linked),
            "replaced": len(existing) - len(kept)}


# ---------------------------------------------------------------- CLI

def add_parsers(sub, common):
    from pathlib import Path as P
    notes = sub.add_parser("notes", parents=[common], help="八股文 collections beside your interview questions: import, browse, link")
    action = notes.add_subparsers(dest="notes_action", required=True)
    imp = action.add_parser("import", parents=[common], help="Import a folder of Markdown chapters as one collection")
    imp.add_argument("--source", type=P, required=True, help="Folder of .md files; each '## ' heading is one question")
    imp.add_argument("--name", required=True, help="Short ID, e.g. agent or java")
    imp.add_argument("--title", help="Display name, e.g. Agent 八股")
    imp.add_argument("--origin", help="Where the collection comes from, shown with every answer")
    imp.add_argument("--order", type=int, help="Position among collections (lower first)")
    action.add_parser("list", parents=[common], help="Collections, chapters and link counts")
    find = action.add_parser("search", parents=[common], help="Find notes by words in the title or answer")
    find.add_argument("--query", required=True)
    find.add_argument("--limit", type=int, default=20)
    show = action.add_parser("show", parents=[common], help="One note with its answer, source and linked questions")
    show.add_argument("note_id")
    remove = action.add_parser("remove", parents=[common], help="Delete a collection and its links")
    remove.add_argument("--name", required=True)
    candidates = action.add_parser("link-candidates", parents=[common], help="Task: closest notes for each question")
    candidates.add_argument("--question", action="append", help="Only these questions (repeatable)")
    candidates.add_argument("--unlinked", action="store_true", help="Only questions never judged before")
    candidates.add_argument("--top-k", type=int, default=TOP_K)
    link = action.add_parser("link", parents=[common], help="Record the agent's links from a link task response")
    link.add_argument("--input", type=P, required=True)


def dispatch(bank, args):
    name = args.notes_action
    if name == "import":
        return import_collection(bank, args.source, args.name, args.title, args.origin, args.order)
    if name == "list":
        return summary(bank)
    if name == "search":
        return search_notes(bank, args.query, args.limit)
    if name == "show":
        return show_note(bank, args.note_id)
    if name == "remove":
        return remove_collection(bank, args.name)
    if name == "link-candidates":
        return link_candidates(bank, args.question, args.top_k, args.unlinked)
    return stage_links(bank, read_json(args.input))
