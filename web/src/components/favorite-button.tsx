import { Popover } from "radix-ui";
import { Check, Plus, Star } from "lucide-react";
import { useState } from "react";
import { useFavorites } from "@/lib/favorites";
import { useToast } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// The star in the reader's toolbar: tick the folders an item belongs to, or start a new one.
export function FavoriteButton({ itemId }: { itemId: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const { folders, canWrite, change, holding } = useFavorites();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  if (!canWrite || !folders) return null;
  const inside = new Set(holding(itemId).map((f) => f.id));

  const run = async (job: () => Promise<void>) => {
    setBusy(true);
    try {
      await job();
    } catch (error) {
      toast(error instanceof Error ? error.message : t("failed"));
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: string, folderName: string) =>
    run(async () => {
      const on = inside.has(id);
      await change({ action: on ? "remove" : "add", folder: id, item: itemId });
      toast(t(on ? "fav_removed" : "fav_saved", { f: folderName }));
    });

  const create = (value: string) =>
    run(async () => {
      const next = await change({ action: "create", name: value });
      const created = next[next.length - 1];
      await change({ action: "add", folder: created.id, item: itemId });
      setName("");
      toast(t("fav_saved", { f: created.name }));
    });

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        // The first star needs no setup: it creates a default folder.
        if (next && !folders.length) return void create(t("fav_default"));
        setOpen(next);
      }}
    >
      <Popover.Trigger
        aria-label={t("fav")}
        title={t("fav")}
        className={cn(
          "grid size-8 place-items-center rounded-full transition-colors hover:bg-fill",
          inside.size ? "text-orange" : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Star className="size-[18px]" fill={inside.size ? "currentColor" : "none"} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={6} className="z-50 w-64 rounded-2xl border border-border bg-popover p-1.5 shadow-soft-lg outline-none">
          <p className="px-2.5 pt-1.5 pb-1 text-caption font-medium text-tertiary-foreground">{t("fav_add")}</p>
          <div className="max-h-64 overflow-y-auto">
            {folders.map((folder) => (
              <button
                key={folder.id}
                type="button"
                disabled={busy}
                onClick={() => toggle(folder.id, folder.name)}
                className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-subhead hover:bg-fill"
              >
                <span className={cn("grid size-4 shrink-0 place-items-center rounded border", inside.has(folder.id) ? "border-primary bg-primary text-primary-foreground" : "border-border")}>
                  {inside.has(folder.id) && <Check className="size-3" />}
                </span>
                <span className="min-w-0 flex-1 truncate">{folder.name}</span>
                <span className="text-caption text-tertiary-foreground tabular-nums">{folder.items.length}</span>
              </button>
            ))}
          </div>
          <form
            className="mt-1 flex items-center gap-1.5 border-t border-border px-1.5 pt-2 pb-1"
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim()) create(name.trim());
            }}
          >
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={60}
              placeholder={t("fav_new")}
              aria-label={t("fav_name")}
              className="h-8 min-w-0 flex-1 rounded-lg bg-fill px-2.5 text-footnote outline-none focus:ring-2 focus:ring-ring/30"
            />
            <button type="submit" disabled={busy || !name.trim()} aria-label={t("fav_create")} className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-40">
              <Plus className="size-4" />
            </button>
          </form>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
