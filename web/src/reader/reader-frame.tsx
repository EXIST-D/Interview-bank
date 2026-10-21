import { Dialog, Popover } from "radix-ui";
import { ArrowUp, ChevronLeft, ChevronRight, Link2, ListTree, Maximize2, Minimize2, PanelLeftClose, PanelLeftOpen, StickyNote, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import { useMedia, useToast, WIDE } from "@/lib/hooks";
import { usePref } from "@/lib/prefs";
import { keys } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { FavoriteButton } from "@/components/favorite-button";
import { NoteEditor, type PersonalNote } from "./note-editor";
import "./reader.css";

export type ReaderNav = { index: number; total: number; onStep: (delta: number) => void };

type Entry = { node: HTMLElement; label: string; depth: number };
// Headings of the original text, and bold numbered question lines that long interview write-ups use instead.
const OUTLINE = ".md h3, .md h4, .md [data-toc]";

function Outline({ article, contentKey, notesOpen }: { article: React.RefObject<HTMLElement | null>; contentKey: string; notesOpen: boolean }) {
  const { t } = useI18n();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [far, setFar] = useState(false);

  const collect = useCallback(() => {
    const root = article.current;
    if (!root) return;
    const nodes = [...root.querySelectorAll<HTMLElement>(OUTLINE)];
    setEntries((current) => {
      const next = nodes.map((node) => ({ node, label: (node.textContent ?? "").trim().slice(0, 80), depth: node.tagName === "H4" ? 1 : 0 }));
      return next.length === current.length && next.every((e, i) => e.node === current[i].node) ? current : next;
    });
  }, [article]);

  useEffect(() => {
    // Answers can be revealed or folds opened after the first render; the outline follows the text.
    collect();
    const root = article.current;
    if (!root) return;
    const observer = new MutationObserver(collect);
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [article, collect, contentKey]);

  useEffect(() => {
    const root = article.current;
    if (!root) return;
    const onScroll = () => {
      setFar(root.scrollTop > 900);
      const top = root.getBoundingClientRect().top + 48;
      let index = 0;
      entries.forEach((entry, i) => {
        if (entry.node.getBoundingClientRect().top <= top) index = i;
      });
      setActive(index);
    };
    onScroll();
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => root.removeEventListener("scroll", onScroll);
  }, [article, entries]);

  const go = (entry: Entry) => {
    setOpen(false);
    entry.node.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };

  return (
    <>
      {entries.length >= 3 && (
        <Popover.Root open={open} onOpenChange={setOpen}>
          <Popover.Trigger aria-label={t("toc")} title={t("toc")} className="grid size-8 place-items-center rounded-full text-muted-foreground hover:bg-fill hover:text-foreground data-[state=open]:bg-fill">
            <ListTree className="size-[18px]" />
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content align="end" sideOffset={6} className="z-50 max-h-[70dvh] w-[min(22rem,90vw)] overflow-y-auto rounded-2xl border border-border bg-popover p-1.5 shadow-soft-lg outline-none">
              <p className="px-2.5 pt-1.5 pb-1 text-caption font-medium text-tertiary-foreground">
                {t("toc")} · {entries.length}
              </p>
              {entries.map((entry, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => go(entry)}
                  aria-current={i === active ? "true" : undefined}
                  className={cn(
                    "block w-full rounded-lg px-2.5 py-1.5 text-left text-footnote leading-snug hover:bg-fill",
                    entry.depth && "pl-6 text-muted-foreground",
                    i === active && "bg-accent font-medium text-accent-foreground",
                  )}
                >
                  {entry.label}
                </button>
              ))}
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      )}
      {far && !notesOpen && (
        <button
          type="button"
          aria-label={t("toc_top")}
          title={t("toc_top")}
          onClick={() => article.current?.scrollTo({ top: 0, behavior: "smooth" })}
          className="absolute right-4 bottom-20 z-[2] grid size-10 place-items-center rounded-full border border-border bg-card text-muted-foreground shadow-soft-lg hover:text-foreground wide:right-6"
        >
          <ArrowUp className="size-4" />
        </button>
      )}
    </>
  );
}

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
  personalNote,
  notesOpen,
  onNotesOpen,
  children,
}: {
  nav: ReaderNav;
  /** The open question or note ID; also what the star saves. */
  contentKey: string;
  onBack: () => void;
  listCollapsed: boolean;
  onToggleList: () => void;
  focused: boolean;
  onToggleFocus: () => void;
  hasAnswer: boolean;
  revealed: boolean;
  onToggleAnswer: () => void;
  personalNote?: PersonalNote;
  notesOpen: boolean;
  onNotesOpen: (open: boolean) => void;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const wide = useMedia(WIDE);
  const [size, setSize] = usePref(keys.textSize, 0);
  const article = useRef<HTMLElement>(null);
  const [progress, setProgress] = useState(0);
  const touch = useRef<{ x: number; y: number; at: number } | null>(null);
  const noteTrigger = useRef<HTMLButtonElement>(null);
  const noteHeading = useRef<HTMLHeadingElement>(null);
  const anchor = useRef<{ node: HTMLElement; fraction: number; inset: number } | null>(null);

  const toggleNotes = (open: boolean) => {
    const root = article.current;
    if (root) {
      const top = root.getBoundingClientRect().top;
      const node = [...root.querySelectorAll<HTMLElement>("h1, h2, h3, h4, .md p, .md li, .md pre, .rich p, .rich li")]
        .find((element) => element.getBoundingClientRect().bottom > top + 1);
      if (node) {
        const rect = node.getBoundingClientRect();
        anchor.current = { node, fraction: Math.max(0, (top - rect.top) / Math.max(1, rect.height)), inset: Math.max(0, rect.top - top) };
      }
    }
    onNotesOpen(open);
  };

  useLayoutEffect(() => {
    const point = anchor.current;
    anchor.current = null;
    const root = article.current;
    if (point?.node.isConnected && root?.contains(point.node)) {
      const rect = point.node.getBoundingClientRect();
      root.scrollBy({ top: rect.top + point.fraction * rect.height - root.getBoundingClientRect().top - point.inset, behavior: "instant" });
    }
  }, [notesOpen]);

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
  const canOpenNotes = Boolean(personalNote && (personalNote.canWrite || personalNote.saved));
  const panel = personalNote && (
    <Dialog.Content
      className="ib-notes-panel"
      aria-modal={!wide || undefined}
      onOpenAutoFocus={(event) => {
        // Focus the panel without moving the article, and avoid summoning a phone keyboard just by opening it.
        event.preventDefault();
        requestAnimationFrame(() => noteHeading.current?.focus({ preventScroll: true }));
      }}
      onCloseAutoFocus={(event) => { event.preventDefault(); noteTrigger.current?.focus({ preventScroll: true }); }}
      onInteractOutside={(event) => { if (wide) event.preventDefault(); }}
    >
      <header className="flex shrink-0 items-center gap-2 px-4 pt-4 pb-2">
        <span className="grid size-8 place-items-center rounded-xl bg-accent text-primary"><StickyNote className="size-4" /></span>
        <Dialog.Title ref={noteHeading} tabIndex={-1} className="min-w-0 flex-1 text-callout font-semibold outline-none">{t("my_note")}</Dialog.Title>
        <button type="button" title={t("note_copy_link")} aria-label={t("note_copy_link")} className="ib-note-icon" onClick={async () => {
          try { await navigator.clipboard.writeText(location.origin + location.pathname + location.hash); toast(t("note_link_copied")); }
          catch { toast(t("note_link_failed")); }
        }}><Link2 className="size-4" /></button>
        <Dialog.Close aria-label={t("note_close")} title={t("note_close")} className="ib-note-icon"><X className="size-[18px]" /></Dialog.Close>
      </header>
      <button type="button" className="mx-4 mb-3 flex shrink-0 items-start gap-1.5 rounded-xl bg-fill px-3 py-2 text-left text-caption text-muted-foreground hover:text-primary" onClick={() => { toggleNotes(false); requestAnimationFrame(() => article.current?.focus({ preventScroll: true })); }}>
        <Link2 className="mt-0.5 size-3.5 shrink-0" /><span className="min-w-0"><span className="block text-tertiary-foreground">{t("note_for_item")}</span><span className="line-clamp-2 font-medium">{personalNote.title}</span></span>
      </button>
      <Dialog.Description className="sr-only">{t("note_panel_description")}</Dialog.Description>
      <NoteEditor key={personalNote.account + ":" + contentKey} itemId={contentKey} note={personalNote} onToast={toast} />
    </Dialog.Content>
  );

  return (
    <Dialog.Root open={notesOpen && canOpenNotes} onOpenChange={toggleNotes} modal={!wide}>
    <section aria-label={t("reader_label")} className="relative flex h-full min-h-0 min-w-0 flex-col bg-card" data-size={size}>
      <header className="no-scrollbar flex h-12 shrink-0 items-center gap-1.5 overflow-x-auto border-b border-border px-3 [&>button]:shrink-0">
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
        <span className="mx-auto shrink-0 whitespace-nowrap text-caption text-muted-foreground tabular-nums sm:text-footnote">
          {nav.index >= 0 ? t("position", { i: nav.index + 1, n: nav.total }) : ""}
        </span>
        <Outline article={article} contentKey={contentKey} notesOpen={notesOpen} />
        <FavoriteButton itemId={contentKey} />
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
        {canOpenNotes && <Dialog.Trigger asChild><button ref={noteTrigger} type="button" title={t("note_open")} aria-label={t("note_open")} className={cn(chip, "relative inline-flex w-8 items-center justify-center gap-1.5 px-0 sm:w-auto sm:px-3", notesOpen && "border-primary/20 bg-accent text-primary")}>
          <StickyNote className="size-3.5" /><span className="hidden sm:inline">{t("note_open")}</span>
          {personalNote?.saved && <span aria-label={t("note_exists")} className="absolute top-1 right-1 size-1.5 rounded-full bg-primary" />}
        </button></Dialog.Trigger>}
      </header>
      <div aria-hidden className="h-0.5 shrink-0">
        <span className="block h-full origin-left bg-primary transition-transform duration-75" style={{ transform: `scaleX(${progress})` }} />
      </div>
      <div className="ib-reader-body relative flex min-h-0 min-w-0 flex-1">
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
        className="ib-reading min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain"
      >
        {children}
      </article>
      {wide && panel}
      </div>
      {!wide && <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[60] bg-black/20" />{panel}</Dialog.Portal>}
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
    </Dialog.Root>
  );
}
