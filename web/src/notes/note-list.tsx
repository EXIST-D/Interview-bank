import { ChevronDown, ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useI18n, type TextKey } from "@/lib/i18n";
import { learningState, noteDetail, type LearningState, type NoteCardData } from "@/lib/notes";
import { usePref } from "@/lib/prefs";
import { store, stored } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Markdown } from "@/reader/markdown";

export function Highlight({ text, words }: { text: string; words: string }) {
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

const STATE_TONE: Record<LearningState, string> = {
  unread: "",
  read: "text-muted-foreground",
  review: "text-warning",
  mastered: "text-success",
};

function NoteRow({
  note,
  current,
  state,
  words,
  crossSource,
  onOpen,
}: {
  note: NoteCardData;
  current: boolean;
  state: LearningState;
  words: string;
  crossSource: boolean;
  onOpen: () => void;
}) {
  const { t } = useI18n();
  const [peek, setPeek] = useState<ReactNode | null>(null);
  const experience = note.experience;
  const topic = note.topic_title || note.area_title || note.chapter_title;
  const meta = [
    experience ? t(`notes_domain_${experience.domain}` as TextKey) + " · " + topic : (crossSource ? note.collection_title + " · " : "") + topic,
    experience &&
      [experience.company || t("notes_experience_company_unknown"), experience.interview_time || (note.kind === "interview" ? t("notes_experience_time_unknown") : "")]
        .filter(Boolean)
        .join(" · "),
    !experience && t(`notes_kind_${note.kind}` as TextKey),
    note.question_type && t(`notes_question_type_${note.question_type}` as TextKey),
    note.public_experience_count ? t("notes_public_count", { n: note.public_experience_count }) : "",
    note.study_note_count ? t("notes_study_count", { n: note.study_note_count }) : "",
  ].filter(Boolean) as string[];

  const togglePeek = async () => {
    if (peek) return setPeek(null);
    setPeek(<p className="text-footnote text-muted-foreground">{t("loading")}</p>);
    try {
      const detail = await noteDetail(note.id);
      setPeek(
        detail.body ? (
          <div className="ib-reading ib-peek line-clamp-[10]">
            <Markdown text={detail.body} />
          </div>
        ) : (
          <p className="text-footnote text-muted-foreground">{t("no_note_answer")}</p>
        ),
      );
    } catch (error) {
      setPeek(<p className="text-footnote text-destructive">{error instanceof Error ? error.message : t("failed")}</p>);
    }
  };

  return (
    <li className={cn("rounded-2xl border bg-card shadow-soft-sm", current ? "border-primary shadow-[0_0_0_3px_var(--accent)]" : "border-transparent")}>
      <div className="flex items-start">
        <button type="button" data-id={note.id} onClick={onOpen} className="min-w-0 flex-1 rounded-2xl px-4 py-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/40">
          <span className={cn("line-clamp-2 text-subhead leading-snug font-medium", state !== "unread" && !current && "text-muted-foreground")}>
            <Highlight text={note.title} words={words} />
          </span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-caption text-muted-foreground">
            {meta.map((item) => (
              <span key={item}>{item}</span>
            ))}
            {note.marked && <span className="text-warning">{t("marked")}</span>}
            {note.asked > 0 && <span className="text-success">{t("asked_times", { n: note.asked })}</span>}
            {state !== "unread" && <span className={STATE_TONE[state]}>{t(`notes_learning_${state}`)}</span>}
            {note.has_my_answer && <span className="text-primary">{t("my_note")}</span>}
            {experience && <span className="text-tertiary-foreground">{t("notes_public_source") + "：" + note.collection_title}</span>}
          </span>
        </button>
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

export type GroupBy = ((note: NoteCardData) => { key: string; label: string }) | null;

// Chapter or topic groups fold; folding all of them turns the list into a table of contents.
export function NoteList({
  notes,
  openId,
  words,
  crossSource,
  groupBy,
  onOpen,
}: {
  notes: NoteCardData[];
  openId: string | null;
  words: string;
  crossSource: boolean;
  groupBy: GroupBy;
  onOpen: (id: string) => void;
}) {
  const { t } = useI18n();
  usePref("ibank-notes-learning", 0);
  const [readList] = usePref<string[]>("ibank-read", []);
  const read = new Set(readList);
  const [folded, setFolded] = useState(() => new Set(stored<string[]>("ibank-folded", [])));
  const toggle = (key: string) => {
    const next = new Set(folded);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    store("ibank-folded", [...next]);
    setFolded(next);
  };
  const row = (note: NoteCardData) => (
    <NoteRow
      key={note.id}
      note={note}
      current={note.id === openId}
      state={learningState(note.id, note.reading, read)}
      words={words}
      crossSource={crossSource}
      onOpen={() => onOpen(note.id)}
    />
  );
  if (!groupBy) return <ol className="flex flex-col gap-2">{notes.map(row)}</ol>;

  // A group can recur when the order does not follow it (e.g. the previous sort while a new page loads);
  // each run gets its own React key so no rows are left behind.
  const groups: { key: string; id: string; label: string; notes: NoteCardData[] }[] = [];
  for (const note of notes) {
    const { key, label } = groupBy(note);
    if (groups.at(-1)?.key !== key) groups.push({ key, id: `${key}#${groups.length}`, label, notes: [] });
    groups.at(-1)!.notes.push(note);
  }
  return (
    <div className="flex flex-col gap-3">
      {groups.map((group) => {
        const closed = folded.has("list:" + group.key);
        const done = group.notes.filter((n) => learningState(n.id, n.reading, read) !== "unread").length;
        return (
          <section key={group.id}>
            <button
              type="button"
              aria-expanded={!closed}
              onClick={() => toggle("list:" + group.key)}
              className="sticky top-0 z-[1] flex w-full items-center gap-1.5 bg-background/90 px-1 py-1.5 text-left text-footnote font-semibold backdrop-blur"
            >
              <ChevronRight className={cn("size-3.5 shrink-0 text-muted-foreground transition-transform", !closed && "rotate-90")} />
              <span className="min-w-0 flex-1 truncate">{group.label}</span>
              <span className="shrink-0 text-caption font-normal text-muted-foreground tabular-nums">{t("group_count", { n: group.notes.length, r: done })}</span>
            </button>
            {!closed && <ol className="mt-1.5 flex flex-col gap-2">{group.notes.map(row)}</ol>}
          </section>
        );
      })}
    </div>
  );
}

export function foldAll(keys: string[], on: boolean) {
  const folded = new Set(stored<string[]>("ibank-folded", []));
  for (const key of keys) {
    if (on) folded.add("list:" + key);
    else folded.delete("list:" + key);
  }
  store("ibank-folded", [...folded]);
}
