import { DropdownMenu as RM, Popover as RP } from "radix-ui";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const surface =
  "ui-pop z-50 min-w-44 overflow-hidden rounded-lg border border-border bg-surface p-1 text-sm shadow-lg focus:outline-none";

// ------------------------------------------------------------------ DropdownMenu

export function DropdownMenu({
  trigger,
  children,
  align = "start",
  side = "bottom",
  className,
}: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}) {
  return (
    <RM.Root modal={false}>
      <RM.Trigger asChild>{trigger}</RM.Trigger>
      <RM.Portal>
        <RM.Content align={align} side={side} sideOffset={6} collisionPadding={8} className={cn(surface, className)}>
          {children}
        </RM.Content>
      </RM.Portal>
    </RM.Root>
  );
}

export function MenuItem({
  icon,
  children,
  onSelect,
  danger,
  disabled,
  shortcut,
  asChild,
}: {
  icon?: ReactNode;
  children: ReactNode;
  onSelect?: () => void;
  danger?: boolean;
  disabled?: boolean;
  shortcut?: ReactNode;
  asChild?: boolean;
}) {
  return (
    <RM.Item
      asChild={asChild}
      disabled={disabled}
      onSelect={onSelect}
      className={cn(
        "flex h-8 cursor-pointer select-none items-center gap-2 rounded-md px-2 outline-none transition-colors duration-100 " +
          "data-[highlighted]:bg-surface-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-3.5",
        danger ? "text-danger" : "text-fg",
      )}
    >
      {asChild ? (
        children
      ) : (
        <span className="flex w-full items-center gap-2">
          {icon && <span className={danger ? "text-danger" : "text-fg-subtle"}>{icon}</span>}
          <span className="flex-1 truncate">{children}</span>
          {shortcut && <span className="text-2xs text-fg-subtle">{shortcut}</span>}
        </span>
      )}
    </RM.Item>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <RM.Label className="px-2 pb-1 pt-1.5 text-2xs font-medium uppercase tracking-wide text-fg-subtle">{children}</RM.Label>;
}

export function MenuSeparator() {
  return <RM.Separator className="-mx-1 my-1 h-px bg-border" />;
}

// ------------------------------------------------------------------ Popover

export function Popover({
  trigger,
  children,
  align = "center",
  side = "bottom",
  className,
  open,
  onOpenChange,
}: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  return (
    <RP.Root open={open} onOpenChange={onOpenChange}>
      <RP.Trigger asChild>{trigger}</RP.Trigger>
      <RP.Portal>
        <RP.Content align={align} side={side} sideOffset={6} collisionPadding={8} className={cn(surface, "p-3", className)}>
          {children}
        </RP.Content>
      </RP.Portal>
    </RP.Root>
  );
}
