import { DropdownMenu } from "radix-ui";
import { Check, Download, ExternalLink, FileDown, LogOut, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { useBank } from "@/lib/bank";
import { useI18n } from "@/lib/i18n";
import { keys } from "@/lib/storage";
import { usePref } from "@/lib/prefs";
import type { ThemeChoice } from "@/lib/theme";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { loginHref, onSignIn } from "@/lib/access";
import { navigate } from "@/lib/router";
import { AgentDialog, type AgentAction } from "./agent-dialog";

const item =
  "flex h-9 cursor-default items-center gap-2.5 rounded-lg px-2.5 text-subhead outline-none select-none data-[highlighted]:bg-fill [&_svg]:size-4 [&_svg]:text-muted-foreground";
const label = "px-2.5 pt-2 pb-1 text-caption font-medium text-tertiary-foreground";

export function SettingsMenu({
  theme,
  onTheme,
  onToast,
}: {
  theme: ThemeChoice;
  onTheme: (choice: ThemeChoice) => void;
  onToast: (text: string) => void;
}) {
  const { t } = useI18n();
  const { library, refresh } = useBank();
  const [thinkFirst, setThinkFirst] = usePref(keys.thinkFirst, false);
  const [size, setSize] = usePref(keys.textSize, 0);
  const [action, setAction] = useState<AgentAction | null>(null);
  const initials = library?.guest ? t("guest") : (library?.account || library?.name || "iB").slice(0, 2).toUpperCase();
  const status = library?.read_only ? t("read_only") : library?.schema_version === 1 ? t("v1_notice") : "";

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger
          aria-label={t("settings")}
          className="grid size-8 place-items-center rounded-full bg-secondary text-caption font-semibold outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring/50 data-[state=open]:ring-2 data-[state=open]:ring-ring/30"
        >
          {initials}
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={8}
            className="z-50 w-64 rounded-2xl border border-border bg-popover p-1.5 shadow-soft-lg outline-none"
          >
            <div className="px-2.5 pt-1.5 pb-2">
              <div className="text-subhead font-semibold">{library?.guest ? t("guest") : library?.account || library?.name}</div>
              <div className="text-caption text-muted-foreground">
                {[status, library && "v" + library.version].filter(Boolean).join(" · ")}
              </div>
            </div>
            {library?.guest && <DropdownMenu.Item className={cn(item, "font-medium text-primary")} asChild><a href={loginHref()} onClick={onSignIn}>{t("login")}</a></DropdownMenu.Item>}
            <DropdownMenu.Separator className="my-1 h-px bg-border" />

            <DropdownMenu.Label className={label}>{t("appearance")}</DropdownMenu.Label>
            <div className="mx-1.5 mb-1 grid grid-cols-3 gap-0.5 rounded-[10px] bg-fill p-0.5">
              {(["auto", "light", "dark"] as const).map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => onTheme(choice)}
                  className={cn(
                    "rounded-lg py-1 text-footnote transition-colors",
                    theme === choice ? "bg-card font-medium shadow-soft-sm dark:bg-[#636366]" : "text-muted-foreground",
                  )}
                >
                  {t(`theme_${choice}`)}
                </button>
              ))}
            </div>
            <DropdownMenu.CheckboxItem
              checked={thinkFirst}
              onSelect={(event) => event.preventDefault()}
              onCheckedChange={(on) => setThinkFirst(on)}
              className={cn(item, "h-auto py-2")}
            >
              <span className="flex-1">
                <span className="block">{t("think_first")}</span>
                <span className="block text-caption text-muted-foreground">{t("think_first_hint")}</span>
              </span>
              <DropdownMenu.ItemIndicator>
                <Check className="!text-primary" />
              </DropdownMenu.ItemIndicator>
            </DropdownMenu.CheckboxItem>
            <DropdownMenu.Item
              onSelect={(event) => {
                event.preventDefault();
                setSize((Number(size) + 1) % 3);
              }}
              className={item}
            >
              <span className="flex-1">{t("text_size")}</span>
              <span className="text-footnote text-muted-foreground">{t(`size_${size as 0 | 1 | 2}`)}</span>
            </DropdownMenu.Item>

            <DropdownMenu.Separator className="my-1 h-px bg-border" />
            <DropdownMenu.Label className={label}>{t("agent_actions")}</DropdownMenu.Label>
            <DropdownMenu.Item className={item} onSelect={() => (library?.can_intake ? navigate("import") : setAction("import"))}>
              <Download />
              {t("import")}
            </DropdownMenu.Item>
            <DropdownMenu.Item className={item} onSelect={() => (library?.can_research ? navigate("import") : setAction("research"))}>
              <Sparkles />
              {t("research")}
            </DropdownMenu.Item>
            <DropdownMenu.Item className={item} onSelect={() => setAction("export")}>
              <FileDown />
              {t("export")}
            </DropdownMenu.Item>

            <DropdownMenu.Separator className="my-1 h-px bg-border" />
            <DropdownMenu.Item
              className={item}
              onSelect={async () => {
                await refresh(true);
                onToast(t("reloaded"));
              }}
            >
              <RefreshCw />
              {t("refresh")}
            </DropdownMenu.Item>
            <DropdownMenu.Item className={item} asChild>
              <a href="https://github.com/EXIST-D/Interview-bank" target="_blank" rel="noopener noreferrer">
                <ExternalLink />
                {t("repo")}
              </a>
            </DropdownMenu.Item>
            {library?.can_logout && (
              <DropdownMenu.Item
                className={cn(item, "text-destructive [&_svg]:text-destructive")}
                onSelect={async () => {
                  try {
                    await api("/api/logout", {});
                  } finally {
                    location.reload();
                  }
                }}
              >
                <LogOut />
                {t("logout")}
              </DropdownMenu.Item>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {library?.guest && <a href={loginHref()} onClick={onSignIn} className="inline-flex h-8 shrink-0 items-center rounded-full bg-primary px-3 text-footnote font-medium text-primary-foreground hover:brightness-95">{t("login")}</a>}
      <AgentDialog action={action} onClose={() => setAction(null)} />
    </>
  );
}
