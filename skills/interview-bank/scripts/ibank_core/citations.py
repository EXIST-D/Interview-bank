"""The two commands that make network requests, both on demand and both public-address only.

verify-citations: do cited pages still answer (status, final URL, time of the check)? Results go to
logs/citations-*.json; the host decides whether an answer needs research again.

page-text: save the readable text of pages the host is citing, so `answer --page-texts` can check every
evidence_quote verbatim even when the host's own web tool returns summaries instead of page text. Texts go to
cache/pages/ (rebuildable, never part of the canonical bank).
"""
from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
import urllib.error
import urllib.request
from typing import Callable, Iterable, Optional
from urllib.parse import urlparse

from . import __version__
from .ids import utc_now
from .schema import require
from .search import select_questions
from .storage import atomic_write, bank_file, dumps, open_bank

TIMEOUT = 10
MAX_REDIRECTS = 3
MAX_URLS = 200


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS


def _public(url: str) -> bool:
    """Citations are public pages; refuse loopback, private and link-local targets."""
    host = urlparse(url).hostname or ""
    if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return True  # unresolvable: the request itself reports the failure
    return all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses)


def check_url(url: str, opener: Optional[Callable] = None) -> dict:
    opener = opener or urllib.request.build_opener(_Redirects()).open
    result = {"url": url, "checked_at": utc_now(), "status": None, "final_url": None, "ok": False, "error": None}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": f"interview-bank/{__version__} citation-check"})
        try:
            with opener(request, timeout=TIMEOUT) as response:
                result.update(status=response.status, final_url=response.geturl(), ok=200 <= response.status < 400, error=None)
                return result
        except urllib.error.HTTPError as exc:
            result.update(status=exc.code, final_url=exc.geturl() if hasattr(exc, "geturl") else url, error=f"HTTP {exc.code}")
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue  # some servers refuse HEAD; ask once more with GET
            return result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            result["error"] = str(getattr(exc, "reason", exc))
            return result
    return result


def verify_citations(bank, question_ids: Iterable[str] = (), workflow_id: Optional[str] = None, limit: int = 50,
                     allow_private: bool = False, opener: Optional[Callable] = None) -> dict:
    require(type(limit) is int and 1 <= limit <= MAX_URLS, f"limit must be 1..{MAX_URLS}")
    with open_bank(bank, shared=True) as (_, config, data):
        ids = list(question_ids)
        if workflow_id:
            from .state import record
            ids += list(record("workflows", data, workflow_id)["question_ids"])
        rows = select_questions(data, stale_days=config.get("answer_stale_days", 180), question_ids=set(ids) if ids else None)
        targets = []
        for q in rows:
            if q["answer"] and q["answer"]["sources"]:
                for source in q["answer"]["sources"]:
                    targets.append((q["id"], q["answer"]["id"], source["url"]))
    targets = targets[:limit]
    results, cache = [], {}
    for qid, answer_id, url in targets:
        if url not in cache:
            if not allow_private and not _public(url):
                cache[url] = {"url": url, "checked_at": utc_now(), "status": None, "final_url": None, "ok": False,
                              "error": "refused: not a public address"}
            else:
                cache[url] = check_url(url, opener)
        results.append({"question_id": qid, "answer_id": answer_id, **cache[url]})
    broken = [r for r in results if not r["ok"]]
    report = {"checked": len(results), "unique_urls": len(cache), "broken": len(broken), "results": results,
              "network_request_performed": bool(cache),
              "hint": "A failed link is a reason to re-check the answer, not proof it is wrong. Show the broken links to the user; "
                      "research again or mark stale with answer-review --status stale --reason."}
    with open_bank(bank) as _:
        log = bank_file(bank, f"logs/citations-{utc_now().replace(':', '').replace('+', 'Z')}.json")
        atomic_write(log, dumps(report) + "\n")
    return {**report, "log": str(log)}


MAX_PAGE_BYTES = 3_000_000
SKIPPED_TAGS = {"script", "style", "noscript", "svg", "template", "head"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "ul", "ol", "tr", "table", "br", "h1", "h2", "h3", "h4", "h5", "h6",
              "pre", "blockquote", "dd", "dt", "header", "footer", "main", "nav", "aside", "figure", "figcaption"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    parser.close()
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in html.unescape("".join(parser.parts)).split("\n"))
    return "\n".join(line for line in lines if line)


def fetch_text(url: str, opener: Optional[Callable] = None) -> dict:
    opener = opener or urllib.request.build_opener(_Redirects()).open
    request = urllib.request.Request(url, headers={"User-Agent": f"interview-bank/{__version__} page-text",
                                                   "Accept": "text/html,text/plain;q=0.9"})
    try:
        with opener(request, timeout=TIMEOUT) as response:
            kind = response.headers.get("Content-Type", "")
            body = response.read(MAX_PAGE_BYTES + 1)
            charset = response.headers.get_content_charset() or "utf-8"
            final = response.geturl()
    except urllib.error.HTTPError as exc:
        return {"url": url, "ok": False, "error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"url": url, "ok": False, "error": str(getattr(exc, "reason", exc))}
    if not ("html" in kind or kind.startswith("text/") or not kind):
        return {"url": url, "ok": False, "error": f"not a text page ({kind})"}
    if len(body) > MAX_PAGE_BYTES:
        return {"url": url, "ok": False, "error": "page larger than 3 MB"}
    raw = body.decode(charset, errors="replace")
    text = html_text(raw) if "html" in kind or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")) else raw
    return {"url": url, "ok": bool(text.strip()), "final_url": final, "text": text,
            "error": None if text.strip() else "no readable text (the page may need JavaScript)"}


def page_texts(bank, urls: Iterable[str], allow_private: bool = False, opener: Optional[Callable] = None) -> dict:
    urls = list(dict.fromkeys(urls))
    require(1 <= len(urls) <= 50, "page-text takes 1..50 URLs")
    for url in urls:
        parsed = urlparse(url)
        require(parsed.scheme in ("http", "https") and bool(parsed.netloc) and not parsed.username, f"Not a public HTTP(S) URL: {url}")
    folder = bank_file(bank, "cache/pages")
    folder.mkdir(parents=True, exist_ok=True)
    mapping, results = {}, []
    for url in urls:
        if not allow_private and not _public(url):
            results.append({"url": url, "ok": False, "error": "refused: not a public address"})
            continue
        fetched = fetch_text(url, opener)
        if fetched["ok"]:
            path = folder / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] + ".txt")
            atomic_write(path, fetched["text"] + "\n")
            mapping[url] = str(path)
            moved = fetched["final_url"].rstrip("/") != url.rstrip("/")
            if moved:
                mapping[fetched["final_url"]] = str(path)  # either URL may be cited; both find the saved text
            results.append({"url": url, "ok": True, "path": str(path), "characters": len(fetched["text"]),
                            "final_url": fetched["final_url"], **({"redirected": True} if moved else {})})
        else:
            results.append({"url": url, "ok": False, "error": fetched["error"]})
    index = folder / f"page-texts-{utc_now().replace(':', '').replace('+', 'Z')}.json"
    atomic_write(index, dumps(mapping) + "\n")
    redirected = [r["url"] for r in results if r.get("redirected")]
    return {"saved": len(mapping), "failed": len(results) - len(mapping), "results": results, "page_texts": str(index),
            **({"redirected": redirected,
                "warning": "These URLs redirected elsewhere (often an old link landing on an overview page). Read the saved "
                           "text before quoting it; if it is the document you meant, cite final_url (both URLs map to the "
                           "saved text), otherwise find the right page."}
               if redirected else {}),
            "network_request_performed": True,
            "next": f"Quote evidence_quote verbatim from these texts, then answer --page-texts {index}. "
                    "A page that failed (403, JavaScript-only) can still be cited; its quotes are just not verified."}
