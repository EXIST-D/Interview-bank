import { AlertTriangle, ArrowLeft, Building2, Loader2, MessageSquareQuote, Play, Target } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useI18n, type TextKey } from "@/lib/i18n";
import { interview } from "@/lib/interview";
import { HALF_LIVES, prepare, WINDOWS, type Card, type Company, type CompanyRow, type ListDetail, type ListRow, type Order, type Ranked, type Top, type Window } from "@/lib/prepare";
import { href, navigate, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { Practice, type PracticeStart } from "./practice";

const field = "h-9 w-full rounded-[10px] bg-fill px-3 text-subhead outline-none focus:ring-2 focus:ring-ring/30";
const TABS = ["top", "companies", "lists"] as const;
type Tab = (typeof TABS)[number];
const COUNTS = ["5", "10", "20"] as const;

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;
}

function StateChip({ card }: { card: Card }) {
  const { t } = useI18n();
  const { state, due } = card.progress;
  const text = state === "unseen" ? t("view_unseen") : state === "familiar" ? (due ? t("view_due") : t("pp_state_familiar")) : t("view_weak");
  const tone = state === "familiar" && !due ? "text-success" : state === "unseen" ? "text-muted-foreground" : "text-warning";
  return <span className={cn("shrink-0 text-caption font-medium", tone)}>{text}</span>;
}

function Line({ card, rank, meta }: { card: Card; rank?: number; meta?: string }) {
  const { t } = useI18n();
  return (
    <li className="flex items-start gap-3 rounded-xl bg-fill px-3 py-2.5">
      {rank !== undefined && <span className="w-7 shrink-0 pt-0.5 text-right text-footnote font-semibold text-primary tabular-nums">{rank}</span>}
      <div className="min-w-0 flex-1">
        <a href={href("bank", [], { open: card.id })} className="text-subhead leading-relaxed hover:underline">
          {card.canonical}
        </a>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-caption text-muted-foreground">
          {meta && <span>{meta}</span>}
          <span>{t(`status_${card.answer_status}` as TextKey)}</span>
        </p>
      </div>
      <StateChip card={card} />
    </li>
  );
}

/** Practise or interview on a set of questions the page is showing. */
function Actions({ cards, direction, onPractice }: { cards: Card[]; direction: string; onPractice: (ids: string[]) => void }) {
  const { t } = useI18n();
  const { library } = useBank();
  const [count, setCount] = useState<(typeof COUNTS)[number]>("10");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Weak and unseen questions first, then due ones, then the rest, each in the page's own order.
  const order = (card: Card) => (card.progress.state === "familiar" ? (card.progress.due ? 2 : 3) : card.progress.state === "unseen" ? 1 : 0);
  const chosen = useMemo(() => cards.map((card, index) => ({ card, index })).sort((a, b) => order(a.card) - order(b.card) || a.index - b.index).slice(0, Number(count)).map((x) => x.card.id), [cards, count]);
  if (!cards.length) return null;
  const mock = async () => {
    setBusy(true);
    setError(null);
    try {
      const session = await interview.start({ question_ids: chosen, direction });
      navigate("interview", [session.id]);
    } catch (cause) {
      setError(message(cause, t("failed")));
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-36">
          <Segmented value={count} onChange={setCount} label={t("iv_count")} options={COUNTS.map((value) => ({ value, label: value }))} />
        </div>
        <Button variant="tinted" size="sm" onClick={() => onPractice(chosen)}>
          <Play />
          {t("practice")}
        </Button>
        {library?.can_interview && (
          <Button variant="tinted" size="sm" disabled={busy} onClick={mock}>
            {busy ? <Loader2 className="animate-spin" /> : <MessageSquareQuote />}
            {t("board_interview")}
          </Button>
        )}
      </div>
      <p className="text-caption text-muted-foreground">{t("pp_actions_hint")}</p>
      {error && <p className="text-footnote text-destructive">{error}</p>}
    </div>
  );
}

function TopTab({ onPractice }: { onPractice: (ids: string[]) => void }) {
  const { t } = useI18n();
  const { library } = useBank();
  const [window, setWindow] = useState<Window>("all");
  const [order, setOrder] = useState<Order>("weighted");
  const [halfLife, setHalfLife] = useState(365);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [top, setTop] = useState<Top | null>(null);
  const [rows, setRows] = useState<Ranked[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Until the first answer arrives the controls show; a bank without any interview date has no use for them.
  const dated = !top || top.dated > 0;

  const load = useCallback(
    async (offset: number) => {
      setBusy(true);
      setError(null);
      try {
        const next = await prepare.top({ window, order, half_life: halfLife, offset, limit: 30, ...filters });
        setTop(next);
        setRows((current) => (offset ? [...current, ...next.questions] : next.questions));
      } catch (cause) {
        setError(message(cause, t("unreachable")));
      } finally {
        setBusy(false);
      }
    },
    [window, order, halfLife, filters, t],
  );
  useEffect(() => {
    load(0);
  }, [load]);

  const facets: [string, TextKey][] = [
    ["domain", "f_domain"],
    ["technology", "f_technology"],
    ["company", "f_company"],
  ];
  return (
    <div className="flex flex-col gap-4">
      <section className="surface flex flex-col gap-3 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {facets.map(([key, label]) => (
            <label key={key} className="flex flex-col gap-1 text-caption text-muted-foreground">
              {t(label)}
              <select className={field} value={filters[key] ?? ""} onChange={(event) => setFilters((current) => ({ ...current, [key]: event.target.value }))}>
                <option value="">{t("iv_any")}</option>
                {(library?.facets[key as "domain"] ?? []).map((facet) => (
                  <option key={facet.value} value={facet.value}>
                    {facet.label} ({facet.count})
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        {dated && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Segmented value={window} onChange={setWindow} label={t("pp_window")} options={WINDOWS.map((value) => ({ value, label: t(`pp_window_${value}` as TextKey) }))} />
              <Segmented value={order} onChange={setOrder} label={t("pp_order")} options={[{ value: "weighted", label: t("pp_order_weighted") }, { value: "count", label: t("pp_order_count") }]} />
            </div>
            {order === "weighted" && (
              <label className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
                {t("pp_half_life")}
                <select className="h-8 rounded-[10px] bg-fill px-2 text-footnote text-foreground outline-none" value={halfLife} onChange={(event) => setHalfLife(Number(event.target.value))}>
                  {HALF_LIVES.map((days) => (
                    <option key={days} value={days}>
                      {t(`pp_half_${days}` as TextKey)}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </>
        )}
      </section>

      {error && <p className="text-footnote text-destructive">{error}</p>}
      {top && (
        <>
          <p className="text-footnote text-muted-foreground">
            {t("pp_total", { n: top.total })}
            {top.dated === 0
              ? ` · ${t("pp_no_dates")}`
              : `${order === "weighted" ? ` · ${t("pp_explain", { d: top.half_life, u: top.unknown_weight })}` : ""}${top.undated > 0 && window === "all" ? ` · ${t("pp_undated", { n: top.undated })}` : ""}`}
          </p>
          {rows.length === 0 ? (
            <p className="surface p-5 text-subhead text-muted-foreground">{t("pp_empty")}</p>
          ) : (
            <ol className="flex flex-col gap-1.5">
              {rows.map((q) => (
                <Line
                  key={q.id}
                  card={q}
                  rank={q.rank}
                  meta={[t("pp_asked", { n: q.count }), q.companies_n ? t("pp_companies", { n: q.companies_n }) : "", q.last_year ? t("pp_last", { y: q.last_year }) : "", order === "weighted" && top.dated > 0 ? t("pp_score", { s: q.score.toFixed(1) }) : ""]
                    .filter(Boolean)
                    .join(" · ")}
                />
              ))}
            </ol>
          )}
          {rows.length < top.total && (
            <div>
              <Button variant="outline" size="sm" disabled={busy} onClick={() => load(rows.length)}>
                {busy ? <Loader2 className="animate-spin" /> : null}
                {t("more_questions")}
              </Button>
            </div>
          )}
          <Actions cards={rows.slice(0, 30)} direction={t("pp_tab_top")} onPractice={onPractice} />
        </>
      )}
      {!top && !error && <p className="text-footnote text-muted-foreground">{t("loading")}</p>}
    </div>
  );
}

function CompaniesTab() {
  const { t } = useI18n();
  const [companies, setCompanies] = useState<CompanyRow[] | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    prepare.companies().then((result) => setCompanies(result.companies)).catch((cause) => setError(message(cause, t("unreachable"))));
  }, [t]);
  if (error) return <p className="text-footnote text-destructive">{error}</p>;
  if (!companies) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  const shown = companies.filter((c) => c.name.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <div className="flex flex-col gap-4">
      <input type="search" className={field} value={search} placeholder={t("pp_company_search")} aria-label={t("pp_company_search")} onChange={(event) => setSearch(event.target.value)} />
      {shown.length === 0 && <p className="surface p-5 text-subhead text-muted-foreground">{t("pp_company_empty")}</p>}
      <ul className="grid gap-2 sm:grid-cols-2">
        {shown.map((c) => (
          <li key={c.id}>
            <a href={href("prepare", ["company", c.id])} className="surface flex h-full flex-col gap-1.5 p-4 transition-colors hover:bg-fill">
              <span className="flex items-center gap-2 text-callout font-semibold">
                <Building2 className="size-4 text-primary" />
                {c.name}
              </span>
              <span className="text-footnote text-muted-foreground tabular-nums">
                {t("pp_company_line", { q: c.questions, o: c.occurrences })}
                {c.years.length > 0 && ` · ${c.years.length > 1 ? `${c.years[c.years.length - 1]}–${c.years[0]}` : c.years[0]}`}
              </span>
              {c.domains.length > 0 && (
                <span className="flex flex-wrap gap-1.5">
                  {c.domains.map((d) => (
                    <span key={d.id} className="rounded-full bg-fill px-2 py-0.5 text-caption">
                      {d.label} {d.count}
                    </span>
                  ))}
                </span>
              )}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CompanyPage({ id, onPractice }: { id: string; onPractice: (ids: string[]) => void }) {
  const { t } = useI18n();
  const [company, setCompany] = useState<Company | null>(null);
  const [round, setRound] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setCompany(null);
    prepare.company(id).then(setCompany).catch((cause) => setError(message(cause, t("unreachable"))));
  }, [id, t]);
  if (error) return <p className="text-footnote text-destructive">{error}</p>;
  if (!company) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  const rounds = Object.keys(company.summary?.rounds ?? {}).sort();
  const shown = round ? company.questions.filter((q) => q.rounds.includes(round)) : company.questions;
  const roundName = (value: string) => t(`round_${value}` as TextKey) === `round_${value}` ? value : t(`round_${value}` as TextKey);
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-title-2 font-bold">{company.name}</h2>
        {company.summary && (
          <p className="mt-1 text-footnote text-muted-foreground tabular-nums">
            {t("pp_company_line", { q: company.summary.questions, o: company.summary.occurrences })}
            {company.summary.years.length > 0 && ` · ${company.summary.years.join("、")}`}
          </p>
        )}
      </header>
      {rounds.length > 0 && (
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={t("pp_round")}>
          {["", ...rounds].map((value) => (
            <button
              key={value || "all"}
              type="button"
              role="radio"
              aria-checked={round === value}
              onClick={() => setRound(value)}
              className={cn("rounded-full border px-3 py-1.5 text-footnote transition-colors", round === value ? "border-transparent bg-foreground text-background" : "border-border bg-card text-muted-foreground")}
            >
              {value ? `${roundName(value)} ${company.summary?.rounds[value] ?? ""}` : t("view_all")}
            </button>
          ))}
        </div>
      )}
      <ol className="flex flex-col gap-1.5">
        {shown.map((q) => (
          <Line
            key={q.id}
            card={q}
            meta={[t("pp_asked", { n: q.count }), q.rounds.map(roundName).join("、"), q.years_here.join("、")].filter(Boolean).join(" · ")}
          />
        ))}
      </ol>
      <Actions cards={shown} direction={company.name} onPractice={onPractice} />
    </div>
  );
}

const date = (value: string, lang: string) => new Date(value).toLocaleDateString(lang, { month: "short", day: "numeric" });

function ListsTab() {
  const { t, lang } = useI18n();
  const [lists, setLists] = useState<ListRow[] | null>(null);
  const [canSave, setCanSave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    prepare.lists().then((result) => (setLists(result.lists), setCanSave(result.can_save))).catch((cause) => setError(message(cause, t("unreachable"))));
  }, [t]);
  if (error) return <p className="surface p-5 text-subhead text-muted-foreground">{error}</p>;
  if (!lists) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  return (
    <div className="flex flex-col gap-4">
      {canSave && (
        <Button variant="tinted" size="sm" className="self-start" asChild>
          <a href={href("interview", [], { tab: "jd" })}>
            <Target />
            {t("pp_new_list")}
          </a>
        </Button>
      )}
      {lists.length === 0 ? (
        <p className="surface p-5 text-subhead text-muted-foreground">{t(canSave ? "pp_lists_empty" : "pp_lists_empty_readonly")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {lists.map((list) => (
            <li key={list.id}>
              <a href={href("prepare", ["list", list.id])} className="surface flex items-center justify-between gap-3 p-4 transition-colors hover:bg-fill">
                <span className="min-w-0">
                  <span className="block truncate text-callout font-semibold">{list.name}</span>
                  <span className="text-footnote text-muted-foreground tabular-nums">
                    {date(list.created_at, lang)} · {t("pp_list_line", { n: list.questions })}
                    {list.requirements > 0 && ` · ${t("pp_list_cover", { c: list.covered, r: list.requirements })}`}
                  </span>
                </span>
                {list.changed > 0 && <span className="shrink-0 text-caption font-medium text-warning">{t("pp_list_changed", { n: list.changed })}</span>}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const PRIORITY: Record<string, TextKey> = { must: "pp_priority_must", nice: "pp_priority_nice" };

function ListPage({ id, onPractice }: { id: string; onPractice: (ids: string[]) => void }) {
  const { t, lang } = useI18n();
  const [list, setList] = useState<ListDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setList(null);
    prepare.list(id).then(setList).catch((cause) => setError(message(cause, t("unreachable"))));
  }, [id, t]);
  if (error) return <p className="text-footnote text-destructive">{error}</p>;
  if (!list) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  const s = list.summary;
  return (
    <div className="flex flex-col gap-5">
      <header>
        <h2 className="text-title-2 font-bold">{list.name}</h2>
        <p className="mt-1 text-footnote text-muted-foreground tabular-nums">
          {date(list.created_at, lang)} · {t("pp_list_line", { n: s.questions })}
        </p>
        <p className="mt-2 flex flex-wrap gap-x-3 text-footnote tabular-nums">
          <span>{t("view_unseen")} {s.unseen}</span>
          <span className="text-warning">{t("view_weak")} {s.weak}</span>
          <span className="text-success">{t("pp_state_familiar")} {s.familiar}</span>
          <span>{t("view_due")} {s.due}</span>
        </p>
      </header>
      {list.changed.length > 0 && (
        <p className="flex gap-2 rounded-xl bg-orange/10 px-3 py-2.5 text-footnote">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          {t("pp_list_recheck", { n: list.changed.length })}
        </p>
      )}
      {list.requirements.length > 0 && (
        <section>
          <h3 className="mb-1 text-callout font-semibold">{t("pp_requirements")}</h3>
          <p className="mb-2 text-caption text-muted-foreground">{t("pp_requirements_note", { c: list.coverage.directly_covered, r: list.coverage.requirements })}</p>
          <ul className="flex flex-col gap-2">
            {list.requirements.map((r) => {
              const direct = r.matches.some((m) => m.coverage === "direct" && !m.needs_recheck);
              return (
                <li key={r.id} className="surface p-3.5">
                  <p className="flex flex-wrap items-center gap-x-2 text-subhead">
                    <span>“{r.quote}”</span>
                    {PRIORITY[r.priority] && <span className="rounded-full bg-accent px-2 py-0.5 text-caption font-medium text-accent-foreground">{t(PRIORITY[r.priority])}</span>}
                    <span className={cn("text-caption font-medium", direct ? "text-success" : r.matches.length ? "text-warning" : "text-muted-foreground")}>
                      {t(direct ? "pp_cover_direct" : r.matches.length ? "pp_cover_partial" : "pp_cover_none")}
                    </span>
                  </p>
                  {r.matches.map((m) => (
                    <p key={m.question_id} className="mt-1 text-footnote text-muted-foreground">
                      <a className="text-foreground hover:underline" href={href("bank", [], { open: m.question_id })}>
                        {m.title}
                      </a>
                      {` · ${m.reason}`}
                      {m.needs_recheck && <span className="text-warning">{` · ${t("pp_needs_recheck")}`}</span>}
                    </p>
                  ))}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      <section className="flex flex-col gap-3">
        <h3 className="text-callout font-semibold">{t("pp_list_questions")}</h3>
        <ol className="flex flex-col gap-1.5">
          {list.questions.map((q) => (
            <Line key={q.id} card={q} />
          ))}
        </ol>
        <Actions cards={list.questions} direction={list.name} onPractice={onPractice} />
      </section>
    </div>
  );
}

export function PreparePage({ route }: { route: Route }) {
  const { t } = useI18n();
  const { library, refresh } = useBank();
  const [practice, setPractice] = useState<PracticeStart | null>(null);
  const [stamp, setStamp] = useState(0);
  const [first, second] = route.rest;
  const tab: Tab = first === "companies" || first === "company" ? "companies" : first === "lists" || first === "list" ? "lists" : "top";
  const detail = (first === "company" || first === "list") && second ? { kind: first, id: second } : null;

  let body;
  if (detail?.kind === "company") body = <CompanyPage id={detail.id} onPractice={(ids) => setPractice({ kind: "ids", ids })} />;
  else if (detail?.kind === "list") body = <ListPage id={detail.id} onPractice={(ids) => setPractice({ kind: "ids", ids })} />;
  else if (tab === "companies") body = <CompaniesTab />;
  else if (tab === "lists") body = <ListsTab />;
  else body = <TopTab onPractice={(ids) => setPractice({ kind: "ids", ids })} />;

  return (
    <div className="mx-auto max-w-[760px] px-4 pt-6 pb-28 sm:px-6 md:pt-8 md:pb-16">
      {detail ? (
        <a href={href("prepare", [tab])} className="mb-4 inline-flex items-center gap-1 text-footnote text-primary hover:underline">
          <ArrowLeft className="size-3.5" />
          {t(detail.kind === "company" ? "pp_back_companies" : "pp_back_lists")}
        </a>
      ) : (
        <>
          <p className="flex items-center gap-1.5 text-caption font-semibold tracking-wide text-primary">
            <Target className="size-3.5" />
            {t("board_prepare")}
          </p>
          <h1 className="mt-0.5 text-title-1 font-bold">{t("pp_title")}</h1>
          <p className="mt-1.5 mb-5 text-footnote leading-relaxed text-muted-foreground">{t("pp_lead")}</p>
          <div className="mb-4">
            <Segmented
              value={tab}
              onChange={(value) => navigate("prepare", value === "top" ? [] : [value])}
              label={t("board_prepare")}
              options={TABS.map((value) => ({ value, label: t(`pp_tab_${value}` as TextKey) }))}
            />
          </div>
        </>
      )}
      <div key={stamp}>{body}</div>
      <Practice
        start={practice}
        params={() => new URLSearchParams()}
        canRecord={Boolean(library?.can_record)}
        onClose={(recorded) => {
          setPractice(null);
          if (recorded) {
            refresh(true);
            setStamp((value) => value + 1);
          }
        }}
      />
    </div>
  );
}
