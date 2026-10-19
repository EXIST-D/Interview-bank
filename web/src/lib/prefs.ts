import { useCallback, useEffect, useState } from "react";
import { store, stored } from "./storage";
import { queueRead } from "./sync";

// Browser-local preferences shared by components that are open at the same time (menu and reader).
const EVENT = "ibank-pref";

export function setPref(key: string, value: unknown) {
  store(key, value);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }));
}

export function usePref<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => stored(key, fallback));
  useEffect(() => {
    // A key can change (the account name arrives later); read its value then and on every change.
    setValue(stored(key, fallback));
    const update = (event: Event) => {
      if ((event as CustomEvent).detail === key) setValue(stored(key, fallback));
    };
    window.addEventListener(EVENT, update);
    return () => window.removeEventListener(EVENT, update);
    // The fallback is only read on change; a new literal each render must not resubscribe.
  }, [key]);
  const set = useCallback((next: T) => setPref(key, next), [key]);
  return [value, set] as const;
}

// Questions and notes opened in this browser (and, when the server keeps them, on other devices too).
const READ_LIMIT = 5000;
let readSet: Set<string> | null = null;

export function readIds() {
  readSet ??= new Set(stored<string[]>("ibank-read", []));
  return readSet;
}

export function markRead(id: string) {
  const read = readIds();
  if (read.has(id)) return;
  read.add(id);
  setPref("ibank-read", [...read].slice(-READ_LIMIT));
  queueRead(id);
}
