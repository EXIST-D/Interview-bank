import { Dialog } from "radix-ui";
import { CheckCircle2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, questionDetail, type QuestionDetail, type QuestionRow } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { RichText } from "@/reader/markdown";
import { AnswerBody } from "@/reader/question-view";
import "@/reader/reader.css";

const RATINGS = ["again", "hard", "good", "easy"] as const;
type Rating = (typeof RATINGS)[number];
const ROUND_KEY = "ibank-round";

type Saved = { questions: { id: string }[]; index: number; results: Rating[] };
type Pending = { question_id: string; revision: string; rating: Rating; request_id: string; note: string; timezone: string };

export function storedRound(): Saved | null {
  try {
    return JSON.parse(sessionStorage.getItem(ROUND_KEY) || "null");
  } catch {
    return null;
  }
}

export function discardRound() {
  try {
    sessionStorage.removeItem(ROUND_KEY);
  } catch {
    /* nothing to discard */
  }
}

function keep(round: Saved) {
  // Lets a refresh resume the round; only IDs and positions are kept, never what was written.
  try {
    if (round.index >= round.questions.length) sessionStorage.removeItem(ROUND_KEY);
    else sessionStorage.setItem(ROUND_KEY, JSON.stringify(round));
  } catch {
    /* the round lasts for this page only */
  }
}

export type PracticeStart = { kind: "setup" } | { kind: "one"; question: QuestionDetail } | { kind: "ids"; ids: string[] } | { kind: "resume" };

export function Practice({
  start,
  onClose,
  params,
  canRecord,
}: {
  start: PracticeStart | null;
  onClose: (recorded: boolean) => void;
  /** The current list's filters; a round follows them. */
  params: () => URLSearchParams;
  canRecord: boolean;
}) {
  const { t } = useI18n();
  const [size, setSize] = useState<"5" | "10" | "20">("10");
  const [round, setRound] = useState<Saved | null>(null);
  const [current, setCurrent] = useState<QuestionDetail | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef<Pending | null>(null);
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!start) return;
    setError(null);
    setCurrent(null);
    pending.current = null;
    if (start.kind === "one") setRound({ questions: [{ id: start.question.id }], index: 0, results: [] });
    else if (start.kind === "ids") setRound({ questions: start.ids.map((id) => ({ id })), index: 0, results: [] });
    else if (start.kind === "resume") setRound(storedRound());
    else setRound(null);
  }, [start]);

  const index = round?.index ?? 0;
  const questionId = round && index < round.questions.length ? round.questions[index].id : null;

  useEffect(() => {
    if (!round) return;
    keep(round);
  }, [round]);

  useEffect(() => {
    if (!questionId) return;
    let live = true;
    setCurrent(null);
    setRevealed(false);
    setNote("");
    questionDetail(questionId)
      .then((q) => {
        if (!live) return;
        setCurrent(q);
        requestAnimationFrame(() => title.current?.focus({ preventScroll: true }));
      })
      .catch((cause) => live && setError(cause instanceof Error ? cause.message : t("failed")));
    return () => {
      live = false;
    };
  }, [questionId, t]);

  const begin = async () => {
    setBusy(true);
    setError(null);
    try {
      const query = params();
      query.delete("offset");
      query.set("limit", size);
      const result = await api<{ questions: QuestionRow[] }>("/api/practice?" + query);
      if (!result.questions.length) throw new Error(t("no_round"));
      setRound({ questions: result.questions.map((q) => ({ id: q.id })), index: 0, results: [] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("failed"));
    } finally {
      setBusy(false);
    }
  };

  const rate = async (rating: Rating) => {
    if (!round || !current || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (canRecord) {
        // A retry sends the same request ID, so a save that succeeded without an answer is not counted twice.
        pending.current ??= {
          question_id: current.id,
          revision: current.revision,
          rating,
          request_id: crypto.randomUUID(),
          note,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        };
        await api("/api/practice", pending.current);
      }
      const result = pending.current?.rating ?? rating;
      pending.current = null;
      setRound({ ...round, index: round.index + 1, results: [...round.results, result] });
    } catch (cause) {
      setError(t("save_failed", { e: cause instanceof Error ? cause.message : t("failed") }));
    } finally {
      setBusy(false);
    }
  };

  const skip = () => {
    if (!round || busy) return;
    if (pending.current) return setError(t("retry_first"));
    setRound({ ...round, index: round.index + 1 });
  };

  const close = () => {
    if (busy) return;
    if (pending.current && !window.confirm(t("close_unsaved"))) return;
    const unfinished = round && round.index < round.questions.length;
    if (!pending.current && unfinished && note.trim() && !window.confirm(t("close_unsubmitted"))) return;
    discardRound();
    const recorded = Boolean(round?.results.length && canRecord);
    setRound(null);
    onClose(recorded);
  };

  const done = round && index >= round.questions.length;
  const known = round?.results.filter((r) => r === "good" || r === "easy").length ?? 0;

  return (
    <Dialog.Root open={start !== null} onOpenChange={(open) => !open && close()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content
          onEscapeKeyDown={(event) => {
            event.preventDefault();
            close();
          }}
          onPointerDownOutside={(event) => event.preventDefault()}
          className="fixed inset-0 z-50 flex flex-col bg-card outline-none wide:inset-x-auto wide:top-[6dvh] wide:bottom-[6dvh] wide:left-1/2 wide:w-[min(760px,92vw)] wide:-translate-x-1/2 wide:rounded-3xl wide:shadow-soft-lg"
        >
          <header className="flex h-13 shrink-0 items-center gap-3 border-b border-border px-4">
            <Dialog.Title className="text-headline font-semibold">{t("practice_title")}</Dialog.Title>
            {round && !done && (
              <span className="flex flex-1 items-center gap-2 text-caption text-muted-foreground tabular-nums">
                <span className="truncate">{t("progress", { i: index + 1, n: round.questions.length, g: current?.group ?? "" })}</span>
                <span aria-label={t("progress_label")} className="h-1 min-w-12 flex-1 overflow-hidden rounded-full bg-secondary">
                  <span className="block h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${(index / round.questions.length) * 100}%` }} />
                </span>
              </span>
            )}
            <button type="button" onClick={close} aria-label={t("close_practice")} className="ml-auto grid size-8 place-items-center rounded-full bg-fill text-muted-foreground">
              <X className="size-4" />
            </button>
          </header>

          <div className="ib-reading min-h-0 flex-1 overflow-y-auto">
            {!round ? (
              <div className="mx-auto flex max-w-md flex-col gap-4 pt-6">
                <p className="text-subhead font-medium">{t("round_size")}</p>
                <Segmented value={size} onChange={setSize} options={(["5", "10", "20"] as const).map((value) => ({ value, label: value }))} />
                <p className="hint">{t("round_scope")}</p>
                <p className="hint">{t(canRecord ? "mode_record" : "mode_temporary")}</p>
                <Button disabled={busy} onClick={begin}>
                  {t("begin_round")}
                </Button>
              </div>
            ) : done ? (
              <div className="mx-auto flex max-w-md flex-col items-center gap-3 pt-10 text-center">
                <CheckCircle2 className="size-10 text-success" />
                <h3 className="text-title-3 font-semibold">{t("round_done")}</h3>
                <p className="text-subhead tabular-nums">{t("round_summary", { n: round.results.length, k: known, s: round.questions.length - round.results.length })}</p>
                <p className="hint">{t(canRecord ? "round_saved" : "round_temporary")}</p>
                <Button onClick={close}>{t("back_to_bank")}</Button>
              </div>
            ) : !current ? (
              <p className="hint">{error ? t("load_failed") : t("loading")}</p>
            ) : (
              <>
                <h1 ref={title} tabIndex={-1} className="reading-title outline-none">
                  {current.canonical}
                </h1>
                <label htmlFor="practice-response" className="hint block">
                  {t("practice_thinking")}
                </label>
                <textarea
                  id="practice-response"
                  className="note"
                  maxLength={10000}
                  value={note}
                  disabled={busy || Boolean(pending.current)}
                  placeholder={t("practice_placeholder")}
                  onChange={(event) => setNote(event.target.value)}
                />
                {!revealed ? (
                  <div className="actions">
                    <Button onClick={() => setRevealed(true)}>{t("reveal")}</Button>
                    <Button variant="outline" onClick={skip} disabled={busy}>
                      {t("skip_question")}
                    </Button>
                  </div>
                ) : (
                  <>
                    {current.answer ? <AnswerBody status={current.answer_status} answer={current.answer} /> : <p className="no-answer">{t("no_answer")}</p>}
                    {current.my_answer && (
                      <section className="my-answer">
                        <h2 className="answer-head">{t("my_answer")}</h2>
                        <RichText text={current.my_answer.text} />
                      </section>
                    )}
                    <p className="hint mt-4">{t("rate")}</p>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {RATINGS.map((rating) => (
                        <Button
                          key={rating}
                          variant={rating === "good" || rating === "easy" ? "tinted" : "outline"}
                          disabled={busy}
                          className={cn(pending.current?.rating === rating && "ring-2 ring-ring/40")}
                          onClick={() => rate(rating)}
                        >
                          {t(`rating_${rating}`)}
                        </Button>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
            {error && (
              <p role="alert" className="warning mt-3">
                {error}
              </p>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
