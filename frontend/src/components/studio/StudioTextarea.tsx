import { forwardRef } from 'react';
import type { TextareaHTMLAttributes, ReactNode } from 'react';

interface StudioTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

const StudioTextarea = forwardRef<HTMLTextAreaElement, StudioTextareaProps>(
  function StudioTextarea({ label, hint, error, className = '', id, ...rest }, ref) {
    const inputId = id ?? rest.name;
    return (
      <label htmlFor={inputId} className="block">
        {label && (
          <span className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2">
            {label}
          </span>
        )}
        <textarea
          {...rest}
          id={inputId}
          ref={ref}
          className={[
            'w-full bg-ink-2 border border-bone/10 px-4 py-3',
            'font-sans text-[14px] leading-relaxed text-bone placeholder:text-bone-4',
            'transition-colors outline-none resize-y',
            'focus:border-brass focus:bg-ink-3',
            error ? 'border-error/60' : '',
            className,
          ]
            .filter(Boolean)
            .join(' ')}
        />
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

export default StudioTextarea;
