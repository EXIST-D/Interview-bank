import { useEffect, useState } from "react";

// Hash routes keep the reader working under any path prefix (/, /ibank/) without server rewrites.
export type Board = "home" | "bank" | "knowledge" | "public" | "learning" | "mine";
export type Route = { board: Board; rest: string[]; params: URLSearchParams };

const BOARDS: Board[] = ["home", "bank", "knowledge", "public", "learning", "mine"];
const LEGACY_SECTIONS: Record<string, Board> = { bank: "bank", knowledge: "knowledge", experiences: "public", learning: "learning" };

export function parse(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  if (!raw.startsWith("/")) {
    // Links from earlier readers: #section=…, #question=q_…, #note=note_…
    const legacy = new URLSearchParams(raw);
    const params = new URLSearchParams();
    if (legacy.get("question")) params.set("open", legacy.get("question")!);
    if (legacy.get("note")) params.set("open", legacy.get("note")!);
    const board = legacy.get("question") ? "bank" : legacy.get("note") ? "knowledge" : LEGACY_SECTIONS[legacy.get("section") ?? ""] ?? "home";
    return { board, rest: [], params };
  }
  const [path, query = ""] = raw.slice(1).split("?");
  const [first, ...rest] = path.split("/").filter(Boolean).map(decodeURIComponent);
  const board = BOARDS.includes(first as Board) ? (first as Board) : "home";
  return { board, rest, params: new URLSearchParams(query) };
}

export function href(board: Board, rest: string[] = [], params?: Record<string, string>) {
  const path = board === "home" ? "" : [board, ...rest].map(encodeURIComponent).join("/");
  const query = params ? new URLSearchParams(params).toString() : "";
  return "#/" + path + (query ? "?" + query : "");
}

export function navigate(board: Board, rest: string[] = [], params?: Record<string, string>) {
  location.hash = href(board, rest, params);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(location.hash));
  useEffect(() => {
    const update = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
