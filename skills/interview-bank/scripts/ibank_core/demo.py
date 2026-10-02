"""`demo`: a small sample bank to try search, export and the Web reader in a few minutes.

20 synthetic questions under fictional companies (示例科技 / 演示网络). Eight carry reference answers whose
claims were checked against the cited official pages on the access date given; the rest stay unanswered so
the reports show both states. Nothing here comes from a real person's interviews.
"""
from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

from .answers import research_task, stage_answers
from .runs import commit_run, stage_text
from .schema import require
from .storage import guard_bank_path, initialize

ACCESSED = "2026-10-02"
COMPANY_A, COMPANY_B = "示例科技", "演示网络"

# (question, domain, technology or None, company, round)
QUESTIONS = [
    ("Redis 为什么快？", "backend.cache", "redis", COMPANY_A, "technical-1"),
    ("Redis 持久化有哪些方式？", "backend.cache", "redis", COMPANY_A, "technical-1"),
    ("什么是缓存穿透？如何解决？", "backend.cache", "redis", COMPANY_B, "technical-1"),
    ("MySQL 的事务隔离级别有哪些？", "backend.database.transaction", "mysql", COMPANY_A, "technical-2"),
    ("什么是聚簇索引？", "backend.database.index", "mysql", COMPANY_B, "technical-1"),
    ("联合索引的最左前缀原则是什么？", "backend.database.index", "mysql", COMPANY_B, "technical-2"),
    ("HTTP/2 相比 HTTP/1.1 有哪些改进？", "computer-science.network", None, COMPANY_A, "technical-1"),
    ("TCP 三次握手的过程是什么？", "computer-science.network", None, COMPANY_B, "technical-1"),
    ("进程和线程有什么区别？", "computer-science.operating-system", None, COMPANY_A, "technical-1"),
    ("什么是死锁？", "computer-science.concurrency", None, COMPANY_B, "technical-2"),
    ("什么是闭包？", "frontend.javascript", "javascript", COMPANY_A, "technical-1"),
    ("防抖和节流有什么区别？", "frontend.javascript", "javascript", COMPANY_B, "technical-1"),
    ("React 列表渲染为什么需要 key？", "frontend.react", "react", COMPANY_A, "technical-2"),
    ("浏览器的事件循环是什么？", "frontend.browser.event-loop", "javascript", COMPANY_B, "technical-1"),
    ("Kubernetes 中 Pod 是什么？", "cloud.kubernetes", "kubernetes", COMPANY_A, "technical-2"),
    ("Docker 和虚拟机有什么区别？", "cloud.containers", "docker", COMPANY_B, "technical-1"),
    ("RAG 是什么？", "ai.rag", None, COMPANY_A, "technical-1"),
    ("如何评估 Agent 的工具调用？", "ai.agent.tool-use", None, COMPANY_A, "technical-2"),
    ("如何设计一个短链接系统？", "backend.system-design", None, COMPANY_B, "technical-2"),
    ("讲一个你做过的最有挑战的项目，难点是什么？", "career.project", None, COMPANY_B, "technical-2"),
]


def _source(title, url, publisher, note):
    return {"title": title, "url": url, "publisher": publisher, "type": "official_doc", "accessed_at": ACCESSED, "evidence_note": note}


REDIS_FAQ = _source("Redis FAQ", "https://redis.io/docs/latest/develop/get-started/faq/", "Redis",
                    "FAQ: Redis is in-memory but persistent on disk; CPU is rarely the bottleneck, usually memory or network.")
ANSWERS = {
    "Redis 为什么快？": {
        "short_answer": "核心原因是整个数据集放在内存里，以“数据不能大于内存”为代价换取很高的读写速度，内存中的复杂数据结构也更容易操作。"
                        "官方 FAQ 还指出 CPU 很少成为瓶颈，Redis 通常受限于内存或网络；使用 pipelining 时一台普通 Linux 机器可达每秒百万级请求。",
        "key_points": ["数据集放在内存中，以内存容量换取很高的读写速度", "内存中的数据结构操作简单，内部复杂度低",
                       "CPU 很少是瓶颈，通常受内存或网络限制", "pipelining 可显著提高吞吐"],
        "spoken_answer": "我一般从三点说：数据在内存里；数据结构本身就是为内存操作设计的；瓶颈通常在网络和内存而不是 CPU，所以配合 pipelining 吞吐很高。",
        "follow_up_questions": ["数据比内存大怎么办？", "Redis 怎么利用多核？"],
        "common_mistakes": ["把“快”只归因于单线程，忽略了内存存储这一根本原因"],
        "sources": [REDIS_FAQ]},
    "Redis 持久化有哪些方式？": {
        "short_answer": "Redis 提供 RDB 快照、AOF 追加日志、两者同时开启，以及完全关闭持久化。RDB 文件紧凑、重启快，但可能丢最近几分钟的数据；"
                        "AOF 记录每个写操作，默认每秒 fsync，最多丢约 1 秒数据，文件更大。官方建议需要较高数据安全时两者同时使用。",
        "key_points": ["RDB：按间隔做时间点快照，文件紧凑、适合备份、重启快", "AOF：记录每个写命令，默认每秒 fsync",
                       "可以 RDB + AOF 同时开启，也可完全关闭", "两者同时开启时重启用 AOF 恢复"],
        "sources": [_source("Redis persistence", "https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/", "Redis",
                            "Lists RDB, AOF, no persistence and RDB + AOF; AOF default fsync every second; AOF used on restart when both are on.")]},
    "MySQL 的事务隔离级别有哪些？": {
        "short_answer": "InnoDB 支持 SQL:1992 定义的四种隔离级别：READ UNCOMMITTED、READ COMMITTED、REPEATABLE READ 和 SERIALIZABLE，"
                        "默认是 REPEATABLE READ。在默认级别下，同一事务内的普通 SELECT 读取第一次读时建立的快照，因此彼此一致。",
        "key_points": ["四种级别：READ UNCOMMITTED、READ COMMITTED、REPEATABLE READ、SERIALIZABLE", "InnoDB 默认 REPEATABLE READ",
                       "REPEATABLE READ 下一致性读使用事务内第一次读建立的快照", "可用 SET TRANSACTION 或 --transaction-isolation 修改"],
        "common_mistakes": ["说 InnoDB 默认是 READ COMMITTED"],
        "sources": [_source("MySQL 8.0 Reference Manual: Transaction Isolation Levels",
                            "https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html", "Oracle",
                            "Four SQL:1992 levels; InnoDB default REPEATABLE READ; consistent reads use the first read's snapshot.")]},
    "什么是聚簇索引？": {
        "short_answer": "InnoDB 的聚簇索引就是存放行数据本身的索引，通常就是主键。没有主键时用第一个所有列都 NOT NULL 的 UNIQUE 索引，"
                        "再没有就生成隐藏的 GEN_CLUST_INDEX。二级索引里保存主键值，查到后再回聚簇索引取整行，所以主键宜短。",
        "key_points": ["聚簇索引存放行数据，通常与主键同义", "无主键时依次选第一个 NOT NULL 的 UNIQUE 索引或隐藏的 GEN_CLUST_INDEX",
                       "二级索引保存主键值，通过主键回聚簇索引查行", "主键越长，二级索引越占空间"],
        "sources": [_source("MySQL 8.0 Reference Manual: Clustered and Secondary Indexes",
                            "https://dev.mysql.com/doc/refman/8.0/en/innodb-index-types.html", "Oracle",
                            "Clustered index stores row data; selection order; secondary indexes hold primary key columns.")]},
    "HTTP/2 相比 HTTP/1.1 有哪些改进？": {
        "short_answer": "HTTP/2 保持 HTTP 语义不变，改的是传输方式：二进制分帧，同一连接上交错传输多个请求和响应（多路复用），"
                        "用 HPACK 压缩头部，并提供流量控制和请求优先级，从而减少所需的 TCP 连接数、更好地利用网络。",
        "key_points": ["二进制分帧", "单连接多路复用，多个消息交错传输", "HPACK 头部压缩", "流量控制与优先级", "减少 TCP 连接数"],
        "sources": [_source("RFC 9113: HTTP/2", "https://www.rfc-editor.org/rfc/rfc9113", "IETF",
                            "Introduction: binary framing, interleaving on one connection, HPACK field compression, flow control, prioritization.")]},
    "什么是闭包？": {
        "short_answer": "闭包是一个函数与其周围状态（词法环境）引用的组合，让函数可以访问外层作用域；在 JavaScript 中每次创建函数时都会创建闭包。"
                        "即使外层函数已返回，内部函数仍能读写外层变量，常用于模拟私有方法、函数工厂和事件回调。",
        "key_points": ["函数与其词法环境引用的组合", "每次创建函数都会创建闭包", "外层函数返回后内部函数仍可访问外层变量",
                       "用途：模拟私有方法、函数工厂、回调"],
        "follow_up_questions": ["循环里用 var 创建闭包会有什么问题？"],
        "sources": [_source("Closures - JavaScript | MDN", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures", "MDN",
                            "Definition of closure; created at function creation time; emulating private methods; function factories.")]},
    "React 列表渲染为什么需要 key？": {
        "short_answer": "key 让 React 在兄弟节点之间唯一识别每个列表项，即使它的位置因插入、删除或排序而变化。key 必须在兄弟节点间唯一且不能变化，"
                        "不要在渲染时生成。用数组下标作 key 在顺序变化时常导致难以察觉的 bug，应使用来自数据的稳定 ID。",
        "key_points": ["key 在兄弟节点间唯一标识列表项", "key 必须唯一且稳定，不在渲染时生成", "下标作 key 在顺序变化时容易出 bug",
                       "推荐使用数据自身的稳定 ID"],
        "common_mistakes": ["用 Math.random() 生成 key，导致每次重建组件和 DOM"],
        "sources": [_source("Rendering Lists – React", "https://react.dev/learn/rendering-lists", "React",
                            "Keys identify items among siblings; must be unique and unchanging; index keys lead to subtle bugs.")]},
    "Kubernetes 中 Pod 是什么？": {
        "short_answer": "Pod 是 Kubernetes 中可以创建和管理的最小部署单元：一个或多个容器的组合，共享存储和网络资源，并带有如何运行这些容器的规格，"
                        "内容总是同机调度、在共享上下文中运行。通常不直接创建 Pod，而是通过 Deployment、Job 或 StatefulSet 等工作负载资源创建。",
        "key_points": ["最小的可部署计算单元", "一个或多个容器，共享存储与网络", "总是同机调度，运行在共享上下文",
                       "通常通过 Deployment、Job、StatefulSet 等创建"],
        "sources": [_source("Pods | Kubernetes", "https://kubernetes.io/docs/concepts/workloads/pods/", "Kubernetes",
                            "Pods are the smallest deployable units; group of containers with shared storage/network; usually created via workload resources.")]},
}


def build_demo(bank, v2: bool = False) -> dict:
    """Create a new sample bank. The directory must not exist or must be empty."""
    bank = guard_bank_path(bank)
    require(not bank.exists() or not any(bank.iterdir()), "demo needs a new or empty directory; it never touches an existing bank")
    initialize(bank)
    groups = defaultdict(list)
    for text, domain, technology, company, round_name in QUESTIONS:
        groups[(domain, technology, company, round_name)].append(text)
    with tempfile.TemporaryDirectory(prefix="ibank-demo-") as temp:
        for index, ((domain, technology, company, round_name), texts) in enumerate(sorted(groups.items(), key=str)):
            source = Path(temp) / f"demo-{index:02d}.txt"
            source.write_text("\n".join(texts) + "\n", encoding="utf-8")
            staged = stage_text(bank, source, company=company, domains=[domain], technologies=[technology] if technology else [],
                                round_name=round_name, interview_type="campus", retention="none")
            commit_run(bank, staged["run_id"])
    task = research_task(bank, limit=len(QUESTIONS))
    by_text = {item["question"]["canonical"]: item["question"]["id"] for item in task["items"]}
    answers = []
    for text, answer in ANSWERS.items():
        url = answer["sources"][0]["url"]
        answers.append({"question_id": by_text[text], "status": "source_backed", **answer,
                        "evidence": [{"key_point": i, "source_urls": [url]} for i in range(len(answer["key_points"]))]})
    answers += [{"question_id": qid, "skip": True, "reason": "Left unanswered in the demo to show pending answers"}
                for text, qid in by_text.items() if text not in ANSWERS]
    commit_run(bank, stage_answers(bank, {"schema_version": 1, "task_id": task["id"], "answers": answers})["run_id"])
    result = {"bank": str(bank), "questions": len(QUESTIONS), "answered": len(ANSWERS), "schema_version": 1,
              "next": [f"search --bank {bank} --json", f"export --output demo.md --bank {bank} --json", f"web --bank {bank}"]}
    if v2:
        from .migrations import migrate
        migrate(bank, "apply")
        result["schema_version"] = 2
    return result
