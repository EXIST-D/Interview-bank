# Company classification and evidence

Company is an entity in the user's bank, with name, aliases and industries. Add any evidenced employer; there is no fixed employer whitelist. Use companies to discover existing names/aliases before creating another entity.

## Optional profile fields

1.1 supports company_type, ownership, business_models and profile_evidence. Old companies without them remain valid. All fields are optional, but adding/changing profile attributes requires a nonempty profile_evidence describing the source, relevant text and context. Public evidence should include the actual URL and reading date. A URL alone is not proof; actually read it.

| Field | Meaning |
| --- | --- |
| industries | Employer's actual business sectors, e.g. software.enterprise, finance.banking; one or more |
| company_type | Organizational/function category, e.g. software-vendor, consultancy, university |
| ownership | private, state-owned, foreign-owned, joint-venture, public-sector, nonprofit or unknown |
| business_models | Customer/revenue labels, e.g. b2b, subscription, licensing |
| profile_evidence | Source/user statement supporting profile attributes, including uncertainty or temporal scope |

Listing status, funding round, headcount, salary tier and “大厂/独角兽” are not silently inferred or stored as ownership. This release does not provide those volatile attributes. Parent groups, brands and subsidiaries should remain distinct unless their equivalence in this bank is explicitly justified.

## Extraction/classification company object

Use this object as source metadata.company or question.company in extraction, or occurrence.set.company in a classify response. The example is a fictitious demonstration, not a claim about a real employer.

```json
{
  "name": "示例企业软件公司",
  "aliases": ["Example Enterprise Software"],
  "industries": ["企业软件", "SaaS服务"],
  "company_type": "软件厂商",
  "ownership": "民营",
  "business_models": ["ToB", "订阅服务"],
  "profile_evidence": "用户提供的合成说明明确写明：该公司为民营软件厂商，为企业提供订阅制管理软件。"
}
```

Aliases normalize for lookup; industry/profile aliases normalize to catalog IDs. New names create entities. Existing aliases resolve to one entity; ambiguous matches fail. Repeated company facts extend industry/alias lists; a contradictory ownership/type/business-model value is rejected instead of overwriting another screenshot's information. Use curate with new evidence and reason for deliberate corrections.

Company changes during classify are audited with before/after records. For entity-only corrections, curate the companies table:

```json
{
  "schema_version": 1,
  "changes": [{
    "table": "companies",
    "id": "company_FROM_BANK",
    "set": {
      "industries": ["software.enterprise"],
      "ownership": "private",
      "profile_evidence": "用户明确确认该示例是民营企业软件公司；原分类错误。"
    },
    "reason": "根据用户提供的明确说明修正"
  }]
}
```

## Query, statistics and export

```text
companies --query 示例 --bank <bank> --json
companies --industry 软件与IT服务 --ownership 民营 --bank <bank> --json
search --role 后端 --industry 金融 --ownership 国企 --bank <bank> --json
stats --company-type 软件厂商 --business-model B2B --bank <bank> --json
export --format markdown --output enterprise.md --industry software --bank <bank> --json
```

Company listing supports query/industry/company-type/ownership/business-model, limit and offset; it returns canonical-question and occurrence counts. search/stats/export apply these filters to the same occurrence's company. A question appearing at two different employers cannot satisfy one company's name and the other company's ownership simultaneously.

Industry hierarchy queries include descendants. Unknown free-text industries still work as exact labels. Statistics normalize known legacy industry aliases without mutating stored records, and include industries/company_types/ownerships/business_models. Counts are collected occurrences; multilabel distributions can sum above total occurrences.

JSON/JSONL/viewer preserve complete referenced company objects. CSV includes companies_json. Markdown has a readable company/industry section with profile evidence. No command needs an external company database or automatically browses the web.
