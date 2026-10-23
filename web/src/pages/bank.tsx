import { Check, ChevronDown, ChevronRight, GitMerge, PenLine, Play, Search, SlidersHorizontal, StickyNote } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, clearDetails, questionDetail, type Library, type QuestionDetail, type QuestionRow } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useToast } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { markRead, usePref } from "@/lib/prefs";
import { useReading } from "@/lib/reading";
import { href, navigate, type Route } from "@/lib/router";
import { keys, store, stored } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { ReaderFrame } from "@/reader/reader-frame";
import { QuestionView } from "@/reader/question-view";
import { RichText } from "@/reader/markdown";
import { activeFilters, FilterDialog, NO_FILTERS, type Filters } from "./bank-filters";
import { Merges, useMerges } from "./merges";
import { discardRound, Practice, storedRound, type PracticeStart } from "./practice";

const PAGE = 30;
const VIEWS = ["all", "due", "weak", "unseen"] as const;
type View = (typeof VIEWS)[number];

function Highlight({ text, words }: { text: string; words: string }) {
  // Marks the search words in a title; the text itself stays plain text.
  if (!words) return <>{text}</>;
  const pattern = new RegExp("(" + words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
  return (
    <>
      {text.split(pattern).map((part, i) =>
        part.toLowerCase() === words.toLowerCase() ? (
          <mark key={i} className="rounded-sm bg-orange/25 text-inherit">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

function Row({ question, current, read, words, onOpen }: { question: QuestionRow; current: boolean; read: boolean; words: string; onOpen: () => void }) {
  const { t } = useI18n();
  const [peek, setPeek] = useState<ReactNode | null>(null);
  const answered = question.answer_status === "source_backed" || question.answer_status === "reviewed";
  const togglePeek = async () => {
    // A quick look at the answer without leaving the list; opening the reader still marks it read.
    if (peek) return setPeek(null);
    setPeek(<p className="text-footnote text-muted-foreground">{t("loading")}</p>);
    try {
      const detail = await questionDetail(question.id);
      setPeek(
        detail.answer?.short_answer ? (
          <div className="ib-reading ib-peek line-clamp-[8]">
            <RichText text={detail.answer.short_answer} />
          </div>
        ) : (
          <p className="text-footnote text-muted-foreground">{t("no_answer")}</p>
        ),
      );
    } catch (error) {
      setPeek(<p className="text-footnote text-destructive">{error instanceof Error ? error.message : t("failed")}</p>);
    }
  };
  return (
    <li
      className={cn(
        "rounded-2xl border bg-card shadow-soft-sm transition-shadow",
        current ? "border-primary shadow-[0_0_0_3px_var(--accent)]" : "border-transparent",
      )}
    >
      <div className="flex items-start">
        <button type="button" data-id={question.id} onClick={onOpen} className="min-w-0 flex-1 px-4 py-3.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/40 rounded-2xl">
          <span className={cn("line-clamp-2 text-subhead leading-snug font-medium", read && !current && "text-muted-foreground")}>
            <Highlight text={question.canonical} words={words} />
          </span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-caption text-muted-foreground">
            <span>{question.group}</span>
            <span className="tabular-nums">{t("seen", { n: question.frequency })}</span>
            {answered && (
              <span className="flex items-center gap-0.5 text-success">
                <Check className="size-3" />
                {t("status_answered")}
              </span>
            )}
            {question.has_my_answer && (
              <span className="flex items-center gap-0.5 text-primary">
                <PenLine className="size-3" />
                {t("my_answer_mark")}
              </span>
            )}
            {read && <span>{t("read_mark")}</span>}
          </span>
        </button>
        {question.has_my_answer && <a href={href("bank", [], { open: question.id, panel: "notes" })} aria-label={t("note_open_item")} title={t("note_open_item")} className="mt-2 grid size-8 shrink-0 place-items-center rounded-full text-primary hover:bg-accent"><StickyNote className="size-4" /></a>}
        <button
          type="button"
          aria-label={t("peek")}
          aria-expanded={Boolean(peek)}
          onClick={togglePeek}
          className="m-2 grid size-8 shrink-0 place-items-center rounded-full text-tertiary-foreground hover:bg-fill hover:text-foreground"
        >
          <ChevronDown className={cn("size-4 transition-transform duration-200", peek && "rotate-180")} />
        </button>
      </div>
      {peek && (
        <div className="border-t border-border px-4 pt-3 pb-3.5">
          {peek}
          <button type="button" onClick={onOpen} className="mt-2 text-footnote font-medium text-primary">
            {t("read_all")} ›
          </button>
        </div>
      )}
    </li>
  );
}

export function BankPage({ route }: { route: Route }) {
  const { t } = useI18n();
  const toast = useToast();
  const { library: overview } = useBank();

  // The home page's plan links here with a view, and asks for a round straight away.
  const [view, setView] = useState<View>(() => {
    const asked = route.params.get("view") as View | null;
    return asked && VIEWS.includes(asked) ? asked : "all";
  });
  const askedRound = useRef(route.params.get("practice") === "1");
  const [group, setGroup] = useState("");
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [answeredOnly, setAnsweredOnly] = useState(() => stored("ibank-answered-only", false));
  const [query, setQuery] = useState("");
  const [words, setWords] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [data, setData] = useState<Library | null>(null);
  const [rows, setRows] = useState<QuestionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);

  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [revealed, setRevealed] = useState(true);
  const [readList] = usePref<string[]>("ibank-read", []);
  const read = useMemo(() => new Set(readList), [readList]);
  const ids = data?.ids ?? [];
  const { openId, open, close, step, index, layout, setLayout, focused, listHidden, registerReveal, notesOpen, setNotesOpen } = useReading({
    route,
    board: "bank",
    ids,
    searchId: "bank-search",
  });
  useEffect(() => {
    registerReveal(() => setRevealed(true), revealed);
  }, [registerReveal, revealed]);

  // Search waits for a pause in typing.
  useEffect(() => {
    const timer = setTimeout(() => setWords(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const params = useCallback(
    (offset: number, limit = PAGE) => {
      const search = new URLSearchParams({ view, sort: filters.sort, offset: String(offset), limit: String(limit) });
      if (words) search.set("query", words);
      if (group) search.set("group", group);
      for (const key of ["domain", "technology", "company", "role", "industry", "answer_status"] as const) if (filters[key]) search.set(key, filters[key]);
      if (answeredOnly && !filters.answer_status) search.set("answer_status", "answered");
      return search;
    },
    [view, filters, words, group, answeredOnly],
  );

  const load = useCallback(
    async (offset = 0) => {
      const current = ++generation.current;
      setLoading(true);
      setError(null);
      try {
        const next = await api<Library>("/api/library?" + params(offset));
        if (current !== generation.current) return;
        setData(next);
        setRows((previous) => (offset ? [...previous, ...next.questions] : next.questions));
      } catch (cause) {
        if (current === generation.current) setError(cause instanceof Error ? cause.message : t("failed"));
      } finally {
        if (current === generation.current) setLoading(false);
      }
    },
    [params, t],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  useEffect(() => {
    if (!openId) {
      setDetail(null);
      return;
    }
    let live = true;
    questionDetail(openId)
      .then((q) => {
        if (!live) return;
        setDetail(q);
        setRevealed(!stored(keys.thinkFirst, false));
        markRead(q.id);
        store(keys.lastQuestion, { id: q.id, title: q.canonical.slice(0, 40) + (q.canonical.length > 40 ? "…" : "") });
      })
      .catch((cause) => {
        if (!live) return;
        toast(cause instanceof Error ? cause.message : t("load_failed"));
        close();
      });
    return () => {
      live = false;
    };
  }, [openId, toast, t, close]);

  useEffect(() => {
    // Neighbours load in the background so previous/next is instant.
    if (index < 0) return;
    for (const neighbour of [ids[index + 1], ids[index - 1]]) if (neighbour) questionDetail(neighbour).catch(() => {});
  }, [index, ids]);

  const [practice, setPractice] = useState<PracticeStart | null>(null);
  const [resumable, setResumable] = useState(() => storedRound());
  const merges = useMerges(Boolean(data && !data.read_only));
  const [mergesOpen, setMergesOpen] = useState(false);

  useEffect(() => {
    if (!askedRound.current || !data) return;
    askedRound.current = false;
    history.replaceState(null, "", href("bank", [], view === "all" ? undefined : { view }));
    if (data.total) setPractice({ kind: "setup" });
  }, [data, view]);

  const summary = data?.summary ?? overview?.summary;
  const groups = data?.facets.group ?? [];
  const groupTotal = groups.reduce((sum, g) => sum + g.count, 0);
  const filterCount = activeFilters(filters);
  const chip = (active: boolean) =>
    cn(
      "shrink-0 rounded-full border px-3 py-1.5 text-footnote transition-colors",
      active ? "border-transparent bg-foreground text-background" : "border-border bg-card text-muted-foreground shadow-soft-sm hover:text-foreground",
    );

  return (
    <div
      className={cn(
        "wide:grid wide:h-[calc(100dvh-var(--ib-header-height,3.25rem))]",
        focused && "wide:h-dvh",
        listHidden ? "wide:grid-cols-1" : "wide:grid-cols-[minmax(340px,400px)_1fr]",
      )}
    >
      <section aria-label={t("board_bank")} className={cn("min-w-0 wide:overflow-y-auto wide:border-r wide:border-border", listHidden && "wide:hidden")}>
        <div className="flex flex-col gap-3.5 px-4 pt-5 pb-28 wide:pb-8">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-caption font-semibold tracking-wide text-primary">{t("board_bank")}</p>
              <h1 className="mt-0.5 text-title-1 font-bold tabular-nums">{t("bank_count", { n: data?.total ?? summary?.questions ?? "—" })}</h1>
            </div>
            <Button variant="tinted" size="sm" className="mb-1" disabled={!data?.total} onClick={() => setPractice({ kind: "setup" })}>
              <Play />
              {t("practice")}
            </Button>
          </div>
          <label className="flex h-9 items-center gap-2 rounded-[10px] bg-fill px-3 text-muted-foreground focus-within:ring-2 focus-within:ring-ring/30">
            <Search className="size-4 shrink-0" />
            <input
              id="bank-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("search")}
              aria-label={t("search")}
              className="min-w-0 flex-1 bg-transparent text-subhead text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>
          <Segmented
            value={view}
            onChange={setView}
            options={VIEWS.map((value) => ({
              value,
              label: (
                <>
                  {t(`view_${value}`)}
                  {value !== "all" && summary && <span className="ml-1 text-[11px] text-tertiary-foreground tabular-nums">{summary[value]}</span>}
                </>
              ),
            }))}
          />
          <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
            <button type="button" aria-pressed={!group} onClick={() => setGroup("")} className={chip(!group)}>
              {t("all")}
              <span className="ml-1 opacity-60 tabular-nums">{groupTotal || ""}</span>
            </button>
            {groups.map((item) => (
              <button key={item.value} type="button" aria-pressed={group === item.value} onClick={() => setGroup(item.value)} className={chip(group === item.value)}>
                {item.label}
                <span className="ml-1 opacity-60 tabular-nums">{item.count}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-caption text-muted-foreground tabular-nums">
              {data ? t("list_summary", { s: t(`sort_${filters.sort as "frequency"}`), a: data.total_answered }) : ""}
            </span>
            <button
              type="button"
              aria-pressed={answeredOnly}
              onClick={() => {
                store("ibank-answered-only", !answeredOnly);
                setAnsweredOnly(!answeredOnly);
              }}
              className={cn(chip(answeredOnly), "py-1")}
            >
              {t("answered_only")}
            </button>
            <Button variant="outline" size="sm" onClick={() => setFiltersOpen(true)}>
              <SlidersHorizontal />
              {t("filters")}
              {filterCount > 0 && (
                <span className="grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] leading-4 text-primary-foreground">{filterCount}</span>
              )}
            </Button>
          </div>

          {resumable && !practice && (
            <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl bg-accent px-4 py-2.5 text-footnote text-accent-foreground">
              <span className="flex-1">{t("resume_text", { i: resumable.index + 1, n: resumable.questions.length })}</span>
              <button type="button" className="font-semibold" onClick={() => setPractice({ kind: "resume" })}>
                {t("resume")}
              </button>
              <button
                type="button"
                className="text-muted-foreground"
                onClick={() => {
                  discardRound();
                  setResumable(null);
                }}
              >
                {t("discard")}
              </button>
            </div>
          )}
          {merges.open > 0 && (
            <button
              type="button"
              onClick={() => setMergesOpen(true)}
              className="flex items-center gap-2 rounded-2xl bg-orange/14 px-4 py-2.5 text-left text-footnote font-medium text-warning"
            >
              <GitMerge className="size-4 shrink-0" />
              <span className="flex-1">{t("merges_pending", { n: merges.open })}</span>
              <ChevronRight className="size-4" />
            </button>
          )}
          {error && (
            <div role="alert" className="rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">
              {error}{" "}
              <button type="button" className="font-medium underline" onClick={() => load(0)}>
                {t("retry")}
              </button>
            </div>
          )}

          <ol className="flex flex-col gap-2" aria-busy={loading}>
            {rows.map((question) => (
              <Row
                key={question.id}
                question={question}
                current={question.id === openId}
                read={read.has(question.id)}
                words={words}
                onOpen={() => open(question.id)}
              />
            ))}
            {!loading && !rows.length && !error && (
              <li className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-footnote text-muted-foreground">
                {summary?.questions ? t("empty_filtered") : t("empty_bank")}
              </li>
            )}
          </ol>
          {data && rows.length < data.total && (
            <Button variant="outline" className="self-center" disabled={loading} onClick={() => load(rows.length)}>
              {t("more_questions")}
            </Button>
          )}
        </div>
      </section>

      <div className={cn(openId ? "fixed inset-0 z-50 wide:static wide:z-auto" : "hidden wide:block", "min-h-0 min-w-0")}>
        {openId && detail?.id === openId ? (
          <ReaderFrame
            contentKey={detail.id}
            nav={{ index, total: ids.length, onStep: step }}
            onBack={close}
            listCollapsed={layout.list}
            onToggleList={() => setLayout({ list: !layout.list, focus: false })}
            focused={focused}
            onToggleFocus={() => setLayout({ focus: !layout.focus })}
            hasAnswer={Boolean(detail.answer)}
            revealed={revealed}
            onToggleAnswer={() => setRevealed(!revealed)}
            notesOpen={notesOpen}
            onNotesOpen={setNotesOpen}
            personalNote={overview ? {
              title: detail.canonical,
              account: overview.account || overview.name,
              saved: detail.my_answer ?? null,
              canWrite: Boolean(data?.can_write_answer ?? overview.can_write_answer),
              onSaved: (value) => {
                setDetail((current) => current?.id === detail.id ? { ...current, my_answer: value } : current);
                setRows((current) => current.map((row) => row.id === detail.id ? { ...row, has_my_answer: Boolean(value) } : row));
                questionDetail(detail.id, true).catch(() => {});
              },
              onReload: async () => {
                const latest = await questionDetail(detail.id, true);
                setDetail((current) => current?.id === detail.id ? latest : current);
                return latest.my_answer ?? null;
              },
            } : undefined}
          >
            <QuestionView
              question={detail}
              revealed={revealed}
              onReveal={() => setRevealed(true)}
              canReview={Boolean(data?.can_review ?? overview?.can_review)}
              onReviewed={async () => {
                setDetail(await questionDetail(detail.id, true));
                load(0);
              }}
              onOpenNote={(id) => navigate("knowledge", [], { open: id })}
              onPractise={() => setPractice({ kind: "one", question: detail })}
              onToast={toast}
            />
          </ReaderFrame>
        ) : (
          <div className="grid h-full place-content-center justify-items-center gap-3 bg-card text-muted-foreground">
            {openId ? (
              <p className="text-footnote">{t("loading")}</p>
            ) : (
              <>
                <span className="opacity-25">
                  <Logo />
                </span>
                <p className="text-footnote">{t("pick")}</p>
              </>
            )}
          </div>
        )}
      </div>

      <FilterDialog open={filtersOpen} onOpenChange={setFiltersOpen} filters={filters} onChange={setFilters} facets={data?.facets ?? {}} />
      <Practice
        start={practice}
        params={() => params(0)}
        canRecord={Boolean(data?.can_record)}
        onClose={(recorded) => {
          setPractice(null);
          setResumable(storedRound());
          if (recorded) {
            clearDetails();
            load(0);
            if (detail) questionDetail(detail.id).then(setDetail).catch(() => {});
          }
        }}
      />
      <Merges open={mergesOpen} onOpenChange={setMergesOpen} items={merges.items} onChanged={merges.reload} onToast={toast} />
    </div>
  );
}
