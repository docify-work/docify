import { Slot } from "radix-ui";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
export type ButtonSize = "xs" | "sm" | "md";

const base =
  "relative inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out " +
  "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 " +
  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg shadow-sm hover:bg-accent-hover",
  secondary: "border border-border bg-surface text-fg shadow-xs hover:bg-surface-2 hover:border-border-strong",
  ghost: "text-fg-muted hover:bg-surface-2 hover:text-fg",
  subtle: "bg-surface-2 text-fg hover:bg-surface-3",
  danger: "bg-danger text-white shadow-sm hover:bg-danger-hover",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-6 px-2 text-xs [&_svg]:size-3.5",
  sm: "h-7 px-2.5 text-xs [&_svg]:size-3.5",
  md: "h-8 px-3 text-sm [&_svg]:size-4",
};

const iconSizes: Record<ButtonSize, string> = {
  xs: "size-6 [&_svg]:size-3.5",
  sm: "size-7 [&_svg]:size-3.5",
  md: "size-8 [&_svg]:size-4",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Leading icon (lucide element). */
  icon?: ReactNode;
  /** Trailing icon. */
  iconRight?: ReactNode;
  /** Render as the child element (e.g. a router <Link>) with button styles. */
  asChild?: boolean;
  /** Square, icon-only. Prefer <IconButton> which adds a label + tooltip. */
  iconOnly?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    icon,
    iconRight,
    asChild = false,
    iconOnly = false,
    className,
    children,
    disabled,
    type,
    ...rest
  },
  ref,
) {
  const classes = cn(base, variants[variant], iconOnly ? iconSizes[size] : sizes[size], className);
  if (asChild) {
    return (
      <Slot.Root ref={ref} className={classes} {...rest}>
        {children}
      </Slot.Root>
    );
  }
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner size={size === "md" ? 14 : 12} /> : icon}
      {children}
      {iconRight}
    </button>
  );
});
