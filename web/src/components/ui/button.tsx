import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center rounded-full border border-transparent font-medium whitespace-nowrap transition-[background-color,color,box-shadow,transform,filter] duration-150 outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/40 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:brightness-110",
        outline: "border-border bg-card text-foreground shadow-soft-sm hover:bg-muted aria-expanded:bg-muted",
        secondary: "bg-fill text-foreground hover:bg-black/[0.08] dark:hover:bg-white/[0.12]",
        tinted: "bg-accent text-accent-foreground hover:brightness-95 dark:hover:brightness-125",
        ghost: "text-foreground hover:bg-fill aria-expanded:bg-fill",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 gap-1.5 px-5 text-callout",
        xs: "h-7 gap-1 px-2.5 text-caption [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1 px-3.5 text-footnote [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-12 gap-2 px-7 text-body",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { Button, buttonVariants };
