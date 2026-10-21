import { useI18n, type TextKey } from "@/lib/i18n";
import { learningState, setLearning, type LearningState, type NoteDetail, type StudyEdge } from "@/lib/notes";
import { usePref } from "@/lib/prefs";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Markdown, SafeLink } from "./markdown";

function SourceBox({ source }: { source: NoteDetail["source"] }) {
  // The collection's own answer is quoted as published; say where it came from.
  const { t, lang } = useI18n();
  const extra = [source.origin, source.imported_at ? t("imported", { d: new Date(source.imported_at).toLocaleDateString(lang) }) : ""]
    .filter(Boolean)
    .join(" · ");
  return (
    <p className="note-source">
      <strong>{t("note_source")}：</strong>
      {[source.collection, source.chapter, t("source_line", { file: source.file, line: source.line })].join(" › ")}
      {extra && <small>{extra}</small>}
    </p>
  );
}

function LearningControls({ note, onToast }: { note: NoteDetail; onToast: (text: string) => void }) {
  const { t } = useI18n();
  usePref("ibank-notes-learning", 0);
  const state = learningState(note.id, note.reading);
  const change = (value: LearningState | "") => {
    setLearning(note.id, value, note.reading);
    onToast(t("notes_learning_saved"));
  };
  return (
    <section className="my-3 flex flex-wrap items-center gap-x-2 gap-y-2 rounded-xl bg-fill px-3 py-2.5 text-footnote">
      <span className="text-muted-foreground">{t("notes_learning")} ·</span>
      <span className="font-medium">{t(`notes_learning_${state}`)}</span>
      <span className="ml-auto flex flex-wrap gap-1.5">
        {(["review", "mastered"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={state === value}
            onClick={() => change(value)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-caption font-medium transition-colors",
              state === value ? "border-transparent bg-primary text-primary-foreground" : "border-border bg-card hover:bg-fill",
            )}
          >
            {t(`notes_set_${value}`)}
          </button>
        ))}
        <button type="button" onClick={() => change("")} className="px-1.5 text-caption text-primary">
          {t("notes_reset_learning")}
        </button>
      </span>
      <small className="w-full text-caption text-tertiary-foreground">{t("notes_local_hint")}</small>
    </section>
  );
}

function StudyRelations({ note, onOpenNote }: { note: NoteDetail; onOpenNote: (id: string) => void }) {
  const { t } = useI18n();
  const groups: [StudyEdge[] | undefined, TextKey][] = [
    [note.study_notes, "notes_study_related"],
    [note.public_experiences, "notes_public_related"],
  ];
  return (
    <>
      {note.study_links_incomplete ? <p className="notice">{t("notes_relation_incomplete")}</p> : null}
      {groups.map(([edges, label]) =>
        edges?.length ? (
          <details className="source-evidence linked" key={label}>
            <summary>{t(label, { n: edges.length })}</summary>
            <p className="hint">{t("notes_relation_hint")}</p>
            <ul className="linked-list">
              {edges.map((edge) => (
                <li key={edge.id + edge.question_quote}>
                  <p className="hint px-3.5 pt-2">{edge.question_quote}</p>
                  <button type="button" className="linked-item" onClick={() => onOpenNote(edge.id)}>
                    <span className="linked-title">{edge.title}</span>
                    <span className="question-meta">
                      {[edge.company, edge.interview_time, edge.area_title, edge.topic_title, t(edge.relation === "answers" ? "relation_answers" : "relation_covers")]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </button>
                  <details className="source-evidence">
                    <summary>{t("notes_relation_evidence")}</summary>
                    <p className="hint">{edge.reason}</p>
                    <blockquote className="hint">{edge.answer_quote}</blockquote>
                  </details>
                </li>
              ))}
            </ul>
          </details>
        ) : null,
      )}
    </>
  );
}

export function NoteView({
  note: n,
  revealed,
  onReveal,
  onOpenQuestion,
  onOpenNote,
  onToast,
}: {
  note: NoteDetail;
  revealed: boolean;
  onReveal: () => void;
  onOpenQuestion: (id: string) => void;
  onOpenNote: (id: string) => void;
  onToast: (text: string) => void;
}) {
  const { t } = useI18n();
  const value = n.experience;
  const where = value ? t(`notes_domain_${value.domain}` as TextKey) : [n.area_title, n.topic_title].filter(Boolean).join(" › ") || n.chapter_title;
  const tags = [
    n.kind !== "info" && <span className="tag" key="v">{t(`notes_verification_${n.verification}` as TextKey)}</span>,
    n.question_type && <span className="tag" key="q">{t(`notes_question_type_${n.question_type}` as TextKey)}</span>,
    ...(n.tags ?? []).map((tag) => <span className="tag" key={"t" + tag}>{tag}</span>),
    n.marked && <span className="tag mark" key="m">{t("marked")}</span>,
    n.asked > 0 && <span className="tag asked" key="a">{t("asked_times", { n: n.asked })}</span>,
  ].filter(Boolean);
  const time = value?.interview_time
    ? t("notes_experience_time") + "：" + value.interview_time + (!value.year ? " · " + t("notes_experience_year_unknown") : "")
    : t("notes_experience_time_unknown");
  const quotes = [...new Map((value?.facts ?? []).map((fact) => [fact.quote + "\n" + (fact.url || ""), fact])).values()];

  return (
    <>
      <p className="reading-meta">
        <span className="topic">{where}</span>
        <span>{(value ? t("notes_public_source") + "：" : "") + n.collection_title}</span>
      </p>
      <h1 className="reading-title">{n.title}</h1>
      {tags.length > 0 && <div className="tags">{tags}</div>}
      {value && (
        <>
          <p className="reading-meta">
            {[value.company || t("notes_experience_company_unknown"), value.role, value.round, n.kind === "interview" ? time : "",
              value.published_time ? t("notes_experience_published") + "：" + value.published_time : ""]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {value.summary && <p className="hint">{value.summary}</p>}
          {value.incomplete && <p className="notice">{t("notes_experience_incomplete")}</p>}
        </>
      )}
      {n.kind !== "info" && (
        <>
          <p className="note-reference-warning">{t(value ? "notes_experience_warning" : (`notes_warning_${n.verification}` as TextKey))}</p>
          <LearningControls note={n} onToast={onToast} />
          {n.evidence?.map((url) => (
            <SafeLink key={url} url={url} />
          ))}
        </>
      )}
      {!n.body ? (
        <>
          <p className="no-answer">{t("no_note_answer")}</p>
          <SourceBox source={n.source} />
        </>
      ) : revealed ? (
        <section className="answer-body">
          <h2 className="answer-head">{t(n.kind === "info" ? "notes_kind_info" : "notes_original_text")}</h2>
          <Markdown text={n.body} />
          <SourceBox source={n.source} />
        </section>
      ) : (
        <Button className="reveal" onClick={onReveal}>
          {t("show_answer")}
        </Button>
      )}
      {quotes.length > 0 && (
        <details className="source-evidence">
          <summary>{t("notes_experience_evidence")}</summary>
          {quotes.map((fact) => (
            <div key={fact.quote + fact.url}>
              <p className="hint">{fact.quote}</p>
              {fact.url && <SafeLink url={fact.url} />}
            </div>
          ))}
        </details>
      )}
      {n.questions.length > 0 && (
        <section className="linked">
          <h3>{t("asked_in", { n: n.questions.length })}</h3>
          <ul className="linked-list">
            {n.questions.map((q) => (
              <li key={q.id}>
                <button type="button" className="linked-item" onClick={() => onOpenQuestion(q.id)}>
                  <span className="linked-title">{q.canonical}</span>
                  <span className="question-meta">
                    <span>{t("seen", { n: q.frequency })}</span>
                    <span>{t(q.relation === "answers" ? "relation_answers" : "relation_covers")}</span>
                    {q.answered && <span className="has-answer">✓ {t("status_answered")}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <StudyRelations note={n} onOpenNote={onOpenNote} />
    </>
  );
}
