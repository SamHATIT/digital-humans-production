import { forwardRef } from 'react';
import type { SelectHTMLAttributes, ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

export interface StudioSelectOption {
  value: string;
  label: string;
}

interface StudioSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  options: StudioSelectOption[];
  placeholder?: string;
}

const StudioSelect = forwardRef<HTMLSelectElement, StudioSelectProps>(
  function StudioSelect(
    { label, hint, error, options, placeholder, className = '', id, ...rest },
    ref,
  ) {
    const inputId = id ?? rest.name;
    return (
      <label htmlFor={inputId} className="block">
        {label && (
          <span className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2">
            {label}
          </span>
        )}
        <span className="relative block">
          <select
            {...rest}
            id={inputId}
            ref={ref}
            className={[
              'appearance-none w-full bg-ink-2 border border-bone/10 px-4 py-3 pr-10',
              'font-sans text-[14px] text-bone',
              'transition-colors outline-none cursor-pointer',
              'focus:border-brass focus:bg-ink-3',
              error ? 'border-error/60' : '',
              className,
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {placeholder !== undefined && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bone-4 pointer-events-none"
            aria-hidden
          />
        </span>
        {error && (
          <span className="mt-1 block font-mono text-[11px] text-error">{error}</span>
        )}
        {!error && hint && (
          <span className="mt-1 block font-mono text-[11px] text-bone-4">{hint}</span>
        )}
      </label>
    );
  },
);

export default StudioSelect;
