import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  label?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid auto-cols-fr grid-flow-col gap-0.5 rounded-[10px] bg-fill p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          onClick={() => onChange(option.value)}
          className={cn(
            "min-w-0 truncate rounded-lg px-1 py-1.5 text-footnote font-medium whitespace-nowrap transition-colors",
            option.value === value ? "bg-card text-foreground shadow-[0_1px_3px_rgb(0_0_0/0.1)] dark:bg-[#636366]" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export const chipClass = (active: boolean) =>
  cn(
    "shrink-0 rounded-full border px-3 py-1.5 text-footnote transition-colors",
    active ? "border-transparent bg-foreground text-background" : "border-border bg-card text-muted-foreground shadow-soft-sm hover:text-foreground",
  );
