import { ArrowRight, BookOpen, CalendarCheck, Check, Compass, MessagesSquare, Newspaper, Play } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useBank } from "@/lib/bank";
import { useI18n } from "@/lib/i18n";
import { href, type Board } from "@/lib/router";
import { keys, stored, type LastRead } from "@/lib/storage";
import { cn } from "@/lib/utils";
import type { Library, QuestionRow } from "@/lib/api";
import { Button } from "@/components/ui/button";

const TONES = ["text-blue bg-blue/10", "text-primary bg-accent", "text-purple bg-purple/12", "text-warning bg-orange/14"];

// The same topic keeps the same colour everywhere.
export function topicTone(name: string) {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return TONES[Math.abs(hash) % TONES.length];
}

export function TopicTag({ name }: { name: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-caption font-medium", topicTone(name))}>
      <span className="size-1.5 rounded-full bg-current" />
      {name}
    </span>
  );
}

function BoardCard({ board, icon: Icon, tone, hint, stat }: { board: Board; icon: LucideIcon; tone: string; hint: string; stat: string }) {
  const { t } = useI18n();
  return (
    <a
      href={href(board)}
      className="group flex min-w-0 flex-col gap-2 surface p-4 transition-transform duration-300 ease-apple hover:-translate-y-0.5 hover:shadow-soft-lg sm:min-h-44 sm:gap-2.5 sm:p-5"
    >
      <span className={cn("grid size-9 place-items-center rounded-[10px]", tone)}>
        <Icon className="size-[18px]" />
      </span>
      <span className="text-headline font-semibold">{t(`board_${board}` as const)}</span>
      <span className="hidden text-footnote leading-relaxed text-muted-foreground sm:block">{hint}</span>
      <span className="mt-auto flex items-center justify-between pt-1 text-caption text-muted-foreground">
        <span className="truncate tabular-nums">{stat}</span>
        <span className="hidden items-center gap-1 font-medium text-primary sm:flex">
          {t("enter")}
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
        </span>
      </span>
    </a>
  );
}

function ContinueCard({ last, board, label }: { last: LastRead; board: Board; label: string }) {
  const { t } = useI18n();
  return (
    <a
      href={href(board, [], { open: last.id })}
      className="group flex min-w-0 items-center gap-3 surface px-4 py-3.5 transition-shadow hover:shadow-soft-lg sm:gap-4 sm:px-5 sm:py-4"
    >
      <span className={cn("grid size-11 shrink-0 place-items-center rounded-full", board === "bank" ? "bg-blue/10 text-blue" : "bg-accent text-primary")}>
        {board === "bank" ? <MessagesSquare className="size-5" /> : <BookOpen className="size-5" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-caption text-muted-foreground">
          {t("continue_reading")} · {label}
        </span>
        <span className="mt-0.5 block truncate text-callout font-semibold">{last.title}</span>
      </span>
      <Button size="sm" className="shrink-0" tabIndex={-1}>
        {t("continue")}
        <ArrowRight />
      </Button>
    </a>
  );
}

function QuestionLine({ question, rank }: { question: QuestionRow; rank: number }) {
  const { t } = useI18n();
  const answered = question.answer_status === "source_backed" || question.answer_status === "reviewed";
  return (
    <a
      href={href("bank", [], { open: question.id })}
      className="flex items-center gap-4 border-t border-border px-5 py-3.5 transition-colors first:border-t-0 hover:bg-fill/60"
    >
      <span className="w-5 shrink-0 text-center text-callout font-semibold text-tertiary-foreground tabular-nums">{rank}</span>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-1 text-callout">{question.canonical}</span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-caption text-muted-foreground">
          <TopicTag name={question.group} />
          {answered && (
            <span className="flex items-center gap-0.5 text-success">
              <Check className="size-3" />
              {t("answered")}
            </span>
          )}
        </span>
      </span>
      <span className="shrink-0 rounded-full bg-fill px-2.5 py-0.5 text-caption text-muted-foreground tabular-nums">
        {t("times", { n: question.frequency })}
      </span>
    </a>
  );
}

// Retrieval practice spaced by the scheduler: what is due first, then weak spots, then questions never tried.
function TodayPlan({ summary, canRecord }: { summary: Library["summary"]; canRecord: boolean }) {
  const { t } = useI18n();
  // The server counts never-practised questions as due too; the plan shows them apart.
  const reviews = Math.max(0, summary.due - summary.unseen);
  const view = reviews ? "due" : summary.weak ? "weak" : "unseen";
  const stats = [
    { key: "due", label: t("today_due"), n: reviews, tone: "text-destructive" },
    { key: "weak", label: t("today_weak"), n: summary.weak, tone: "text-warning" },
    { key: "unseen", label: t("today_unseen"), n: summary.unseen, tone: "text-blue" },
  ] as const;
  return (
    <section aria-label={t("today_title")} className="mt-3 flex flex-col gap-4 surface p-4 sm:flex-row sm:items-center sm:p-5">
      <div className="min-w-0 flex-1">
        <h2 className="flex items-center gap-2 text-headline font-semibold">
          <CalendarCheck className="size-[18px] text-primary" />
          {t("today_title")}
        </h2>
        <p className="mt-1 text-footnote text-muted-foreground">{!canRecord ? t("today_temporary") : !reviews ? t("today_done") : t("today_hint")}</p>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:flex sm:gap-5">
        {stats.map((stat) => (
          <a key={stat.key} href={href("bank", [], { view: stat.key })} className="rounded-xl bg-fill/60 px-3 py-2 text-center sm:bg-transparent sm:p-0">
            <span className={cn("block text-title-2 font-bold tabular-nums", stat.n ? stat.tone : "text-tertiary-foreground")}>{stat.n}</span>
            <span className="text-caption text-muted-foreground">{stat.label}</span>
          </a>
        ))}
      </div>
      <Button asChild className="shrink-0">
        <a href={href("bank", [], { view, practice: "1" })}>
          <Play />
          {t("today_start")}
        </a>
      </Button>
    </section>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-2xl bg-fill", className)} />;
}

export function HomePage() {
  const { t, lang } = useI18n();
  const { library, notes, error, refresh } = useBank();
  const lastQuestion = stored<LastRead | null>(keys.lastQuestion, null);
  const lastNote = stored<LastRead | null>(keys.lastNote, null);
  const read = stored<string[]>(keys.read, []).length;
  const today = new Date().toLocaleDateString(lang, { month: "long", day: "numeric", weekday: "long" });

  if (error && !library) {
    return (
      <div className="mx-auto max-w-md px-5 py-24 text-center">
        <p className="text-callout text-muted-foreground">{t(error === "unreachable" ? "unreachable" : "failed")}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => refresh(true)}>
          {t("retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1120px] px-4 pt-8 pb-28 sm:px-6 md:pt-10 md:pb-16">
      <p className="text-caption font-semibold tracking-wide text-primary">{t("today", { d: today })}</p>
      <h1 className="mt-1 text-large-title font-bold">{t("home_title")}</h1>
      <p className="mt-1.5 text-callout text-muted-foreground tabular-nums">
        {library
          ? t("home_summary", { q: library.summary.questions, k: notes?.section_counts.knowledge ?? 0, r: read })
          : t("loading")}
      </p>

      {(lastQuestion || lastNote) && (
        <div className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {lastQuestion && <ContinueCard last={lastQuestion} board="bank" label={t("board_bank")} />}
          {lastNote && <ContinueCard last={lastNote} board="knowledge" label={t("board_knowledge")} />}
        </div>
      )}

      {library && library.summary.questions > 0 && <TodayPlan summary={library.summary} canRecord={library.can_record} />}

      <div className="mt-3 grid grid-cols-2 gap-3 sm:mt-4 sm:gap-4 lg:grid-cols-4">
        {!library ? (
          Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-44" />)
        ) : (
          <>
            <BoardCard
              board="bank"
              icon={MessagesSquare}
              tone="bg-blue/10 text-blue"
              hint={t("board_bank_hint")}
              stat={t("bank_stat", { n: library.summary.questions, g: library.facets.group.length })}
            />
            {notes && (
              <>
                <BoardCard
                  board="knowledge"
                  icon={BookOpen}
                  tone="bg-accent text-primary"
                  hint={t("board_knowledge_hint", { s: notes.collections.length })}
                  stat={t("knowledge_stat", { n: notes.section_counts.knowledge, s: notes.collections.length })}
                />
                <BoardCard
                  board="public"
                  icon={Newspaper}
                  tone="bg-purple/12 text-purple"
                  hint={t("board_public_hint")}
                  stat={t("public_stat", { n: notes.section_counts.experiences, c: notes.facets.companies.length })}
                />
                <BoardCard
                  board="learning"
                  icon={Compass}
                  tone="bg-orange/14 text-warning"
                  hint={t("board_learning_hint")}
                  stat={t("learning_stat", { n: notes.section_counts.learning, k: notes.learning_categories.length })}
                />
              </>
            )}
          </>
        )}
      </div>

      <div className="mt-10 flex items-end justify-between">
        <h2 className="text-title-2 font-bold">{t("top_questions")}</h2>
        <Button variant="outline" size="sm" asChild>
          <a href={href("bank")}>{t("see_all")}</a>
        </Button>
      </div>
      <div className="mt-3.5 overflow-hidden surface">
        {library
          ? library.questions.map((question, index) => <QuestionLine key={question.id} question={question} rank={index + 1} />)
          : Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="m-4 h-10" />)}
      </div>
    </div>
  );
}
