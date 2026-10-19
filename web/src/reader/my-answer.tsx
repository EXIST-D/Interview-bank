import { PenLine } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type MyAnswer as Saved } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { RichText } from "./markdown";

const MAX = 20000;
const draftKey = (id: string) => "ibank-my-answer-draft:" + id;

function readDraft(id: string) {
  try {
    return localStorage.getItem(draftKey(id));
  } catch {
    return null;
  }
}

function writeDraft(id: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(draftKey(id));
    else localStorage.setItem(draftKey(id), value);
  } catch {
    /* storage blocked: the draft lasts while the editor is open */
  }
}

// The person's own answer (questions) or note (collection entries): written and kept by them, independent of the
// reference text, and may stay empty.
export function MyAnswer({
  questionId,
  saved,
  canWrite,
  onSaved,
  onReload,
  onToast,
  note = false,
}: {
  /** A question ID or a collection note ID. */
  questionId: string;
  /** Labels it "my note" for collection entries. */
  note?: boolean;
  saved: Saved | null;
  canWrite: boolean;
  onSaved: (value: Saved | null) => void;
  /** Fetch the question again after another device saved first; the draft stays in the editor. */
  onReload: () => void;
  onToast: (text: string) => void;
}) {
  const { t, lang } = useI18n();
  const label = t(note ? "my_note" : "my_answer");
  const draft = readDraft(questionId);
  const [editing, setEditing] = useState(() => canWrite && draft !== null && draft !== (saved?.text ?? ""));
  const [text, setText] = useState(() => draft ?? saved?.text ?? "");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const area = useRef<HTMLTextAreaElement>(null);

  const announced = useRef(false);
  useEffect(() => {
    // A restored draft is announced once, when the question opens.
    if (announced.current) return;
    announced.current = true;
    if (editing && draft !== null && draft !== (saved?.text ?? "")) onToast(t("my_answer_draft"));
  }, [editing, draft, saved, onToast, t]);

  useEffect(() => {
    const node = area.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = Math.min(node.scrollHeight + 2, 560) + "px";
  }, [text, editing]);

  if (!canWrite && !saved) return null;

  const save = async (value: string) => {
    setBusy(true);
    setConflict(null);
    try {
      const result = await api<{ my_answer: Saved | null }>("/api/my-answer", {
        item_id: questionId,
        text: value,
        expected_updated_at: saved?.updated_at ?? "",
      });
      writeDraft(questionId, null);
      setEditing(false);
      setText(result.my_answer?.text ?? "");
      onSaved(result.my_answer);
      onToast(t(result.my_answer ? "my_answer_saved" : "my_answer_cleared"));
    } catch (error) {
      const message = error instanceof Error ? error.message : t("failed");
      if (/changed elsewhere/i.test(message)) setConflict(message);
      else onToast(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="my-answer" aria-label={label}>
      <h2 className="answer-head">
        <PenLine className="size-3.5" />
        {label}
        {saved && !editing && <small className="ml-auto font-normal">{t("my_answer_updated", { d: new Date(saved.updated_at).toLocaleDateString(lang) })}</small>}
      </h2>
      {editing ? (
        <>
          {saved && text.trim() !== saved.text && (
            <details className="my-answer-saved" open={Boolean(conflict) || undefined}>
              <summary>{t("my_answer_saved_version")}</summary>
              <RichText text={saved.text} />
            </details>
          )}
          <textarea
            ref={area}
            className="note my-answer-input"
            value={text}
            maxLength={MAX}
            autoFocus
            placeholder={t("my_answer_placeholder")}
            aria-label={label}
            onChange={(event) => {
              setText(event.target.value);
              writeDraft(questionId, event.target.value);
            }}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") save(text);
            }}
          />
          {conflict && (
            <p className="warning">
              {conflict}{" "}
              <button type="button" className="font-medium underline" onClick={onReload}>
                {t("my_answer_reload")}
              </button>
            </p>
          )}
          <div className="actions items-center">
            <Button size="sm" disabled={busy || text.trim() === (saved?.text ?? "")} onClick={() => save(text)} aria-keyshortcuts="Meta+Enter">
              {t("my_answer_save")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => {
                writeDraft(questionId, null);
                setText(saved?.text ?? "");
                setEditing(false);
                setConflict(null);
              }}
            >
              {t("my_answer_cancel")}
            </Button>
            {saved && (
              <Button
                size="sm"
                variant="link"
                className="text-destructive"
                disabled={busy}
                onClick={() => window.confirm(t("my_answer_clear_confirm")) && save("")}
              >
                {t("my_answer_clear")}
              </Button>
            )}
            <small className="ml-auto text-caption text-tertiary-foreground tabular-nums">{t("my_answer_count", { n: text.length })}</small>
          </div>
        </>
      ) : saved ? (
        <>
          <RichText text={saved.text} />
          {canWrite && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              {t("my_answer_edit")}
            </Button>
          )}
        </>
      ) : (
        <div className="my-answer-empty">
          <p className="hint">{t(note ? "my_note_hint" : "my_answer_hint")}</p>
          <Button size="sm" variant="tinted" onClick={() => setEditing(true)}>
            <PenLine />
            {t(note ? "my_note_write" : "my_answer_write")}
          </Button>
        </div>
      )}
    </section>
  );
}
