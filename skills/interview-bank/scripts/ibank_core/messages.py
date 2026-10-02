"""Reader-facing wording for reports (and the Web reader's language switch), in Chinese and English.

config.language decides: anything starting with "en" gives English, everything else Chinese. CLI errors stay
in English because agents read them; question text is never translated.
"""
from __future__ import annotations

MESSAGES = {
    "zh-CN": {
        "title": "面试题整理报告",
        "intro": "共 {count} 道题；出现次数按收集记录统计。各领域内按出现次数降序排列、从 1 编号，同次数按题干排序。",
        "topic": "专题：{name} · 选择修订：{revision}",
        "filters": "筛选条件：{expression}；来源条件由同一条收集记录满足。",
        "goal": "备考目标：{goal}",
        "changed": "其中 {count} 道题自专题保存后发生变化，相关 JD 映射待重新核验。",
        "jd": "JD 知识要求 {requirements} 项，直接覆盖 {covered} 项；这只是当前题库的知识覆盖，不代表岗位能力或面试命中率。",
        "overview": "领域概览", "overview_head": "| 领域 | 题目数 |",
        "progress": "答案进度：已核验来源 {verified} 道，待检索或重新核验 {pending} 道。答案均仅供参考。",
        "group": "{title}（{count} 题）",
        "problem": "原题链接：", "seen": "出现 {count} 次", "companies": "公司：", "tags": "标签：", "more": " 等",
        "event_years": "面试年份：", "source_years": "资料年份：", "list_sep": "、", "empty": "当前筛选下没有可复用的知识题。",
        "answer": "答案（参考）", "pending": "待检索与核验。", "stale": "待重新核验；历史答案见结构化附件。",
        "draft": "待检索与核验；已有草稿见结构化附件。", "uncited": "待补充来源核验；已有内容见结构化附件。",
        "reviewed": "已人工审阅", "sourced": "已核验来源", "sources": "参考资料：", "source_sep": "；",
        "spoken": "口述版", "follow_ups": "常见追问", "mistakes": "易错点", "colon": "：",
        "other": "其他知识题", "unverified_tag": "待核验", "anki_problem": "原题",
    },
    "en": {
        "title": "Interview question report",
        "intro": "{count} questions; frequency counts collected occurrences. Within each topic, questions are numbered "
                 "from 1 by frequency, ties by wording.",
        "topic": "Topic: {name} · selection revision {revision}",
        "filters": "Filter: {expression}; source conditions are met by the same collected occurrence.",
        "goal": "Preparing for: {goal}",
        "changed": "{count} questions changed since the topic was saved; their JD mappings need a recheck.",
        "jd": "{requirements} JD knowledge requirements, {covered} directly covered. This is coverage of the current bank, "
              "not a measure of fit or of interview odds.",
        "overview": "Topics", "overview_head": "| Topic | Questions |",
        "progress": "Answers: {verified} verified against sources, {pending} pending research or recheck. Answers are for reference.",
        "group": "{title} ({count})",
        "problem": "Original problem: ", "seen": "Seen {count}×", "companies": "Companies: ", "tags": "Tags: ", "more": " and more",
        "event_years": "Interview years: ", "source_years": "Source years: ", "list_sep": ", ", "empty": "No reusable questions match this filter.",
        "answer": "Answer (reference)", "pending": "pending research and verification.", "stale": "needs a recheck; earlier versions are in the JSON attachment.",
        "draft": "pending verification; a draft is in the JSON attachment.", "uncited": "needs sources; existing content is in the JSON attachment.",
        "reviewed": "human-reviewed", "sourced": "verified against sources", "sources": "Sources: ", "source_sep": "; ",
        "spoken": "Spoken version", "follow_ups": "Follow-up questions", "mistakes": "Common mistakes", "colon": ": ",
        "other": "Other questions", "unverified_tag": "unverified", "anki_problem": "Problem",
    },
}

# Report groups and top-level domains in English (Chinese labels come from the catalog).
GROUPS_EN = {
    "RAG 与知识检索": "RAG and retrieval", "记忆与上下文": "Memory and context", "工具调用与协议": "Tool use and protocols",
    "多智能体协作": "Multi-agent systems", "Agent 安全与可靠性": "Agent safety and reliability", "评测与优化": "Evaluation",
    "Agent 架构与工作流": "Agent architecture", "大模型基础与应用": "LLM foundations", "数据库": "Databases", "缓存": "Caching",
    "后端工程": "Backend", "算法与数据结构": "Algorithms and data structures", "计算机基础": "Computer science",
    "前端工程": "Frontend", "测试与质量": "Testing and quality", "软件工程": "Software engineering", "云与运维": "Cloud and operations",
    "项目与协作": "Projects and collaboration", "其他知识题": "Other questions",
}
TOP_DOMAINS_EN = {
    "computer-science": "Computer science", "backend": "Backend", "frontend": "Frontend", "ai": "AI", "data": "Data",
    "cloud": "Cloud and operations", "security": "Security", "testing": "Testing and quality", "mobile": "Mobile",
    "systems": "Systems", "hardware": "Hardware", "robotics": "Robotics", "game": "Games", "graphics": "Graphics",
    "engineering": "Software engineering", "product": "Product", "design": "Design", "career": "Projects and collaboration",
}


def language(config_or_code) -> str:
    code = config_or_code.get("language", "zh-CN") if isinstance(config_or_code, dict) else (config_or_code or "zh-CN")
    return "en" if str(code).lower().startswith("en") else "zh-CN"


def text(lang: str, key: str, **values) -> str:
    return MESSAGES[lang][key].format(**values)


def group_title(lang: str, title: str, top_domain: str | None = None) -> str:
    if lang == "zh-CN":
        return title
    return GROUPS_EN.get(title) or TOP_DOMAINS_EN.get(top_domain or "", title)


def label(lang: str, dimension: str, value: str, chinese: str) -> str:
    """Catalog labels are Chinese; in English, technologies keep their names and domains use their ID's last part."""
    if lang == "zh-CN" or dimension == "technologies":
        return chinese
    leaf = value.split(".")[-1]
    return TOP_DOMAINS_EN.get(value) or leaf.replace("-", " ").capitalize()
