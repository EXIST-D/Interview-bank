import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import { useI18n, type TextKey } from "@/lib/i18n";
import type { SourceCard } from "@/lib/notes";
import { SafeLink } from "@/reader/markdown";

export function languageLabel(t: (key: TextKey) => string, value?: string) {
  return value === "zh-CN" ? t("notes_language_zh") : value === "en" ? t("notes_language_en") : value === "mixed" ? t("notes_language_mixed") : value || "";
}

export function SourceInfo({ source, onClose, onOpenNote }: { source: SourceCard | null; onClose: () => void; onOpenNote: (id: string) => void }) {
  const { t, lang } = useI18n();
  const date = (value?: string) => (value ? new Date(value).toLocaleDateString(lang) : "");
  return (
    <Dialog.Root open={source !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto rounded-t-3xl bg-background p-5 shadow-soft-lg outline-none wide:inset-x-auto wide:top-1/2 wide:bottom-auto wide:left-1/2 wide:w-[520px] wide:-translate-x-1/2 wide:-translate-y-1/2 wide:rounded-3xl">
          {source && (
            <>
              <div className="flex items-start justify-between gap-4">
                <Dialog.Title className="text-title-3 font-semibold">{source.title}</Dialog.Title>
                <Dialog.Close aria-label={t("close")} className="grid size-8 shrink-0 place-items-center rounded-full bg-fill text-muted-foreground">
                  <X className="size-4" />
                </Dialog.Close>
              </div>
              <Dialog.Description className="mt-2 text-subhead leading-relaxed text-muted-foreground">
                {source.metadata.description || source.origin}
              </Dialog.Description>
              <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 overflow-hidden rounded-2xl bg-card text-subhead shadow-soft-sm">
                {(
                  [
                    ["notes_source_author", source.metadata.author],
                    ["notes_source_license", source.metadata.license],
                    ["notes_source_version", source.metadata.version],
                    ["notes_source_language", languageLabel(t, source.metadata.language)],
                    ["notes_source_upstream_updated", date(source.metadata.updated_at)],
                    ["notes_source_imported", date(source.imported_at)],
                    ["notes_source_updated", date(source.organization_updated_at)],
                  ] as [TextKey, string | undefined][]
                ).map(([key, value], index) => (
                  <div key={key} className={"col-span-2 grid grid-cols-subgrid px-4 py-2.5" + (index ? " border-t border-border" : "")}>
                    <dt className="text-muted-foreground">{t(key)}</dt>
                    <dd className="min-w-0 truncate text-right" title={value}>
                      {value || t("notes_unknown")}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-footnote font-medium text-primary">
                {source.metadata.homepage && <SafeLink url={source.metadata.homepage}>{t("notes_source_original")} ↗</SafeLink>}
                {source.metadata.license_url && <SafeLink url={source.metadata.license_url}>{t("notes_source_license_link")} ↗</SafeLink>}
                {source.information_ids.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onOpenNote(source.information_ids[0]);
                    }}
                  >
                    {t("notes_license_full")}
                  </button>
                )}
              </div>
              {source.organization_stale && <p className="mt-3 rounded-xl bg-orange/14 px-3 py-2 text-footnote text-warning">{t("notes_source_changed")}</p>}
              {source.reading_groups_incomplete ? (
                <p className="mt-3 rounded-xl bg-orange/14 px-3 py-2 text-footnote text-warning">{t("notes_reading_changed")}</p>
              ) : null}
              <h3 className="mt-5 mb-1.5 text-footnote font-semibold text-muted-foreground">{t("notes_source_history")}</h3>
              {!source.history.length && <p className="text-footnote text-muted-foreground">{t("notes_no_history")}</p>}
              {[...source.history]
                .reverse()
                .slice(0, 8)
                .map((item) => (
                  <p key={item.at} className="py-0.5 text-footnote">
                    {date(item.at)} ·{" "}
                    {t("notes_history_item", {
                      c: item.changed.chapters || 0,
                      n: item.changed.notes || 0,
                      a: item.changed.areas ? t("notes_history_directory") : t("notes_history_metadata"),
                    })}
                  </p>
                ))}
              <p className="mt-4 text-caption text-tertiary-foreground">{t("notes_manage_hint")}</p>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
