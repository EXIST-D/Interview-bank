import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearDetails, type Library, type NotesOverview } from "./api";
import { clearNotes, setLearningAccount, sourceCards } from "./notes";

// Counts for the top bar, the overview and the settings menu. Each board loads its own lists.
type BankState = {
  library: Library | null;
  notes: NotesOverview | null;
  error: string | null;
  /** fresh: also forget cached questions, notes and source cards (the menu's 刷新). */
  refresh: (fresh?: boolean) => Promise<void>;
};

const Bank = createContext<BankState>({ library: null, notes: null, error: null, refresh: async () => {} });
export const useBank = () => useContext(Bank);

export function BankProvider({ children }: { children: React.ReactNode }) {
  const [library, setLibrary] = useState<Library | null>(null);
  const [notes, setNotes] = useState<NotesOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (fresh = false) => {
    setError(null);
    if (fresh) {
      clearDetails();
      clearNotes();
    }
    try {
      const next = await api<Library>("/api/library?limit=5&sort=frequency");
      setLearningAccount(next.account || next.name);
      setLibrary(next);
      // The public-interview section carries every section's counts with the smallest response.
      if (next.notes?.total) setNotes((await sourceCards("experiences")) as unknown as NotesOverview);
      else setNotes(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "failed");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <Bank.Provider value={{ library, notes, error, refresh }}>{children}</Bank.Provider>;
}
