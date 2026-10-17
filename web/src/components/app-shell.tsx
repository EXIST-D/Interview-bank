import { Dialog } from "radix-ui";
import { BookOpen, Compass, House, MessagesSquare, MoreHorizontal, Newspaper, Shuffle } from "lucide-react";
import { useState } from "react";
import { useBank } from "@/lib/bank";
import { useI18n } from "@/lib/i18n";
import { href, navigate, type Board } from "@/lib/router";
import { keys, stored } from "@/lib/storage";
import type { ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { BoardNav, type BoardItem } from "./board-nav";
import { SettingsMenu } from "./settings-menu";

export function Logo() {
  return (
    <span aria-hidden className="grid size-[26px] place-items-center rounded-[7px] bg-primary text-[12px] font-semibold text-primary-foreground">
      iB
    </span>
  );
}

function useBoards(): BoardItem[] {
  const { library, notes } = useBank();
  const items: BoardItem[] = [{ board: "home" }, { board: "bank", count: library?.summary.questions }];
  if (notes) {
    items.push(
      { board: "knowledge", count: notes.section_counts.knowledge },
      { board: "public", count: notes.section_counts.experiences },
      { board: "learning", count: notes.section_counts.learning },
    );
  }
  return items;
}

function randomQuestion() {
  // For a spare minute: any interview question, unread ones first.
  return (ids: string[]) => {
    const read = new Set(stored<string[]>(keys.read, []));
    const unread = ids.filter((id) => !read.has(id));
    const pool = unread.length ? unread : ids;
    if (pool.length) navigate("bank", [], { open: pool[Math.floor(Math.random() * pool.length)] });
  };
}

export function TopBar({
  board,
  theme,
  onTheme,
  onToast,
}: {
  board: Board;
  theme: ThemeChoice;
  onTheme: (choice: ThemeChoice) => void;
  onToast: (text: string) => void;
}) {
  const { t } = useI18n();
  const { library } = useBank();
  const boards = useBoards();
  const pick = randomQuestion();
  return (
    <header className="ib-topbar glass sticky top-0 z-40 border-b border-border">
      <div className="mx-auto flex h-13 max-w-[1440px] items-center gap-4 px-4 sm:px-5">
        <a href={href("home")} className="flex min-w-0 items-center gap-2.5">
          <Logo />
          <span className="text-headline font-semibold tracking-tight whitespace-nowrap">{t("app_name")}</span>
          {library && (
            <span className="hidden truncate text-footnote text-muted-foreground lg:inline">{library.account || library.name}</span>
          )}
        </a>
        <div className="mx-auto hidden md:block">
          <BoardNav items={boards} current={board} />
        </div>
        <div className="ml-auto flex items-center gap-1.5 md:ml-0">
          <button
            type="button"
            title={t("random")}
            aria-label={t("random")}
            onClick={() => library && pick(library.ids)}
            className="grid size-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-fill hover:text-foreground"
          >
            <Shuffle className="size-4" />
          </button>
          <SettingsMenu theme={theme} onTheme={onTheme} onToast={onToast} />
        </div>
      </div>
    </header>
  );
}

const TAB_ICONS = { home: House, bank: MessagesSquare, knowledge: BookOpen, public: Newspaper, learning: Compass } as const;

export function TabBar({ board }: { board: Board }) {
  const { t } = useI18n();
  const { notes } = useBank();
  const [more, setMore] = useState(false);
  const inMore = board === "public" || board === "learning";
  const tabs: { board: Board; label: string }[] = [
    { board: "home", label: t("board_home") },
    { board: "bank", label: t("tab_bank") },
    ...(notes ? [{ board: "knowledge" as Board, label: t("tab_knowledge") }] : []),
  ];
  const tab = (active: boolean) =>
    cn("flex flex-col items-center gap-0.5 pt-1.5 text-[10px] font-medium transition-colors", active ? "text-primary" : "text-tertiary-foreground");
  return (
    <nav aria-label={t("boards")} className="glass pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-border md:hidden">
      <div className="grid h-[52px]" style={{ gridTemplateColumns: `repeat(${tabs.length + (notes ? 1 : 0)}, 1fr)` }}>
        {tabs.map(({ board: target, label }) => {
          const Icon = TAB_ICONS[target as keyof typeof TAB_ICONS];
          return (
            <a key={target} href={href(target)} aria-current={board === target ? "page" : undefined} className={tab(board === target)}>
              <Icon className="size-[22px]" strokeWidth={board === target ? 2.2 : 1.8} />
              {label}
            </a>
          );
        })}
        {notes && (
          <Dialog.Root open={more} onOpenChange={setMore}>
            <Dialog.Trigger className={tab(inMore)}>
              <MoreHorizontal className="size-[22px]" strokeWidth={inMore ? 2.2 : 1.8} />
              {t("tab_more")}
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
              <Dialog.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 rounded-t-3xl bg-card p-3 shadow-soft-lg outline-none">
                <Dialog.Title className="sr-only">{t("tab_more")}</Dialog.Title>
                <div className="mx-auto mb-3 h-1 w-9 rounded-full bg-secondary" />
                {(["public", "learning"] as const).map((target) => {
                  const Icon = TAB_ICONS[target];
                  return (
                    <a
                      key={target}
                      href={href(target)}
                      onClick={() => setMore(false)}
                      className="flex items-center gap-3 rounded-xl px-3 py-3 text-body active:bg-fill"
                    >
                      <Icon className="size-5 text-primary" />
                      <span className="flex-1">{t(`board_${target}`)}</span>
                      <span className="text-footnote text-muted-foreground tabular-nums">
                        {target === "public" ? notes.section_counts.experiences : notes.section_counts.learning}
                      </span>
                    </a>
                  );
                })}
                <div className="h-3" />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        )}
      </div>
    </nav>
  );
}

export function Toast({ text }: { text: string | null }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-full bg-foreground px-4 py-2 text-footnote text-background shadow-soft-lg transition-all duration-300 ease-apple md:bottom-8",
        text ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
      )}
    >
      {text}
    </div>
  );
}
