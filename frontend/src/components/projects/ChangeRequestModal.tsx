/**
 * ChangeRequestModal — création d'un change request.
 */
import { useState } from 'react';
import { X } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';
import StudioInput from '../studio/StudioInput';
import StudioTextarea from '../studio/StudioTextarea';
import StudioSelect from '../studio/StudioSelect';
import StudioRadioGroup from '../studio/StudioRadioGroup';

interface ChangeRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { title: string; description: string; category: string; priority: 'low' | 'medium' | 'high' }) => void | Promise<void>;
}

const CATEGORIES = [
  { value: 'business_rule', en: 'Business rule',  fr: 'Règle métier' },
  { value: 'integration',   en: 'Integration',    fr: 'Intégration' },
  { value: 'ui_ux',         en: 'UI / UX',        fr: 'UI / UX' },
  { value: 'security',      en: 'Security',       fr: 'Sécurité' },
  { value: 'other',         en: 'Other',          fr: 'Autre' },
];

export default function ChangeRequestModal({ isOpen, onClose, onSubmit }: ChangeRequestModalProps) {
  const { t } = useLang();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('business_rule');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit({ title: title.trim(), description: description.trim(), category, priority });
      setTitle(''); setDescription(''); setCategory('business_rule'); setPriority('medium');
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-ink-2 border border-brass/30 w-full max-w-xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-start justify-between p-6 border-b border-bone/10">
          <div>
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-1">
              {t('New change request', 'Nouvelle demande de changement')}
            </p>
            <h3 className="font-serif italic text-2xl text-bone">
              {t('Speak up.', 'Exprimez-vous.')}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-bone-4 hover:text-bone transition-colors"
            aria-label={t('Close', 'Fermer')}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <StudioInput
            label={t('Title', 'Titre')}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('Short summary', 'Résumé court')}
          />

          <StudioTextarea
            label={t('Description', 'Description')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('Tell us what should change and why.', 'Décrivez ce qui doit changer, et pourquoi.')}
            rows={5}
          />

          <StudioSelect
            label={t('Category', 'Catégorie')}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={CATEGORIES.map((c) => ({ value: c.value, label: t(c.en, c.fr) }))}
          />

          <StudioRadioGroup
            name="cr-priority"
            label={t('Priority', 'Priorité')}
            value={priority}
            onChange={(v) => setPriority(v as 'low' | 'medium' | 'high')}
            options={[
              { value: 'low',    label: t('Low',    'Basse') },
              { value: 'medium', label: t('Medium', 'Moyenne') },
              { value: 'high',   label: t('High',   'Haute') },
            ]}
          />
        </div>

        <div className="flex items-center justify-end gap-2 p-6 border-t border-bone/10">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 font-mono text-[10px] tracking-cta uppercase text-bone-3 hover:text-bone transition-colors"
          >
            {t('Cancel', 'Annuler')}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !title.trim() || !description.trim()}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? t('Submitting…', 'Envoi…') : t('Submit', 'Envoyer')}
            {!submitting && <span aria-hidden="true">→</span>}
          </button>
        </div>
      </div>
    </div>
  );
}
