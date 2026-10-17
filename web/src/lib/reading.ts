import { useCallback, useEffect, useRef, useState } from "react";
import { useMedia, WIDE } from "./hooks";
import { href, navigate, type Board, type Route } from "./router";
import { store, stored } from "./storage";

type Layout = { list: boolean; focus: boolean };

// Which item is open, previous/next, folding the list, focus mode and the keyboard; shared by every board.
// The hash is the source of truth (links, random pick, the phone's back gesture). On wide screens opening
// replaces the entry; on phones it pushes one so the system back gesture closes the reader.
export function useReading({ route, board, ids, searchId }: { route: Route; board: Board; ids: string[]; searchId: string }) {
  const wide = useMedia(WIDE);
  // The reader that owns the answer's visibility registers how Space reveals it.
  const reveal = useRef<{ fn: () => void; revealed: boolean }>({ fn: () => {}, revealed: true });
  const registerReveal = useCallback((fn: () => void, revealed: boolean) => {
    reveal.current = { fn, revealed };
  }, []);
  const [openId, setOpenId] = useState<string | null>(() => route.params.get("open"));
  const [layout, setLayoutState] = useState<Layout>(() => ({ list: false, focus: false, ...stored<Partial<Layout>>("ibank-layout", {}) }));
  const pushed = useRef(false);

  useEffect(() => {
    setOpenId(route.params.get("open"));
  }, [route]);

  const here = useCallback(
    (open?: string) => {
      const params: Record<string, string> = {};
      route.params.forEach((value, key) => {
        if (key !== "open") params[key] = value;
      });
      if (open) params.open = open;
      return { rest: route.rest, params };
    },
    [route],
  );

  const open = useCallback(
    (id: string) => {
      const { rest, params } = here(id);
      if (wide) {
        history.replaceState(null, "", href(board, rest, params));
        setOpenId(id);
      } else {
        pushed.current = true;
        navigate(board, rest, params);
      }
    },
    [wide, board, here],
  );

  const close = useCallback(() => {
    if (pushed.current) {
      pushed.current = false;
      history.back();
    } else {
      const { rest, params } = here();
      history.replaceState(null, "", href(board, rest, params));
      setOpenId(null);
    }
  }, [board, here]);

  const index = openId ? ids.indexOf(openId) : -1;
  const step = useCallback(
    (delta: number) => {
      const target = ids[index + delta];
      if (!target) return;
      const { rest, params } = here(target);
      history.replaceState(history.state, "", href(board, rest, params));
      setOpenId(target);
    },
    [ids, index, board, here],
  );

  const setLayout = useCallback((changes: Partial<Layout>) => {
    setLayoutState((current) => {
      const next = { ...current, ...changes };
      store("ibank-layout", next);
      return next;
    });
  }, []);

  const focused = wide && Boolean(openId) && layout.focus;
  const listHidden = wide && Boolean(openId) && (layout.list || layout.focus);

  useEffect(() => {
    document.body.toggleAttribute("data-focus", focused);
    return () => document.body.removeAttribute("data-focus");
  }, [focused]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || document.querySelector("[role=dialog]")) return;
      if (event.key === "/") {
        event.preventDefault();
        document.getElementById(searchId)?.focus();
      }
      if (!openId) return;
      if (event.key === "ArrowRight" || event.key === "j") step(1);
      if (event.key === "ArrowLeft" || event.key === "k") step(-1);
      if (event.key === " " && !reveal.current.revealed) {
        event.preventDefault();
        reveal.current.fn();
      }
      if (event.key === "Escape") {
        if (focused) setLayout({ focus: false });
        else if (!wide) close();
      }
      if (wide && (event.key === "f" || event.key === "F")) setLayout({ focus: !layout.focus });
      if (wide && (event.key === "l" || event.key === "L")) setLayout({ list: !layout.list, focus: false });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openId, step, focused, wide, close, layout, setLayout, searchId]);

  useEffect(() => {
    if (openId) document.querySelector(`[data-id="${CSS.escape(openId)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [openId]);

  return { wide, openId, open, close, step, index, layout, setLayout, focused, listHidden, registerReveal };
}

export const thinkFirst = () => stored("ibank-think-first", false);
