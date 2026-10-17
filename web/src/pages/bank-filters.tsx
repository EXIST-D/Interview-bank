import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import type { Facet } from "@/lib/api";
import { useI18n, type TextKey } from "@/lib/i18n";
import { Button } from "@/components/ui/button";

export const FACETS = ["domain", "technology", "company", "role", "industry"] as const;
export type Filters = Record<(typeof FACETS)[number] | "answer_status", string> & { sort: string };
export const NO_FILTERS: Filters = { domain: "", technology: "", company: "", role: "", industry: "", answer_status: "", sort: "frequency" };

export function activeFilters(filters: Filters) {
  return (Object.keys(NO_FILTERS) as (keyof Filters)[]).filter((key) => filters[key] !== NO_FILTERS[key]).length;
}

export function Field({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-4 border-t border-border px-4 py-2.5 first:border-t-0">
      <span className="shrink-0 text-subhead">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 max-w-[60%] truncate rounded-lg bg-transparent py-1 text-right text-subhead text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        {children}
      </select>
    </label>
  );
}

export function FilterDialog({
  open,
  onOpenChange,
  filters,
  onChange,
  facets,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  filters: Filters;
  onChange: (filters: Filters) => void;
  facets: Partial<Record<(typeof FACETS)[number], Facet[]>>;
}) {
  const { t } = useI18n();
  const set = (key: keyof Filters) => (value: string) => onChange({ ...filters, [key]: value });
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto rounded-t-3xl bg-background p-4 shadow-soft-lg outline-none wide:inset-x-auto wide:top-1/2 wide:bottom-auto wide:left-1/2 wide:w-[440px] wide:-translate-x-1/2 wide:-translate-y-1/2 wide:rounded-3xl">
          <div className="flex items-center justify-between pb-3">
            <Dialog.Title className="text-headline font-semibold">{t("filters")}</Dialog.Title>
            <Dialog.Close aria-label={t("close")} className="grid size-8 place-items-center rounded-full bg-fill text-muted-foreground">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <div className="overflow-hidden rounded-2xl bg-card shadow-soft-sm">
            {FACETS.map((key) => {
              const values = facets[key] ?? [];
              const label = t(`f_${key}` as TextKey);
              return (
                <Field key={key} label={label} value={filters[key]} onChange={set(key)}>
                  <option value="">{t("all")}</option>
                  {values.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label + (item.count ? ` · ${item.count}` : "")}
                    </option>
                  ))}
                  {filters[key] && !values.some((v) => v.value === filters[key]) && (
                    <option value={filters[key]}>{filters[key] + t("no_questions_here")}</option>
                  )}
                </Field>
              );
            })}
          </div>
          <div className="mt-3 overflow-hidden rounded-2xl bg-card shadow-soft-sm">
            <Field label={t("f_answer")} value={filters.answer_status} onChange={set("answer_status")}>
              <option value="">{t("all")}</option>
              {(["answered", "source_backed", "reviewed", "missing", "stale"] as const).map((status) => (
                <option key={status} value={status}>
                  {t(`status_${status}`)}
                </option>
              ))}
            </Field>
            <Field label={t("sort")} value={filters.sort} onChange={set("sort")}>
              {(["frequency", "recent", "title"] as const).map((sort) => (
                <option key={sort} value={sort}>
                  {t(`sort_${sort}`)}
                </option>
              ))}
            </Field>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <Button variant="link" size="sm" className="px-1" onClick={() => onChange(NO_FILTERS)} disabled={!activeFilters(filters)}>
              {t("reset")}
            </Button>
            <Dialog.Close asChild>
              <Button size="sm">{t("apply")}</Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
