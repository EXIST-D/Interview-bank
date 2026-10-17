import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Field } from "@/pages/bank-filters";

export type FilterField = { key: string; label: string; options: { value: string; label: string }[] };

// One sheet of select fields; each board decides which fields it offers.
export function NotesFilters({
  open,
  onOpenChange,
  fields,
  values,
  defaults,
  onChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fields: FilterField[];
  values: Record<string, string>;
  defaults: Record<string, string>;
  onChange: (changes: Record<string, string>) => void;
}) {
  const { t } = useI18n();
  const changed = fields.some((field) => (values[field.key] ?? "") !== (defaults[field.key] ?? ""));
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
            {fields.map((field) => (
              <Field key={field.key} label={field.label} value={values[field.key] ?? ""} onChange={(value) => onChange({ [field.key]: value })}>
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Field>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between">
            <Button
              variant="link"
              size="sm"
              className="px-1"
              disabled={!changed}
              onClick={() => onChange(Object.fromEntries(fields.map((field) => [field.key, defaults[field.key] ?? ""])))}
            >
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
