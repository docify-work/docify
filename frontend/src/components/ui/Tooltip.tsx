import { Info } from "lucide-react";
import { Tooltip as RT } from "radix-ui";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export const TooltipProvider = ({ children }: { children: ReactNode }) => (
  <RT.Provider delayDuration={250} skipDelayDuration={300}>
    {children}
  </RT.Provider>
);

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  /** Render nothing extra when there's no content. */
  disabled?: boolean;
  className?: string;
}

const contentClass =
  "ui-pop z-50 max-w-72 rounded-md bg-fg px-2 py-1.5 text-xs leading-snug text-canvas shadow-md " +
  "select-none [text-wrap:pretty]";

export function Tooltip({ content, children, side = "top", align = "center", disabled, className }: TooltipProps) {
  if (disabled || content == null || content === "") return <>{children}</>;
  return (
    <RT.Root>
      <RT.Trigger asChild>{children}</RT.Trigger>
      <RT.Portal>
        <RT.Content side={side} align={align} sideOffset={6} collisionPadding={8} className={cn(contentClass, className)}>
          {content}
        </RT.Content>
      </RT.Portal>
    </RT.Root>
  );
}

/** ⓘ icon that reveals helper text. Use instead of explanatory paragraphs. */
export function InfoTip({
  children,
  label = "More info",
  side = "top",
  className,
}: {
  children: ReactNode;
  label?: string;
  side?: TooltipProps["side"];
  className?: string;
}) {
  return (
    <Tooltip content={children} side={side}>
      <button
        type="button"
        aria-label={label}
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-full align-middle text-fg-subtle " +
            "transition-colors duration-150 hover:text-fg focus-visible:text-fg",
          className,
        )}
        onClick={(e) => e.preventDefault()}
      >
        <Info className="size-3.5" aria-hidden="true" />
      </button>
    </Tooltip>
  );
}
