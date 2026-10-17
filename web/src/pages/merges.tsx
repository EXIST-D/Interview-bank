import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n, type TextKey } from "@/lib/i18n";
import { Button } from "@/components/ui/button";

export type MergeItem = { run_id: string; question_id: string; question: string; target: string; reason: string; decision?: { action: string } | null };
const ACTIONS: [string, TextKey][] = [
  ["MERGE_VARIANT", "merge_same"],
  ["KEEP_RELATED", "merge_related"],
  ["KEEP_DISTINCT", "merge_distinct"],
];

/** Uncertain merges staged by the agent; only a writable reader can record decisions. */
export function useMerges(enabled: boolean) {
  const [items, setItems] = useState<MergeItem[]>([]);
  const reload = useCallback(async () => {
    if (!enabled) return setItems([]);
    try {
      setItems((await api<{ items: MergeItem[] }>("/api/dedupe-reviews")).items);
    } catch {
      setItems([]);
    }
  }, [enabled]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { items, reload, open: items.filter((item) => !item.decision).length };
}

function Decision({ item, onSaved, onToast }: { item: MergeItem; onSaved: () => void; onToast: (text: string) => void }) {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const decide = async (action: string) => {
    if (!note.trim()) return setError(t("merge_need_note"));
    setBusy(true);
    setError(null);
    try {
      await api("/api/dedupe-decision", { run_id: item.run_id, question_id: item.question_id, action, note });
      onToast(t("merge_saved", { run: item.run_id }));
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <textarea className="note" maxLength={2000} placeholder={t("merge_note")} aria-label={t("merge_note")} value={note} onChange={(event) => setNote(event.target.value)} />
      {error && <p className="warning">{error}</p>}
      <div className="actions">
        {ACTIONS.map(([action, label]) => (
          <Button key={action} size="sm" variant={action === "MERGE_VARIANT" ? "default" : "outline"} disabled={busy} onClick={() => decide(action)}>
            {t(label)}
          </Button>
        ))}
      </div>
    </>
  );
}

export function Merges({ open, onOpenChange, items, onChanged, onToast }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: MergeItem[];
  onChanged: () => void;
  onToast: (text: string) => void;
}) {
  const { t } = useI18n();
  const labels = Object.fromEntries(ACTIONS.map(([action, label]) => [action, t(label)]));
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-3xl bg-background p-4 shadow-soft-lg outline-none wide:inset-x-auto wide:top-[6dvh] wide:bottom-auto wide:left-1/2 wide:max-h-[88dvh] wide:w-[min(720px,92vw)] wide:-translate-x-1/2 wide:rounded-3xl">
          <div className="flex items-center justify-between pb-2">
            <Dialog.Title className="text-headline font-semibold">{t("merges")}</Dialog.Title>
            <Dialog.Close aria-label={t("close")} className="grid size-8 place-items-center rounded-full bg-fill text-muted-foreground">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="pb-3 text-footnote text-muted-foreground">{t("merge_intro")}</Dialog.Description>
          {!items.length && <p className="text-footnote text-muted-foreground">{t("merge_none")}</p>}
          <div className="ib-reading flex flex-col gap-3 !p-0">
            {items.map((item) => (
              <section key={item.run_id + item.question_id} className="surface p-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  {([["merge_new", item.question], ["merge_existing", item.target]] as [TextKey, string][]).map(([label, text]) => (
                    <div key={label} className="rounded-xl bg-fill px-3 py-2.5">
                      <small className="text-caption text-muted-foreground">{t(label)}</small>
                      <p className="mt-1 text-subhead leading-relaxed">{text}</p>
                    </div>
                  ))}
                </div>
                <p className="hint mt-2">{t("merge_reason", { r: item.reason })}</p>
                {item.decision ? (
                  <p className="hint font-medium">{t("merge_decided", { a: labels[item.decision.action] ?? item.decision.action })}</p>
                ) : (
                  <Decision item={item} onSaved={onChanged} onToast={onToast} />
                )}
              </section>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
