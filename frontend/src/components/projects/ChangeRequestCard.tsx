/**
 * ChangeRequestCard — item expandable pour le tab Change requests.
 */
import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';

export type CRStatus = 'draft' | 'submitted' | 'analyzed' | 'approved' | 'processing' | 'completed' | 'rejected';
export type CRPriority = 'low' | 'medium' | 'high';

export interface ChangeRequestItem {
  id: number;
  title: string;
  description: string;
  category?: string;
  status: CRStatus;
  priority: CRPriority;
  created_at?: string;
  author?: string;
}

interface ChangeRequestCardProps {
  item: ChangeRequestItem;
  onSubmit?: () => void;
  onApprove?: () => void;
}

const STATUS_LABEL: Record<CRStatus, { en: string; fr: string }> = {
  draft:      { en: 'Draft',      fr: 'Brouillon' },
  submitted:  { en: 'Submitted',  fr: 'Soumis' },
  analyzed:   { en: 'Analyzed',   fr: 'Analysé' },
  approved:   { en: 'Approved',   fr: 'Approuvé' },
  processing: { en: 'Processing', fr: 'En cours' },
  completed:  { en: 'Completed',  fr: 'Terminé' },
  rejected:   { en: 'Rejected',   fr: 'Rejeté' },
};

const STATUS_COLOR: Record<CRStatus, string> = {
  draft:      'text-bone-4',
  submitted:  'text-indigo',
  analyzed:   'text-ochre',
  approved:   'text-sage',
  processing: 'text-plum',
  completed:  'text-success',
  rejected:   'text-error',
};

const PRIORITY_DOT: Record<CRPriority, string> = {
  low:    'bg-bone-4',
  medium: 'bg-ochre',
  high:   'bg-error',
};

export default function ChangeRequestCard({ item, onSubmit, onApprove }: ChangeRequestCardProps) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-ink-2 border border-bone/10 hover:border-brass/30 transition-colors">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left p-5 flex items-center justify-between gap-4"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 mb-1.5">
            <span className={`w-2 h-2 rounded-full ${PRIORITY_DOT[item.priority]}`} aria-label={`priority ${item.priority}`} />
            <p className={`font-mono text-[10px] tracking-eyebrow uppercase ${STATUS_COLOR[item.status]}`}>
              {t(STATUS_LABEL[item.status].en, STATUS_LABEL[item.status].fr)}
            </p>
            {item.category && (
              <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                · {item.category}
              </p>
            )}
          </div>
          <h3 className="font-serif italic text-lg text-bone leading-tight truncate">
            {item.title}
          </h3>
          {!open && (
            <p className="font-mono text-[11px] text-bone-3 line-clamp-1 mt-1">
              {item.description}
            </p>
          )}
        </div>
        <div className="text-bone-4 flex-shrink-0">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-bone/5 pt-4 space-y-4">
          <p className="font-mono text-[12px] text-bone-2 leading-relaxed whitespace-pre-wrap">
            {item.description}
          </p>

          {(item.author || item.created_at) && (
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {[item.author, item.created_at].filter(Boolean).join(' · ')}
            </p>
          )}

          <div className="flex items-center gap-2 pt-2">
            {item.status === 'draft' && onSubmit && (
              <button
                type="button"
                onClick={onSubmit}
                className="px-4 py-2 font-mono text-[10px] tracking-cta uppercase bg-brass text-ink hover:bg-brass-2 transition-colors"
              >
                {t('Submit for review', 'Soumettre à revue')} →
              </button>
            )}
            {item.status === 'analyzed' && onApprove && (
              <button
                type="button"
                onClick={onApprove}
                className="px-4 py-2 font-mono text-[10px] tracking-cta uppercase bg-sage text-ink hover:opacity-90 transition-opacity"
              >
                ✓ {t('Approve', 'Approuver')}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
