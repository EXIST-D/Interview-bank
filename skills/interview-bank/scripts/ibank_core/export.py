"""Portable, provenance-preserving study exports. User data stays in bank/exports."""
import copy
import csv
import html
import io
import re
from pathlib import Path
from urllib.parse import quote

from .ids import utc_now
from .index import connect_index
from .search import select_questions
from .schema import require
from .storage import atomic_write, bank_file, dumps, jsonl_text, open_bank
from .catalog import display
from .editorial import exclusion_reason


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
    return '其他知识题'


def answer_section(question):
    """Publish concise sourced answers; retain unverified/history content in JSON."""
    answer, status = question['answer'], question['answer_status']
    if not answer or status == 'missing':
        return ['答案（参考）：待检索与核验。']
    if status not in ('source_backed', 'reviewed'):
        note = '待重新核验；历史答案见结构化附件。' if status == 'stale' else '待检索与核验；已有草稿见结构化附件。'
        return ['答案（参考）：' + note]
    if not answer['sources']:
        return ['答案（参考）：待补充来源核验；已有内容见结构化附件。']
    state = '已人工审阅' if status == 'reviewed' else '已核验来源'
    out = [f'答案（参考） · {state}']
    lines = [line.strip() for line in answer['short_answer'].splitlines() if line.strip()]
    if len(lines) > 1:
        out.append('\n'.join('- ' + md(re.sub(r'^(?:[-*•]|\d+[.)、])\s*', '', line)) for line in lines))
    else:
        out.append(md(answer['short_answer']))
    links = ['[' + md(s['title']) + '](' + quote(s['url'], safe=':/?&=%+#@!$,;~') + ')' for s in answer['sources']]
    out.append('参考资料：' + '；'.join(links))
    return out


def markdown(payload, *, include_answers=True):
    """Navigable study report with topic totals and frequency-ordered questions."""
    selected = set(payload['report']['question_ids'])
    questions = [q for q in payload['questions'] if q['id'] in selected]
    companies = {c['id']: c['name'] for c in payload['companies']}
    sources = {s['id']: s for s in payload['sources']}
    out = ['# 面试题整理报告', f"共 {len(questions)} 道题；出现次数按收集记录统计。各领域内按出现次数降序排列、从 1 编号，同次数按题干排序。"]
    groups = {}
    for q in questions:
        groups.setdefault(report_group(q), []).append(q)
    if groups:
        out.append('## 领域概览')
        out.append('| 领域 | 题目数 |\n|---|---:|\n' + '\n'.join(f'| {title} | {len(rows)} |' for title, rows in groups.items()))
    verified = sum(bool(q['answer'] and q['answer']['sources'] and q['answer_status'] in ('source_backed', 'reviewed')) for q in questions)
    if include_answers:
        out.append(f'答案进度：已核验来源 {verified} 道，待检索或重新核验 {len(questions) - verified} 道。答案均仅供参考。')
    for title, rows in groups.items():
        out.append(f'## {title}（{len(rows)} 题）')
        for number, q in enumerate(sorted(rows, key=lambda row: (-row['frequency'], row['canonical'])), 1):
            text = q['canonical'].strip()
            # Keep code/line-sensitive prompts out of the heading and preserve them verbatim.
            if '\n' in text:
                out.append(f'### {number}. ' + md(text.splitlines()[0]))
                out.append(fenced(text))
            else:
                out.append(f'### {number}. ' + md(text))
            if include_answers:
                out.extend(answer_section(q))
            company_names = sorted({companies[o['company_id']] for o in q['occurrences'] if o['company_id'] in companies})
            tags = list(dict.fromkeys(display(d, v) for d in ('domains', 'technologies') for v in q[d]))
            meta = [f"出现 {q['frequency']} 次"]
            if company_names: meta.append('公司：' + '、'.join(md(n) for n in company_names))
            if tags: meta.append('标签：' + ' / '.join(md(t) for t in tags[:6]) + (' 等' if len(tags) > 6 else ''))
            years = sorted({o['event_date'][:4] for o in q['occurrences'] if o['event_date']})
            if years:
                meta.append('面试年份：' + '、'.join(years))
            else:
                source_years = sorted({sources[o['source_id']]['source_date'][:4] for o in q['occurrences']
                                       if o['source_id'] in sources and sources[o['source_id']]['source_date']})
                if source_years: meta.append('资料年份：' + '、'.join(source_years))
            out.append(' · '.join(meta))
    if not questions: out.append('当前筛选下没有可复用的知识题。')
    return '\n\n'.join(out) + '\n'


def export_bank(bank, output, format="markdown", *, include_paths=False, answer_mode="both", **filters):
    require(format in ("markdown", "json", "jsonl", "csv", "viewer"), "Unsupported export format")
    require(answer_mode in ("both", "with", "without"), "Invalid answer mode")
    require(format == 'markdown' or answer_mode == 'both', "Answer mode only applies to Markdown")
    with open_bank(bank) as (_, config, data):
        target = Path(output)
        if not target.is_absolute():
            target = bank / target if target.parts and target.parts[0] == "exports" else bank / "exports" / target
        exports = bank_file(bank, "exports").resolve()
        require(target.resolve().is_relative_to(exports) and target.resolve() != exports, "Export output must stay inside bank/exports")
        conn = connect_index(bank, data)
        try:
            questions = select_questions(conn, stale_days=config.get("answer_stale_days", 180), **filters)
        finally:
            conn.close()
        qids = {q["id"] for q in questions}
        sids = {o["source_id"] for q in questions for o in q["occurrences"]}
        sources = copy.deepcopy([s for s in data["sources"] if s["id"] in sids])
        if not include_paths:
            for source in sources:
                source["path"] = None
        payload = {"schema_version": 1, "exported_at": utc_now(), "filters": filters, "questions": questions,
                   "sources": sources, "companies": [c for c in data["companies"] if c["id"] in {o["company_id"] for q in questions for o in q["occurrences"]}],
                   "relations": [r for r in data["relations"] if r["from_question_id"] in qids and r["to_question_id"] in qids]}
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
            content = markdown(payload, include_answers=answer_mode != 'without')
            question_content = markdown(payload, include_answers=False) if question_target else None
            atomic_write(companion, dumps(payload) + "\n")
            if question_target:
                atomic_write(question_target, question_content)
        elif format in ("json", "viewer"):
            content = dumps(payload) + "\n"
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
