/**
 * ProjectActivityFeed — feed mono "Recent activity" (overview tab).
 */
import { useLang } from '../../contexts/LangContext';

export interface ActivityItem {
  id: string | number;
  who: string;
  what: string;
  when: string; // formatted relative time
  accent?: 'indigo' | 'plum' | 'terra' | 'sage' | 'ochre' | 'brass';
}

interface ProjectActivityFeedProps {
  items: ActivityItem[];
}

const ACCENT_TEXT: Record<NonNullable<ActivityItem['accent']>, string> = {
  indigo: 'text-indigo',
  plum:   'text-plum',
  terra:  'text-terra',
  sage:   'text-sage',
  ochre:  'text-ochre',
  brass:  'text-brass',
};

export default function ProjectActivityFeed({ items }: ProjectActivityFeedProps) {
  const { t } = useLang();

  return (
    <div className="bg-ink-2 border border-bone/10 p-6">
      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-4">
        {t('Recent activity', 'Activité récente')}
      </p>

      {items.length === 0 ? (
        <p className="font-mono text-[12px] text-bone-3 italic py-2">
          {t('Nothing yet.', 'Rien pour le moment.')}
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="flex items-baseline gap-3 pb-3 border-b border-bone/5 last:border-0 last:pb-0">
              <span className={`font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[item.accent ?? 'brass']} flex-shrink-0`}>
                ◗ {item.who}
              </span>
              <span className="font-mono text-[12px] text-bone-2 flex-1 leading-relaxed">
                {item.what}
              </span>
              <span className="font-mono text-[10px] text-bone-4 flex-shrink-0 tabular-nums">
                {item.when}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
