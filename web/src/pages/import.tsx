import { AlertTriangle, Check, CornerDownRight, ImagePlus, Loader2, RotateCcw, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ClipboardEvent, type DragEvent } from "react";
import { ApiError } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useToast } from "@/lib/hooks";
import { useI18n, type TextKey } from "@/lib/i18n";
import { intake, prepare, ROUNDS, RUNNING, type Hints, type IntakeSource, type Job, type Overview, type Prepared } from "@/lib/intake";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";

// Thumbnails of this tab's uploads by job and screenshot index; a reload shows the list without them.
const thumbs = new Map<string, (string | null)[]>();
const field = "h-9 w-full rounded-[10px] bg-fill px-3 text-subhead outline-none focus:ring-2 focus:ring-ring/30";

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;
}

function Progress({ job }: { job: Job }) {
  const { t } = useI18n();
  const p = job.progress;
  const text =
    job.status === "extracting"
      ? t("imp_reading", { i: Math.min((p?.done ?? 0) + 1, p?.total ?? 1), n: p?.total ?? 1 })
      : job.status === "saving"
        ? t("imp_saving")
        : t("imp_answering", { i: Math.min((p?.done ?? 0) + 1, p?.total ?? 1), n: p?.total ?? 1 });
  const share = p && p.total ? Math.round((p.done / p.total) * 100) : 8;
  return (
    <section className="surface p-6" aria-live="polite">
      <p className="flex items-center gap-2 text-callout font-medium">
        <Loader2 className="size-4 animate-spin text-primary" />
        {text}
      </p>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-fill">
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.max(8, share)}%` }} />
      </div>
      {job.status === "answering" && <p className="mt-3 text-footnote text-muted-foreground">{t("imp_answering_hint")}</p>}
    </section>
  );
}

function Picker({ overview, onStarted }: { overview: Overview; onStarted: (job: Job) => void }) {
  const { t } = useI18n();
  const limits = overview.limits!;
  const max = Math.min(limits.max_images_per_job, limits.images_left_today);
  const [items, setItems] = useState<Prepared[]>([]);
  const [hints, setHints] = useState<Hints>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const add = async (files: File[]) => {
    setError(null);
    const images = files.filter((file) => file.type.startsWith("image/") || /\.(heic|heif)$/i.test(file.name));
    if (items.length + images.length > max) setError(t("imp_too_many", { n: max }));
    const room = images.slice(0, Math.max(0, max - items.length));
    setBusy(t("imp_preparing"));
    const ready: Prepared[] = [];
    for (const file of room) {
      try {
        ready.push(await prepare(file, limits.max_image_bytes));
      } catch {
        setError(t("imp_unsupported", { name: file.name }));
      }
    }
    setItems((current) => [...current, ...ready]);
    setBusy(null);
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    add([...event.dataTransfer.files]);
  };
  const onPaste = (event: ClipboardEvent) => {
    const files = [...event.clipboardData.files];
    if (files.length) {
      event.preventDefault();
      add(files);
    }
  };

  const start = async () => {
    setError(null);
    try {
      setBusy(t("imp_uploading", { i: 1, n: items.length }));
      let job = await intake.create(Object.fromEntries(Object.entries(hints).filter(([, v]) => v)));
      for (const [index, item] of items.entries()) {
        setBusy(t("imp_uploading", { i: index + 1, n: items.length }));
        if (item.original.size > limits.max_image_bytes) throw new Error(t("imp_too_large", { name: item.name }));
        job = await intake.upload(job.id, index, item.original);
        for (const [view, blob] of item.views.entries()) job = await intake.upload(job.id, index, blob, view);
      }
      thumbs.set(job.id, items.map((item) => item.thumb));
      onStarted(await intake.start(job.id));
    } catch (cause) {
      setError(message(cause, t("failed")));
      setBusy(null);
    }
  };

  const hint = (key: keyof Hints, value: string) => setHints((current) => ({ ...current, [key]: value }));
  return (
    <div className="flex flex-col gap-4" onPaste={onPaste}>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
        disabled={Boolean(busy) || max <= 0}
        className="flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-border bg-card px-4 py-10 text-center transition-colors hover:border-primary/50 disabled:opacity-50"
      >
        <span className="grid size-12 place-items-center rounded-2xl bg-accent text-primary">
          <ImagePlus className="size-6" />
        </span>
        <span className="text-callout font-medium">{t("imp_pick")}</span>
        <span className="text-footnote text-muted-foreground">{t("imp_drop", { n: max })}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept="image/*"
        multiple
        hidden
        aria-label={t("imp_pick")}
        onChange={(event) => {
          add([...(event.target.files ?? [])]);
          event.target.value = "";
        }}
      />
      {items.length > 0 && (
        <ul className="grid grid-cols-3 gap-2.5 sm:grid-cols-5">
          {items.map((item, index) => (
            <li key={item.key} className="relative overflow-hidden rounded-xl bg-fill">
              {item.thumb ? (
                <img src={item.thumb} alt={item.name} className="aspect-[3/4] w-full object-cover object-top" />
              ) : (
                <div className="grid aspect-[3/4] place-items-center p-2 text-caption break-all text-muted-foreground">{item.name}</div>
              )}
              <span className="absolute bottom-1 left-1 rounded-full bg-black/55 px-1.5 text-[11px] text-white">
                {index + 1}
                {item.tiles > 0 && ` · ${t("imp_tiles", { n: item.tiles })}`}
              </span>
              <button
                type="button"
                aria-label={t("imp_remove")}
                disabled={Boolean(busy)}
                onClick={() => setItems((current) => current.filter((other) => other.key !== item.key))}
                className="absolute top-1 right-1 grid size-6 place-items-center rounded-full bg-black/55 text-white"
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <fieldset className="surface grid gap-3 p-4 sm:grid-cols-2">
        <legend className="sr-only">{t("imp_hints")}</legend>
        <p className="text-footnote text-muted-foreground sm:col-span-2">{t("imp_hints")}</p>
        <label className="grid gap-1 text-caption text-muted-foreground">
          {t("imp_company")}
          <input className={field} maxLength={80} value={hints.company ?? ""} onChange={(e) => hint("company", e.target.value)} />
        </label>
        <label className="grid gap-1 text-caption text-muted-foreground">
          {t("imp_position")}
          <input className={field} maxLength={80} value={hints.position ?? ""} onChange={(e) => hint("position", e.target.value)} />
        </label>
        <label className="grid gap-1 text-caption text-muted-foreground">
          {t("imp_round")}
          <select className={field} value={hints.round ?? ""} onChange={(e) => hint("round", e.target.value)}>
            <option value="">{t("imp_unknown")}</option>
            {ROUNDS.map((round) => (
              <option key={round} value={round}>
                {t(`round_${round}` as TextKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-caption text-muted-foreground">
          {t("imp_date")}
          <input className={field} type="month" value={hints.event_date ?? ""} onChange={(e) => hint("event_date", e.target.value)} />
        </label>
      </fieldset>
      {error && <p className="text-footnote text-destructive">{error}</p>}
      <div className="flex items-center justify-between gap-3">
        <span className="text-footnote text-muted-foreground">{busy ?? t("imp_left", { n: limits.images_left_today })}</span>
        <Button disabled={!items.length || Boolean(busy)} onClick={start}>
          {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {t("imp_start", { n: items.length })}
        </Button>
      </div>
    </div>
  );
}

type Edit = { keep: boolean; canonical: string };
type Meta = { company: string; round: string; event_date: string };

function Review({ job, onChange }: { job: Job; onChange: (job: Job) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const sources = [...job.sources].sort((a, b) => a.index - b.index);
  const [edits, setEdits] = useState<Record<string, Edit>>(() =>
    Object.fromEntries(sources.flatMap((s) => s.questions.map((q) => [q.id, { keep: true, canonical: q.canonical_suggestion }]))),
  );
  const [meta, setMeta] = useState<Record<string, Meta>>(() =>
    Object.fromEntries(
      sources.map((s) => [s.source_id, { company: s.metadata.company ?? "", round: s.metadata.round ?? "", event_date: s.metadata.event_date ?? "" }]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(job.error);
  const pictures = thumbs.get(job.id);
  const kept = Object.values(edits).filter((edit) => edit.keep && edit.canonical.trim()).length;
  const failed = sources.some((s) => s.status === "failed");
  const duplicates = job.images.filter((image) => image.duplicate).length;

  const act = async (run: () => Promise<Job>) => {
    setBusy(true);
    setError(null);
    try {
      onChange(await run());
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };
  const confirm = () =>
    act(() =>
      intake.confirm(
        job.id,
        sources
          .filter((s) => s.status === "extracted")
          .map((s) => ({
            source_id: s.source_id,
            metadata: meta[s.source_id],
            questions: s.questions.map((q) => {
              const edit = edits[q.id];
              const text = edit.canonical.trim();
              return { id: q.id, keep: edit.keep && Boolean(text), ...(text && text !== q.canonical_suggestion ? { canonical: text } : {}) };
            }),
          })),
      ),
    );
  const cancel = () =>
    act(async () => {
      const result = await intake.cancel(job.id);
      toast(t("imp_cancelled"));
      return result;
    });

  const setMetaField = (id: string, key: keyof Meta, value: string) => setMeta((all) => ({ ...all, [id]: { ...all[id], [key]: value } }));
  const notice = (source: IntakeSource) =>
    source.status === "failed"
      ? t("imp_failed_shot", { r: source.error ?? "" })
      : source.status === "no_questions"
        ? t("imp_empty_shot", { r: source.reason ?? "" })
        : t("imp_skip_shot", { r: source.reason ?? "" });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-title-3 font-semibold">{t("imp_review_title")}</h2>
        <p className="mt-1 text-footnote text-muted-foreground">{t("imp_review_lead")}</p>
        {duplicates > 0 && <p className="mt-1 text-footnote text-muted-foreground">{t("imp_dup", { n: duplicates })}</p>}
      </div>
      {sources.map((source) => (
        <section key={source.source_id} className="surface flex flex-col gap-3 p-4" aria-label={t("imp_shot", { n: source.index + 1 })}>
          <div className="flex gap-3">
            {pictures?.[source.index] && (
              <img src={pictures[source.index]!} alt="" className="h-24 w-16 shrink-0 rounded-lg bg-fill object-cover object-top" />
            )}
            <div className="min-w-0 flex-1">
              <h3 className="text-headline font-semibold">{t("imp_shot", { n: source.index + 1 })}</h3>
              {source.status === "extracted" ? (
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <input
                    className={cn(field, "col-span-2 sm:col-span-1")}
                    aria-label={t("imp_company")}
                    placeholder={t("imp_company")}
                    maxLength={80}
                    value={meta[source.source_id].company}
                    onChange={(e) => setMetaField(source.source_id, "company", e.target.value)}
                  />
                  <select
                    className={field}
                    aria-label={t("imp_round")}
                    value={meta[source.source_id].round}
                    onChange={(e) => setMetaField(source.source_id, "round", e.target.value)}
                  >
                    <option value="">{t("imp_round")}</option>
                    {ROUNDS.map((round) => (
                      <option key={round} value={round}>
                        {t(`round_${round}` as TextKey)}
                      </option>
                    ))}
                  </select>
                  <input
                    className={field}
                    aria-label={t("imp_date")}
                    placeholder="2026-10"
                    maxLength={10}
                    value={meta[source.source_id].event_date}
                    onChange={(e) => setMetaField(source.source_id, "event_date", e.target.value)}
                  />
                </div>
              ) : (
                <p className={cn("mt-1 text-footnote", source.status === "failed" ? "text-destructive" : "text-muted-foreground")}>{notice(source)}</p>
              )}
              {Boolean(source.self_introductions_dropped) && (
                <p className="mt-1 text-caption text-tertiary-foreground">{t("imp_intro_dropped", { n: source.self_introductions_dropped! })}</p>
              )}
            </div>
          </div>
          {source.questions.length > 0 && (
            <ol className="flex flex-col gap-2">
              {source.questions.map((q) => {
                const edit = edits[q.id];
                const flagged = q.flags.length > 0;
                return (
                  <li
                    key={q.id}
                    className={cn(
                      "flex gap-2.5 rounded-xl px-3 py-2.5",
                      flagged ? "bg-orange/10" : "bg-fill",
                      !edit.keep && "opacity-50",
                      q.parent_id && "ml-5",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-1.5 size-4 shrink-0 accent-[var(--primary)]"
                      aria-label={t("imp_keep")}
                      checked={edit.keep}
                      onChange={(e) => setEdits((all) => ({ ...all, [q.id]: { ...edit, keep: e.target.checked } }))}
                    />
                    <div className="min-w-0 flex-1">
                      <textarea
                        rows={Math.min(6, Math.max(1, Math.ceil(edit.canonical.length / 36)))}
                        maxLength={2000}
                        aria-label={t("imp_question")}
                        value={edit.canonical}
                        onChange={(e) => setEdits((all) => ({ ...all, [q.id]: { ...edit, canonical: e.target.value } }))}
                        className="w-full resize-y bg-transparent text-subhead leading-relaxed outline-none"
                      />
                      {(q.original_text !== q.canonical_suggestion || flagged || q.parent_id) && (
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">
                          {q.parent_id && (
                            <span className="inline-flex items-center gap-0.5">
                              <CornerDownRight className="size-3" />
                              {t("imp_followup")}
                            </span>
                          )}
                          {q.flags.map((flag) => (
                            <span key={flag} className="inline-flex items-center gap-0.5 text-warning">
                              <AlertTriangle className="size-3" />
                              {t(flag === "contact" ? "imp_contact" : "imp_low")}
                            </span>
                          ))}
                          {q.original_text !== q.canonical_suggestion && <span className="min-w-0 break-words">{t("imp_original", { t: q.original_text })}</span>}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </section>
      ))}
      {error && <p className="text-footnote text-destructive">{error}</p>}
      <div className="glass sticky bottom-[calc(52px+env(safe-area-inset-bottom))] -mx-4 flex flex-wrap items-center justify-end gap-2 border-t border-border px-4 py-3 md:bottom-0">
        {!kept && <span className="mr-auto text-footnote text-muted-foreground">{t("imp_none_kept")}</span>}
        {failed && (
          <Button variant="outline" size="sm" disabled={busy} onClick={() => act(() => intake.retryRead(job.id))}>
            <RotateCcw />
            {t("imp_reread")}
          </Button>
        )}
        <Button variant="ghost" size="sm" disabled={busy} onClick={cancel}>
          {t("imp_cancel")}
        </Button>
        <Button size="sm" disabled={busy} onClick={confirm}>
          {busy ? <Loader2 className="animate-spin" /> : <Check />}
          {t("imp_confirm", { n: kept })}
        </Button>
      </div>
    </div>
  );
}

const MERGE_CHOICES = [
  ["MERGE_VARIANT", "merge_same"],
  ["KEEP_RELATED", "merge_related"],
  ["KEEP_DISTINCT", "merge_distinct"],
] as const;

function MergeReview({ job, onChange }: { job: Job; onChange: (job: Job) => void }) {
  const { t } = useI18n();
  const items = job.merge_review ?? [];
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await intake.merge(job.id, items.map((item) => ({ question_id: item.question_id, action: choices[item.question_id] }))));
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-title-3 font-semibold">{t("imp_merge_title")}</h2>
        <p className="mt-1 text-footnote text-muted-foreground">{t("imp_merge_lead")}</p>
        {job.notice && <p className="mt-1 text-footnote text-warning">{job.notice}</p>}
      </div>
      {items.map((item) => (
        <section key={item.question_id} className="surface flex flex-col gap-3 p-4">
          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                ["merge_new", item.question],
                ["merge_existing", item.target],
              ] as const
            ).map(([label, text]) => (
              <div key={label} className="rounded-xl bg-fill px-3 py-2.5">
                <small className="text-caption text-muted-foreground">{t(label)}</small>
                <p className="mt-1 text-subhead leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
          <p className="text-caption text-muted-foreground">{t("imp_merge_reason", { r: item.reason })}</p>
          <Segmented
            label={t("imp_merge_title")}
            value={choices[item.question_id] ?? ""}
            onChange={(value) => setChoices((all) => ({ ...all, [item.question_id]: value }))}
            options={MERGE_CHOICES.map(([value, label]) => ({ value, label: t(label) }))}
          />
        </section>
      ))}
      {error && <p className="text-footnote text-destructive">{error}</p>}
      <div className="flex justify-end">
        <Button disabled={busy || items.some((item) => !choices[item.question_id])} onClick={submit}>
          {busy ? <Loader2 className="animate-spin" /> : <Check />}
          {t("imp_merge_confirm")}
        </Button>
      </div>
    </div>
  );
}

function Done({ job, onChange, onAgain }: { job: Job; onChange: (job: Job) => void; onAgain: () => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const result = job.result;
  const answers = job.answers;
  const failed = Object.entries(answers?.failed ?? {});
  const retry = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await intake.retryAnswers(job.id));
    } catch (cause) {
      setError(message(cause, t("failed")));
    } finally {
      setBusy(false);
    }
  };
  const link = (id: string, text: string) => (
    <a href={href("bank", [], { open: id })} className="block rounded-xl bg-fill px-3 py-2 text-subhead leading-relaxed hover:bg-black/[0.06] dark:hover:bg-white/[0.1]">
      {text}
    </a>
  );
  return (
    <section className="surface flex flex-col gap-4 p-5" aria-live="polite">
      <h2 className="flex items-center gap-2 text-title-3 font-semibold">
        <span className="grid size-7 place-items-center rounded-full bg-accent text-primary">
          <Check className="size-4" />
        </span>
        {t("imp_done_title")}
      </h2>
      {job.error && <p className="text-footnote text-destructive">{job.error}</p>}
      {result?.nothing_new && <p className="text-subhead text-muted-foreground">{t("imp_nothing_new")}</p>}
      {result && !result.nothing_new && (
        <>
          <div>
            <h3 className="text-callout font-semibold">{t("imp_added", { n: result.added.length })}</h3>
            <div className="mt-2 flex flex-col gap-1.5">{result.added.map((q) => <div key={q.id}>{link(q.id, q.canonical)}</div>)}</div>
          </div>
          {result.merged.length > 0 && (
            <div>
              <h3 className="text-callout font-semibold">{t("imp_merged", { n: result.merged.length })}</h3>
              <div className="mt-2 flex flex-col gap-1.5">
                {result.merged.map((q, index) => (
                  <div key={q.id + index}>{link(q.id, q.canonical)}</div>
                ))}
              </div>
            </div>
          )}
          {result.related > 0 && <p className="text-footnote text-muted-foreground">{t("imp_related", { n: result.related })}</p>}
        </>
      )}
      {answers && (answers.done.length > 0 || failed.length > 0) && (
        <div className="rounded-xl bg-accent/60 px-3 py-2.5 text-footnote">
          <p>{t("imp_answers", { n: answers.done.length })}</p>
          {failed.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-warning">{t("imp_answers_failed", { n: failed.length, r: failed[0][1] })}</span>
              <Button size="xs" variant="outline" disabled={busy} onClick={retry}>
                <RotateCcw />
                {t("imp_retry_answers")}
              </Button>
            </div>
          )}
        </div>
      )}
      {Boolean(result?.answers_skipped_for_limit) && (
        <p className="text-caption text-muted-foreground">{t("imp_limit_answers", { n: result!.answers_skipped_for_limit! })}</p>
      )}
      {error && <p className="text-footnote text-destructive">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" size="sm" asChild>
          <a href={href("bank")}>{t("imp_open_bank")}</a>
        </Button>
        <Button size="sm" onClick={onAgain}>
          <ImagePlus />
          {t("imp_again")}
        </Button>
      </div>
    </section>
  );
}

function Pending({ job, onChange }: { job: Job; onChange: (job: Job) => void }) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(job.error);
  const run = async (step: () => Promise<Job>) => {
    try {
      onChange(await step());
    } catch (cause) {
      setError(message(cause, t("failed")));
    }
  };
  return (
    <section className="surface flex flex-col gap-3 p-5">
      <p className="text-subhead">{t("imp_resume", { n: job.images.length })}</p>
      {error && <p className="text-footnote text-destructive">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => run(() => intake.cancel(job.id))}>
          {t("imp_cancel")}
        </Button>
        <Button size="sm" disabled={!job.images.length} onClick={() => run(() => intake.start(job.id))}>
          <Sparkles />
          {t("imp_start", { n: job.images.length })}
        </Button>
      </div>
    </section>
  );
}

export function ImportPage() {
  const { t, lang } = useI18n();
  const { refresh } = useBank();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = job?.status;

  const load = useCallback(async () => {
    try {
      const next = await intake.overview();
      setOverview(next);
      setJob(next.active ?? null);
    } catch (cause) {
      setError(message(cause, t("unreachable")));
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!job || !RUNNING.includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        setJob(await intake.job(job.id));
      } catch {
        /* the next tick retries */
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [job?.id, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (status === "done") refresh(true);
  }, [status, refresh]);

  const update = (next: Job) => setJob(next.status === "cancelled" ? null : next);
  const again = () => {
    setJob(null);
    load();
  };

  let body;
  if (error) body = <p className="text-footnote text-destructive">{error}</p>;
  else if (!overview) body = <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  else if (!overview.enabled) body = <p className="surface p-5 text-subhead text-muted-foreground">{t("imp_disabled")}</p>;
  else if (!job) body = <Picker overview={overview} onStarted={setJob} />;
  else if (RUNNING.includes(job.status)) body = <Progress job={job} />;
  else if (job.status === "collecting") body = <Pending job={job} onChange={update} />;
  else if (job.status === "review") body = <Review key={job.id + job.updated_at} job={job} onChange={update} />;
  else if (job.status === "merge_review") body = <MergeReview job={job} onChange={update} />;
  else body = <Done job={job} onChange={update} onAgain={again} />;

  const date = (value: string) => new Date(value).toLocaleString(lang, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  const recent = (overview?.recent ?? []).filter((entry) => entry.id !== job?.id && entry.status !== "cancelled");
  return (
    <div className="mx-auto max-w-[880px] px-4 pt-6 pb-28 sm:px-6 md:pt-8 md:pb-16">
      <p className="flex items-center gap-1.5 text-caption font-semibold tracking-wide text-primary">
        <ImagePlus className="size-3.5" />
        {t("board_import")}
      </p>
      <h1 className="mt-0.5 text-title-1 font-bold">{t("imp_title")}</h1>
      <p className="mt-1.5 mb-5 text-footnote leading-relaxed text-muted-foreground">
        {t("imp_lead")}
        {overview?.models && ` ${t("imp_models", { v: overview.models.vision.model, a: overview.models.text.model })}`}
      </p>
      {body}
      {!job && recent.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-2 text-callout font-semibold">{t("imp_recent")}</h2>
          <ul className="flex flex-col gap-1.5">
            {recent.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between gap-3 rounded-xl bg-fill px-3 py-2 text-footnote">
                <span>{date(entry.created_at)}</span>
                <span className="text-muted-foreground">
                  {entry.result
                    ? t("imp_recent_line", { i: entry.images, a: entry.result.added.length, m: entry.result.merged.length, d: entry.answers?.done.length ?? 0 })
                    : t(`imp_status_${entry.status}` as TextKey)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
