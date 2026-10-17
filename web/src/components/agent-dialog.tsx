import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export type AgentAction = "import" | "research" | "export";

// Writing to the bank stays with the agent on the user's computer; this only says what to ask for.
export function AgentDialog({ action, onClose }: { action: AgentAction | null; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog.Root open={action !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(92vw,460px)] -translate-x-1/2 -translate-y-1/2 surface p-6 outline-none">
          {action && (
            <>
              <div className="flex items-start justify-between gap-4">
                <Dialog.Title className="text-title-3 font-semibold">{t(action)}</Dialog.Title>
                <Dialog.Close aria-label={t("close")} className="-m-1 rounded-full p-1 text-muted-foreground hover:bg-fill">
                  <X className="size-4" />
                </Dialog.Close>
              </div>
              <Dialog.Description className="mt-3 text-subhead leading-relaxed text-muted-foreground">
                {t(`info_${action}_text`)}
              </Dialog.Description>
              <pre className="mt-3 rounded-xl bg-fill px-4 py-3 font-mono text-footnote whitespace-pre-wrap select-all">
                {t(`info_${action}_example`)}
              </pre>
              <p className="mt-4 text-caption text-tertiary-foreground">{t("info_soon")}</p>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
