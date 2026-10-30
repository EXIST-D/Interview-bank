import { AlertTriangle, Loader2, MessageSquareQuote, Play, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, questionDetail, type QuestionDetail } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useI18n, type TextKey } from "@/lib/i18n";
import { interview, type Overview, type Plan, type Session, type SessionRow } from "@/lib/interview";
import { prepare } from "@/lib/prepare";
import { href, navigate, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { UsageLine } from "./import";
import { SessionView } from "./interview-session";

const VIEWS = ["all", "due", "weak", "unseen"] as const;
const COUNTS = ["5", "10", "20"] as const;
const FILTERS = [
  ["group", "iv_f_group"],
  ["domain", "f_domain"],
  ["technology", "f_technology"],
  ["company", "f_company"],
] as const;
const field = "h-9 w-full rounded-[10px] bg-fill px-3 text-subhead outline-none focus:ring-2 focus:ring-ring/30";

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;
}

function begin(session: Session) {
  navigate("interview", [session.id]);
}

function Direction({ onError }: { onError: (text: string | null) => void }) {
  const { t } = useI18n();
  const { library } = useBank();
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [view, setView] = useState<(typeof VIEWS)[number]>("all");
  const [count, setCount] = useState<(typeof COUNTS)[number]>("10");
  const [random, setRandom] = useState(false);
  const [total, setTotal] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const chosen = { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), ...(view === "all" ? {} : { view }) };
  const query = new URLSearchParams(chosen).toString();
  useEffect(() => {
    let live = true;
    api<{ total: number }>("/api/practice?" + new URLSearchParams({ ...chosen, limit: "1" }))
      .then((result) => live && setTotal(result.total))
      .catch(() => live && setTotal(null));
    return () => {
      live = false;
    };
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setBusy(true);
    onError(null);
    try {
      const labels = FILTERS.map(([key]) => library?.facets[key as "group"]?.find((facet) => facet.value === filters[key])?.label).filter(Boolean);
      begin(await interview.start({ filters: chosen, limit: Number(count), order: random ? "random" : "frequency", direction: labels.join(" · ") || t("iv_whole_bank") }));
    } catch (cause) {
      onError(message(cause, t("failed")));
      setBusy(false);
    }
  };

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {FILTERS.map(([key, label]) => (
          <label key={key} className="flex flex-col gap-1 text-caption text-muted-foreground">
            {t(label as TextKey)}
            <select className={field} value={filters[key] ?? ""} onChange={(event) => setFilters((current) => ({ ...current, [key]: event.target.value }))}>
              <option value="">{t("iv_any")}</option>
              {(library?.facets[key as "group"] ?? []).map((facet) => (
                <option key={facet.value} value={facet.value}>
                  {facet.label} ({facet.count})
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <Segmented value={view} onChange={setView} label={t("iv_scope")} options={VIEWS.map((value) => ({ value, label: t(`view_${value}` as TextKey) }))} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="w-40">
          <Segmented value={count} onChange={setCount} label={t("iv_count")} options={COUNTS.map((value) => ({ value, label: value }))} />
        </div>
        <label className="flex items-center gap-2 text-footnote">
          <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={random} onChange={(event) => setRandom(event.target.checked)} />
          {t("iv_random")}
        </label>
        <span className="ml-auto text-caption text-muted-foreground tabular-nums">{total === null ? "" : t("iv_matching", { n: total })}</span>
      </div>
      <p className="text-caption text-muted-foreground">{t("iv_reference_first")}</p>
      <div>
        <Button disabled={busy || total === 0} onClick={start}>
          {busy ? <Loader2 className="animate-spin" /> : <Play />}
          {t("iv_start")}
        </Button>
      </div>
    </section>
  );
}

function JobDescription({ onError }: { onError: (text: string | null) => void }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [count, setCount] = useState<(typeof COUNTS)[number]>("10");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [kept, setKept] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const running = plan?.status === "running";

  useEffect(() => {
    if (!plan || plan.status !== "running") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await interview.planResult(plan.id);
        setPlan(next);
        if (next.status === "done") setKept(new Set(next.picks.map((pick) => pick.id)));
      } catch (cause) {
        onError(message(cause, t("failed")));
        setPlan(null);
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [plan, onError, t]);

  const pick = async () => {
    setBusy(true);
    onError(null);
    setPlan(null);
    try {
      setPlan(await interview.plan(text, Number(count)));
    } catch (cause) {
      onError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };

  const [name, setName] = useState("");
  const save = async () => {
    if (!plan) return;
    setBusy(true);
    onError(null);
    try {
      const saved = await prepare.save(plan.id, plan.picks.filter((item) => kept.has(item.id)).map((item) => item.id), name);
      navigate("prepare", ["list", saved.id]);
    } catch (cause) {
      onError(message(cause, t("failed")));
      setBusy(false);
    }
  };

  const start = async () => {
    if (!plan) return;
    setBusy(true);
    onError(null);
    try {
      const picks = plan.picks.filter((item) => kept.has(item.id));
      begin(
        await interview.start({
          question_ids: picks.map((item) => item.id),
          direction: t("iv_jd_direction"),
          jd: text.trim().replace(/\s+/g, " ").slice(0, 80),
          reasons: Object.fromEntries(picks.map((item) => [item.id, { quote: item.quote, reason: item.reason }])),
        }),
      );
    } catch (cause) {
      onError(message(cause, t("failed")));
      setBusy(false);
    }
  };

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <label className="flex flex-col gap-1.5 text-caption text-muted-foreground">
        {t("iv_jd_label")}
        <textarea
          rows={7}
          maxLength={6000}
          value={text}
          disabled={running}
          placeholder={t("iv_jd_placeholder")}
          onChange={(event) => setText(event.target.value)}
          className="w-full resize-y rounded-[10px] bg-fill px-3 py-2.5 text-subhead leading-relaxed text-foreground outline-none focus:ring-2 focus:ring-ring/30"
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-40">
          <Segmented value={count} onChange={setCount} label={t("iv_count")} options={COUNTS.map((value) => ({ value, label: value }))} />
        </div>
        <Button variant="tinted" disabled={busy || running || text.trim().length < 20} onClick={pick}>
          {running ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {t(running ? "iv_jd_picking" : "iv_jd_pick")}
        </Button>
      </div>
      <p className="text-caption text-muted-foreground">{t("iv_jd_note")}</p>
      {plan?.status === "failed" && <p className="text-footnote text-destructive">{plan.error}</p>}
      {plan?.status === "done" && (
        <div className="flex flex-col gap-3">
          {plan.picks.length === 0 ? (
            <p className="text-subhead text-muted-foreground">{t("iv_jd_none")}</p>
          ) : (
            <>
              <p className="text-footnote font-medium">{t("iv_jd_result", { n: plan.picks.length, c: plan.considered })}</p>
              <ul className="flex flex-col gap-2">
                {plan.picks.map((item) => (
                  <li key={item.id} className={cn("flex gap-2.5 rounded-xl bg-fill px-3 py-2.5", !kept.has(item.id) && "opacity-50")}>
                    <input
                      type="checkbox"
                      className="mt-1 size-4 shrink-0 accent-[var(--primary)]"
                      aria-label={item.canonical}
                      checked={kept.has(item.id)}
                      onChange={(event) =>
                        setKept((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(item.id);
                          else next.delete(item.id);
                          return next;
                        })
                      }
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-subhead leading-relaxed">{item.canonical}</p>
                      <p className="mt-0.5 text-caption text-muted-foreground">
                        {item.reason}
                        {item.quote && ` · ${t("iv_jd_quote", { q: item.quote })}`}
                        {!item.answered && ` · ${t("iv_jd_nref")}`}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {plan.uncovered.length > 0 && <p className="text-footnote text-muted-foreground">{t("iv_jd_uncovered", { r: plan.uncovered.join("；") })}</p>}
          {plan.picks.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button disabled={busy || kept.size === 0} onClick={start}>
                  {busy ? <Loader2 className="animate-spin" /> : <Play />}
                  {t("iv_start")}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  className={cn(field, "max-w-64")}
                  maxLength={120}
                  value={name}
                  placeholder={t("pp_list_name")}
                  aria-label={t("pp_list_name")}
                  onChange={(event) => setName(event.target.value)}
                />
                <Button variant="tinted" disabled={busy || kept.size === 0} onClick={save}>
                  {t("pp_save_list")}
                </Button>
              </div>
              <p className="text-caption text-muted-foreground">{t("pp_save_note")}</p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ReviewOne({ id, onError }: { id: string; onError: (text: string | null) => void }) {
  const { t } = useI18n();
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    questionDetail(id).then(setQuestion).catch((cause) => onError(message(cause, t("failed"))));
  }, [id, onError, t]);
  const start = async () => {
    setBusy(true);
    onError(null);
    try {
      begin(await interview.start({ question_ids: [id], mode: "review" }));
    } catch (cause) {
      onError(message(cause, t("failed")));
      setBusy(false);
    }
  };
  if (!question) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  const reference = question.answer && (question.answer_status === "source_backed" || question.answer_status === "reviewed");
  return (
    <section className="surface flex flex-col gap-3 p-5">
      <p className="text-caption font-semibold tracking-wide text-primary">{t("iv_review_title")}</p>
      <h2 className="text-title-3 font-semibold">{question.canonical}</h2>
      <p className="text-footnote text-muted-foreground">{t("iv_review_lead")}</p>
      {!reference && (
        <p className="flex gap-2 rounded-xl bg-orange/10 px-3 py-2.5 text-footnote">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          {t("iv_review_noref")}
        </p>
      )}
      <div>
        <Button disabled={busy} onClick={start}>
          {busy ? <Loader2 className="animate-spin" /> : <Play />}
          {t("iv_review_start")}
        </Button>
      </div>
    </section>
  );
}

function Recent({ rows }: { rows: SessionRow[] }) {
  const { t, lang } = useI18n();
  if (!rows.length) return null;
  const date = (value: string) => new Date(value).toLocaleString(lang, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return (
    <section className="mt-8">
      <h2 className="mb-2 text-callout font-semibold">{t("iv_recent")}</h2>
      <ul className="flex flex-col gap-1.5">
        {rows.map((row) => (
          <li key={row.id}>
            <a href={href("interview", [row.id])} className="flex items-center justify-between gap-3 rounded-xl bg-fill px-3 py-2.5 text-footnote transition-colors hover:bg-black/[0.08] dark:hover:bg-white/[0.12]">
              <span className="min-w-0">
                <span className="block truncate text-subhead font-medium">{row.name}</span>
                <span className="text-muted-foreground">
                  {date(row.created_at)} · {t(row.mode === "review" ? "iv_mode_review" : "iv_mode_mock")} · {t("iv_row", { a: row.answered, n: row.total, g: row.graded })}
                </span>
              </span>
              <span className={cn("shrink-0 font-medium", row.status === "running" ? "text-primary" : "text-muted-foreground")}>
                {row.status === "running" ? t("iv_continue") : t(row.status === "completed" ? "iv_status_completed" : "iv_status_cancelled")}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function InterviewPage({ route }: { route: Route }) {
  const { t } = useI18n();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"direction" | "jd">(route.params.get("tab") === "jd" ? "jd" : "direction");
  const sessionId = route.rest[0];
  const asked = route.params.get("question");

  const load = useCallback(async () => {
    try {
      setOverview(await interview.overview());
    } catch (cause) {
      setError(message(cause, t("unreachable")));
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load, sessionId]);

  let body;
  if (!overview && error) body = <p className="text-footnote text-destructive">{error}</p>;
  else if (!overview) body = <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  else if (!overview.enabled) body = <p className="surface p-5 text-subhead text-muted-foreground">{t("iv_disabled")}</p>;
  else if (sessionId) body = <SessionView key={sessionId} id={sessionId} />;
  else
    body = (
      <>
        {asked && <ReviewOne id={asked} onError={setError} />}
        <Segmented
          value={tab}
          onChange={setTab}
          label={t("iv_title")}
          options={[
            { value: "direction", label: t("iv_tab_direction") },
            { value: "jd", label: t("iv_tab_jd") },
          ]}
        />
        {tab === "direction" ? <Direction onError={setError} /> : <JobDescription onError={setError} />}
        {error && (
          <p role="alert" className="text-footnote text-destructive">
            {error}
          </p>
        )}
        <Recent rows={overview.sessions} />
      </>
    );

  return (
    <div className="mx-auto max-w-[760px] px-4 pt-6 pb-28 sm:px-6 md:pt-8 md:pb-16">
      {!sessionId && (
        <>
          <p className="flex items-center gap-1.5 text-caption font-semibold tracking-wide text-primary">
            <MessageSquareQuote className="size-3.5" />
            {t("board_interview")}
          </p>
          <h1 className="mt-0.5 text-title-1 font-bold">{t("iv_title")}</h1>
          <p className="mt-1.5 mb-5 text-footnote leading-relaxed text-muted-foreground">
            {t("iv_lead")}
            {overview?.enabled && ` ${t("iv_model", { m: overview.model, n: overview.left_today })}`}
          </p>
          {overview?.enabled && overview.usage.today && (
            <p className="-mt-3 mb-5 text-caption text-tertiary-foreground">
              {t("usage_today")}
              <UsageLine usage={overview.usage.today} priced={overview.usage.priced} />
            </p>
          )}
        </>
      )}
      <div className="flex flex-col gap-4">{body}</div>
    </div>
  );
}
