"""Optional online check that cited pages still answer: status, final URL and time of the check.

This is the only command that makes network requests, and only when the user asks for it. It
reads nothing into the bank: results go to logs/citations-*.json and are returned to the host,
which decides whether an answer needs research again (answer-review --status stale).
"""
from __future__ import annotations

import ipaddress
import socket
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
