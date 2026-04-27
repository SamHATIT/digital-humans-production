import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Check,
  Download,
  Edit2,
  Filter,
  Loader2,
  Plus,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import { useLang } from '../contexts/LangContext';
import StudioInput from '../components/studio/StudioInput';
import StudioTextarea from '../components/studio/StudioTextarea';
import StudioSelect from '../components/studio/StudioSelect';
import StudioRadioGroup from '../components/studio/StudioRadioGroup';
import { getAgentAvatar } from '../lib/agents';

type BRPriority = 'must' | 'should' | 'could' | 'wont';
type BRStatus = 'pending' | 'validated' | 'modified' | 'deleted';

interface BusinessRequirement {
  id: number;
  br_id: string;
  category: string | null;
  requirement: string;
  priority: BRPriority;
  status: BRStatus;
  source: 'extracted' | 'manual';
  original_text: string | null;
  client_notes: string | null;
  order_index: number;
}

interface BRStats {
  total: number;
  pending: number;
  validated: number;
  modified: number;
  deleted: number;
}

const CATEGORIES = [
  'Lead Management',
  'Opportunity Management',
  'Account Management',
  'Contact Management',
  'Case Management',
  'Service Cloud',
  'Sales Cloud',
  'Marketing Cloud',
  'Reports & Dashboards',
  'Integration',
  'Security',
  'Data Migration',
  'User Management',
  'Workflow & Automation',
  'Custom Development',
  'Other',
];

const PRIORITY_ACCENT: Record<BRPriority, string> = {
  must: 'border-error/40 text-error',
  should: 'border-ochre/40 text-ochre',
  could: 'border-indigo/40 text-indigo',
  wont: 'border-bone/15 text-bone-4',
};

const STATUS_GLYPH: Record<BRStatus, string> = {
  pending: '○',
  validated: '✓',
  modified: '◑',
  deleted: '✗',
};

export default function BRValidationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const executionId = searchParams.get('executionId');
  const navigate = useNavigate();
  const { t } = useLang();

  const [brs, setBrs] = useState<BusinessRequirement[]>([]);
  const [stats, setStats] = useState<BRStats>({
    total: 0,
    pending: 0,
    validated: 0,
    modified: 0,
    deleted: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);

  const [editingBR, setEditingBR] = useState<BusinessRequirement | null>(null);
  const [inlineEditId, setInlineEditId] = useState<number | null>(null);
  const [inlineEditData, setInlineEditData] = useState<Partial<BusinessRequirement>>({});
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBR, setNewBR] = useState<{
    category: string;
    requirement: string;
    priority: BRPriority;
    client_notes: string;
  }>({ category: '', requirement: '', priority: 'should', client_notes: '' });

  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  useEffect(() => {
    if (projectId) fetchBRs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const fetchBRs = async () => {
    try {
      setLoading(true);
      const data = await api.get(`/api/br/${projectId}`);
      setBrs(data.brs ?? []);
      setStats({
        total: data.total ?? 0,
        pending: data.pending ?? 0,
        validated: data.validated ?? 0,
        modified: data.modified ?? 0,
        deleted: data.deleted ?? 0,
      });
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to load requirements.', 'Échec du chargement des exigences.'),
      );
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateBR = async () => {
    if (!editingBR) return;
    try {
      await api.put(`/api/br/item/${editingBR.id}`, {
        category: editingBR.category,
        requirement: editingBR.requirement,
        priority: editingBR.priority,
        client_notes: editingBR.client_notes,
      });
      setEditingBR(null);
      fetchBRs();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to update requirement.', "Échec de la mise à jour de l'exigence."),
      );
    }
  };

  const handleDeleteBR = async (id: number) => {
    const ok = window.confirm(
      t(
        'Are you sure you want to delete this requirement?',
        'Voulez-vous vraiment supprimer cette exigence ?',
      ),
    );
    if (!ok) return;
    try {
      await api.delete(`/api/br/item/${id}`);
      fetchBRs();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to delete requirement.', 'Échec de la suppression.'),
      );
    }
  };

  const handleAddBR = async () => {
    if (!newBR.requirement.trim()) return;
    try {
      await api.post(`/api/br/${projectId}`, newBR);
      setIsAddModalOpen(false);
      setNewBR({ category: '', requirement: '', priority: 'should', client_notes: '' });
      fetchBRs();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to add requirement.', "Échec de l'ajout."),
      );
    }
  };

  const handleValidateAll = async () => {
    setValidating(true);
    try {
      await api.post(`/api/br/${projectId}/validate-all`);
      if (executionId) {
        await api.post(`/api/pm-orchestrator/execute/${executionId}/resume`);
        navigate(`/execution/${executionId}/monitor`);
      } else {
        navigate(`/execution/${projectId}`);
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to validate requirements.', 'Échec de la validation.'),
      );
    } finally {
      setValidating(false);
    }
  };

  const handleExportCSV = () => {
    const token = localStorage.getItem('token');
    window.open(`/api/br/${projectId}/export?token=${token}`, '_blank');
  };

  const startInlineEdit = (br: BusinessRequirement) => {
    setInlineEditId(br.id);
    setInlineEditData({
      category: br.category,
      requirement: br.requirement,
      priority: br.priority,
      client_notes: br.client_notes,
    });
  };

  const saveInlineEdit = async () => {
    if (inlineEditId === null) return;
    try {
      await api.put(`/api/br/item/${inlineEditId}`, {
        category: inlineEditData.category,
        requirement: inlineEditData.requirement,
        priority: inlineEditData.priority,
        client_notes: inlineEditData.client_notes,
      });
      setInlineEditId(null);
      setInlineEditData({});
      fetchBRs();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('Failed to save changes.', 'Échec de l’enregistrement.'),
      );
    }
  };

  const cancelInlineEdit = () => {
    setInlineEditId(null);
    setInlineEditData({});
  };

  const filteredBRs = useMemo(
    () =>
      brs.filter((br) => {
        if (filterCategory && br.category !== filterCategory) return false;
        if (filterStatus && br.status !== filterStatus) return false;
        return true;
      }),
    [brs, filterCategory, filterStatus],
  );

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
        <Loader2 className="w-5 h-5 animate-spin text-brass mx-auto" />
        <p className="mt-4 font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          {t('Reading the brief…', 'Lecture du brief…')}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="mb-12"
      >
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          {t('№ 03 · Intermission', '№ 03 · Entracte')}
        </p>
        <h1 className="mt-4 font-serif italic text-[44px] md:text-[56px] leading-[1.05] text-bone max-w-3xl">
          {t('Sophie has read your brief.', 'Sophie a lu votre brief.')}
        </h1>

        <div className="mt-6 flex items-start gap-5 max-w-3xl">
          <img
            src={getAgentAvatar('pm', 'small')}
            alt="Sophie"
            className="w-14 h-14 object-cover border border-indigo/40 shrink-0"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
          <p className="font-mono text-[12px] tracking-[0.04em] text-bone-3 leading-relaxed">
            {t(
              `Here is what I understood — ${stats.total} business requirements drafted from your brief. Tell me what is right, what is missing, what to refine.`,
              `Voici ce que j'ai compris — ${stats.total} business requirements rédigées d'après votre brief. Dites-moi ce qui est juste, ce qui manque, ce qu'il faut affiner.`,
            )}
          </p>
        </div>
      </motion.section>

      {error && (
        <div className="mb-6 border border-error/40 bg-ink-2 px-5 py-3 flex items-start gap-3">
          <p className="flex-1 font-mono text-[11px] text-error">{error}</p>
          <button
            type="button"
            onClick={() => setError(null)}
            className="font-mono text-[11px] tracking-cta uppercase text-bone-4 hover:text-bone"
          >
            {t('Dismiss', 'Ignorer')}
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-y border-bone/5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleExportCSV}
            className="inline-flex items-center gap-2 px-3 py-2 border border-bone/15 hover:border-brass/40 transition-colors font-mono text-[11px] tracking-cta uppercase text-bone-3 hover:text-bone"
          >
            <Download className="w-3.5 h-3.5" />
            {t('Export CSV', 'Export CSV')}
          </button>
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-2 px-3 py-2 border border-brass bg-brass/10 hover:bg-brass/20 transition-colors font-mono text-[11px] tracking-cta uppercase text-brass"
          >
            <Plus className="w-3.5 h-3.5" />
            {t('Add requirement', 'Ajouter une exigence')}
          </button>

          <div className="flex items-center gap-2 ml-2">
            <Filter className="w-3.5 h-3.5 text-bone-4" />
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="bg-ink-2 border border-bone/10 px-3 py-1.5 font-mono text-[11px] text-bone-3 focus:border-brass outline-none"
            >
              <option value="">{t('All categories', 'Toutes catégories')}</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-ink-2 border border-bone/10 px-3 py-1.5 font-mono text-[11px] text-bone-3 focus:border-brass outline-none"
            >
              <option value="">{t('All statuses', 'Tous statuts')}</option>
              <option value="pending">{t('Pending', 'En attente')}</option>
              <option value="validated">{t('Validated', 'Validé')}</option>
              <option value="modified">{t('Modified', 'Modifié')}</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-4 font-mono text-[11px]">
          <span className="text-success">
            {stats.validated} {t('validated', 'validé(s)')}
          </span>
          <span className="text-ochre">
            {stats.modified} {t('modified', 'modifié(s)')}
          </span>
          <span className="text-bone-4">
            {stats.pending} {t('pending', 'en attente')}
          </span>
        </div>
      </div>

      {/* BR list */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-12">
        {filteredBRs.map((br, idx) => {
          const isEditing = inlineEditId === br.id;
          return (
            <motion.article
              key={br.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, delay: Math.min(idx, 8) * 0.03 }}
              className="border border-bone/10 bg-ink-2 hover:border-brass/30 transition-colors p-5 group flex flex-col"
            >
              <header className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] tracking-eyebrow uppercase text-brass">
                    {br.br_id}
                  </span>
                  <span
                    aria-hidden
                    className="font-mono text-[14px] text-bone-3"
                    title={br.status}
                  >
                    {STATUS_GLYPH[br.status]}
                  </span>
                </div>
                {!isEditing && (
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() => startInlineEdit(br)}
                      aria-label={t('Edit', 'Éditer')}
                      className="p-1.5 text-bone-4 hover:text-brass transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteBR(br.id)}
                      aria-label={t('Delete', 'Supprimer')}
                      className="p-1.5 text-bone-4 hover:text-error transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </header>

              <div className="flex flex-wrap items-center gap-2 mb-3">
                {isEditing ? (
                  <>
                    <select
                      value={inlineEditData.priority || 'should'}
                      onChange={(e) =>
                        setInlineEditData({
                          ...inlineEditData,
                          priority: e.target.value as BRPriority,
                        })
                      }
                      className="bg-ink-3 border border-bone/15 px-2 py-1 font-mono text-[11px] text-bone"
                    >
                      {(['must', 'should', 'could', 'wont'] as const).map((p) => (
                        <option key={p} value={p}>
                          {p.toUpperCase()}
                        </option>
                      ))}
                    </select>
                    <select
                      value={inlineEditData.category || ''}
                      onChange={(e) =>
                        setInlineEditData({ ...inlineEditData, category: e.target.value })
                      }
                      className="bg-ink-3 border border-bone/15 px-2 py-1 font-mono text-[11px] text-bone"
                    >
                      <option value="">{t('No category', 'Sans catégorie')}</option>
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </>
                ) : (
                  <>
                    <span
                      className={`px-2 py-0.5 border font-mono text-[10px] tracking-eyebrow uppercase ${PRIORITY_ACCENT[br.priority]}`}
                    >
                      {br.priority}
                    </span>
                    {br.category && (
                      <span className="px-2 py-0.5 border border-bone/10 font-mono text-[10px] tracking-eyebrow uppercase text-bone-3">
                        {br.category}
                      </span>
                    )}
                  </>
                )}
              </div>

              {isEditing ? (
                <textarea
                  value={inlineEditData.requirement || ''}
                  onChange={(e) =>
                    setInlineEditData({ ...inlineEditData, requirement: e.target.value })
                  }
                  rows={3}
                  className="w-full bg-ink-3 border border-bone/15 focus:border-brass outline-none px-3 py-2 font-sans text-[13px] text-bone resize-y mb-2"
                />
              ) : (
                <p className="font-sans text-[14px] text-bone leading-relaxed mb-2">
                  {br.requirement}
                </p>
              )}

              {isEditing ? (
                <textarea
                  value={inlineEditData.client_notes || ''}
                  onChange={(e) =>
                    setInlineEditData({
                      ...inlineEditData,
                      client_notes: e.target.value,
                    })
                  }
                  rows={1}
                  placeholder={t('Notes (optional)…', 'Notes (optionnel)…')}
                  className="w-full bg-ink-3 border border-bone/15 focus:border-brass outline-none px-3 py-1.5 font-mono text-[11px] text-bone-3 resize-y mb-2"
                />
              ) : (
                br.client_notes && (
                  <p className="font-mono text-[11px] text-bone-4 mb-2">
                    {t('Note', 'Note')}: {br.client_notes}
                  </p>
                )
              )}

              {isEditing && (
                <div className="flex gap-2 mt-2 pt-3 border-t border-bone/5">
                  <button
                    type="button"
                    onClick={saveInlineEdit}
                    className="inline-flex items-center gap-1 px-3 py-1.5 border border-brass bg-brass/10 hover:bg-brass/20 font-mono text-[11px] tracking-cta uppercase text-brass"
                  >
                    <Save className="w-3 h-3" />
                    {t('Save', 'Enregistrer')}
                  </button>
                  <button
                    type="button"
                    onClick={cancelInlineEdit}
                    className="inline-flex items-center gap-1 px-3 py-1.5 border border-bone/15 hover:border-bone/30 font-mono text-[11px] tracking-cta uppercase text-bone-3"
                  >
                    <X className="w-3 h-3" />
                    {t('Cancel', 'Annuler')}
                  </button>
                </div>
              )}

              {br.source === 'extracted' && (
                <p className="mt-auto pt-3 border-t border-bone/5 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                  {t('Extracted by Sophie', 'Extrait par Sophie')}
                </p>
              )}
            </motion.article>
          );
        })}
      </div>

      {filteredBRs.length === 0 && (
        <div className="border border-bone/10 bg-ink-2 px-6 py-12 mb-8 text-center">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
            {filterCategory || filterStatus
              ? t('No requirement matches the filters.', 'Aucune exigence ne correspond aux filtres.')
              : t('No requirement yet.', 'Aucune exigence pour le moment.')}
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap justify-between items-center gap-4 border-t border-bone/5 pt-6">
        <button
          type="button"
          onClick={() => navigate('/projects')}
          className="font-mono text-[11px] tracking-cta uppercase text-bone-3 hover:text-bone transition-colors"
        >
          {t('← Decline · Cast someone else', '← Refuser · Distribuer autrement')}
        </button>

        <button
          type="button"
          onClick={handleValidateAll}
          disabled={validating || stats.total === 0}
          className="inline-flex items-center gap-3 px-6 py-3 border border-brass bg-brass text-ink hover:bg-brass-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-mono text-[11px] tracking-cta uppercase"
        >
          {validating ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {t('Validating…', 'Validation…')}
            </>
          ) : (
            <>
              <Check className="w-3.5 h-3.5" />
              {t('Approve and continue → SDS phase', 'Approuver et continuer → SDS')}
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </div>

      {/* Edit Modal */}
      {editingBR && (
        <Modal onClose={() => setEditingBR(null)} title={`${t('Edit', 'Éditer')} ${editingBR.br_id}`}>
          <div className="space-y-5">
            <StudioSelect
              name="category"
              label={t('Category', 'Catégorie')}
              value={editingBR.category ?? ''}
              onChange={(e) =>
                setEditingBR({ ...editingBR, category: e.target.value })
              }
              placeholder={t('Select a category…', 'Choisir une catégorie…')}
              options={CATEGORIES.map((c) => ({ value: c, label: c }))}
            />
            <StudioTextarea
              name="requirement"
              label={t('Requirement', 'Exigence')}
              value={editingBR.requirement}
              onChange={(e) =>
                setEditingBR({ ...editingBR, requirement: e.target.value })
              }
              rows={4}
            />
            <StudioRadioGroup
              name="priority"
              label={t('Priority', 'Priorité')}
              value={editingBR.priority}
              onChange={(v) =>
                setEditingBR({ ...editingBR, priority: v as BRPriority })
              }
              options={(['must', 'should', 'could', 'wont'] as const).map((p) => ({
                value: p,
                label: p.toUpperCase(),
              }))}
            />
            <StudioTextarea
              name="client_notes"
              label={t('Notes (optional)', 'Notes (optionnel)')}
              value={editingBR.client_notes ?? ''}
              onChange={(e) =>
                setEditingBR({ ...editingBR, client_notes: e.target.value })
              }
              rows={2}
            />
            {editingBR.original_text && editingBR.source === 'extracted' && (
              <div>
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2">
                  {t('Original (from Sophie)', 'Original (par Sophie)')}
                </p>
                <p className="border border-bone/10 bg-ink-3 px-4 py-3 font-mono text-[12px] text-bone-3 leading-relaxed">
                  {editingBR.original_text}
                </p>
              </div>
            )}
          </div>
          <div className="mt-8 flex justify-end gap-3 border-t border-bone/5 pt-5">
            <button
              type="button"
              onClick={() => setEditingBR(null)}
              className="px-4 py-2 border border-bone/15 hover:border-bone/30 font-mono text-[11px] tracking-cta uppercase text-bone-3"
            >
              {t('Cancel', 'Annuler')}
            </button>
            <button
              type="button"
              onClick={handleUpdateBR}
              className="inline-flex items-center gap-2 px-4 py-2 border border-brass bg-brass/10 hover:bg-brass/20 font-mono text-[11px] tracking-cta uppercase text-brass"
            >
              <Save className="w-3.5 h-3.5" />
              {t('Save', 'Enregistrer')}
            </button>
          </div>
        </Modal>
      )}

      {/* Add Modal */}
      {isAddModalOpen && (
        <Modal
          onClose={() => setIsAddModalOpen(false)}
          title={t('New requirement', 'Nouvelle exigence')}
        >
          <div className="space-y-5">
            <StudioSelect
              name="category"
              label={t('Category', 'Catégorie')}
              value={newBR.category}
              onChange={(e) => setNewBR({ ...newBR, category: e.target.value })}
              placeholder={t('Select a category…', 'Choisir une catégorie…')}
              options={CATEGORIES.map((c) => ({ value: c, label: c }))}
            />
            <StudioTextarea
              name="requirement"
              label={t('Requirement *', 'Exigence *')}
              value={newBR.requirement}
              onChange={(e) => setNewBR({ ...newBR, requirement: e.target.value })}
              rows={4}
              placeholder={t(
                'Describe the business requirement…',
                "Décrivez l'exigence métier…",
              )}
            />
            <StudioRadioGroup
              name="newPriority"
              label={t('Priority', 'Priorité')}
              value={newBR.priority}
              onChange={(v) =>
                setNewBR({ ...newBR, priority: v as BRPriority })
              }
              options={(['must', 'should', 'could', 'wont'] as const).map((p) => ({
                value: p,
                label: p.toUpperCase(),
              }))}
            />
            <StudioInput
              name="client_notes"
              label={t('Notes (optional)', 'Notes (optionnel)')}
              value={newBR.client_notes}
              onChange={(e) => setNewBR({ ...newBR, client_notes: e.target.value })}
            />
          </div>
          <div className="mt-8 flex justify-end gap-3 border-t border-bone/5 pt-5">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="px-4 py-2 border border-bone/15 hover:border-bone/30 font-mono text-[11px] tracking-cta uppercase text-bone-3"
            >
              {t('Cancel', 'Annuler')}
            </button>
            <button
              type="button"
              onClick={handleAddBR}
              disabled={!newBR.requirement.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 border border-brass bg-brass/10 hover:bg-brass/20 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-[11px] tracking-cta uppercase text-brass"
            >
              <Plus className="w-3.5 h-3.5" />
              {t('Add', 'Ajouter')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

interface ModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div className="fixed inset-0 bg-ink/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className="bg-ink-2 border border-bone/10 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="p-6 border-b border-bone/5 flex items-center justify-between">
          <h2 className="font-serif italic text-2xl text-bone">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-bone-4 hover:text-bone transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </motion.div>
    </div>
  );
}
