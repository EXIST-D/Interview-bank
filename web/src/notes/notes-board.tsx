import { useCallback, useEffect, useRef, useState } from "react";
import { useBank } from "@/lib/bank";
import { useToast } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { learningState, noteDetail, notesPage, recordVisit, sectionOf, type NoteCardData, type NoteDetail, type NotesPage, type NotesSection } from "@/lib/notes";
import { markRead } from "@/lib/prefs";
import { noteSaved } from "@/lib/personal-note-mark";
import { thinkFirst, type useReading } from "@/lib/reading";
import { navigate } from "@/lib/router";
import { keys, store } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/app-shell";
import { NoteView } from "@/reader/note-view";
import { ReaderFrame } from "@/reader/reader-frame";

/** One list of notes with pagination; a browser-local learning filter fetches every matching card first. */
export function useNotesList(params: (offset: number, limit?: number) => URLSearchParams, learning: string) {
  const { t } = useI18n();
  const [data, setData] = useState<NotesPage | null>(null);
  const [rows, setRows] = useState<NoteCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  const load = useCallback(
    async (offset = 0) => {
      const current = ++generation.current;
      setLoading(true);
      setError(null);
      try {
        let next = await notesPage(params(offset));
        let cards = next.notes;
        if (learning !== "all") {
          let at = cards.length;
          while (at < next.total) {
            const more = await notesPage(params(at, 1000));
            if (current !== generation.current) return;
            if (!more.notes.length) break;
            cards = cards.concat(more.notes);
            at += more.notes.length;
          }
          cards = cards.filter((n) => learningState(n.id, n.reading) === learning);
          next = { ...next, total: cards.length, ids: cards.map((n) => n.id) };
        }
        if (current !== generation.current) return;
        setData(next);
        setRows((previous) => (offset ? [...previous, ...cards] : cards));
      } catch (cause) {
        if (current === generation.current) setError(cause instanceof Error ? cause.message : t("failed"));
      } finally {
        if (current === generation.current) setLoading(false);
      }
    },
    [params, learning, t],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  return { data, rows, loading, error, load };
}

type Reading = ReturnType<typeof useReading>;

/** The reader column for notes: loads the open note, records the visit and hands links to other boards. */
export function NoteReader({
  reading,
  ids,
  accepts,
  rows,
}: {
  reading: Reading;
  ids: string[];
  /** Notes this board shows itself; any other note is sent to the board where it belongs. */
  accepts: (note: NoteDetail) => boolean;
  rows: NoteCardData[];
}) {
  const { t } = useI18n();
  const toast = useToast();
  const { library } = useBank();
  const { openId, open, close, step, index, layout, setLayout, focused, notesOpen, setNotesOpen } = reading;
  const [detail, setDetail] = useState<NoteDetail | null>(null);
  const [revealed, setRevealed] = useState(true);

  useEffect(() => {
    if (!openId) {
      setDetail(null);
      return;
    }
    let live = true;
    noteDetail(openId)
      .then((note) => {
        if (!live) return;
        if (!accepts(note)) {
          history.replaceState(null, "", noteHref(note) + (notesOpen ? "&panel=notes" : ""));
          dispatchEvent(new HashChangeEvent("hashchange"));
          return;
        }
        setDetail(note);
        setRevealed(!thinkFirst());
        if (note.kind !== "info") recordVisit(note.id, note.reading);
        markRead(note.id);
        store(keys.lastNote, { id: note.id, title: note.title.slice(0, 40) + (note.title.length > 40 ? "…" : "") });
      })
      .catch((cause) => {
        if (!live) return;
        toast(cause instanceof Error ? cause.message : t("load_failed"));
        close();
      });
    return () => {
      live = false;
    };
    // accepts is a fresh closure per render; only the open note decides when to reload.
  }, [openId, toast, t, close]);

  useEffect(() => {
    if (index < 0) return;
    for (const neighbour of [ids[index + 1], ids[index - 1]]) if (neighbour) noteDetail(neighbour).catch(() => {});
  }, [index, ids]);

  // Space reveals the answer through the shared keyboard handler.
  const { registerReveal } = reading;
  useEffect(() => {
    registerReveal(() => setRevealed(true), revealed);
  }, [registerReveal, revealed]);

  return (
    <div className={cn(openId ? "fixed inset-0 z-50 wide:static wide:z-auto" : "hidden wide:block", "min-h-0 min-w-0")}>
      {openId && detail && (detail.id === openId || detail.reading?.note_ids.includes(openId)) ? (
        <ReaderFrame
          contentKey={detail.id}
          nav={{ index, total: ids.length, onStep: step }}
          onBack={close}
          listCollapsed={layout.list}
          onToggleList={() => setLayout({ list: !layout.list, focus: false })}
          focused={focused}
          onToggleFocus={() => setLayout({ focus: !layout.focus })}
          hasAnswer={Boolean(detail.body)}
          revealed={revealed}
          onToggleAnswer={() => setRevealed(!revealed)}
          notesOpen={notesOpen}
          onNotesOpen={setNotesOpen}
          personalNote={detail.kind !== "info" && library ? {
            title: detail.title,
            account: library.account || library.name,
            saved: detail.my_answer ?? null,
            canWrite: Boolean(library.can_write_personal),
            onSaved: (value) => {
              noteSaved(detail.id, Boolean(value));
              setDetail((current) => current?.id === detail.id ? { ...current, my_answer: value, has_my_answer: Boolean(value) } : current);
              noteDetail(detail.id, true).catch(() => {});
            },
            onReload: async () => {
              const latest = await noteDetail(detail.id, true);
              setDetail((current) => current?.id === detail.id ? latest : current);
              return latest.my_answer ?? null;
            },
          } : undefined}
        >
          <NoteView
            note={detail}
            revealed={revealed}
            onReveal={() => setRevealed(true)}
            onOpenQuestion={(id) => navigate("bank", [], { open: id })}
            onOpenNote={(id) => (rows.some((n) => n.id === id) ? open(id) : navigate("knowledge", [], { open: id }))}
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
  );
}

/** Where a note lives in the new reader. */
export function noteHref(note: { id: string; collection: string; section?: NotesSection; experience?: unknown; kind: string }) {
  const section = sectionOf(note);
  if (section === "experiences") return "#/public?open=" + encodeURIComponent(note.id);
  if (section === "learning") return "#/learning/all?open=" + encodeURIComponent(note.id);
  return "#/knowledge/" + encodeURIComponent(note.collection) + "?open=" + encodeURIComponent(note.id);
}
