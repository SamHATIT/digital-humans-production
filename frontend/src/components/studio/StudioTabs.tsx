/**
 * StudioTabs — Tabs Studio sobres : mono uppercase, soulignement brass animé.
 * Aligné sur les NavLinks du StudioHeader.
 */
import type { ReactNode } from 'react';

export interface StudioTabItem {
  id: string;
  label: ReactNode;
  count?: number;
}

interface StudioTabsProps {
  tabs: StudioTabItem[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export default function StudioTabs({ tabs, active, onChange, className = '' }: StudioTabsProps) {
  return (
    <div
      role="tablist"
      className={`flex items-center gap-1 border-b border-bone/10 ${className}`}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`relative px-4 py-3 font-mono text-[11px] tracking-eyebrow uppercase transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/60 ${
              isActive ? 'text-brass' : 'text-bone-3 hover:text-bone'
            }`}
          >
            <span className="inline-flex items-center gap-2">
              {tab.label}
              {typeof tab.count === 'number' && (
                <span
                  className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] tabular-nums ${
                    isActive ? 'bg-brass/20 text-brass' : 'bg-ink-3 text-bone-4'
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </span>
            {isActive && (
              <span
                aria-hidden="true"
                className="absolute left-0 right-0 -bottom-px h-px bg-brass"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
