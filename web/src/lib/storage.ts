// Browser-local preferences. Keys are shared with the previous reader so a reader keeps its settings.
let guest = false;
export function setGuestStorage(value: boolean) { guest = value; }
export const readingScope = () => guest ? "guest" : "account";
const scoped = (key: string) => guest && ["ibank-read", "ibank-last", "ibank-last-note"].includes(key) ? "guest:" + key : key;

export function stored<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(scoped(key));
    return value === null ? fallback : (JSON.parse(value) as T);
  } catch {
    return fallback;
  }
}

export function store(key: string, value: unknown) {
  try {
    localStorage.setItem(scoped(key), JSON.stringify(value));
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}

export type LastRead = { id: string; title: string };

export const keys = {
  theme: "ibank-theme",
  thinkFirst: "ibank-think-first",
  textSize: "ibank-text-size",
  read: "ibank-read",
  lastQuestion: "ibank-last",
  lastNote: "ibank-last-note",
} as const;
