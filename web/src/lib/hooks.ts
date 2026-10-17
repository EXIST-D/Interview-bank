import { createContext, useContext, useEffect, useState } from "react";

export function useMedia(query: string) {
  const [matches, setMatches] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const media = matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

export const WIDE = "(min-width: 900px)";

export const ToastContext = createContext<(text: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);
