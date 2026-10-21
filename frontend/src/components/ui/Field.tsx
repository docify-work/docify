import { AnimatePresence, motion } from "motion/react";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { InfoTip } from "./Tooltip";

export interface FieldProps {
  label?: ReactNode;
  /** Helper text — shown in an ⓘ tooltip next to the label. */
  info?: ReactNode;
  error?: string | null;
  /** Small right-aligned text in the label row (e.g. a "Forgot?" link). */
  aside?: ReactNode;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

/** Label row + control + animated error. Every form control renders through this. */
export function Field({ label, info, error, aside, htmlFor, className, children }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {(label || aside) && (
        <div className="flex min-h-4 items-center gap-1">
          {label && (
            <label htmlFor={htmlFor} className="text-xs font-medium text-fg-muted">
              {label}
            </label>
          )}
          {info && <InfoTip>{info}</InfoTip>}
          {aside && <span className="ml-auto text-xs">{aside}</span>}
        </div>
      )}
      {children}
      <AnimatePresence initial={false}>
        {error && (
          <motion.p
            id={htmlFor ? `${htmlFor}-error` : undefined}
            role="alert"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="text-xs text-danger"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

export const controlClass =
  "w-full rounded-md border border-border bg-surface px-2.5 text-sm text-fg shadow-xs " +
  "placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-150 ease-out " +
  "hover:border-border-strong focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15 " +
  "disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-danger aria-invalid:focus:ring-danger/15";

type ControlExtras = Omit<FieldProps, "children" | "htmlFor"> & { fieldClassName?: string };

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size">, ControlExtras {
  size?: "sm" | "md";
  /** Leading icon inside the input. */
  icon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, info, error, aside, fieldClassName, className, id, size = "md", icon, ...rest },
  ref,
) {
  const auto = useId();
  const inputId = id ?? auto;
  const control = (
    <div className="relative">
      {icon && (
        <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-fg-subtle [&_svg]:size-3.5">
          {icon}
        </span>
      )}
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className={cn(controlClass, size === "sm" ? "h-7 text-xs" : "h-8", icon ? "pl-8" : undefined, className)}
        {...rest}
      />
    </div>
  );
  if (!label && !error && !aside) return control;
  return (
    <Field label={label} info={info} error={error} aside={aside} htmlFor={inputId} className={fieldClassName}>
      {control}
    </Field>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, ControlExtras {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, info, error, aside, fieldClassName, className, id, ...rest },
  ref,
) {
  const auto = useId();
  const inputId = id ?? auto;
  const control = (
    <textarea
      ref={ref}
      id={inputId}
      aria-invalid={error ? true : undefined}
      aria-describedby={error ? `${inputId}-error` : undefined}
      className={cn(controlClass, "min-h-16 resize-y py-1.5 leading-relaxed", className)}
      {...rest}
    />
  );
  if (!label && !error && !aside) return control;
  return (
    <Field label={label} info={info} error={error} aside={aside} htmlFor={inputId} className={fieldClassName}>
      {control}
    </Field>
  );
});

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size">, ControlExtras {
  options: SelectOption[];
  size?: "sm" | "md";
}

/** Native select (best keyboard/mobile behaviour), styled to match. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, info, error, aside, fieldClassName, className, id, options, size = "md", ...rest },
  ref,
) {
  const auto = useId();
  const inputId = id ?? auto;
  const control = (
    <div className={cn("relative", className)}>
      <select
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        className={cn(controlClass, "appearance-none pr-7", size === "sm" ? "h-7 text-xs" : "h-8")}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle"
      />
    </div>
  );
  if (!label && !error && !aside) return control;
  return (
    <Field label={label} info={info} error={error} aside={aside} htmlFor={inputId} className={fieldClassName}>
      {control}
    </Field>
  );
});
