import { Check, Minus } from "lucide-react";
import { Checkbox as RC, Switch as RS } from "radix-ui";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { InfoTip } from "./Tooltip";

interface ToggleBase {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: ReactNode;
  info?: ReactNode;
  disabled?: boolean;
  id?: string;
  className?: string;
  "aria-label"?: string;
}

/** On/off setting. Label on the left, switch on the right (settings-row style). */
export function Switch({ checked, onCheckedChange, label, info, disabled, id, className, ...aria }: ToggleBase) {
  const auto = useId();
  const sid = id ?? auto;
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {label && (
        <label htmlFor={sid} className="text-sm text-fg">
          {label}
        </label>
      )}
      {info && <InfoTip>{info}</InfoTip>}
      <RS.Root
        id={sid}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-label={aria["aria-label"]}
        className={cn(
          "relative ml-auto inline-flex h-[18px] w-8 shrink-0 items-center rounded-full border border-transparent " +
            "bg-border-strong transition-colors duration-200 ease-out data-[state=checked]:bg-accent " +
            "disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-ring",
        )}
      >
        <RS.Thumb
          className={
            "block size-3.5 translate-x-0.5 rounded-full bg-white shadow-sm transition-transform duration-200 " +
            "ease-[var(--ease-out)] data-[state=checked]:translate-x-[15px]"
          }
        />
      </RS.Root>
    </div>
  );
}

export interface CheckboxProps extends Omit<ToggleBase, "checked"> {
  checked: boolean | "indeterminate";
}

export function Checkbox({ checked, onCheckedChange, label, info, disabled, id, className, ...aria }: CheckboxProps) {
  const auto = useId();
  const cid = id ?? auto;
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <RC.Root
        id={cid}
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        disabled={disabled}
        aria-label={aria["aria-label"]}
        className={
          "grid size-4 shrink-0 place-items-center rounded-[4px] border border-border-strong bg-surface shadow-xs " +
          "transition-colors duration-150 hover:border-accent data-[state=checked]:border-accent " +
          "data-[state=checked]:bg-accent data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent " +
          "text-accent-fg disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-ring"
        }
      >
        <RC.Indicator className="animate-fade-in">
          {checked === "indeterminate" ? <Minus className="size-3" strokeWidth={3} /> : <Check className="size-3" strokeWidth={3} />}
        </RC.Indicator>
      </RC.Root>
      {label && (
        <label htmlFor={cid} className={cn("text-sm", disabled ? "text-fg-subtle" : "text-fg")}>
          {label}
        </label>
      )}
      {info && <InfoTip>{info}</InfoTip>}
    </div>
  );
}
