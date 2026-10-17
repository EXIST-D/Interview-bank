import { SlidersHorizontal, X } from "lucide-react";
import { useCallback, useState } from "react";
import { useI18n, type TextKey } from "@/lib/i18n";
import { sectionOf } from "@/lib/notes";
import { useReading } from "@/lib/reading";
import type { Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { chipClass, Segmented } from "@/components/ui/segmented";
import { NoteList, type GroupBy } from "@/notes/note-list";
import { NoteReader, useNotesList } from "@/notes/notes-board";
import { NotesFilters, type FilterField } from "@/notes/notes-filters";
import { SearchField, useDebounced } from "./knowledge";

const PAGE = 100;
const DEFAULTS = { company: "", kind: "study", sort: "recent" };

export function PublicPage({ route }: { route: Route }) {
  const { t } = useI18n();
  const [group, setGroup] = useState<"year" | "domain">("year");
  const [domain, setDomain] = useState("");
  const [year, setYear] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>(DEFAULTS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [query, setQuery] = useState("");
  const words = useDebounced(query);

  const params = useCallback(
    (offset: number, limit = PAGE) => {
      // The server sorts by domain only when asked; dates stay the order inside each domain.
      const sort = filters.sort === "recent" && group === "domain" ? "domain" : filters.sort;
      const search = new URLSearchParams({ section: "experiences", kind: filters.kind || "study", sort, offset: String(offset), limit: String(limit) });
      if (words) search.set("query", words);
      if (domain) search.set("experience_domain", domain);
      if (year) search.set("year", year);
      if (filters.company) search.set("company", filters.company);
      return search;
    },
    [filters, group, words, domain, year],
  );
  const { data, rows, loading, error, load } = useNotesList(params, "all");
  const ids = data?.ids ?? [];
  const reading = useReading({ route, board: "public", ids, searchId: "public-search" });
  const { openId, open, focused, listHidden } = reading;
  const facets = data?.facets;

  const unknownYear = t("notes_experience_year_unknown");
  const groupBy: GroupBy =
    !words && filters.sort === "recent"
      ? group === "year"
        ? (n) => ({ key: "year:" + (n.experience?.year || "unknown"), label: n.experience?.year || unknownYear })
        : (n) => ({ key: "domain:" + n.experience?.domain, label: t(`notes_domain_${n.experience?.domain}` as TextKey) })
      : null;

  const years = Object.entries(facets?.experience_years ?? {}).sort(([a], [b]) => (a === "unknown" ? 1 : b === "unknown" ? -1 : b.localeCompare(a)));
  const fields: FilterField[] = facets
    ? [
        {
          key: "company",
          label: t("notes_experience_company"),
          options: [
            { value: "", label: t("notes_experience_company_all") },
            ...facets.companies.map((company) => ({ value: company, label: company })),
            ...(facets.unknown_company ? [{ value: "unknown", label: t("notes_experience_company_unknown") }] : []),
          ],
        },
        {
          key: "kind",
          label: t("notes_kind"),
          options: [
            { value: "study", label: t("all") },
            ...Object.entries(facets.kinds).map(([kind, n]) => ({ value: kind, label: `${t(`notes_kind_${kind}` as TextKey)} · ${n}` })),
          ],
        },
        {
          key: "sort",
          label: t("sort"),
          options: [
            { value: "recent", label: t("notes_experience_recent") },
            { value: "order", label: t("notes_experience_order") },
          ],
        },
      ]
    : [];
  const filterCount = fields.filter((field) => (filters[field.key] ?? "") !== (DEFAULTS as Record<string, string>)[field.key]).length;
  const active = [
    domain && { label: t(`notes_domain_${domain}` as TextKey), clear: () => setDomain("") },
    year && { label: year === "unknown" ? unknownYear : year, clear: () => setYear("") },
    filters.company && {
      label: filters.company === "unknown" ? t("notes_experience_company_unknown") : filters.company,
      clear: () => setFilters((current) => ({ ...current, company: "" })),
    },
  ].filter(Boolean) as { label: string; clear: () => void }[];

  return (
    <div
      className={cn(
        "wide:grid wide:h-[calc(100dvh-3.25rem)]",
        focused && "wide:h-dvh",
        listHidden ? "wide:grid-cols-1" : "wide:grid-cols-[minmax(340px,420px)_1fr]",
      )}
    >
      <section aria-label={t("board_public")} className={cn("min-w-0 wide:overflow-y-auto wide:border-r wide:border-border", listHidden && "wide:hidden")}>
        <div className="flex flex-col gap-3 px-4 pt-5 pb-28 wide:pb-8">
          <div>
            <p className="text-caption font-semibold tracking-wide text-primary">{t("board_public")}</p>
            <h1 className="mt-0.5 text-title-1 font-bold tabular-nums">{t("notes_public_total", { n: data?.total ?? "—" })}</h1>
            <p className="mt-1 text-footnote text-muted-foreground">{t("notes_experiences_hint")}</p>
          </div>
          <SearchField id="public-search" value={query} onChange={setQuery} placeholder={t("search_public")} />
          <Segmented
            label={t("notes_public_group")}
            value={group}
            onChange={setGroup}
            options={[
              { value: "year", label: t("notes_public_by_year") },
              { value: "domain", label: t("notes_public_by_domain") },
            ]}
          />
          <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
            <button type="button" aria-pressed={!domain} onClick={() => setDomain("")} className={chipClass(!domain)}>
              {t("notes_public_domain_all")}
            </button>
            {Object.entries(facets?.experience_domains ?? {}).map(([id, n]) => (
              <button key={id} type="button" aria-pressed={domain === id} onClick={() => setDomain(domain === id ? "" : id)} className={chipClass(domain === id)}>
                {t(`notes_domain_${id}` as TextKey)}
                <span className="ml-1 opacity-60 tabular-nums">{n}</span>
              </button>
            ))}
          </div>
          <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
            <button type="button" aria-pressed={!year} onClick={() => setYear("")} className={chipClass(!year)}>
              {t("notes_experience_year_all")}
            </button>
            {years.map(([id, n]) => (
              <button key={id} type="button" aria-pressed={year === id} onClick={() => setYear(year === id ? "" : id)} className={chipClass(year === id)}>
                {id === "unknown" ? unknownYear : id}
                <span className="ml-1 opacity-60 tabular-nums">{n}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <p className="min-w-0 flex-1 truncate px-0.5 text-caption text-muted-foreground tabular-nums">
              {data ? t("notes_public_total", { n: data.total }) + (filters.sort === "recent" ? " · " + t("notes_public_latest") : "") : t("loading")}
            </p>
            <Button variant="outline" size="sm" onClick={() => setFiltersOpen(true)} disabled={!facets}>
              <SlidersHorizontal />
              {t("filters")}
              {filterCount > 0 && <span className="grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] leading-4 text-primary-foreground">{filterCount}</span>}
            </Button>
          </div>
          {active.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {active.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={item.clear}
                  aria-label={t("notes_public_clear", { value: item.label })}
                  className="flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-caption font-medium text-accent-foreground"
                >
                  {item.label}
                  <X className="size-3" />
                </button>
              ))}
            </div>
          )}
          {error && (
            <div role="alert" className="rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">
              {error}{" "}
              <button type="button" className="font-medium underline" onClick={() => load(0)}>
                {t("retry")}
              </button>
            </div>
          )}
          <div aria-busy={loading}>
            <NoteList notes={rows} openId={openId} words={words} crossSource={false} groupBy={groupBy} onOpen={open} />
            {!loading && !rows.length && !error && (
              <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-footnote text-muted-foreground">{t("empty_notes")}</p>
            )}
          </div>
          {data && rows.length < data.total && (
            <Button variant="outline" className="self-center" disabled={loading} onClick={() => load(rows.length)}>
              {t("more_questions")}
            </Button>
          )}
        </div>
      </section>
      <NoteReader reading={reading} ids={ids} rows={rows} accepts={(note) => sectionOf(note) === "experiences"} />
      <NotesFilters
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        fields={fields}
        values={filters}
        defaults={DEFAULTS}
        onChange={(changes) => setFilters((current) => ({ ...current, ...changes }))}
      />
    </div>
  );
}
