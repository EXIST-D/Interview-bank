import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { useBank } from "./bank";

export type FavoriteItem = {
  id: string;
  added_at: string;
  section: "bank" | "knowledge" | "experiences" | "learning";
  target: string;
  title: string;
  where: string | null;
  missing: boolean;
};
export type Folder = { id: string; name: string; created_at: string; updated_at: string; items: FavoriteItem[] };
type Response = { folders: Folder[]; can_write: boolean };

export type FavoriteChange =
  | { action: "create"; name: string }
  | { action: "rename"; folder: string; name: string }
  | { action: "delete"; folder: string }
  | { action: "move"; folder: string; position: number }
  | { action: "add" | "remove"; folder: string; item: string };

type State = {
  folders: Folder[] | null;
  canWrite: boolean;
  change: (change: FavoriteChange) => Promise<Folder[]>;
  /** Folders holding an item. */
  holding: (id: string) => Folder[];
  reload: () => Promise<void>;
};

const Favorites = createContext<State>({ folders: null, canWrite: false, change: async () => [], holding: () => [], reload: async () => {} });
export const useFavorites = () => useContext(Favorites);

export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const { library } = useBank();
  const [state, setState] = useState<Response | null>(null);
  const reload = useCallback(async () => {
    try {
      setState(await api<Response>("/api/favorites"));
    } catch {
      setState({ folders: [], can_write: false });
    }
  }, []);
  useEffect(() => {
    if (!library) return;
    if (library.guest) setState({ folders: [], can_write: false });
    else reload();
  }, [reload, library]);
  const change = useCallback(async (payload: FavoriteChange) => {
    const next = await api<Response>("/api/favorites", payload);
    setState(next);
    return next.folders;
  }, []);
  const byItem = useMemo(() => {
    const map = new Map<string, Folder[]>();
    for (const folder of state?.folders ?? []) for (const item of folder.items) map.set(item.id, [...(map.get(item.id) ?? []), folder]);
    return map;
  }, [state]);
  const holding = useCallback((id: string) => byItem.get(id) ?? [], [byItem]);
  return (
    <Favorites.Provider value={{ folders: state?.folders ?? null, canWrite: Boolean(state?.can_write), change, holding, reload }}>
      {children}
    </Favorites.Provider>
  );
}
