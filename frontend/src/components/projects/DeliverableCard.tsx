/**
 * DeliverableCard — item de liste pour le tab Deliverables.
 */
import type { ReactNode } from 'react';
import { FileText, Download, Eye, Package } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';

export type DeliverableKind = 'doc' | 'zip' | 'schema' | 'preview';

export interface DeliverableItem {
  id: string | number;
  kind: DeliverableKind;
  title: string;
  version?: string;
  date?: string;
  meta?: string;
}

interface DeliverableCardProps {
  item: DeliverableItem;
  onView?: () => void;
  onDownload?: () => void;
}

const ICONS: Record<DeliverableKind, ReactNode> = {
  doc:     <FileText className="w-4 h-4" />,
  zip:     <Package className="w-4 h-4" />,
  schema:  <FileText className="w-4 h-4" />,
  preview: <Eye className="w-4 h-4" />,
};

export default function DeliverableCard({ item, onView, onDownload }: DeliverableCardProps) {
  const { t } = useLang();

  return (
    <div className="bg-ink-2 border border-bone/10 hover:border-brass/30 transition-colors p-5 flex items-center justify-between gap-6">
      <div className="flex items-center gap-4 min-w-0 flex-1">
        <div className="w-10 h-10 bg-ink-3 border border-bone/10 flex items-center justify-center text-brass flex-shrink-0">
          {ICONS[item.kind]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-3 mb-1">
            <h3 className="font-serif italic text-lg text-bone truncate">{item.title}</h3>
            {item.version && (
              <span className="font-mono text-[10px] tracking-eyebrow uppercase text-brass flex-shrink-0">
                {item.version}
              </span>
            )}
          </div>
          <p className="font-mono text-[11px] text-bone-4 truncate">
            {[item.date, item.meta].filter(Boolean).join(' · ')}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {onView && (
          <button
            type="button"
            onClick={onView}
            className="px-3 py-2 font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 hover:text-bone transition-colors"
          >
            {t('View', 'Voir')}
          </button>
        )}
        {onDownload && (
          <button
            type="button"
            onClick={onDownload}
            className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] tracking-eyebrow uppercase text-brass hover:text-bone transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            {t('Download', 'Télécharger')}
          </button>
        )}
      </div>
    </div>
  );
}
