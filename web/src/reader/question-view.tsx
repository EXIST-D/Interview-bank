import { useState } from "react";
import { api, type Answer, type QuestionDetail } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { RichText, SafeLink } from "./markdown";

const answered = (status: string) => status === "source_backed" || status === "reviewed";

export function AnswerBody({ status, answer }: { status: string; answer: Answer }) {
  const { t } = useI18n();
  const sources = answer.sources ?? [];
  const points = answer.key_points ?? [];
  const extras = [
    ["spoken_answer", "spoken"],
    ["follow_up_questions", "follow_ups"],
    ["common_mistakes", "mistakes"],
    ["deep_dive", "deep_dive"],
  ] as const;
  return (
    <section className="answer-body">
      {status === "ai_draft" && <p className="warning">{t("draft_warning")}</p>}
      {status === "stale" && <p className="warning">{t("stale_warning")}</p>}
      <h2 className="answer-head">
        {t("answer")}
        {answered(status) && <span className="verified">{t(status === "reviewed" ? "status_reviewed" : "status_source_backed")}</span>}
      </h2>
      <RichText text={answer.short_answer} />
      {answer.code_example && (
        <details className="extra" open>
          <summary>{t("code")}</summary>
          <RichText text={"```\n" + answer.code_example + "\n```"} />
        </details>
      )}
      {points.length > 0 && (
        // Each key point with the sources that support it: the answer is checkable, not only plausible.
        <details className="extra points">
          <summary>{t("points")}</summary>
          <ol>
            {points.map((point, index) => {
              const urls = [...new Set((answer.evidence ?? []).filter((e) => e.key_point === index).flatMap((e) => e.source_urls ?? []))];
              return (
                <li key={index}>
                  {point}
                  {urls.length > 0 && (
                    <span className="refs">
                      {urls.map((url) => {
                        const source = sources.find((s) => s.url === url);
                        const number = source ? sources.indexOf(source) + 1 : 0;
                        return (
                          <SafeLink key={url} url={url} title={source?.title || url}>
                            {number ? String(number) : "↗"}
                          </SafeLink>
                        );
                      })}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </details>
      )}
      {extras.map(([field, key]) => {
        const value = answer[field];
        const text = Array.isArray(value) ? value.map((v) => "- " + v).join("\n") : String(value || "").trim();
        if (!text) return null;
        return (
          <details className="extra" key={field}>
            <summary>{t(key)}</summary>
            <RichText text={text} />
          </details>
        );
      })}
      {sources.length > 0 && (
        <div className="sources-box">
          <h3>{t("sources")}</h3>
          <ol className="sources">
            {sources.map((source) => {
              let host = "";
              try {
                host = new URL(source.url).hostname.replace(/^www\./, "");
              } catch {
                return null;
              }
              return (
                <li key={source.url}>
                  <SafeLink url={source.url}>{source.title || host}</SafeLink>
                  <small>{host}</small>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}

function ReviewControls({ question, onSaved, onToast }: { question: QuestionDetail; onSaved: () => void; onToast: (text: string) => void }) {
  // Human review is the reader's own decision; the agent has no way to submit it.
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (decision: "reviewed" | "stale") => {
    if (!note.trim()) {
      onToast(t("review_need_note"));
      return;
    }
    setBusy(true);
    try {
      await api("/api/review", { question_id: question.id, answer_id: question.answer!.id, decision, note });
      onToast(t(decision === "reviewed" ? "review_saved" : "stale_saved"));
      onSaved();
    } catch (error) {
      onToast(error instanceof Error ? error.message : t("failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <details>
      <summary>{t("review")}</summary>
      <p className="hint">{t("review_hint")}</p>
      <textarea
        className="note"
        maxLength={2000}
        placeholder={t("review_placeholder")}
        aria-label={t("review_label")}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <div className="actions">
        <Button size="sm" disabled={busy} onClick={() => send("reviewed")}>
          {t("review_ok")}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => send("stale")}>
          {t("review_stale")}
        </Button>
      </div>
    </details>
  );
}

export function QuestionView({
  question: q,
  revealed,
  onReveal,
  canReview,
  onReviewed,
  onOpenNote,
  onPractise,
  onToast,
}: {
  question: QuestionDetail;
  onPractise: () => void;
  revealed: boolean;
  onReveal: () => void;
  canReview: boolean;
  onReviewed: () => void;
  onOpenNote: (id: string) => void;
  onToast: (text: string) => void;
}) {
  const { t, lang } = useI18n();
  const date = (value?: string) => (value ? new Date(value).toLocaleDateString(lang) : "");
  const facts = [t("seen", { n: q.frequency }), q.companies.slice(0, 3).join(lang === "en" ? ", " : "、"), q.years.join("/")].filter(Boolean);
  return (
    <>
      <p className="reading-meta">
        <span className="topic">{q.group}</span>
        <span>{facts.join(" · ")}</span>
      </p>
      <h1 className="reading-title">{q.canonical}</h1>
      {(q.technologies.length > 0 || q.problem_url) && (
        <div className="tags">
          {q.technologies.slice(0, 6).map((tech) => (
            <span className="tag" key={tech}>
              {tech}
            </span>
          ))}
          {q.problem_url && (
            <SafeLink url={q.problem_url.url} className="tag">
              {t("problem")} ↗
            </SafeLink>
          )}
        </div>
      )}
      {!q.answer ? (
        <p className="no-answer">{t("no_answer")}</p>
      ) : revealed ? (
        <AnswerBody status={q.answer_status} answer={q.answer} />
      ) : (
        <Button className="reveal" onClick={onReveal}>
          {t("show_answer")}
        </Button>
      )}
      {q.notes && q.notes.length > 0 && (
        <section className="linked">
          <h3>{t("related_notes", { n: q.notes.length })}</h3>
          <ul className="linked-list">
            {q.notes.map((note) => (
              <li key={note.id}>
                <button type="button" className="linked-item" onClick={() => onOpenNote(note.id)}>
                  <span className="linked-title">{note.title}</span>
                  <span className="question-meta">
                    <span>{note.where}</span>
                    <span>{t(note.relation === "answers" ? "relation_answers" : "relation_covers")}</span>
                    {note.marked && <span className="mark">{t("marked")}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="reading-more">
        <details>
          <summary>{t("origins", { n: q.occurrences.length })}</summary>
          {q.occurrences.map((occurrence, index) => {
            const start = occurrence.locator?.start_seconds ?? occurrence.locator?.start;
            const where = [occurrence.platform, occurrence.year, start !== undefined && start !== null ? `${start}s` : ""].filter(Boolean).join(" · ");
            return (
              <p className="origin" key={index}>
                {occurrence.text}
                {where && <small>{where}</small>}
              </p>
            );
          })}
        </details>
        {q.history.length > 0 && (
          <details>
            <summary>{t("history", { n: q.history.length })}</summary>
            {q.history.map((item, index) => (
              <p className="origin" key={index}>
                {`${t(`rating_${item.rating}` as "rating_good")} · ${date(item.occurred_at)} — ${item.note || t("no_note")}`}
                <small>{t("next_review", { d: date(item.next_review_at) })}</small>
              </p>
            ))}
          </details>
        )}
        {canReview && q.answer && <ReviewControls key={q.id + q.revision} question={q} onSaved={onReviewed} onToast={onToast} />}
        <Button variant="link" size="sm" className="px-0" onClick={onPractise}>
          {t("practise_one")}
        </Button>
      </div>
    </>
  );
}
