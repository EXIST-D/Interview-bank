"""Portable, provenance-preserving study exports. User data stays in bank/exports."""
import copy
import csv
import html
import io
import re
from pathlib import Path
from urllib.parse import quote

from .ids import utc_now
from .search import select_questions
from .schema import require
from .storage import atomic_write, bank_file, dumps, jsonl_text, open_bank
from .catalog import display
from .editorial import exclusion_reason
from .messages import group_title, label, language, text


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text


def md(text):
    return re.sub(r"([\\`*_\[\]#])", lambda match: "\\" + match.group(0), html.escape(str(text), quote=False))


def fenced(text, language=""):
    fence = "`" * max(3, max((len(s) for s in str(text).split() if set(s) == {"`"}), default=0) + 1)
    # Any contiguous run may occur inside code, not only whitespace-delimited runs.
    import re
    fence = "`" * max(len(fence), max((len(m) for m in re.findall(r"`+", str(text))), default=0) + 1)
    return f"{fence}{language}\n{text}\n{fence}"


def report_group(question):
    domains = question['domains']
    groups = [('ai.rag', 'RAG 与知识检索'), ('ai.agent.memory', '记忆与上下文'),
              ('ai.agent.tool-use', '工具调用与协议'), ('ai.agent.protocol', '工具调用与协议'),
              ('ai.multi-agent', '多智能体协作'), ('ai.agent.safety', 'Agent 安全与可靠性'),
              ('ai.evaluation', '评测与优化'), ('ai.agent', 'Agent 架构与工作流'),
              ('ai', '大模型基础与应用'), ('backend.database', '数据库'),
              ('backend.cache', '缓存'), ('backend', '后端工程'),
              ('computer-science.algorithm', '算法与数据结构'),
              ('computer-science.data-structure', '算法与数据结构'),
              ('computer-science', '计算机基础'), ('frontend', '前端工程'),
              ('testing', '测试与质量'), ('engineering', '软件工程'),
              ('cloud', '云与运维'), ('career', '项目与协作')]
    for domain in domains:
        for prefix, title in groups:
            if domain == prefix or domain.startswith(prefix + '.'):
                return title
        # Every built-in top-level domain has a catalog label (移动技术, 信息安全, 数据技术 ...).
        top = domain.split('.')[0]
        if display('domains', top) != top:
            return display('domains', top)
    return '其他知识题'


ANSWER_EXTRAS = ('folded', 'inline', 'none')


def answer_extras(answer, mode='folded', lang='zh-CN'):
    """Spoken version, follow-ups and pitfalls are interview practice material; show them when written."""
    parts, colon = [], text(lang, 'colon')
    if answer.get('spoken_answer', '').strip():
        title = text(lang, 'spoken')
        parts.append((title, f'**{title}**{colon}' + md(answer['spoken_answer'].strip())))
    for field, key in (('follow_up_questions', 'follow_ups'), ('common_mistakes', 'mistakes')):
        if answer.get(field):
            title = text(lang, key)
            parts.append((title, f'**{title}**\n' + '\n'.join('- ' + md(item) for item in answer[field])))
    if mode == 'none' or not parts:
        return []
    body = '\n\n'.join(part for _, part in parts)
    if mode == 'inline':
        return [body]
    return ['<details><summary>' + ' · '.join(title for title, _ in parts) + '</summary>\n\n' + body + '\n\n</details>']


def answer_section(question, extras='folded', lang='zh-CN'):
    """Publish concise sourced answers; retain unverified/history content in JSON."""
    answer, status = question['answer'], question['answer_status']
    heading, colon = text(lang, 'answer'), text(lang, 'colon')
    if not answer or status == 'missing':
        return [heading + colon + text(lang, 'pending')]
    if status not in ('source_backed', 'reviewed'):
        return [heading + colon + text(lang, 'stale' if status == 'stale' else 'draft')]
    if not answer['sources']:
        return [heading + colon + text(lang, 'uncited')]
    out = [f"{heading} · {text(lang, 'reviewed' if status == 'reviewed' else 'sourced')}"]
    lines = [line.strip() for line in answer['short_answer'].splitlines() if line.strip()]
    if len(lines) > 1:
        out.append('\n'.join('- ' + md(re.sub(r'^(?:[-*•]|\d+[.)、])\s*', '', line)) for line in lines))
    else:
        out.append(md(answer['short_answer']))
    links = ['[' + md(s['title']) + '](' + quote(s['url'], safe=':/?&=%+#@!$,;~') + ')' for s in answer['sources']]
    out.append(text(lang, 'sources') + text(lang, 'source_sep').join(links))
    return out + answer_extras(answer, extras, lang)


def _tag(value):
    return re.sub(r"\s+", "_", value.strip())


def anki(payload, lang='zh-CN'):
    """Tab-separated notes Anki imports directly: front, back (HTML), tags.

    Only currently valid sourced answers go on the back; other questions keep an empty back and the tag 待核验.
    """
    selected = set(payload['report']['question_ids'])
    lines = ["#separator:Tab", "#html:true", "#tags column:3"]
    for q in payload['questions']:
        if q['id'] not in selected:
            continue
        front = html.escape(q['canonical'].strip()).replace("\n", "<br>")
        answer = q['answer']
        valid = bool(answer and answer['sources'] and q['answer_status'] in ('source_backed', 'reviewed'))
        back = ""
        if valid:
            back = "<p>" + html.escape(answer['short_answer']).replace("\n", "<br>") + "</p>"
            back += "<p>" + " · ".join(f'<a href="{html.escape(s["url"])}">{html.escape(s.get("title") or s["url"])}</a>'
                                       for s in answer['sources']) + "</p>"
        if q.get('problem_url'):
            back += (f'<p>{text(lang, "anki_problem")}{text(lang, "colon")}<a href="{html.escape(q["problem_url"]["url"])}">'
                     f'{html.escape(q["problem_url"]["title"])}</a></p>')
        tags = [_tag(t) for t in (*q['domains'], *q['technologies'])] + ([] if valid else [text(lang, "unverified_tag")])
        lines.append("\t".join(field.replace("\t", " ") for field in (front, back, " ".join(dict.fromkeys(tags)))))
    return "\n".join(lines) + "\n"


def _group_name(lang, title, question):
    return group_title(lang, title, question['domains'][0].split('.')[0] if question['domains'] else None)


def markdown(payload, *, include_answers=True, extras='folded', lang='zh-CN'):
    """Navigable study report with topic totals and frequency-ordered questions."""
    selected = set(payload['report']['question_ids'])
    questions = [q for q in payload['questions'] if q['id'] in selected]
    companies = {c['id']: c['name'] for c in payload['companies']}
    sources = {s['id']: s for s in payload['sources']}
    sep, colon = text(lang, 'list_sep'), text(lang, 'colon')
    out = ['# ' + text(lang, 'title'), text(lang, 'intro', count=len(questions))]
    if payload.get("context"):
        context = payload["context"]
        out.append(text(lang, 'topic', name=md(context.get("name", "")), revision=context.get("selection_revision", 1)))
        if 'expression' in context:
            from .selection import describe
            out.append(text(lang, 'filters', expression=md(describe(context['expression']))))
        if context.get('source_intent'):
            out.append(text(lang, 'goal', goal=md(context['source_intent'])))
        if context.get('changed_questions'):
            out.append(text(lang, 'changed', count=len(context['changed_questions'])))
        coverage = context.get("jd_coverage", {})
        if coverage.get("requirements"):
            out.append(text(lang, 'jd', requirements=coverage['requirements'], covered=coverage['directly_covered']))
        if context.get('requirements'):
            out.append('\n'.join('- ' + md(r['quote']) + colon + md(r['coverage']) for r in context['requirements']))
    groups, names = {}, {}
    for q in questions:
        title = report_group(q)
        groups.setdefault(title, []).append(q)
        names.setdefault(title, _group_name(lang, title, q))
    if groups:
        out.append('## ' + text(lang, 'overview'))
        out.append(text(lang, 'overview_head') + '\n|---|---:|\n' + '\n'.join(f'| {names[title]} | {len(rows)} |' for title, rows in groups.items()))
    verified = sum(bool(q['answer'] and q['answer']['sources'] and q['answer_status'] in ('source_backed', 'reviewed')) for q in questions)
    if include_answers:
        out.append(text(lang, 'progress', verified=verified, pending=len(questions) - verified))
    for title, rows in groups.items():
        out.append('## ' + text(lang, 'group', title=names[title], count=len(rows)))
        for number, q in enumerate(sorted(rows, key=lambda row: (-row['frequency'], row['canonical'])), 1):
            wording = q['canonical'].strip()
            # Keep code/line-sensitive prompts out of the heading and preserve them verbatim.
            if '\n' in wording:
                out.append(f'### {number}. ' + md(wording.splitlines()[0]))
                out.append(fenced(wording))
            else:
                out.append(f'### {number}. ' + md(wording))
            link = q.get('problem_url')
            if link:
                out.append(text(lang, 'problem') + f"[{md(link['title'])}](<{link['url']}>)")
            if include_answers:
                out.extend(answer_section(q, extras, lang))
            company_names = sorted({companies[o['company_id']] for o in q['occurrences'] if o['company_id'] in companies})
            tags = list(dict.fromkeys(label(lang, d, v, display(d, v)) for d in ('domains', 'technologies') for v in q[d]))
            meta = [text(lang, 'seen', count=q['frequency'])]
            if company_names: meta.append(text(lang, 'companies') + sep.join(md(n) for n in company_names))
            if tags: meta.append(text(lang, 'tags') + ' / '.join(md(t) for t in tags[:6]) + (text(lang, 'more') if len(tags) > 6 else ''))
            years = sorted({o['event_date'][:4] for o in q['occurrences'] if o['event_date']})
            if years:
                meta.append(text(lang, 'event_years') + sep.join(years))
            else:
                source_years = sorted({sources[o['source_id']]['source_date'][:4] for o in q['occurrences']
                                       if o['source_id'] in sources and sources[o['source_id']]['source_date']})
                if source_years: meta.append(text(lang, 'source_years') + sep.join(source_years))
            out.append(' · '.join(meta))
    if not questions: out.append(text(lang, 'empty'))
    return '\n\n'.join(out) + '\n'


def export_bank(bank, output, format="markdown", *, include_paths=False, answer_mode="both", report_context=None, answer_extras_mode="folded", **filters):
    require(format in ("markdown", "json", "jsonl", "csv", "viewer", "anki"), "Unsupported export format")
    require(answer_extras_mode in ANSWER_EXTRAS, "answer extras must be folded, inline or none")
    require(answer_mode in ("both", "with", "without"), "Invalid answer mode")
    require(format == 'markdown' or answer_mode == 'both', "Answer mode only applies to Markdown")
    with open_bank(bank, shared=True) as (_, config, data):
        target = Path(output)
        if not target.is_absolute():
            target = bank / target if target.parts and target.parts[0] == "exports" else bank / "exports" / target
        exports = bank_file(bank, "exports").resolve()
        require(target.resolve().is_relative_to(exports) and target.resolve() != exports, "Export output must stay inside bank/exports")
        questions = select_questions(data, stale_days=config.get("answer_stale_days", 180), **filters)
        qids = {q["id"] for q in questions}
        sids = {o["source_id"] for q in questions for o in q["occurrences"]}
        sources = copy.deepcopy([s for s in data["sources"] if s["id"] in sids])
        if not include_paths:
            for source in sources:
                source["path"] = None
        payload = {"schema_version": 1, "exported_at": utc_now(), "filters": filters, "questions": questions,
                   "sources": sources, "companies": [c for c in data["companies"] if c["id"] in {o["company_id"] for q in questions for o in q["occurrences"]}],
                   "relations": [r for r in data["relations"] if r["from_question_id"] in qids and r["to_question_id"] in qids]}
        if report_context is not None:
            payload["context"] = report_context
        excluded = [{"question_id": q["id"], "reason": exclusion_reason(q)} for q in questions if exclusion_reason(q)]
        omitted = {item["question_id"] for item in excluded}
        payload["report"] = {"question_ids": [q["id"] for q in questions if q["id"] not in omitted],
                             "excluded": excluded, "year_policy": "event year, otherwise explicitly labeled source year",
                             "numbering_policy": "per domain, frequency descending, canonical text tie-break",
                             "groups": [{"title": title, "count": sum(q['id'] not in omitted and report_group(q) == title for q in questions)}
                                        for title in dict.fromkeys(report_group(q) for q in questions if q['id'] not in omitted)]}
        companion = question_target = None
        visible = [q for q in questions if q['id'] not in omitted]
        answered = sum(bool(q['answer'] and q['answer']['sources'] and q['answer_status'] in ('source_backed', 'reviewed')) for q in visible)
        if format == "markdown":
            companion = target.with_name(target.name + ".details.json")
            require(companion.resolve().is_relative_to(exports), "Report details must stay inside bank/exports")
            if answer_mode == 'both':
                question_target = target.with_name(target.stem + '（题目版）' + target.suffix)
                require(question_target.resolve().is_relative_to(exports), "Question report must stay inside bank/exports")
                require(len({target.resolve(), companion.resolve(), question_target.resolve()}) == 3, "Export paths must not alias each other")
            payload['report']['answer_mode'] = answer_mode
            payload['report']['answered_questions'] = answered
            payload['report']['pending_answers'] = len(visible) - answered
            lang = language(config)
            content = markdown(payload, include_answers=answer_mode != 'without', extras=answer_extras_mode, lang=lang)
            question_content = markdown(payload, include_answers=False, lang=lang) if question_target else None
            atomic_write(companion, dumps(payload) + "\n")
            if question_target:
                atomic_write(question_target, question_content)
        elif format in ("json", "viewer"):
            content = dumps(payload) + "\n"
        elif format == "anki":
            content = anki(payload, language(config))
        elif format == "jsonl":
            content = jsonl_text({"schema_version": 1, "question": q,
                "sources": [s for s in sources if s["id"] in {o["source_id"] for o in q["occurrences"]}],
                "companies": [c for c in payload["companies"] if c["id"] in {o["company_id"] for o in q["occurrences"]}],
                "relations": [r for r in payload["relations"] if q["id"] in (r["from_question_id"], r["to_question_id"])]} for q in questions)
        else:
            handle = io.StringIO(newline="")
            writer = csv.writer(handle)
            writer.writerow(["id", "question", "frequency", "total_frequency", "roles", "domains", "technologies", "answer_status", "short_answer", "source_ids", "occurrences_json", "citations_json", "companies_json"])
            for q in questions:
                writer.writerow([safe_cell(v) for v in (q["id"], q["canonical"], q["frequency"], q["total_frequency"],
                    ";".join(q["role_tracks"]), ";".join(q["domains"]), ";".join(q["technologies"]), q["answer_status"],
                    q["answer"]["short_answer"] if q["answer"] else "", ";".join(sorted({o["source_id"] for o in q["occurrences"]})),
                    dumps(q["occurrences"]), dumps(q["answer"]["sources"] if q["answer"] else []),
                    dumps([c for c in payload["companies"] if c["id"] in {o["company_id"] for o in q["occurrences"]}]))])
            content = "\ufeff" + handle.getvalue()
        atomic_write(target, content)
        return {"output": str(target.resolve()), "format": format,
                "questions": len(payload["report"]["question_ids"]) if format == "markdown" else len(questions),
                "report_questions": len(payload["report"]["question_ids"]), "excluded_questions": len(excluded),
                "details_output": str(companion.resolve()) if companion else None,
                "answer_output": str(target.resolve()) if format == 'markdown' and answer_mode != 'without' else None,
                "question_output": str(question_target.resolve()) if question_target else str(target.resolve()) if format == 'markdown' and answer_mode == 'without' else None,
                "answered_questions": answered, "pending_answers": len(visible) - answered,
                "source_paths_included": include_paths}
