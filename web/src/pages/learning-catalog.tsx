import { ArrowRight, BookOpen, ChevronDown, ChevronLeft, List, Search } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { type SourceCard } from "@/lib/notes";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SearchField, useSourceCards } from "./knowledge";

export type LearningKind = "roadmap" | "tutorial" | "resource" | "career" | "news" | "all";

export const learningCount = (item: { count: number; kinds?: Record<string, number> }, kind: LearningKind) =>
  kind === "all" ? item.count : (item.kinds?.[kind] ?? 0);

function sourceCount(source: SourceCard, kind: LearningKind) {
  return kind === "all" ? source.content_total : (source.kinds[kind] ?? 0);
}

function Directory({ source, kind, query }: { source: SourceCard; kind: LearningKind; query: string }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(Boolean(query));
  const sourceMatches = source.title.toLocaleLowerCase().includes(query);
  const areas = source.areas.filter((area) => learningCount(area, kind) > 0).map((area) => ({
    ...area,
    topics: area.topics.filter((topic) => learningCount(topic, kind) > 0 &&
      (sourceMatches || area.title.toLocaleLowerCase().includes(query) || topic.title.toLocaleLowerCase().includes(query))),
  })).filter((area) => !query || sourceMatches || area.title.toLocaleLowerCase().includes(query) || area.topics.length);
  if (query && !sourceMatches && !areas.length) return null;
  const count = sourceCount(source, kind);
  const groups = source.areas.reduce((n, area) => n + area.topics.filter((topic) => learningCount(topic, kind) > 0).length, 0);
  const open = expanded;
  const target = (area?: string, topic?: string) => href("learning", [kind], {
    view: "list", source: source.name, ...(area ? { area } : {}), ...(topic ? { topic } : {}),
  });
  return (
    <article className="min-w-0 overflow-hidden surface">
      <h2>
        <button type="button" aria-expanded={open} aria-controls={`learning-${source.name}`} onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center gap-3 p-4.5 text-left outline-none transition-colors hover:bg-fill/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/40 sm:p-5">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-primary"><BookOpen className="size-5" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-callout font-semibold leading-snug">{source.title}</span>
            <span className="mt-1 block text-caption text-muted-foreground tabular-nums">{t("learning_source_meta", { n: count, g: groups })}</span>
          </span>
          <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
        </button>
      </h2>
      {open && <div id={`learning-${source.name}`} className="border-t border-border px-4.5 pt-4 pb-4.5 sm:px-5 sm:pb-5">
        {source.metadata.description && <p className="mb-4 line-clamp-2 text-footnote leading-relaxed text-muted-foreground">{source.metadata.description}</p>}
        <div className="space-y-5">
          {areas.map((area) => <section key={area.id}>
            <h3 className="mb-2 flex items-baseline justify-between gap-3 text-footnote font-semibold">
              <span>{area.title}</span><span className="shrink-0 font-normal text-muted-foreground tabular-nums">{learningCount(area, kind)}</span>
            </h3>
            <div className="grid gap-1 sm:grid-cols-2">
              {area.topics.map((topic) => <a key={topic.id} href={target(area.id, topic.id)}
                className="group flex min-w-0 items-center justify-between gap-3 rounded-xl bg-fill/60 px-3 py-2.5 text-footnote transition-colors hover:bg-accent hover:text-primary">
                <span className="min-w-0 leading-snug">{topic.title}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-caption text-muted-foreground tabular-nums">{learningCount(topic, kind)}<ArrowRight className="size-3.5 group-hover:text-primary" /></span>
              </a>)}
              {!area.topics.length && <a className="text-footnote text-primary" href={target(area.id)}>{t("learning_view_entries")} →</a>}
            </div>
          </section>)}
        </div>
        <a href={target()} className="mt-4 inline-flex items-center gap-1 text-footnote font-medium text-primary">{t("learning_source_all")}<ArrowRight className="size-3.5" /></a>
      </div>}
    </article>
  );
}

export function LearningCatalog({ kind, initialSource = "" }: { kind: LearningKind; initialSource?: string }) {
  const { t } = useI18n();
  const { page, error } = useSourceCards("learning");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState(initialSource);
  const sources = (page?.collections ?? []).filter((s) => sourceCount(s, kind) > 0);
  const words = query.trim().toLocaleLowerCase();
  const visible = sources.filter((s) => (!source || s.name === source) && (!words || s.title.toLocaleLowerCase().includes(words) ||
    s.areas.some((area) => learningCount(area, kind) > 0 && (area.title.toLocaleLowerCase().includes(words) ||
      area.topics.some((topic) => learningCount(topic, kind) > 0 && topic.title.toLocaleLowerCase().includes(words))))));
  const total = sources.reduce((n, s) => n + sourceCount(s, kind), 0);
  const groups = sources.reduce((n, s) => n + s.areas.reduce((count, area) => count + area.topics.filter((topic) => learningCount(topic, kind) > 0).length, 0), 0);
  return <div className="mx-auto max-w-[1040px] px-4 pt-6 pb-28 sm:px-6 md:pt-10 md:pb-16">
    <a href={href("learning")} className="mb-2 inline-flex items-center text-footnote font-medium text-primary"><ChevronLeft className="size-4" />{t("learning_home")}</a>
    <h1 className="text-large-title font-bold">{kind === "all" ? t("learning_all") : t(`notes_kind_${kind}`)}</h1>
    <p className="mt-2 max-w-2xl text-callout leading-relaxed text-muted-foreground">{t("learning_directory_hint")}</p>
    <p className="mt-2 text-footnote text-muted-foreground tabular-nums">{page ? t("learning_directory_meta", { s: sources.length, g: groups, n: total }) : t("loading")}</p>
    <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1"><SearchField id="learning-catalog-search" value={query} onChange={setQuery} placeholder={t("learning_search_directory")} /></div>
      <select aria-label={t("learning_sources")} value={source} onChange={(event) => setSource(event.target.value)} className="h-9 min-w-0 max-w-full rounded-[10px] bg-fill px-3 text-footnote sm:max-w-64">
        <option value="">{t("notes_source_all")}</option>
        {sources.map((s) => <option key={s.name} value={s.name}>{s.title}</option>)}
      </select>
      <a href={href("learning", [kind], { view: "list", ...(source ? { source } : {}) })} className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-[10px] border border-border bg-card px-3 text-footnote font-medium"><List className="size-4" />{t("learning_view_entries")}</a>
    </div>
    {error && <p role="alert" className="mt-5 rounded-xl bg-destructive/10 p-4 text-footnote text-destructive">{error}</p>}
    {!page && !error && <div className="mt-5 h-24 animate-pulse rounded-2xl bg-fill" />}
    <div className="mt-5 space-y-3">
      {visible.map((s) => <Directory key={s.name + words} source={s} kind={kind} query={words} />)}
    </div>
    {page && !visible.length && <p role="status" className="mt-6 text-footnote text-muted-foreground">{t("empty_notes")}</p>}
    {words && <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-fill px-4 py-3 text-footnote text-muted-foreground">
      <span>{t("learning_directory_search_hint")}</span>
      <Button variant="link" asChild><a href={href("learning", [kind], { view: "list", query: query.trim(), ...(source ? { source } : {}) })}><Search className="size-3.5" />{t("learning_search_body")}</a></Button>
    </div>}
  </div>;
}
