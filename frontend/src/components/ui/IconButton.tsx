import { forwardRef, type ReactNode } from "react";
import { Button, type ButtonProps } from "./Button";
import { Tooltip } from "./Tooltip";

export interface IconButtonProps extends Omit<ButtonProps, "icon" | "iconRight" | "iconOnly" | "children"> {
  /** Accessible name; also shown as tooltip. */
  label: string;
  icon: ReactNode;
  tooltip?: boolean;
  tooltipSide?: "top" | "right" | "bottom" | "left";
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "ghost", size = "sm", tooltip = true, tooltipSide, ...rest },
  ref,
) {
  const btn = (
    <Button ref={ref} variant={variant} size={size} iconOnly aria-label={label} {...rest}>
      {rest.loading ? null : icon}
    </Button>
  );
  return tooltip ? (
    <Tooltip content={label} side={tooltipSide}>
      {btn}
    </Tooltip>
  ) : (
    btn
  );
});
