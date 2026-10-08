# Export formats and report language

`export --format <format> --output <name>` writes under bank/exports; Markdown is described in [query/export](query-export.md).

| Format | Content |
|---|---|
| markdown | Two reader editions plus `<output>.details.json` (below) |
| json / viewer | Snapshot: questions with occurrences and answer history, referenced sources, companies, relations |
| jsonl | One question envelope per line with its related records |
| csv | UTF-8 BOM, formula-safe cells, JSON columns for occurrences, citations and companies |
| anki | Tab-separated notes for Anki's File → Import (front, back, tags) |

## Anki

Front: the question. Back: the current sourced short answer with source links (and the problem link when set).
Questions without one get an empty back and the tag 待核验. Tags are domain and technology IDs. Report-excluded
questions are left out.

## Report language

`config.language` `zh-CN` (default) or `en` (`config --input '{"language": "en"}'`, then commit) switches headings,
answer states, the practice block, topic names, tags and Anki cards; question wording is never translated.
The Web reader follows the same setting.
