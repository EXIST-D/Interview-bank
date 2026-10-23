import { ArrowRight, BriefcaseBusiness, ChevronLeft, LayoutGrid, Newspaper, Route as RouteIcon, SquareTerminal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useState } from "react";
import { useI18n, type TextKey } from "@/lib/i18n";
import { LEARNING_KINDS, sectionOf } from "@/lib/notes";
import { useReading } from "@/lib/reading";
import { href, navigate, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { chipClass, Segmented } from "@/components/ui/segmented";
import { NoteList } from "@/notes/note-list";
import { NoteReader, useNotesList } from "@/notes/notes-board";
import { SearchField, useDebounced, useSourceCards } from "./knowledge";
import { LearningCatalog, learningCount } from "./learning-catalog";

const PAGE = 100;
type Kind = (typeof LEARNING_KINDS)[number];
const ICONS: Record<Kind, { icon: LucideIcon; tone: string }> = {
  roadmap: { icon: RouteIcon, tone: "bg-accent text-primary" },
  tutorial: { icon: SquareTerminal, tone: "bg-blue/10 text-blue" },
  resource: { icon: LayoutGrid, tone: "bg-purple/12 text-purple" },
  career: { icon: BriefcaseBusiness, tone: "bg-orange/14 text-warning" },
  news: { icon: Newspaper, tone: "bg-fill text-foreground" },
};

function Categories() {
  const { t } = useI18n();
  const { page } = useSourceCards("learning");
  return (
    <div className="mx-auto max-w-[1120px] px-4 pt-8 pb-28 sm:px-6 md:pt-10 md:pb-16">
      <p className="text-caption font-semibold tracking-wide text-primary">{t("board_learning")}</p>
      <h1 className="mt-1 text-large-title font-bold">{t("mode_learning")}</h1>
      <p className="mt-1.5 text-callout text-muted-foreground">{t("learning_home_hint")}</p>
      <div className="mt-2 flex items-center justify-between gap-4">
        <p className="text-footnote text-muted-foreground tabular-nums">{page ? t("learning_summary", { n: page.section_counts.learning }) : t("loading")}</p>
        <a href={href("learning", ["all"])} className="shrink-0 text-footnote font-medium text-primary">
          {t("learning_browse_all")}
        </a>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {!page
          ? Array.from({ length: 5 }, (_, i) => <div key={i} className="h-44 animate-pulse rounded-[1.25rem] bg-fill" />)
          : page.learning_categories.map((category) => {
              const kind = category.kind as Kind;
              const { icon: Icon, tone } = ICONS[kind];
              const card = (
                <>
                  <span className={cn("grid size-10 place-items-center rounded-xl", tone)}>
                    <Icon className="size-5" />
                  </span>
                  <span className="text-headline font-semibold">{t(`notes_kind_${kind}`)}</span>
                  <span className="text-footnote leading-relaxed text-muted-foreground">{t(`learning_hint_${kind}`)}</span>
                  <span className="mt-auto flex items-center justify-between pt-1 text-caption text-muted-foreground">
                    <span className="tabular-nums">{t("learning_card_meta", { n: category.count, s: category.sources })}</span>
                    {category.count > 0 && (
                      <span className="flex items-center gap-1 font-medium text-primary">
                        {t("enter")}
                        <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
                      </span>
                    )}
                  </span>
                </>
              );
              const style = "group flex min-h-44 flex-col gap-2.5 surface p-5 transition-transform duration-300 ease-apple";
              return category.count ? (
                <a key={kind} href={href("learning", [kind])} className={cn(style, "hover:-translate-y-0.5 hover:shadow-soft-lg")}>
                  {card}
                </a>
              ) : (
                <div key={kind} aria-disabled className={cn(style, "opacity-50")}>
                  {card}
                </div>
              );
            })}
      </div>
    </div>
  );
}

type LearningFilter = "all" | "unread" | "review" | "mastered";

function Materials({ route, kind }: { route: Route; kind: Kind | "all" }) {
  const { t } = useI18n();
  const { page: meta } = useSourceCards("learning");
  const source = route.params.get("source") ?? "";
  const area = route.params.get("area") ?? "";
  const topic = route.params.get("topic") ?? "";
  const [learning, setLearning] = useState<LearningFilter>("all");
  const [query, setQuery] = useState(route.params.get("query") ?? "");
  const words = useDebounced(query);

  const params = useCallback(
    (offset: number, limit = PAGE) => {
      const search = new URLSearchParams({ section: "learning", kind: kind === "all" ? "study" : kind, sort: "order", view: "knowledge", offset: String(offset), limit: String(limit) });
      if (source) search.set("collection", source);
      if (source && area) search.set("area", area);
      if (source && topic) search.set("topic", topic);
      if (words) search.set("query", words);
      return search;
    },
    [kind, source, area, topic, words],
  );
  const { data, rows, loading, error, load } = useNotesList(params, learning);
  const ids = data?.ids ?? [];
  const reading = useReading({ route, board: "learning", ids, searchId: "learning-search" });
  const { openId, open, focused, listHidden } = reading;
  const go = (nextKind: string, nextSource = source) => navigate("learning", [nextKind], { view: "list", ...(nextSource ? { source: nextSource } : {}) });
  const sources = (meta?.collections ?? []).filter((c) => (kind === "all" ? c.content_total : c.kinds?.[kind]) > 0);
  const kinds = meta?.learning_categories ?? [];
  const selectedSource = sources.find((s) => s.name === source);
  const selectedArea = selectedSource?.areas.find((a) => a.id === area);
  const selectedTopic = selectedArea?.topics.find((value) => value.id === topic);

  return (
    <div
      className={cn(
        "wide:grid wide:h-[calc(100dvh-var(--ib-header-height,3.25rem))]",
        focused && "wide:h-dvh",
        listHidden ? "wide:grid-cols-1" : "wide:grid-cols-[minmax(340px,420px)_1fr]",
      )}
    >
      <section aria-label={t("board_learning")} className={cn("min-w-0 wide:overflow-y-auto wide:border-r wide:border-border", listHidden && "wide:hidden")}>
        <div className="flex flex-col gap-3 px-4 pt-5 pb-28 wide:pb-8">
          <div>
            <a href={href("learning", [kind])} className="mb-1 flex items-center gap-0.5 text-footnote font-medium text-primary">
              <ChevronLeft className="size-4" />
              {t("learning_directory_back")}
            </a>
            <h1 className="text-title-1 font-bold">{kind === "all" ? t("learning_all") : t(`notes_kind_${kind}`)}</h1>
            <p className="mt-1 text-footnote text-muted-foreground">{kind === "all" ? t("learning_home_hint") : t(`learning_hint_${kind}`)}</p>
            {selectedSource && <p className="mt-2 text-footnote leading-relaxed text-primary">{[selectedSource.title, selectedArea?.title, selectedTopic?.title].filter(Boolean).join(" / ")}</p>}
          </div>
          <SearchField id="learning-search" value={query} onChange={setQuery} placeholder={t("search_learning")} />
          <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
            <button type="button" aria-pressed={kind === "all"} onClick={() => go("all")} className={chipClass(kind === "all")}>
              {t("all")}
            </button>
            {kinds.map((category) => (
              <button
                key={category.kind}
                type="button"
                aria-pressed={kind === category.kind}
                disabled={!category.count}
                onClick={() => go(category.kind)}
                className={cn(chipClass(kind === category.kind), "disabled:opacity-40")}
              >
                {t(`notes_kind_${category.kind}` as TextKey)}
                <span className="ml-1 opacity-60 tabular-nums">{category.count}</span>
              </button>
            ))}
          </div>
          <label className="flex items-center justify-between gap-3 rounded-xl bg-card px-3.5 py-2 text-subhead shadow-soft-sm">
            <span className="shrink-0 text-muted-foreground">{t("learning_sources")}</span>
            <select
              value={source}
              onChange={(event) => go(kind, event.target.value)}
              className="min-w-0 max-w-[70%] truncate bg-transparent text-right outline-none"
            >
              <option value="">{t("notes_source_all")}</option>
              {sources.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.title} · {kind === "all" ? c.content_total : c.kinds[kind]}
                </option>
              ))}
            </select>
          </label>
          {selectedSource && <label className="flex items-center justify-between gap-3 rounded-xl bg-card px-3.5 py-2 text-subhead shadow-soft-sm">
            <span className="shrink-0 text-muted-foreground">{t("learning_topic")}</span>
            <select aria-label={t("learning_topic")} value={topic} onChange={(event) => {
              const next = event.target.value;
              const parent = selectedSource.areas.find((a) => a.topics.some((value) => value.id === next));
              navigate("learning", [kind], { view: "list", source, ...(parent ? { area: parent.id, topic: next } : {}) });
            }} className="min-w-0 max-w-[70%] truncate bg-transparent text-right outline-none">
              <option value="">{t("learning_topic_all")}</option>
              {selectedSource.areas.filter((a) => learningCount(a, kind) > 0).map((a) => <optgroup key={a.id} label={a.title}>
                {a.topics.filter((value) => learningCount(value, kind) > 0).map((value) => <option key={value.id} value={value.id}>{value.title} · {learningCount(value, kind)}</option>)}
              </optgroup>)}
            </select>
          </label>}
          <Segmented
            label={t("notes_learning")}
            value={learning}
            onChange={setLearning}
            options={(["all", "unread", "review", "mastered"] as const).map((value) => ({ value, label: t(value === "all" ? "all" : `notes_learning_${value}`) }))}
          />
          <p className="px-0.5 text-caption text-muted-foreground tabular-nums">{data ? t("notes_count", { n: data.total }) : t("loading")}</p>
          {error && (
            <div role="alert" className="rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">
              {error}{" "}
              <button type="button" className="font-medium underline" onClick={() => load(0)}>
                {t("retry")}
              </button>
            </div>
          )}
          <div aria-busy={loading}>
            <NoteList notes={rows} openId={openId} words={words} crossSource={!source} groupBy={topic || words ? null : (note) => ({ key: `learning:${note.collection}:${note.area}:${note.topic}`, label: `${!source ? note.collection_title + " · " : ""}${note.topic_title || note.area_title || note.chapter_title}` })} onOpen={open} />
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
      <NoteReader reading={reading} ids={ids} rows={rows} accepts={(note) => sectionOf(note) === "learning"} />
    </div>
  );
}

export function LearningPage({ route }: { route: Route }) {
  const kind = route.rest[0];
  // A link to one material (#/learning?open=…) opens it within all materials.
  if (!kind && route.params.get("open")) return <Materials key="all" route={route} kind="all" />;
  if (!kind) return <Categories />;
  const valid = kind === "all" || (LEARNING_KINDS as readonly string[]).includes(kind);
  const current = valid ? (kind as Kind | "all") : "all";
  if (!route.params.get("open") && route.params.get("view") !== "list" && !route.params.get("topic") && !route.params.get("area")) return <LearningCatalog key={current} kind={current} initialSource={route.params.get("source") ?? ""} />;
  return <Materials key={current} route={route} kind={current} />;
}
