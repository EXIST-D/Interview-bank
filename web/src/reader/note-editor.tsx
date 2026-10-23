import { Check, RotateCcw } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api, ApiError, type MyAnswer } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Markdown } from "./markdown";

const LiveMarkdownEditor = lazy(() => import("./live-markdown").then((module) => ({ default: module.LiveMarkdownEditor })));

type Draft = { text: string; base: string };
const memory = new Map<string, Draft>();
// Source entry IDs are shared by accounts. A draft must belong to this account and bank path, too.
const draftKey = (account: string, id: string) => "ibank-note-draft:" + JSON.stringify([location.pathname, account, id]);

function readDraft(key: string): Draft | null {
  if (memory.has(key)) return memory.get(key)!;
  try {
    const draft = JSON.parse(localStorage.getItem(key) ?? "null");
    if (draft && typeof draft.text === "string" && typeof draft.base === "string" && draft.text.length <= 20000) return draft;
  } catch { /* storage may be blocked */ }
  return null;
}

function keepDraft(key: string, draft: Draft | null) {
  if (draft) memory.set(key, draft);
  else memory.delete(key);
  try {
    if (draft) localStorage.setItem(key, JSON.stringify(draft));
    else localStorage.removeItem(key);
  } catch { /* The in-memory copy survives closing the panel and switching entries in this tab. */ }
}

export type PersonalNote = {
  title: string;
  account: string;
  saved: MyAnswer | null;
  canWrite: boolean;
  onSaved: (value: MyAnswer | null) => void;
  onReload: () => Promise<MyAnswer | null>;
};

/** The storage/API name remains my_answer so earlier personal notes and version history stay intact. */
export function NoteEditor({ itemId, note, onToast }: { itemId: string; note: PersonalNote; onToast: (message: string) => void }) {
  const { t, lang } = useI18n();
  const key = draftKey(note.account, itemId);
  const [draft] = useState(() => readDraft(key));
  const [saved, setSaved] = useState(note.saved);
  const [text, setText] = useState(() => draft?.text ?? note.saved?.text ?? "");
  const [base, setBase] = useState(() => draft?.base ?? note.saved?.updated_at ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(Boolean(draft && draft.base !== (note.saved?.updated_at ?? "")));
  const [restored, setRestored] = useState(Boolean(draft && draft.text !== (note.saved?.text ?? "")));
  const alive = useRef(true);
  const inFlight = useRef(false);
  const previousSaved = useRef(note.saved);
  const dirty = text !== (saved?.text ?? "");

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  // A save can complete while this panel is closed and reopened. A newer draft is never replaced.
  useEffect(() => {
    if (previousSaved.current?.updated_at === note.saved?.updated_at) return;
    const prior = previousSaved.current;
    previousSaved.current = note.saved;
    setSaved(note.saved);
    if (text === (prior?.text ?? "") || text === (note.saved?.text ?? "")) {
      setText(note.saved?.text ?? "");
      setBase(note.saved?.updated_at ?? "");
      setConflict(false);
      keepDraft(key, null);
    } else if (base !== (note.saved?.updated_at ?? "")) setConflict(true);
  }, [note.saved, text, base, key]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const change = (value: string) => {
    setText(value);
    setRestored(false);
    keepDraft(key, value === (saved?.text ?? "") ? null : { text: value, base });
  };

  const save = async () => {
    if (inFlight.current || !note.canWrite || !dirty || conflict || text.length > 20000) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    const snapshot = { text, base };
    try {
      const result = await api<{ my_answer: MyAnswer | null }>("/api/my-answer", {
        item_id: itemId, text: snapshot.text, expected_updated_at: snapshot.base,
      });
      const pending = readDraft(key);
      if (pending?.text === snapshot.text && pending.base === snapshot.base) keepDraft(key, null);
      note.onSaved(result.my_answer);
      if (alive.current) {
        setSaved(result.my_answer);
        setText(result.my_answer?.text ?? "");
        setBase(result.my_answer?.updated_at ?? "");
        setRestored(false);
        setConflict(false);
      }
      onToast(t(result.my_answer ? "my_answer_saved" : "my_answer_cleared"));
    } catch (cause) {
      if (!alive.current) return;
      if (cause instanceof ApiError && /changed elsewhere/i.test(cause.message)) setConflict(true);
      else setError(cause instanceof Error ? cause.message : t("failed"));
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  };

  const reload = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const latest = await note.onReload();
      if (!alive.current) return;
      previousSaved.current = latest;
      setSaved(latest);
      setBase(latest?.updated_at ?? "");
      setConflict(false);
      // Keep the person's draft; the latest server text remains available for comparison below.
      keepDraft(key, text === (latest?.text ?? "") ? null : { text, base: latest?.updated_at ?? "" });
    } catch (cause) {
      if (alive.current) setError(cause instanceof Error ? cause.message : t("failed"));
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  };

  return (
    <div className="ib-note-editor">
      <div className="ib-note-content">
        {conflict && <div role="alert" className="mb-3 rounded-xl bg-orange/12 px-3 py-2.5 text-footnote text-warning"><p>{t("note_conflict")}</p><button type="button" disabled={busy} onClick={reload} className="mt-1 font-medium underline">{t("note_reload")}</button></div>}
        {error && <p role="alert" className="mb-3 rounded-xl bg-destructive/10 p-3 text-footnote text-destructive">{error}</p>}
        <Suspense fallback={<p role="status" className="p-4 text-footnote text-muted-foreground">{t("loading")}</p>}>
          <LiveMarkdownEditor value={text} readOnly={busy || !note.canWrite} onChange={change} onSave={save} />
        </Suspense>
        {saved && dirty && <details className="ib-note-comparison rounded-xl border border-border px-3 py-2 text-footnote"><summary className="cursor-pointer text-muted-foreground">{t("my_answer_saved_version")}</summary><div className="ib-reading ib-note-preview mt-2"><Markdown text={saved.text} /></div></details>}
      </div>
      <footer className="pb-safe shrink-0 border-t border-border px-4 pt-3">
        <p aria-live="polite" className="mb-2 flex min-h-4 items-center gap-1.5 text-caption text-muted-foreground">
          {!dirty && saved && <Check className="size-3.5 text-success" />}
          {busy ? t("note_saving") : dirty ? t(restored ? "my_answer_draft" : "note_draft") : saved ? t("my_answer_updated", { d: new Date(saved.updated_at).toLocaleString(lang, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) }) : t("my_note_hint")}
        </p>
        <div className="mb-3 flex items-center gap-2">
          {note.canWrite && <><Button size="sm" disabled={busy || !dirty || conflict} onClick={save} aria-keyshortcuts="Control+Enter Meta+Enter">{t("my_answer_save")}</Button>
            <button type="button" className="ib-note-reset" title={t("note_discard")} aria-label={t("note_discard")} disabled={busy || !dirty} onClick={() => {
              if (!window.confirm(t("note_discard_confirm"))) return;
              keepDraft(key, null); setText(saved?.text ?? ""); setBase(saved?.updated_at ?? ""); setConflict(false); setRestored(false); setError("");
            }}><RotateCcw className="size-3.5" /></button></>}
          <span className="ml-auto text-caption text-tertiary-foreground tabular-nums">{text.length.toLocaleString(lang)} / 20,000</span>
        </div>
      </footer>
    </div>
  );
}
