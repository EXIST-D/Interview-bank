# Classification catalog · 1.1.0

Use the host to classify meaning. The catalog normalizes labels and validates them; it does not infer semantics from keywords. Read only the relevant catalog slice with the CLI instead of loading the entire catalog into context.

## Discover labels

```text
taxonomy --dimension role_tracks --query 后端 --json
taxonomy --dimension domains --query 向量 --json
taxonomy --dimension technologies --query Spring --json
taxonomy --dimension industries --query 金融 --json
taxonomy --dimension company_type --json
taxonomy --dimension ownership --json
taxonomy --dimension business_models --json
```

No bank is needed. Pass --bank to include that bank's committed role/domain extensions. --limit (default 50) and --offset page results; total describes all matches. Every item has id, Chinese label and unambiguous aliases; hierarchical dimensions have parent. Machine-readable vocabulary: [classification-catalog.json](classification-catalog.json); required role/domain codes and other enums: [taxonomy.json](taxonomy.json).

## Coverage

| Dimension | Built-in entries | Coverage |
| --- | ---: | --- |
| role_tracks | 67 | Frontend/Web/cross-platform/build; backend Java/Go/Python/.NET/Node/C++; mobile; LLM/NLP/vision/speech/recommendation/multimodal; data engineering/analytics/science/warehouse/governance; SRE/cloud/MLOps; QA/security; database/DBA; embedded/IoT/robotics/driving; games/graphics/systems/compiler/network/hardware/chip; product/design/solutions |
| domains | 186 | Computer science; database/index/transaction/vector/graph/timeseries; cache/distributed systems; frontend/browser/rendering/SSR; LLM/RAG/retrieval/reranking/tool-use/memory/safety/evaluation; data/lakehouse/governance; cloud/CI/CD/observability; security; testing/mobile/embedded; hardware/robotics/graphics; software engineering/product/design/career |
| technologies | 229 | Languages, frameworks, databases, middleware, cloud/observability, mobile, AI/model-serving/Agent frameworks and protocols, data platforms, test/build tools, network/graphics/hardware technologies |
| industries | 83 | Internet, enterprise software/cloud/consulting, AI, banking/securities/insurance/payments/fintech, semiconductor/electronics, telecom/manufacturing/automotive, energy/healthcare/education, government/retail/logistics/media/games/construction/agriculture/professional services |
| company_type | 13 | Platform/software/hardware/service providers, consultancy/outsourcing, enterprise IT, research/university/government/public institution/nonprofit; unknown included |
| ownership | 7 | Private/state-owned/foreign-owned/joint-venture/public-sector/nonprofit; unknown included |
| business_models | 12 | B2B/B2C/B2G, marketplace/subscription/advertising/licensing/commission/hardware/professional services/open-source services/usage-based |

Counts include hierarchy parents, broad categories and unknown where listed; they are not all mutually exclusive leaf categories. Companies are unlimited user-bank entities, not an invented fixed list of employers.

## Classification decisions

Prefer the most specific justified leaf: backend.java, backend.database.vector, ai.agent.tool-use. Parent filters include descendants: --role 后端 matches backend.java; --domain 数据库 includes vector/index/transaction; --industry 金融 includes banking/fintech. A leaf filter does not match an unspecified parent. Avoid tagging both a parent and its child merely to improve search.

Use multiple labels for actual independently tested concepts. For a Python implementation of RAG, ai.rag describes the problem and python describes the technology; do not add every possible AI framework. Specific technology labels require actual mention or uniquely identifiable evidence; do not infer LangChain just from “Agent”.

Occurrence roles describe the interview/source context. Question roles describe concept suitability. If only the latter can be inferred, keep the occurrence role unknown rather than claiming a known recruitment role. Role filters use occurrence context.

Chinese names and common aliases are accepted in screenshot extraction, selected-text role/domain flags, classification/curation and queries. Examples: Java后端→backend.java, 向量数据库→backend.database.vector, SpringBoot→spring-boot, Postgres→postgresql, K8s→kubernetes. Canonical bundles remain a strict lower-level interface.

Preserve language/framework/version distinctions: C/C++/C#, React/React Native, Python/Python3, Redis/Redis 7 are not auto-collapsed. Unknown technology tags remain extensible lowercase strings. Preserve version details in canonical and original text even when adding a general technology tag.

## Companies and industries

Use [company protocol](company-classification.md). Record real employer name/aliases and multiple evidenced industries. A group's subsidiary, brand and legal hiring entity are not automatically the same employer. Do not strip legal suffixes or merge similar names by guesswork.

Separate industry (what the employer does), company_type (organization/function), ownership (ownership nature), and business_models (customers/revenue). A software vendor serving banks is not automatically a bank. Choose software.enterprise/finance.fintech when the actual evidence supports it; do not misclassify customer sectors as the employer's industry.

Company identity, industry, ownership and business facts need source or user evidence. Query public sources only when enrichment is requested or needed for the user's requested company classification, and record what was actually read. Do not maintain speculative company ownership lists. Unknown information stays unset/unknown.

## Other enum values and extensions

- question_type: concept, coding, project, system-design, scenario, debugging, behavioral, math, case.
- difficulty: easy, medium, hard, unknown.
- interview_type: campus, intern, experienced, unknown.
- round: written, technical-1, technical-2, technical-3, manager, hr, cross, unknown.

Extend role_tracks/domains through config, then commit. Custom IDs can be hierarchical, e.g. {"taxonomy_extensions":{"role_tracks":["custom-specialist"],"domains":["custom.topic"]}}. New extensions cannot redefine built-in aliases. Industries and technologies accept additional strings; normalize common aliases but preserve unknown specific labels.

1.0 banks remain readable, including older technology spellings and free-text industries, without rewriting their JSONL. Queries/statistics normalize those labels at read time. Existing broad labels are not magically refined: run classify and commit to adopt finer categories. New company profile fields are optional additive fields supported in 1.1; older 1.0 runtimes do not understand them.
