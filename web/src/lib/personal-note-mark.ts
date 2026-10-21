import { useEffect, useState } from "react";

export function noteSaved(id: string, exists: boolean) {
  dispatchEvent(new CustomEvent("ibank-note-saved", { detail: { id, exists } }));
}

/** Lists keep their lightweight card metadata; a personal save updates just the matching badge. */
export function usePersonalNoteMark(id: string, initial: boolean) {
  const [exists, setExists] = useState(initial);
  useEffect(() => setExists(initial), [id, initial]);
  useEffect(() => {
    const update = (event: Event) => {
      const detail = (event as CustomEvent<{ id: string; exists: boolean }>).detail;
      if (detail.id === id) setExists(detail.exists);
    };
    addEventListener("ibank-note-saved", update);
    return () => removeEventListener("ibank-note-saved", update);
  }, [id]);
  return exists;
}
