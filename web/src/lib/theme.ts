import { useEffect, useState } from "react";
import { keys, store, stored } from "./storage";

export type ThemeChoice = "auto" | "light" | "dark";

const system = matchMedia("(prefers-color-scheme: dark)");

function apply(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "auto" && system.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(() => stored<ThemeChoice>(keys.theme, "auto"));
  useEffect(() => {
    apply(choice);
    const follow = () => apply(choice);
    system.addEventListener("change", follow);
    return () => system.removeEventListener("change", follow);
  }, [choice]);
  const set = (next: ThemeChoice) => {
    store(keys.theme, next);
    setChoice(next);
  };
  return [choice, set] as const;
}

apply(stored<ThemeChoice>(keys.theme, "auto"));
