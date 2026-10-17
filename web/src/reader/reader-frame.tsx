import { ChevronLeft, ChevronRight, Maximize2, Minimize2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import { usePref } from "@/lib/prefs";
import { keys } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import "./reader.css";

export type ReaderNav = { index: number; total: number; onStep: (delta: number) => void };

// The reader's frame: toolbar, progress bar, the reading column and previous/next. The content is the previous reader's.
export function ReaderFrame({
  nav,
  contentKey,
  onBack,
  listCollapsed,
  onToggleList,
  focused,
  onToggleFocus,
  hasAnswer,
  revealed,
  onToggleAnswer,
  children,
}: {
  nav: ReaderNav;
  contentKey: string;
  onBack: () => void;
  listCollapsed: boolean;
  onToggleList: () => void;
  focused: boolean;
  onToggleFocus: () => void;
  hasAnswer: boolean;
  revealed: boolean;
  onToggleAnswer: () => void;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const [size, setSize] = usePref(keys.textSize, 0);
  const article = useRef<HTMLElement>(null);
  const [progress, setProgress] = useState(0);
  const touch = useRef<{ x: number; y: number; at: number } | null>(null);

  const measure = () => {
    const node = article.current;
    if (!node) return;
    const room = node.scrollHeight - node.clientHeight;
    setProgress(room > 0 ? Math.min(1, node.scrollTop / room) : 0);
  };

  useEffect(() => {
    article.current?.scrollTo(0, 0);
    article.current?.focus({ preventScroll: true });
    measure();
  }, [contentKey]);

  const chip = "h-8 rounded-full border border-border bg-card px-3 text-footnote font-medium shadow-soft-sm transition-colors hover:bg-fill";

  return (
    <section aria-label={t("reader_label")} className="flex h-full min-h-0 flex-col bg-card" data-size={size}>
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
        <button type="button" onClick={onBack} aria-label={t("back")} className="grid size-8 place-items-center rounded-full hover:bg-fill wide:hidden">
          <ChevronLeft className="size-5" />
        </button>
        <button
          type="button"
          onClick={onToggleList}
          aria-keyshortcuts="L"
          title={t(listCollapsed ? "show_list" : "hide_list")}
          aria-label={t(listCollapsed ? "show_list" : "hide_list")}
          className="hidden size-8 place-items-center rounded-full text-muted-foreground hover:bg-fill hover:text-foreground wide:grid"
        >
          {listCollapsed ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
        </button>
        <span className="mx-auto text-footnote text-muted-foreground tabular-nums">
          {nav.index >= 0 ? t("position", { i: nav.index + 1, n: nav.total }) : ""}
        </span>
        <button
          type="button"
          onClick={onToggleFocus}
          aria-pressed={focused}
          aria-keyshortcuts="F"
          className={cn(chip, "hidden items-center gap-1.5 wide:inline-flex")}
        >
          {focused ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          {t(focused ? "focus_exit" : "focus")}
        </button>
        <button type="button" aria-label={t("text_size")} title={t(`size_${(Number(size) % 3) as 0 | 1 | 2}`)} onClick={() => setSize((Number(size) + 1) % 3)} className={chip}>
          Aa
        </button>
        {hasAnswer && (
          <button type="button" onClick={onToggleAnswer} className={chip}>
            {t(revealed ? "hide_answer" : "show_answer")}
          </button>
        )}
      </header>
      <div aria-hidden className="h-0.5 shrink-0">
        <span className="block h-full origin-left bg-primary transition-transform duration-75" style={{ transform: `scaleX(${progress})` }} />
      </div>
      <article
        ref={article}
        tabIndex={-1}
        onScroll={measure}
        onTouchStart={(event) => {
          const point = event.touches[0];
          touch.current = event.touches.length === 1 ? { x: point.clientX, y: point.clientY, at: Date.now() } : null;
        }}
        onTouchEnd={(event) => {
          // Swipe between questions; vertical scrolling is left alone.
          const start = touch.current;
          touch.current = null;
          if (!start) return;
          const point = event.changedTouches[0];
          const dx = point.clientX - start.x;
          const dy = point.clientY - start.y;
          if (Date.now() - start.at < 600 && Math.abs(dx) > 70 && Math.abs(dy) < Math.abs(dx) / 2) nav.onStep(dx < 0 ? 1 : -1);
        }}
        className="ib-reading min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >
        {children}
      </article>
      <nav aria-label={t("reader_nav")} className="pb-safe grid shrink-0 grid-cols-2 gap-2.5 border-t border-border bg-card px-3 pt-2.5 wide:px-[max(32px,calc((100%-720px)/2))]">
        <Button variant="outline" className="mb-2.5 h-11 rounded-xl" disabled={nav.index <= 0} onClick={() => nav.onStep(-1)}>
          <ChevronLeft />
          {t("previous")}
        </Button>
        <Button className="mb-2.5 h-11 rounded-xl bg-foreground text-background" disabled={nav.index < 0 || nav.index >= nav.total - 1} onClick={() => nav.onStep(1)}>
          {t("next")}
          <ChevronRight />
        </Button>
      </nav>
    </section>
  );
}
