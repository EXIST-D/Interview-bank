import { AlertTriangle, ArrowRight, Check, CircleDashed, CornerDownRight, Loader2, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, questionDetail, type QuestionDetail } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useI18n, type TextKey } from "@/lib/i18n";
import { interview, type CheckState, type Feedback, type Response, type Session } from "@/lib/interview";
import { href, navigate } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AnswerBody } from "@/reader/question-view";
import "@/reader/reader.css";

const RATINGS = ["again", "hard", "good", "easy"] as const;
const draftKey = (session: string, question: string, followUp: boolean) => `ibank-iv-draft:${session}:${question}:${followUp ? "f" : "m"}`;

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;
}

function readDraft(key: string) {
  try {
    return sessionStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(key: string, value: string) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    /* the draft lasts for this page only */
  }
}

const CHECK_STYLE: Record<CheckState, string> = { covered: "text-success", partial: "text-warning", missed: "text-destructive" };

function CheckIcon({ status }: { status: CheckState }) {
  const Icon = status === "covered" ? Check : status === "partial" ? CircleDashed : X;
  return <Icon className={cn("mt-0.5 size-4 shrink-0", CHECK_STYLE[status])} aria-hidden />;
}

/** One answer's feedback next to the reference it was checked against (loaded only after the answer is in). */
function FeedbackCard({ response, canRate, compact = false }: { response: Response; canRate: boolean; compact?: boolean }) {
  const { t } = useI18n();
  const feedback = response.feedback as Feedback;
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [rated, setRated] = useState<string | null>(null);
  const [rating, setRating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(crypto.randomUUID());

  useEffect(() => {
    let live = true;
    questionDetail(response.question_id).then((q) => live && setDetail(q)).catch(() => {});
    return () => {
      live = false;
    };
  }, [response.question_id]);

  // Key-point numbers belong to the reference answer the feedback was written against.
  const sameReference = Boolean(detail?.answer && detail.answer.id === feedback.reference_answer_id);
  const points = sameReference ? (detail?.answer?.key_points ?? []) : [];

  const rate = async (value: (typeof RATINGS)[number]) => {
    if (!detail) return;
    setRating(true);
    setError(null);
    try {
      const fresh = await questionDetail(response.question_id, true);
      await api("/api/practice", {
        question_id: fresh.id,
        revision: fresh.revision,
        rating: value,
        request_id: request.current,
        note: "",
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      setRated(value);
    } catch (cause) {
      setError(t("save_failed", { e: message(cause, t("failed")) }));
    } finally {
      setRating(false);
    }
  };

  return (
    <section className="flex flex-col gap-4" aria-label={t("iv_feedback")}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <h3 className="text-callout font-semibold">{t("iv_feedback")}</h3>
        {feedback.generated_by && <span className="text-caption text-muted-foreground">{t("iv_by", { m: feedback.generated_by.model })}</span>}
      </div>
      {feedback.limited_basis && (
        <p className="flex gap-2 rounded-xl bg-orange/10 px-3 py-2.5 text-footnote">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          {t("iv_limited")}
        </p>
      )}
      {feedback.generated_by?.checks.map((check) => (
        <p key={check} className="text-caption text-muted-foreground">
          {check}
        </p>
      ))}

      {feedback.key_point_checks.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-footnote font-semibold text-muted-foreground">{t("iv_points")}</h4>
          <ul className="flex flex-col gap-1.5">
            {feedback.key_point_checks.map((check) => (
              <li key={check.index} className="flex gap-2 rounded-xl bg-fill px-3 py-2 text-footnote">
                <CheckIcon status={check.status} />
                <div className="min-w-0">
                  <p className="leading-relaxed">
                    <span className={cn("mr-1.5 font-medium", CHECK_STYLE[check.status])}>{t(`iv_check_${check.status}` as TextKey)}</span>
                    {points[check.index] ?? t("iv_point_n", { n: check.index + 1 })}
                  </p>
                  {check.note && <p className="mt-0.5 text-muted-foreground">{check.note}</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {feedback.observations.map((item, index) => (
          <li key={index} className="rounded-xl border border-border px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-2 text-caption">
              <span className="rounded-full bg-accent px-2 py-0.5 font-medium text-accent-foreground">{t(`iv_dim_${item.dimension}` as TextKey)}</span>
              {item.verdict && (
                <span className={cn("font-medium", item.verdict === "met" ? "text-success" : item.verdict === "gap" ? "text-warning" : "text-destructive")}>
                  {t(`iv_verdict_${item.verdict}` as TextKey)}
                </span>
              )}
            </div>
            {item.quote && (
              <blockquote className="mt-1.5 border-l-2 border-primary/40 pl-2.5 text-footnote text-muted-foreground">
                <CornerDownRight className="mr-1 inline size-3" />
                {item.quote}
              </blockquote>
            )}
            <p className="mt-1.5 text-subhead leading-relaxed">{item.note}</p>
          </li>
        ))}
      </ul>

      {feedback.review_topics.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-footnote font-semibold text-muted-foreground">{t("iv_review_topics")}</h4>
          <div className="flex flex-wrap gap-1.5">
            {feedback.review_topics.map((topic) => (
              <span key={topic} className="rounded-full bg-fill px-2.5 py-1 text-footnote">
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {!compact && (
        <div className="ib-reading">
          {detail?.answer ? <AnswerBody status={detail.answer_status} answer={detail.answer} /> : <p className="no-answer">{detail ? t("no_answer") : t("loading")}</p>}
        </div>
      )}

      {!compact && canRate && detail && (
        <div>
          <p className="mb-1.5 text-footnote text-muted-foreground">{t("iv_rate")}</p>
          {rated ? (
            <p className="text-footnote text-success">{t("iv_rated", { r: t(`rating_${rated}` as TextKey) })}</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {RATINGS.map((value) => (
                <Button key={value} size="sm" variant={value === "good" || value === "easy" ? "tinted" : "outline"} disabled={rating} onClick={() => rate(value)}>
                  {t(`rating_${value}` as TextKey)}
                </Button>
              ))}
            </div>
          )}
          {error && <p className="mt-1.5 text-footnote text-destructive">{error}</p>}
        </div>
      )}
    </section>
  );
}

function Prompt({ session, label }: { session: Session; label: string }) {
  const { t } = useI18n();
  const current = session.current;
  const index = Math.min(session.position + (current.status === "question" && !current.follow_up ? 1 : 0), session.total);
  const why = current.question_id ? session.meta.reasons?.[current.question_id] : undefined;
  return (
    <header>
      <p className="flex flex-wrap items-center gap-x-2 text-caption font-semibold tracking-wide text-primary tabular-nums">
        {t("iv_progress", { i: Math.max(1, index), n: session.total })}
        {current.follow_up && <span className="rounded-full bg-accent px-2 py-0.5 text-accent-foreground">{t("iv_followup_tag")}</span>}
      </p>
      <h2 className="reading-title mt-1.5 outline-none">{label}</h2>
      {why && (
        <p className="mt-1 text-caption text-muted-foreground">
          {t("iv_why", { r: why.reason ?? "" })}
          {why.quote ? ` ${t("iv_jd_quote", { q: why.quote })}` : ""}
        </p>
      )}
    </header>
  );
}

function AnswerForm({ session, onChange }: { session: Session; onChange: (next: Session) => void }) {
  const { t } = useI18n();
  const current = session.current;
  const key = draftKey(session.id, current.question_id ?? "", Boolean(current.follow_up));
  const [text, setText] = useState(() => readDraft(key));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<string | null>(null);
  const max = 8000;

  const submit = async () => {
    if (busy || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      // A retry sends the same request ID, so an answer saved without a reply is not recorded twice.
      request.current ??= crypto.randomUUID();
      const next = await interview.answer(session.id, current.question_id!, request.current, text);
      writeDraft(key, "");
      request.current = null;
      onChange(next);
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <Prompt session={session} label={current.prompt ?? ""} />
      {current.changed_since_start && <p className="warning">{t("iv_changed")}</p>}
      <label htmlFor="iv-answer" className="hint block">
        {t("iv_your_answer")}
      </label>
      <textarea
        id="iv-answer"
        className="note"
        rows={9}
        maxLength={max}
        value={text}
        disabled={busy}
        placeholder={t("iv_answer_placeholder")}
        onChange={(event) => {
          setText(event.target.value);
          writeDraft(key, event.target.value);
          request.current = null;
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submit();
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-caption text-muted-foreground">{t("iv_submit_hint")}</p>
        <span className="text-caption text-tertiary-foreground tabular-nums">{text.length} / {max}</span>
      </div>
      {error && (
        <p role="alert" className="warning">
          {error}
        </p>
      )}
      <div>
        <Button disabled={busy || !text.trim()} onClick={submit}>
          {busy ? <Loader2 className="animate-spin" /> : <ArrowRight />}
          {t("iv_submit")}
        </Button>
      </div>
    </div>
  );
}

function Grading({ session, response, onChange }: { session: Session; response: Response | undefined; onChange: (next: Session) => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const failed = session.grading?.state === "failed";
  const idle = !session.grading;
  const retry = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await interview.regrade(session.id));
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      <Prompt session={session} label={response?.prompt ?? ""} />
      <div className="rounded-xl bg-fill px-3 py-2.5">
        <p className="text-caption text-muted-foreground">{t("iv_your_answer")}</p>
        <p className="mt-1 text-subhead leading-relaxed whitespace-pre-wrap">{response?.text}</p>
      </div>
      {failed || idle ? (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="warning">
            {t("iv_grade_failed", { e: session.grading?.error ?? t("iv_interrupted") })}
          </p>
          <Button variant="outline" size="sm" disabled={busy} onClick={retry}>
            <RotateCcw />
            {t("iv_regrade")}
          </Button>
        </div>
      ) : (
        <p className="flex items-center gap-2 text-callout font-medium">
          <Loader2 className="size-4 animate-spin text-primary" />
          {t("iv_grading")}
        </p>
      )}
      {!failed && !idle && <p className="text-footnote text-muted-foreground">{t("iv_grading_hint")}</p>}
      {error && <p className="text-footnote text-destructive">{error}</p>}
    </div>
  );
}

function Report({ session }: { session: Session }) {
  const { t, lang } = useI18n();
  const { library } = useBank();
  const summary = session.summary;
  const date = new Date(session.created_at).toLocaleString(lang, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex flex-col gap-5">
      <header>
        <p className="text-caption font-semibold tracking-wide text-primary">{t("iv_report")}</p>
        <h2 className="mt-0.5 text-title-2 font-bold">{session.name}</h2>
        <p className="mt-1 text-caption text-muted-foreground">
          {date} · {t(session.status === "completed" ? "iv_status_completed" : "iv_status_cancelled")}
        </p>
      </header>
      {summary && summary.answered > 0 ? (
        <section className="surface flex flex-col gap-2 p-4 text-subhead">
          <p>{t("iv_sum_answered", { a: summary.answered, g: summary.graded })}</p>
          {summary.key_points.covered + summary.key_points.partial + summary.key_points.missed > 0 && (
            <p>{t("iv_sum_points", { c: summary.key_points.covered, p: summary.key_points.partial, m: summary.key_points.missed })}</p>
          )}
          {summary.limited > 0 && <p className="text-footnote text-muted-foreground">{t("iv_sum_limited", { n: summary.limited })}</p>}
          {summary.ungraded > 0 && <p className="text-footnote text-warning">{t("iv_sum_ungraded", { n: summary.ungraded })}</p>}
          {summary.weak_topics.length > 0 && (
            <div className="mt-1">
              <p className="mb-1.5 text-footnote font-semibold text-muted-foreground">{t("iv_review_topics")}</p>
              <div className="flex flex-wrap gap-1.5">
                {summary.weak_topics.map((topic) => (
                  <span key={topic} className="rounded-full bg-fill px-2.5 py-1 text-footnote">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      ) : (
        <p className="surface p-4 text-subhead text-muted-foreground">{t("iv_no_answers")}</p>
      )}
      <ol className="flex flex-col gap-3">
        {session.responses.map((response) => (
          <li key={response.id}>
            <details className="surface p-4" open={session.responses.length === 1}>
              <summary className="cursor-pointer text-subhead font-medium">
                {response.follow_up && <span className="mr-1.5 rounded-full bg-accent px-2 py-0.5 text-caption text-accent-foreground">{t("iv_followup_tag")}</span>}
                {response.prompt}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div className="rounded-xl bg-fill px-3 py-2.5">
                  <p className="text-caption text-muted-foreground">{t("iv_your_answer")}</p>
                  <p className="mt-1 text-subhead leading-relaxed whitespace-pre-wrap">{response.text}</p>
                </div>
                {response.feedback ? (
                  <FeedbackCard response={response} canRate={Boolean(library?.can_record)} compact={session.responses.length > 1} />
                ) : (
                  <p className="text-footnote text-warning">{t("iv_not_graded")}</p>
                )}
                <a className="text-footnote text-primary hover:underline" href={href("bank", [], { open: response.question_id })}>
                  {t("iv_open_question")}
                </a>
              </div>
            </details>
          </li>
        ))}
      </ol>
      <div className="flex gap-2">
        <Button variant="tinted" asChild>
          <a href={href("interview")}>{t("iv_again")}</a>
        </Button>
      </div>
    </div>
  );
}

export function SessionView({ id }: { id: string }) {
  const { t } = useI18n();
  const { library } = useBank();
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seen, setSeen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const top = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setSession(await interview.session(id));
    } catch (cause) {
      setError(message(cause, t("unreachable")));
    }
  }, [id, t]);
  useEffect(() => {
    setSession(null);
    setError(null);
    setSeen(null);
    load();
  }, [load]);

  const grading = session?.grading?.state === "running";
  useEffect(() => {
    if (!grading) return;
    const timer = window.setInterval(load, 1500);
    return () => window.clearInterval(timer);
  }, [grading, load]);

  const latest = session?.responses[session.responses.length - 1];
  const showing = Boolean(session && session.status === "running" && latest?.feedback && seen !== latest.id);
  const feedbackId = showing ? latest?.id : null;
  useEffect(() => {
    if (feedbackId) top.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [feedbackId]);

  const act = async (step: () => Promise<Session>, after?: () => void) => {
    setBusy(true);
    setError(null);
    try {
      setSession(await step());
      after?.();
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };

  if (error && !session) return <p className="text-footnote text-destructive">{error}</p>;
  if (!session) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;

  const current = session.current;
  const finished = session.status !== "running";
  const askFollowUp = Boolean(latest?.feedback?.suggested_follow_up) && session.follow_ups_left > 0 && !current.follow_up && current.status !== "cancelled";
  const closing = current.status === "completed";
  const end = () => {
    if (!closing && !window.confirm(t("iv_end_confirm"))) return;
    act(() => interview.end(session.id));
  };

  let body;
  if (finished) body = <Report session={session} />;
  else if (showing && latest) {
    body = (
      <div className="flex flex-col gap-4">
        <div className="rounded-xl bg-fill px-3 py-2.5">
          <p className="text-caption text-muted-foreground">
            {latest.follow_up ? `${t("iv_followup_tag")} · ` : ""}
            {latest.prompt}
          </p>
          <p className="mt-1 text-subhead leading-relaxed whitespace-pre-wrap">{latest.text}</p>
        </div>
        <FeedbackCard key={latest.id} response={latest} canRate={Boolean(library?.can_record)} />
        {askFollowUp && latest.feedback?.suggested_follow_up && (
          <section className="surface flex flex-col gap-2 p-4">
            <p className="text-footnote text-muted-foreground">{t("iv_followup_why", { r: latest.feedback.suggested_follow_up.reason })}</p>
            <p className="text-subhead font-medium">{latest.feedback.suggested_follow_up.prompt}</p>
            <div>
              <Button variant="tinted" size="sm" disabled={busy} onClick={() => act(() => interview.followUp(session.id), () => setSeen(latest.id))}>
                <CornerDownRight />
                {t("iv_ask_followup")}
              </Button>
            </div>
          </section>
        )}
        <div className="glass sticky bottom-[calc(52px+env(safe-area-inset-bottom))] -mx-4 flex flex-wrap items-center justify-end gap-2 border-t border-border px-4 py-3 md:bottom-0">
          {closing ? (
            <Button disabled={busy} onClick={end}>
              {busy ? <Loader2 className="animate-spin" /> : <Check />}
              {t("iv_finish")}
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => setSeen(latest.id)}>
              <ArrowRight />
              {t("iv_next")}
            </Button>
          )}
        </div>
      </div>
    );
  } else if (current.status === "question") body = <AnswerForm key={`${current.question_id}:${session.responses.length}`} session={session} onChange={setSession} />;
  else if (current.status === "awaiting_feedback") body = <Grading session={session} response={latest} onChange={setSession} />;
  else
    body = (
      <section className="surface flex flex-col items-start gap-3 p-5">
        <p className="text-subhead">{t("iv_all_answered")}</p>
        <Button disabled={busy} onClick={end}>
          {busy ? <Loader2 className="animate-spin" /> : <Check />}
          {t("iv_view_report")}
        </Button>
      </section>
    );

  return (
    <div ref={top} className="scroll-mt-20">
      <div className="mb-4 flex items-center justify-between gap-3">
        <a href={href("interview")} onClick={(event) => (event.preventDefault(), navigate("interview"))} className="text-footnote text-primary hover:underline">
          {t("iv_back")}
        </a>
        {!finished && (
          <Button variant="ghost" size="sm" disabled={busy} onClick={end}>
            {t("iv_end")}
          </Button>
        )}
      </div>
      <div className="ib-reading">{body}</div>
      {error && (
        <p role="alert" className="mt-3 text-footnote text-destructive">
          {error}
        </p>
      )}
      {!finished && session.left_today <= 0 && <p className="mt-3 text-footnote text-warning">{t("iv_no_quota")}</p>}
    </div>
  );
}
