/**
 * ProjectHealthCard — vue d'état du projet (overview tab).
 */
import { useLang } from '../../contexts/LangContext';

interface ProjectHealthCardProps {
  phase: string;
  health?: 'nominal' | 'warning' | 'critical';
  creditsUsed?: number;
  creditsAllowance?: number;
  nextMilestone?: string | null;
}

export default function ProjectHealthCard({
  phase,
  health = 'nominal',
  creditsUsed,
  creditsAllowance,
  nextMilestone,
}: ProjectHealthCardProps) {
  const { t } = useLang();
  const healthColor =
    health === 'nominal' ? 'text-success' : health === 'warning' ? 'text-warning' : 'text-error';
  const healthLabel = (() => {
    switch (health) {
      case 'warning': return t('Warning', 'Attention');
      case 'critical': return t('Critical', 'Critique');
      default: return t('Nominal', 'Nominal');
    }
  })();

  const ratio =
    typeof creditsUsed === 'number' && typeof creditsAllowance === 'number' && creditsAllowance > 0
      ? Math.min(100, Math.round((creditsUsed / creditsAllowance) * 100))
      : null;

  return (
    <div className="bg-ink-2 border border-bone/10 p-6">
      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-4">
        {t('Project state', 'État du projet')}
      </p>

      <dl className="space-y-4">
        <div className="flex items-baseline justify-between border-b border-bone/5 pb-3">
          <dt className="font-mono text-[11px] text-bone-3">{t('Phase', 'Phase')}</dt>
          <dd className="font-serif italic text-lg text-bone">{phase}</dd>
        </div>

        <div className="flex items-baseline justify-between border-b border-bone/5 pb-3">
          <dt className="font-mono text-[11px] text-bone-3">{t('Health', 'Santé')}</dt>
          <dd className={`font-mono text-[12px] tracking-eyebrow uppercase ${healthColor}`}>
            ◗ {healthLabel}
          </dd>
        </div>

        {ratio !== null && (
          <div className="border-b border-bone/5 pb-3">
            <div className="flex items-baseline justify-between mb-2">
              <dt className="font-mono text-[11px] text-bone-3">
                {t('Credits used', 'Crédits utilisés')}
              </dt>
              <dd className="font-mono text-[12px] text-bone-2 tabular-nums">
                {creditsUsed} / {creditsAllowance}
              </dd>
            </div>
            <div className="h-px bg-bone/10 relative">
              <div
                className="absolute left-0 top-0 h-px bg-brass"
                style={{ width: `${ratio}%` }}
              />
            </div>
          </div>
        )}

        {nextMilestone && (
          <div className="flex items-baseline justify-between">
            <dt className="font-mono text-[11px] text-bone-3">
              {t('Next milestone', 'Prochain jalon')}
            </dt>
            <dd className="font-mono text-[12px] text-bone-2">{nextMilestone}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
