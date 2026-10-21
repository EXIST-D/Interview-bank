import { Dialog, DropdownMenu } from "radix-ui";
import { ArrowRight, ChevronLeft, Info, ListTree, MoreHorizontal, Search, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useBank } from "@/lib/bank";
import { useToast } from "@/lib/hooks";
import { useI18n, type TextKey } from "@/lib/i18n";
import { learningState, noteDetail, notesPage, rememberReadingGroups, sectionOf, sourceCards, type NotesPage, type SourceCard } from "@/lib/notes";
import { usePref } from "@/lib/prefs";
import { queueShelf, shelfKey } from "@/lib/sync";
import { useReading } from "@/lib/reading";
import { href, navigate, type Route } from "@/lib/router";
import { keys, stored, type LastRead } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { NoteList, type GroupBy } from "@/notes/note-list";
import { noteHref, NoteReader, useNotesList } from "@/notes/notes-board";
import { NotesFilters, type FilterField } from "@/notes/notes-filters";
import { languageLabel, SourceInfo } from "@/notes/source-info";

const PAGE = 100;
const TILES = ["#0b7f7a", "#ff9f0a", "#0a84ff", "#5e5ce6", "#7d5fff", "#30b07a", "#32ade6", "#ff375f", "#34c759", "#bf5af2"];

function tile(name: string) {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return TILES[Math.abs(hash) % TILES.length];
}

export function SearchField({ id, value, onChange, placeholder }: { id: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="flex h-9 items-center gap-2 rounded-[10px] bg-fill px-3 text-muted-foreground focus-within:ring-2 focus-within:ring-ring/30">
      <Search className="size-4 shrink-0" />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="min-w-0 flex-1 bg-transparent text-subhead text-foreground outline-none placeholder:text-muted-foreground"
      />
    </label>
  );
}

export function useDebounced(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value.trim());
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value.trim()), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Source cards of one section, loaded once per session; reading groups are remembered for learning states. */
export function useSourceCards(section: "knowledge" | "experiences" | "learning") {
  const [page, setPage] = useState<NotesPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    sourceCards(section)
      .then((next) => {
        if (!live) return;
        rememberReadingGroups(next.collections ?? []);
        setPage(next);
      })
      .catch((cause) => live && setError(cause instanceof Error ? cause.message : "failed"));
    return () => {
      live = false;
    };
  }, [section]);
  return { page, error };
}

// ---------------------------------------------------------------- shelf

type ShelfPrefs = { version: 1; order: string[]; expanded: string[]; at?: string };
const NO_SHELF: ShelfPrefs = { version: 1, order: [], expanded: [] };

function useShelfOrder(sources: SourceCard[], account: string) {
  // Per account; the name arrives after the first render, and other devices' order arrives through lib/sync.
  const [prefs, setPrefs] = usePref<ShelfPrefs>(shelfKey(account), NO_SHELF);
  const joined = sources.map((s) => s.name).join("\n");
  const names = useMemo(() => (joined ? joined.split("\n") : []), [joined]);
  const order = useMemo(() => {
    // Newly added sources append; retired or invalid saved names are dropped.
    const known = new Set(names);
    const saved = (prefs.version === 1 ? prefs.order : []).filter((id, i, all) => known.has(id) && all.indexOf(id) === i);
    return [...saved, ...names.filter((id) => !saved.includes(id))];
  }, [prefs, names]);
  const save = (next: string[]) => {
    setPrefs({ version: 1, order: next, expanded: prefs.expanded ?? [], at: new Date().toISOString() });
    queueShelf(next);
  };
  const move = (id: string, position: number) => {
    const rest = order.filter((name) => name !== id);
    rest.splice(Math.max(0, Math.min(position, rest.length)), 0, id);
    save(rest);
    return rest.indexOf(id);
  };
  const byName = new Map(sources.map((s) => [s.name, s]));
  return { ordered: order.map((name) => byName.get(name)!).filter(Boolean), move, reset: () => save(names), custom: order.some((name, i) => name !== names[i]) };
}

function SourceTile({
  source,
  position,
  total,
  onMove,
  onInfo,
}: {
  source: SourceCard;
  position: number;
  total: number;
  onMove: (position: number) => void;
  onInfo: () => void;
}) {
  const { t } = useI18n();
  usePref("ibank-notes-learning", 0);
  usePref<string[]>("ibank-read", []);
  const done = source.content_ids.filter((id) => learningState(id) !== "unread").length;
  const percent = source.content_total ? Math.round((done / source.content_total) * 100) : 0;
  const last = stored<LastRead | null>(keys.lastNote, null);
  const canContinue =
    last && (source.content_ids.includes(last.id) || Object.values(source.reading_members ?? {}).some((group) => group.note_ids.includes(last.id)));
  const areas = source.areas.filter((area) => area.count).slice(0, 3);
  return (
    <article className="group relative flex flex-col gap-3 surface p-4.5 transition-shadow hover:shadow-soft-lg">
      <a href={href("knowledge", [source.name])} className="absolute inset-0 rounded-[1.25rem]" aria-label={source.title} />
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-[11px] text-callout font-semibold text-white" style={{ background: tile(source.name) }}>
          {source.title.replace(/^[^A-Za-z\u4e00-\u9fa5]+/, "").slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-callout leading-snug font-semibold">{source.title}</h3>
          <p className="mt-0.5 text-caption text-muted-foreground tabular-nums">
            {t("notes_count_title", { n: source.content_total })} · {languageLabel(t, source.metadata.language)}
          </p>
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            aria-label={t("shelf_move", { title: source.title })}
            className="relative z-[1] -mt-1 -mr-1 grid size-8 place-items-center rounded-full text-tertiary-foreground hover:bg-fill hover:text-foreground data-[state=open]:bg-fill"
          >
            <MoreHorizontal className="size-4" />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" sideOffset={4} className="z-50 w-44 rounded-2xl border border-border bg-popover p-1.5 shadow-soft-lg">
              <DropdownMenu.Item onSelect={onInfo} className="flex h-9 items-center gap-2 rounded-lg px-2.5 text-subhead outline-none data-[highlighted]:bg-fill">
                <Info className="size-4 text-muted-foreground" />
                {t("notes_source_info")}
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              {(
                [
                  ["shelf_first", 0],
                  ["shelf_previous", position - 1],
                  ["shelf_next", position + 1],
                  ["shelf_last", total - 1],
                ] as [TextKey, number][]
              ).map(([label, target]) => (
                <DropdownMenu.Item
                  key={label}
                  disabled={target < 0 || target >= total || target === position}
                  onSelect={() => onMove(target)}
                  className="flex h-9 items-center rounded-lg px-2.5 text-subhead outline-none data-[disabled]:opacity-35 data-[highlighted]:bg-fill"
                >
                  {t(label)}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      {areas.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {areas.map((area) => (
            <span key={area.id} className="rounded-full bg-fill px-2 py-0.5 text-caption text-muted-foreground">
              {area.title}
            </span>
          ))}
        </div>
      )}
      <div className="mt-auto">
        <div className="h-1 overflow-hidden rounded-full bg-secondary">
          <span className="block h-full rounded-full bg-primary transition-[width] duration-500 ease-apple" style={{ width: `${percent}%` }} />
        </div>
        <div className="mt-2 flex items-center justify-between text-caption text-muted-foreground">
          <span className="tabular-nums">{t("shelf_read", { p: percent })}</span>
          {canContinue ? (
            <a href={href("knowledge", [source.name], { open: last!.id })} className="relative z-[1] flex items-center gap-1 font-medium text-primary">
              {t("notes_continue")}
              <ArrowRight className="size-3.5" />
            </a>
          ) : (
            <span className="flex items-center gap-1 font-medium text-primary">
              {t("notes_start")}
              <ArrowRight className="size-3.5" />
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

function Shelf() {
  const { t } = useI18n();
  const toast = useToast();
  const { library } = useBank();
  const { page, error } = useSourceCards("knowledge");
  const [info, setInfo] = useState<SourceCard | null>(null);
  const [query, setQuery] = useState("");
  const words = useDebounced(query);
  const [results, setResults] = useState<NotesPage | null>(null);
  const sources = page?.collections ?? [];
  const { ordered, move, reset, custom } = useShelfOrder(sources, library?.account || library?.name || "local");

  useEffect(() => {
    if (!words) return setResults(null);
    let live = true;
    notesPage(new URLSearchParams({ section: "knowledge", kind: "study", view: "knowledge", sort: "order", query: words, limit: "60" }))
      .then((next) => live && setResults(next))
      .catch((cause) => live && toast(cause instanceof Error ? cause.message : t("failed")));
    return () => {
      live = false;
    };
  }, [words, toast, t]);

  const total = sources.reduce((n, c) => n + c.content_total, 0);
  const information = sources.reduce((n, c) => n + c.information_total, 0);

  return (
    <div className="mx-auto max-w-[1120px] px-4 pt-8 pb-28 sm:px-6 md:pt-10 md:pb-16">
      <p className="text-caption font-semibold tracking-wide text-primary">{t("board_knowledge")}</p>
      <h1 className="mt-1 text-large-title font-bold">{t("notes_home_title")}</h1>
      <p className="mt-1.5 text-callout text-muted-foreground">{t("notes_home_hint")}</p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="sm:w-80">
          <SearchField id="shelf-search" value={query} onChange={setQuery} placeholder={t("notes_search_all")} />
        </div>
        <p className="flex-1 text-footnote text-muted-foreground tabular-nums">
          {page ? t("notes_home_summary", { s: sources.length, n: total, i: information }) : t("loading")}
        </p>
        {custom && !words && (
          <Button
            variant="link"
            size="sm"
            className="self-start px-0 sm:self-auto"
            onClick={() => {
              reset();
              toast(t("shelf_reset_done"));
            }}
          >
            {t("shelf_reset")}
          </Button>
        )}
      </div>
      {error && <p className="mt-6 rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">{error}</p>}

      {words ? (
        <div className="mt-5 max-w-3xl">
          <p className="mb-2 text-caption text-muted-foreground">{results ? t("notes_count_title", { n: results.total }) + " · " + t("notes_search_all_hint") : t("loading")}</p>
          {results && (
            <NoteList
              notes={results.notes}
              openId={null}
              words={words}
              crossSource
              groupBy={null}
              onOpen={(id) => {
                const note = results.notes.find((n) => n.id === id)!;
                location.hash = noteHref(note);
              }}
            />
          )}
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {!page
            ? Array.from({ length: 6 }, (_, i) => <div key={i} className="h-44 animate-pulse rounded-[1.25rem] bg-fill" />)
            : ordered.map((source, index) => (
                <SourceTile
                  key={source.name}
                  source={source}
                  position={index}
                  total={ordered.length}
                  onInfo={() => setInfo(source)}
                  onMove={(target) => {
                    const at = move(source.name, target);
                    toast(t("shelf_moved", { title: source.title, n: at + 1, total: ordered.length }));
                  }}
                />
              ))}
        </div>
      )}
      <SourceInfo source={info} onClose={() => setInfo(null)} onOpenNote={(id) => info && navigate("knowledge", [info.name], { open: id })} />
    </div>
  );
}

// ---------------------------------------------------------------- one source

type Directory = { view: "knowledge" | "original"; area: string; topic: string; chapter: string };

function DirectoryTree({
  source,
  dir,
  onPick,
  onInfo,
}: {
  source: SourceCard;
  dir: Directory;
  onPick: (changes: Partial<Directory>) => void;
  onInfo: () => void;
}) {
  const { t } = useI18n();
  const entry = (active: boolean, sub = false) =>
    cn(
      "flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-footnote transition-colors",
      sub && "pl-6",
      active ? "bg-accent font-medium text-accent-foreground" : sub ? "text-muted-foreground hover:bg-fill hover:text-foreground" : "hover:bg-fill",
    );
  const count = (n: number) => <small className="shrink-0 text-caption text-tertiary-foreground tabular-nums">{n}</small>;
  const all = !dir.area && !dir.topic && dir.chapter === "";
  return (
    <div className="flex flex-col gap-0.5">
      <a href={href("knowledge")} className="mb-2 flex items-center gap-0.5 px-1 text-footnote font-medium text-primary">
        <ChevronLeft className="size-4" />
        {t("all_sources")}
      </a>
      <h2 className="px-2.5 text-headline leading-snug font-bold">{source.title}</h2>
      <p className="px-2.5 pt-1 pb-3 text-caption text-muted-foreground">
        {[t("notes_count_title", { n: source.content_total }), languageLabel(t, source.metadata.language), source.metadata.license].filter(Boolean).join(" · ")}
      </p>
      <div className="mx-1 mb-2">
        <Segmented
          value={dir.view}
          onChange={(view) => onPick({ view, area: "", topic: "", chapter: "" })}
          options={[
            { value: "knowledge", label: t("notes_knowledge") },
            { value: "original", label: t("notes_original") },
          ]}
        />
      </div>
      <button type="button" className={entry(all)} onClick={() => onPick({ area: "", topic: "", chapter: "" })}>
        <span>{t("notes_all_source")}</span>
        {count(source.content_total)}
      </button>
      {dir.view === "knowledge"
        ? source.areas
            .filter((area) => area.count)
            .map((area) => (
              <div key={area.id} className="mt-1">
                <button type="button" className={cn(entry(dir.area === area.id && !dir.topic), "font-semibold")} onClick={() => onPick({ area: area.id, topic: "", chapter: "" })}>
                  <span>{area.title}</span>
                  {count(area.count)}
                </button>
                {dir.area === area.id &&
                  area.topics
                    .filter((topic) => topic.count)
                    .map((topic) => (
                      <button key={topic.id} type="button" className={entry(dir.topic === topic.id, true)} onClick={() => onPick({ area: area.id, topic: topic.id, chapter: "" })}>
                        <span>{topic.title}</span>
                        {count(topic.count)}
                      </button>
                    ))}
              </div>
            ))
        : source.chapters
            .filter((chapter) => chapter.count)
            .map((chapter) => (
              <button
                key={chapter.index}
                type="button"
                className={entry(dir.chapter === String(chapter.index), true)}
                onClick={() => onPick({ chapter: String(chapter.index), area: "", topic: "" })}
              >
                <span>{chapter.title}</span>
                {count(chapter.count)}
              </button>
            ))}
      <button type="button" onClick={onInfo} className="mt-3 flex items-center gap-1.5 px-2.5 py-1.5 text-footnote text-muted-foreground hover:text-foreground">
        <Info className="size-3.5" />
        {t("notes_source_info")}
      </button>
    </div>
  );
}

type Quick = "all" | "marked" | "asked" | "unread";
const NOTE_FILTERS = { tag: "", kind: "study", question_type: "", connection: "", verification: "", learning: "all", sort: "order" };

function SourceView({ route, name }: { route: Route; name: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const { page: meta, error: metaError } = useSourceCards("knowledge");
  const source = meta?.collections?.find((c) => c.name === name) ?? null;
  const dir: Directory = {
    view: route.params.get("view") === "original" ? "original" : "knowledge",
    area: route.params.get("area") ?? "",
    topic: route.params.get("topic") ?? "",
    chapter: route.params.get("chapter") ?? "",
  };
  const [quick, setQuick] = useState<Quick>("all");
  const [filters, setFilters] = useState<Record<string, string>>(NOTE_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [dirOpen, setDirOpen] = useState(false);
  const [info, setInfo] = useState(false);
  const [query, setQuery] = useState("");
  const words = useDebounced(query);
  const [scope, setScope] = useState<"topic" | "source" | "all">("source");
  useEffect(() => {
    if (meta && !source) {
      toast(t("entry_missing"));
      navigate("knowledge");
    }
  }, [meta, source, toast, t]);

  const hasTopic = dir.view === "original" ? dir.chapter !== "" : Boolean(dir.topic);
  const effectiveScope = scope === "topic" && !hasTopic ? "source" : scope;
  const learning = quick === "unread" ? "unread" : filters.learning;

  const params = useCallback(
    (offset: number, limit = PAGE) => {
      const search = new URLSearchParams({ section: "knowledge", view: dir.view, sort: filters.sort, kind: filters.kind || "study", offset: String(offset), limit: String(limit) });
      if (!(words && effectiveScope === "all")) search.set("collection", name);
      if (!words || effectiveScope === "topic") {
        if (dir.view === "original" && dir.chapter !== "") search.set("chapter", dir.chapter);
        if (dir.view === "knowledge") {
          if (dir.area) search.set("area", dir.area);
          if (dir.topic) search.set("topic", dir.topic);
        }
      }
      if (words) search.set("query", words);
      for (const key of ["tag", "verification", "question_type", "connection"]) if (filters[key]) search.set(key, filters[key]);
      if (quick === "marked") search.set("marked", "1");
      if (quick === "asked") search.set("asked", "1");
      return search;
    },
    [dir.view, dir.chapter, dir.area, dir.topic, filters, words, effectiveScope, name, quick],
  );

  const { data, rows, loading, error, load } = useNotesList(params, learning);
  const ids = data?.ids ?? [];
  const reading = useReading({ route, board: "knowledge", ids, searchId: "source-search" });
  const { openId, open, focused, listHidden } = reading;

  const pick = (changes: Partial<Directory>) => {
    const next = { ...dir, ...changes };
    const query: Record<string, string> = {};
    if (next.view === "original") query.view = "original";
    if (next.area) query.area = next.area;
    if (next.topic) query.topic = next.topic;
    if (next.chapter !== "") query.chapter = next.chapter;
    if (openId) query.open = openId;
    setQuery("");
    setDirOpen(false);
    navigate("knowledge", [name], query);
  };

  const groupBy: GroupBy =
    !words && filters.sort === "order" && !hasTopic
      ? dir.view === "knowledge"
        ? (n) => ({ key: `${n.collection}:${n.area}:${n.topic}`, label: n.topic_title || n.area_title || n.chapter_title })
        : (n) => ({ key: `${n.collection}:${n.chapter}`, label: n.chapter_title })
      : null;

  const area = source?.areas.find((a) => a.id === dir.area);
  const topic = area?.topics.find((x) => x.id === dir.topic);
  const chapter = source?.chapters.find((c) => String(c.index) === dir.chapter);
  const heading = topic?.title || chapter?.title || area?.title || t("notes_all_source");
  const eyebrow = topic ? area?.title : source?.title;
  const facets = data?.facets;
  const fields: FilterField[] = facets
    ? [
        { key: "tag", label: t("notes_tags"), options: [{ value: "", label: t("notes_tags_all") }, ...facets.tags.map((tag) => ({ value: tag, label: tag }))] },
        {
          key: "kind",
          label: t("notes_kind"),
          options: [
            { value: "study", label: t("notes_kind_study") },
            ...Object.entries(facets.kinds)
              .filter(([kind]) => kind !== "info")
              .map(([kind, n]) => ({ value: kind, label: `${t(`notes_kind_${kind}` as TextKey)} · ${n}` })),
          ],
        },
        {
          key: "question_type",
          label: t("notes_question_type"),
          options: [
            { value: "", label: t("notes_question_type_all") },
            ...Object.entries(facets.question_types).map(([type, n]) => ({ value: type, label: `${t(`notes_question_type_${type}` as TextKey)} · ${n}` })),
          ],
        },
        {
          key: "connection",
          label: t("notes_connection"),
          options: [{ value: "", label: t("notes_connection_all") }, ...(["any", "personal", "public", "none"] as const).map((c) => ({ value: c, label: t(`notes_connection_${c}`) }))],
        },
        {
          key: "verification",
          label: t("notes_verification"),
          options: [
            { value: "", label: t("notes_verification_all") },
            ...Object.keys(facets.verification).map((v) => ({ value: v, label: t(`notes_verification_${v}` as TextKey) })),
          ],
        },
        {
          key: "learning",
          label: t("notes_learning"),
          options: (["all", "read", "review", "mastered"] as const).map((v) => ({ value: v, label: t(`notes_learning_${v}`) })),
        },
        {
          key: "sort",
          label: t("sort"),
          options: [
            { value: "order", label: t("notes_experience_order") },
            { value: "asked", label: t("asked_sort") },
          ],
        },
      ]
    : [];
  const filterCount = fields.filter((field) => (filters[field.key] ?? "") !== (NOTE_FILTERS as Record<string, string>)[field.key]).length;

  if (metaError) return <p className="m-6 rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">{metaError}</p>;

  const tree = source && <DirectoryTree source={source} dir={dir} onPick={pick} onInfo={() => setInfo(true)} />;

  return (
    <div
      className={cn(
        "wide:grid wide:h-[calc(100dvh-3.25rem)]",
        focused && "wide:h-dvh",
        listHidden ? "wide:grid-cols-1" : "wide:grid-cols-[minmax(340px,400px)_1fr] roomy:grid-cols-[240px_minmax(340px,380px)_1fr]",
      )}
    >
      <aside aria-label={t("directory")} className={cn("hidden overflow-y-auto border-r border-border px-2.5 pt-5 pb-8", !listHidden && "roomy:block")}>
        {tree ?? <div className="mx-2 h-64 animate-pulse rounded-2xl bg-fill" />}
      </aside>

      <section aria-label={t("board_knowledge")} className={cn("min-w-0 wide:overflow-y-auto wide:border-r wide:border-border", listHidden && "wide:hidden")}>
        <div className="flex flex-col gap-3 px-4 pt-5 pb-28 wide:pb-8">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <a href={href("knowledge")} className="mb-1 flex items-center gap-0.5 text-footnote font-medium text-primary roomy:hidden">
                <ChevronLeft className="size-4" />
                {t("all_sources")}
              </a>
              <p className="truncate text-caption font-semibold tracking-wide text-primary">{eyebrow}</p>
              <h1 className="mt-0.5 text-title-2 font-bold">{heading}</h1>
            </div>
            <Button variant="outline" size="sm" className="mt-1 roomy:hidden" onClick={() => setDirOpen(true)}>
              <ListTree />
              {t("directory")}
            </Button>
          </div>
          <SearchField id="source-search" value={query} onChange={setQuery} placeholder={t("search_notes")} />
          {query.trim() && (
            <Segmented
              label={t("search_scope")}
              value={effectiveScope}
              onChange={setScope}
              options={[
                ...(hasTopic ? [{ value: "topic" as const, label: t("notes_scope_topic") }] : []),
                { value: "source" as const, label: t("notes_scope_source") },
                { value: "all" as const, label: t("notes_scope_all") },
              ]}
            />
          )}
          <Segmented
            value={quick}
            onChange={setQuick}
            options={[
              { value: "all", label: t("all") },
              { value: "marked", label: t("marked_only") },
              { value: "asked", label: t("asked_only") },
              { value: "unread", label: t("notes_learning_unread") },
            ]}
          />
          <div className="flex items-center gap-2">
            <p className="min-w-0 flex-1 px-0.5 text-caption text-muted-foreground tabular-nums">{data ? t("notes_count", { n: data.total }) : t("loading")}</p>
            <Button variant="outline" size="sm" onClick={() => setFiltersOpen(true)} disabled={!facets}>
              <SlidersHorizontal />
              {t("filters")}
              {filterCount > 0 && <span className="grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] leading-4 text-primary-foreground">{filterCount}</span>}
            </Button>
          </div>
          {error && (
            <div role="alert" className="rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">
              {error}{" "}
              <button type="button" className="font-medium underline" onClick={() => load(0)}>
                {t("retry")}
              </button>
            </div>
          )}
          <div aria-busy={loading}>
            <NoteList notes={rows} openId={openId} words={words} crossSource={effectiveScope === "all" && Boolean(words)} groupBy={groupBy} onOpen={open} />
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

      <NoteReader
        reading={reading}
        ids={ids}
        rows={rows}
        accepts={(note) => sectionOf(note) === "knowledge" && (note.collection === name || note.kind === "info")}
      />

      <Dialog.Root open={dirOpen} onOpenChange={setDirOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
          <Dialog.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[80dvh] overflow-y-auto rounded-t-3xl bg-background p-3 shadow-soft-lg outline-none wide:inset-y-0 wide:right-auto wide:left-0 wide:max-h-none wide:w-80 wide:rounded-none wide:rounded-r-3xl">
            <div className="flex justify-end">
              <Dialog.Close aria-label={t("close")} className="grid size-8 place-items-center rounded-full bg-fill text-muted-foreground">
                <X className="size-4" />
              </Dialog.Close>
            </div>
            <Dialog.Title className="sr-only">{t("directory")}</Dialog.Title>
            {tree}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <NotesFilters
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        fields={fields}
        values={filters}
        defaults={NOTE_FILTERS}
        onChange={(changes) => setFilters((current) => ({ ...current, ...changes }))}
      />
      <SourceInfo source={info ? source : null} onClose={() => setInfo(false)} onOpenNote={open} />
    </div>
  );
}

// ---------------------------------------------------------------- entry

export function KnowledgePage({ route }: { route: Route }) {
  const { t } = useI18n();
  const toast = useToast();
  const name = route.rest[0];
  const pending = !name ? route.params.get("open") : null;
  const notesPanel = route.params.get("panel") === "notes";

  // A link to one note without its source (#note=…, related notes): find where it lives first.
  useEffect(() => {
    if (!pending) return;
    let live = true;
    noteDetail(pending)
      .then((note) => {
        if (!live) return;
        history.replaceState(null, "", noteHref(note) + (notesPanel ? "&panel=notes" : ""));
        dispatchEvent(new HashChangeEvent("hashchange"));
      })
      .catch((cause) => {
        if (!live) return;
        toast(cause instanceof Error ? cause.message : t("entry_missing"));
        history.replaceState(null, "", href("knowledge"));
        dispatchEvent(new HashChangeEvent("hashchange"));
      });
    return () => {
      live = false;
    };
  }, [pending, notesPanel, toast, t]);

  if (pending) return <p className="p-10 text-center text-footnote text-muted-foreground">{t("loading")}</p>;
  return name ? <SourceView key={name} route={route} name={name} /> : <Shelf />;
}
