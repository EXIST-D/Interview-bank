import { useLayoutEffect, useRef, useState } from "react";
import { href, type Board } from "@/lib/router";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type BoardItem = { board: Board; count?: number };

// A capsule segmented control of links; the white thumb slides to the current section.
export function BoardNav({ items, current }: { items: BoardItem[]; current: Board }) {
  const { t } = useI18n();
  const root = useRef<HTMLElement>(null);
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const measure = () => {
      const active = root.current?.querySelector<HTMLElement>('[aria-current="page"]');
      setThumb(active ? { left: active.offsetLeft, width: active.offsetWidth } : null);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (root.current) observer.observe(root.current);
    return () => observer.disconnect();
  }, [current, items]);

  return (
    <nav ref={root} aria-label={t("boards")} className="relative flex items-center gap-0.5 rounded-full bg-fill p-[3px]">
      {thumb && (
        <span
          aria-hidden
          className="absolute top-[3px] bottom-[3px] rounded-full bg-card shadow-[0_1px_3px_rgb(0_0_0/0.1),0_1px_1px_rgb(0_0_0/0.04)] transition-[left,width] duration-300 ease-apple dark:bg-[#636366]"
          style={{ left: thumb.left, width: thumb.width }}
        />
      )}
      {items.map(({ board, count }) => {
        const active = board === current;
        return (
          <a
            key={board}
            href={href(board)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative rounded-full px-3.5 py-1.5 text-footnote whitespace-nowrap transition-colors duration-150 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              active ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`board_${board}`)}
            {count !== undefined && <span className="ml-1 text-caption text-tertiary-foreground tabular-nums">{count}</span>}
          </a>
        );
      })}
    </nav>
  );
}
