import type { ReactNode } from 'react';

export interface StudioRadioOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
}

interface StudioRadioGroupProps {
  name: string;
  label?: ReactNode;
  options: StudioRadioOption[];
  value: string;
  onChange: (value: string) => void;
  layout?: 'grid' | 'stack';
  error?: ReactNode;
}

export default function StudioRadioGroup({
  name,
  label,
  options,
  value,
  onChange,
  layout = 'grid',
  error,
}: StudioRadioGroupProps) {
  return (
    <fieldset className="block">
      {label && (
        <legend className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2">
          {label}
        </legend>
      )}
      <div
        className={
          layout === 'grid'
            ? 'grid grid-cols-1 sm:grid-cols-2 gap-3'
            : 'flex flex-col gap-3'
        }
      >
        {options.map((opt) => {
          const checked = opt.value === value;
          return (
            <label
              key={opt.value}
              className={[
                'cursor-pointer border px-4 py-3 transition-colors',
                checked
                  ? 'border-brass bg-ink-3'
                  : 'border-bone/10 bg-ink-2 hover:border-brass/40',
              ].join(' ')}
            >
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={checked}
                onChange={() => onChange(opt.value)}
                className="sr-only"
              />
              <span className="flex items-center gap-3">
                <span
                  aria-hidden
                  className={[
                    'inline-block w-3 h-3 rounded-full border',
                    checked ? 'border-brass bg-brass' : 'border-bone/30',
                  ].join(' ')}
                />
                <span className="flex flex-col leading-tight">
                  <span className="font-sans text-[14px] text-bone">{opt.label}</span>
                  {opt.description && (
                    <span className="mt-1 font-mono text-[11px] text-bone-4">
                      {opt.description}
                    </span>
                  )}
                </span>
              </span>
            </label>
          );
        })}
      </div>
      {error && (
        <span className="mt-2 block font-mono text-[11px] text-error">{error}</span>
      )}
    </fieldset>
  );
}
