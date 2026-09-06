# Host workflow examples

## Screenshots to bank

User: “整理这些面试截图，分公司和技术栈，重复题合并。”

Initialize the specified bank if new. Run images, view all unique files, save partial extraction results, stage complete extraction, inspect review items, retrieve dedupe candidates, reason about each item, stage decisions, commit final stage. Then research and verify concise reference answers for all included questions in the requested scope, committing in batches, and export both answer and question-only editions. Skip research when the user explicitly requests questions only. Give actual completion counts and any skipped/unreadable sources or unresolved evidence gaps.

## Company and date statistics

User: “统计最近三个月字节后端数据库题。”

Use --company 字节跳动 --role backend --domain backend.database with explicit date range or --recent-days 90 (state the convention). Show canonical questions, matching occurrences, original source context and date precision. A question seen at another company alone must not count toward ByteDance.

## Related versus duplicate

“B+ 树为什么适合数据库索引”和“B+ 树与 B 树的区别”有交集，但答案范围不同，通常保留为相关题。“Redis 为什么快”和“Redis 高性能的原因”在语境相同时可以合并。同样的代码只改变量大小写，不能通过不区分大小写的文本归一化自动合并。

## Resumed extraction

After an interrupted batch, run-show <intake> and inspect saved extraction.json. Continue actual viewing for remaining source IDs. extract-save replaces corrected per-source results. stage --from-intake validates full coverage. If data/config changed after a later cognitive task was issued, regenerate that task.

## Reference answer

User: “给 Redis 高频题补充官方资料支持的答案。”

research selects the requested subset. Search and read official pages, prepare structured answers with dates and per-key-point evidence, answer stages the versions, then commit. Export Markdown. If a page is inaccessible, use another readable primary source or report the missing evidence; never fabricate a citation.

## Correction and undo

User corrects a company's alias or a question's classification. curate/classify stages a reasoned before/after change. Commit it. If the last snapshot edit was wrong and no later data/config changed, undo stages its previous state. Undo of import-plus-dedupe retains the imported questions and reverses the merges. A plain import is not physically deleted.
