import { X } from "lucide-react";
import { Dialog as RD } from "radix-ui";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { Input } from "./Field";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  /** One short line under the title (screen readers get it as the description). */
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const widths = { sm: "max-w-sm", md: "max-w-md", lg: "max-w-2xl" } as const;

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "sm", className }: DialogProps) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="ui-overlay fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]" />
        <RD.Content
          className={cn(
            "ui-dialog fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 flex max-h-[85vh] w-[calc(100vw-2rem)] flex-col rounded-lg border " +
              "border-border bg-surface shadow-lg focus:outline-none",
            widths[size],
            className,
          )}
        >
          <div className="flex items-start gap-2 px-4 pt-3.5">
            <div className="min-w-0 flex-1">
              <RD.Title className="text-base font-semibold">{title}</RD.Title>
              {description ? (
                <RD.Description className="mt-0.5 text-xs text-fg-muted">{description}</RD.Description>
              ) : (
                <RD.Description className="sr-only">{typeof title === "string" ? title : "Dialog"}</RD.Description>
              )}
            </div>
            <RD.Close
              aria-label="Close"
              className="-mr-1.5 grid size-7 place-items-center rounded-md text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg"
            >
              <X className="size-4" />
            </RD.Close>
          </div>
          {children && <div className="min-h-0 flex-1 overflow-auto px-4 py-3">{children}</div>}
          {footer && (
            <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-2.5">{footer}</div>
          )}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel?: string;
  tone?: "danger" | "primary";
  loading?: boolean;
  /** If set, the user must type this text to enable the confirm button. */
  confirmText?: string;
  onConfirm: () => void;
}

export function ConfirmDialog(props: ConfirmDialogProps) {
  // Remount the body on each open so the typed confirmation resets.
  return (
    <Dialog
      open={props.open}
      onOpenChange={props.onOpenChange}
      title={props.title}
      description={props.description}
      size="sm"
    >
      {props.open ? <ConfirmBody {...props} /> : null}
    </Dialog>
  );
}

function ConfirmBody({ onOpenChange, confirmLabel = "Confirm", tone = "danger", loading, confirmText, onConfirm }: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const blocked = confirmText != null && typed !== confirmText;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!blocked) onConfirm();
      }}
      className="flex flex-col gap-3"
    >
      {confirmText != null && (
        <Input
          autoFocus
          label={
            <>
              Type <code className="rounded-xs bg-surface-2 px-1 text-fg">{confirmText}</code> to confirm
            </>
          }
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
      )}
      <div className="-mx-4 -mb-3 flex justify-end gap-2 border-t border-border px-4 py-2.5">
        <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          size="sm"
          type="submit"
          variant={tone === "danger" ? "danger" : "primary"}
          loading={loading}
          disabled={blocked}
          autoFocus={confirmText == null}
        >
          {confirmLabel}
        </Button>
      </div>
    </form>
  );
}

export interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  side?: "left" | "right";
  children: ReactNode;
  className?: string;
  /** Hide the header row (e.g. a nav drawer that brings its own). */
  bare?: boolean;
}

/** Side sheet. Used for the mobile nav and detail panels. */
export function Drawer({ open, onOpenChange, title, side = "right", children, className, bare }: DrawerProps) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="ui-overlay fixed inset-0 z-50 bg-overlay" />
        <RD.Content
          className={cn(
            "fixed inset-y-0 z-50 flex w-[min(420px,calc(100vw-3rem))] flex-col border-border bg-surface shadow-lg focus:outline-none",
            side === "right" ? "ui-drawer-right right-0 border-l" : "ui-drawer-left left-0 border-r",
            className,
          )}
        >
          <RD.Title className="sr-only">{title}</RD.Title>
          <RD.Description className="sr-only">{typeof title === "string" ? title : "Panel"}</RD.Description>
          {!bare && (
            <div className="flex h-11 items-center justify-between border-b border-border px-3">
              <span className="text-sm font-semibold" aria-hidden="true">
                {title}
              </span>
              <RD.Close aria-label="Close" className="grid size-7 place-items-center rounded-md text-fg-subtle hover:bg-surface-2 hover:text-fg">
                <X className="size-4" />
              </RD.Close>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-auto">{children}</div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
