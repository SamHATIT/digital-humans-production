/**
 * ProjectDetailPage — A5.4
 * Hub Studio : Overview / Deliverables / Change requests / Settings (modal).
 * № 03 · the work in production.
 *
 * Préserve TOUS les contrats API existants (project, sds-versions, change-requests, chat).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Loader2, Settings, ExternalLink } from 'lucide-react';
import api from '../services/api';
import { useLang } from '../contexts/LangContext';
import StudioTabs from '../components/studio/StudioTabs';
import ProjectHealthCard from '../components/projects/ProjectHealthCard';
import ProjectActivityFeed from '../components/projects/ProjectActivityFeed';
import type { ActivityItem } from '../components/projects/ProjectActivityFeed';
import DeliverableCard from '../components/projects/DeliverableCard';
import type { DeliverableItem } from '../components/projects/DeliverableCard';
import ChangeRequestCard from '../components/projects/ChangeRequestCard';
import type { ChangeRequestItem, CRStatus, CRPriority } from '../components/projects/ChangeRequestCard';
import ChangeRequestModal from '../components/projects/ChangeRequestModal';
import ProjectSettingsModal from '../components/ProjectSettingsModal';

interface Project {
  id: number;
  name: string;
  description: string;
  salesforce_product: string;
  organization_type: string;
  status: string;
  current_sds_version: number;
  sf_connected?: boolean;
  git_connected?: boolean;
  sf_instance_url?: string;
  git_repo_url?: string;
}

interface SDSVersion {
  id: number;
  version_number: number;
  file_name: string;
  notes: string;
  generated_at: string;
  download_url: string;
}

interface RawCR {
  id: number;
  cr_number?: string;
  title: string;
  description?: string;
  category: string;
  status: string;
  priority: string;
  created_at: string;
}

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  message: string;
  created_at: string;
}

type TabId = 'overview' | 'deliverables' | 'changes' | 'chat';

function normalizePriority(p: string): CRPriority {
  const v = p?.toLowerCase();
  if (v === 'low' || v === 'medium' || v === 'high') return v;
  return 'medium';
}
function normalizeStatus(s: string): CRStatus {
  const v = s?.toLowerCase();
  const allowed: CRStatus[] = ['draft', 'submitted', 'analyzed', 'approved', 'processing', 'completed', 'rejected'];
  return (allowed.includes(v as CRStatus) ? v : 'draft') as CRStatus;
}

function phaseLabel(status: string, t: <T>(en: T, fr: T) => T): string {
  const map: Record<string, { en: string; fr: string }> = {
    draft:          { en: 'Casting',     fr: 'Casting' },
    in_progress:    { en: 'Act II',      fr: 'Acte II' },
    sds_generated:  { en: 'SDS phase',   fr: 'Phase SDS' },
    sds_in_review:  { en: 'SDS review',  fr: 'Revue SDS' },
    sds_approved:   { en: 'SDS approved', fr: 'SDS approuvé' },
    build_ready:    { en: 'BUILD phase', fr: 'Phase BUILD' },
    completed:      { en: 'Live',        fr: 'En production' },
    failed:         { en: 'Failed',      fr: 'Échoué' },
  };
  const e = map[status?.toLowerCase()];
  return e ? t(e.en, e.fr) : status;
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { t, lang } = useLang();

  const [project, setProject] = useState<Project | null>(null);
  const [sdsVersions, setSdsVersions] = useState<SDSVersion[]>([]);
  const [crs, setCrs] = useState<RawCR[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [latestExecutionId, setLatestExecutionId] = useState<number | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('overview');

  const [chatInput, setChatInput] = useState('');
  const [chatPosting, setChatPosting] = useState(false);
  const [showCRModal, setShowCRModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [approvingSDS, setApprovingSDS] = useState(false);
  const [startingBuild, setStartingBuild] = useState(false);
  const [snapshotting, setSnapshotting] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [proj, sds, crsResp, chatResp] = await Promise.all([
          api.get(`/api/projects/${projectId}`),
          api.get(`/api/projects/${projectId}/sds-versions`).catch(() => ({ versions: [] })),
          api.get(`/api/projects/${projectId}/change-requests`).catch(() => ({ change_requests: [] })),
          api.get(`/api/projects/${projectId}/chat/history`).catch(() => ({ messages: [] })),
        ]);
        if (cancelled) return;
        setProject(proj);
        setSdsVersions(sds?.versions ?? sds ?? []);
        setCrs(crsResp?.change_requests ?? crsResp ?? []);
        setChatMessages(chatResp?.messages ?? chatResp ?? []);
        // try to find latest execution id (used for SDS HTML preview)
        try {
          const exec = await api.get(`/api/pm-orchestrator/projects/${projectId}/executions`).catch(() => null);
          const list = exec?.executions ?? exec ?? [];
          if (Array.isArray(list) && list.length > 0) {
            setLatestExecutionId(list[0]?.id ?? null);
          }
        } catch {/* ignore */}
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? 'Failed to load project');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    if (tab === 'chat') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, tab]);

  const sendChat = async () => {
    if (!chatInput.trim() || !projectId) return;
    const message = chatInput.trim();
    setChatInput('');
    const optimistic: ChatMessage = {
      id: Date.now(),
      role: 'user',
      message,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, optimistic]);
    setChatPosting(true);
    try {
      const resp = await api.post(`/api/projects/${projectId}/chat`, { message });
      if (resp?.assistant_message) {
        setChatMessages((prev) => [...prev, resp.assistant_message]);
      }
    } catch (err: any) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          message: t('Sorry — I could not respond.', 'Désolée — je n’ai pas pu répondre.'),
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatPosting(false);
    }
  };

  const submitCR = async (crId: number) => {
    if (!projectId) return;
    try {
      await api.post(`/api/projects/${projectId}/change-requests/${crId}/submit`);
      setCrs((prev) => prev.map((c) => (c.id === crId ? { ...c, status: 'submitted' } : c)));
    } catch {
      window.alert(t('Could not submit.', 'Soumission impossible.'));
    }
  };

  const approveCR = async (crId: number) => {
    if (!projectId) return;
    try {
      await api.post(`/api/projects/${projectId}/change-requests/${crId}/approve`, {});
      setCrs((prev) => prev.map((c) => (c.id === crId ? { ...c, status: 'approved' } : c)));
    } catch {
      window.alert(t('Could not approve.', 'Approbation impossible.'));
    }
  };

  const createCR = async (data: { title: string; description: string; category: string; priority: 'low' | 'medium' | 'high' }) => {
    if (!projectId) return;
    try {
      const resp = await api.post(`/api/projects/${projectId}/change-requests`, data);
      const created = resp?.change_request ?? resp;
      if (created) setCrs((prev) => [created, ...prev]);
    } catch {
      window.alert(t('Could not create change request.', 'Création impossible.'));
    }
  };

  const approveSDS = async () => {
    if (!projectId) return;
    setApprovingSDS(true);
    try {
      await api.post(`/api/projects/${projectId}/approve-sds`);
      setProject((prev) => (prev ? { ...prev, status: 'sds_approved' } : prev));
    } catch {
      window.alert(t('Could not approve SDS.', 'Approbation SDS impossible.'));
    } finally {
      setApprovingSDS(false);
    }
  };

  const startBuild = async () => {
    if (!projectId) return;
    setStartingBuild(true);
    try {
      const resp = await api.post(`/api/pm-orchestrator/projects/${projectId}/start-build`);
      if (resp?.execution_id) {
        navigate(`/execution/${resp.execution_id}/build`);
      }
    } catch {
      window.alert(t('Could not start BUILD.', 'Démarrage BUILD impossible.'));
    } finally {
      setStartingBuild(false);
    }
  };

  const snapshotSDS = async () => {
    if (!projectId) return;
    setSnapshotting(true);
    try {
      await api.post(`/api/projects/${projectId}/sds-versions`, {});
      const sds = await api.get(`/api/projects/${projectId}/sds-versions`).catch(() => ({ versions: [] }));
      setSdsVersions(sds?.versions ?? sds ?? []);
    } catch {
      window.alert(t('Could not snapshot SDS.', 'Snapshot impossible.'));
    } finally {
      setSnapshotting(false);
    }
  };

  const downloadSDS = (versionNumber: number) => {
    const token = localStorage.getItem('token');
    window.open(
      `/api/projects/${projectId}/sds-versions/${versionNumber}/download?token=${token}`,
      '_blank',
    );
  };

  const previewSDSHtml = () => {
    if (!latestExecutionId) return;
    const token = localStorage.getItem('token');
    window.open(
      `/api/pm-orchestrator/execute/${latestExecutionId}/sds-html?token=${token}`,
      '_blank',
    );
  };

  // ─── Derived data ──────────────────────────────────────────────────────────
  const formattedCRs: ChangeRequestItem[] = useMemo(
    () =>
      crs.map((c) => ({
        id: c.id,
        title: c.title,
        description: c.description ?? '',
        category: c.category,
        status: normalizeStatus(c.status),
        priority: normalizePriority(c.priority),
        created_at: c.created_at,
      })),
    [crs],
  );

  const deliverables: DeliverableItem[] = useMemo(() => {
    const items: DeliverableItem[] = sdsVersions.map((v) => ({
      id: `sds-${v.id}`,
      kind: 'doc' as const,
      title: v.file_name || `SDS v${v.version_number}`,
      version: `v${v.version_number}`,
      date: v.generated_at ? new Date(v.generated_at).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB') : undefined,
      meta: v.notes,
    }));
    if (latestExecutionId) {
      items.unshift({
        id: 'sds-html-preview',
        kind: 'preview',
        title: t('SDS · live preview', 'SDS · prévisualisation'),
        meta: t('HTML rendering of the latest SDS', 'Rendu HTML du dernier SDS'),
      });
    }
    return items;
  }, [sdsVersions, latestExecutionId, lang, t]);

  const recentActivity: ActivityItem[] = useMemo(() => {
    const items: ActivityItem[] = [];
    sdsVersions.slice(0, 3).forEach((v) => {
      items.push({
        id: `sds-${v.id}`,
        who: 'Sophie',
        what: t(
          `Saved SDS v${v.version_number}.`,
          `Snapshot SDS v${v.version_number}.`,
        ),
        when: v.generated_at
          ? new Date(v.generated_at).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB')
          : '',
        accent: 'indigo',
      });
    });
    crs.slice(0, 3).forEach((c) => {
      items.push({
        id: `cr-${c.id}`,
        who: 'CR',
        what: c.title,
        when: c.created_at ? new Date(c.created_at).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB') : '',
        accent: 'plum',
      });
    });
    return items.slice(0, 6);
  }, [sdsVersions, crs, lang, t]);

  // ─── Render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-ink-2 border border-bone/10 h-32 animate-pulse mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-ink-2 border border-bone/10 h-60 animate-pulse" />
          <div className="bg-ink-2 border border-bone/10 h-60 animate-pulse" />
        </div>
      </section>
    );
  }

  if (error || !project) {
    return (
      <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="bg-ink-2 border border-error/30 p-6">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-error mb-2">
            {t('Error', 'Erreur')}
          </p>
          <p className="font-mono text-[12px] text-bone-2">{error ?? t('Project not found', 'Projet introuvable')}</p>
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="mt-6 inline-flex items-center gap-2 px-4 py-2 font-mono text-[10px] tracking-cta uppercase text-bone-3 hover:text-bone transition-colors"
          >
            ← {t('Back to projects', 'Retour aux projets')}
          </button>
        </div>
      </section>
    );
  }

  const showApproveSDS = ['sds_generated', 'sds_in_review'].includes(project.status);
  const showStartBuild = project.status === 'sds_approved';

  const tabsList = [
    { id: 'overview' as TabId,     label: t('Overview',     'Vue') },
    { id: 'deliverables' as TabId, label: t('Deliverables', 'Livrables'), count: deliverables.length },
    { id: 'changes' as TabId,      label: t('Changes',      'Demandes'),  count: crs.length },
    { id: 'chat' as TabId,         label: t('Chat',         'Chat') },
  ];

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
        <div className="min-w-0">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
            № 03 · {project.organization_type?.toUpperCase() || 'PROJECT'} · {phaseLabel(project.status, t).toUpperCase()}
          </p>
          <h1 className="font-serif italic text-4xl md:text-5xl text-bone leading-[1.05] truncate">
            {project.name}
          </h1>
          {project.description && (
            <p className="font-mono text-[12px] text-bone-3 mt-3 max-w-3xl line-clamp-2">
              {project.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            type="button"
            onClick={() => setShowSettings(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 border border-bone/10 hover:border-brass/40 text-bone-3 hover:text-bone font-mono text-[10px] tracking-cta uppercase transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            {t('Settings', 'Réglages')}
          </button>
        </div>
      </div>

      {/* Contextual primary CTA */}
      {(showApproveSDS || showStartBuild) && (
        <div className="bg-ink-2 border border-brass/30 p-5 mb-8 flex items-center justify-between gap-6">
          <div className="min-w-0">
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass mb-1">
              {showApproveSDS ? t('SDS ready for review', 'SDS prête à revue') : t('SDS approved', 'SDS approuvé')}
            </p>
            <p className="font-serif italic text-xl text-bone">
              {showApproveSDS
                ? t('The casting is set. Approve to move to BUILD.', 'Le casting est posé. Approuvez pour passer au BUILD.')
                : t('Curtain up. Begin the BUILD phase.', 'Lever de rideau. Démarrez la phase BUILD.')}
            </p>
          </div>
          {showApproveSDS && (
            <button
              type="button"
              onClick={approveSDS}
              disabled={approvingSDS}
              className="inline-flex items-center gap-2 px-5 py-3 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-50 flex-shrink-0"
            >
              {approvingSDS ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : '✓'}
              {t('Approve SDS', 'Approuver SDS')}
            </button>
          )}
          {showStartBuild && (
            <button
              type="button"
              onClick={startBuild}
              disabled={startingBuild}
              className="inline-flex items-center gap-2 px-5 py-3 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-50 flex-shrink-0"
            >
              {startingBuild ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : '◗'}
              {t('Begin BUILD', 'Démarrer BUILD')} →
            </button>
          )}
        </div>
      )}

      {/* Tabs */}
      <StudioTabs
        tabs={tabsList}
        active={tab}
        onChange={(id) => setTab(id as TabId)}
        className="mb-8"
      />

      {/* Overview */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ProjectHealthCard
            phase={phaseLabel(project.status, t)}
            health="nominal"
            nextMilestone={
              showApproveSDS
                ? t('Awaiting your approval', 'En attente de votre approbation')
                : showStartBuild
                ? t('BUILD ready to start', 'BUILD prêt à démarrer')
                : null
            }
          />
          <ProjectActivityFeed items={recentActivity} />
        </div>
      )}

      {/* Deliverables */}
      {tab === 'deliverables' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between mb-2">
            <p className="font-mono text-[11px] text-bone-3">
              {deliverables.length} {t('deliverable(s)', 'livrable(s)')}
            </p>
            <button
              type="button"
              onClick={snapshotSDS}
              disabled={snapshotting}
              className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] tracking-cta uppercase text-brass hover:text-bone transition-colors disabled:opacity-50"
            >
              {snapshotting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : '◗'}
              {t('Snapshot current SDS', 'Snapshot du SDS courant')}
            </button>
          </div>

          {deliverables.length === 0 ? (
            <div className="bg-ink-2 border border-bone/10 p-12 text-center">
              <p className="font-serif italic text-xl text-bone-2">
                {t('No deliverables yet.', 'Pas encore de livrables.')}
              </p>
            </div>
          ) : (
            deliverables.map((d) => (
              <DeliverableCard
                key={d.id}
                item={d}
                onView={
                  d.id === 'sds-html-preview'
                    ? previewSDSHtml
                    : undefined
                }
                onDownload={
                  d.id === 'sds-html-preview'
                    ? undefined
                    : () => {
                        const v = sdsVersions.find((sv) => `sds-${sv.id}` === d.id);
                        if (v) downloadSDS(v.version_number);
                      }
                }
              />
            ))
          )}
        </div>
      )}

      {/* Change requests */}
      {tab === 'changes' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between mb-2">
            <p className="font-mono text-[11px] text-bone-3">
              {crs.length} {t('change request(s)', 'demande(s)')}
            </p>
            <button
              type="button"
              onClick={() => setShowCRModal(true)}
              className="inline-flex items-center gap-2 px-3 py-2 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
            >
              + {t('New change request', 'Nouvelle demande')}
            </button>
          </div>

          {formattedCRs.length === 0 ? (
            <div className="bg-ink-2 border border-bone/10 p-12 text-center">
              <p className="font-serif italic text-xl text-bone-2 mb-2">
                {t('No change requests yet.', 'Pas encore de demandes.')}
              </p>
              <p className="font-mono text-[11px] text-bone-3">
                {t(
                  'Spotted something to refine? Open a request — Sophie will pick it up.',
                  'Vous voulez affiner quelque chose ? Ouvrez une demande — Sophie la récupèrera.',
                )}
              </p>
            </div>
          ) : (
            formattedCRs.map((c) => (
              <ChangeRequestCard
                key={c.id}
                item={c}
                onSubmit={() => submitCR(c.id)}
                onApprove={() => approveCR(c.id)}
              />
            ))
          )}
        </div>
      )}

      {/* Chat */}
      {tab === 'chat' && (
        <div className="bg-ink-2 border border-bone/10">
          <div className="p-5 border-b border-bone/10">
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass mb-1">
              Sophie
            </p>
            <p className="font-serif italic text-lg text-bone">
              {t('What would you like to discuss?', 'De quoi voulez-vous parler ?')}
            </p>
          </div>

          <div className="max-h-[480px] overflow-y-auto p-5 space-y-4">
            {chatMessages.length === 0 ? (
              <p className="font-mono text-[12px] text-bone-3 italic text-center py-8">
                {t('No messages yet — open the conversation.', 'Pas de messages — ouvrez la conversation.')}
              </p>
            ) : (
              chatMessages.map((m) => (
                <div
                  key={m.id}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 ${
                      m.role === 'user'
                        ? 'bg-brass/15 border border-brass/30 text-bone'
                        : 'bg-ink-3 border border-bone/10 text-bone-2'
                    }`}
                  >
                    <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-1.5">
                      {m.role === 'user' ? t('You', 'Vous') : 'Sophie'}
                    </p>
                    <p className="font-mono text-[12px] leading-relaxed whitespace-pre-wrap">
                      {m.message}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="p-5 border-t border-bone/10 flex items-end gap-3">
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendChat();
                }
              }}
              placeholder={t('Speak to Sophie…', 'Parlez à Sophie…')}
              rows={2}
              className="flex-1 bg-ink-3 border border-bone/10 px-4 py-3 font-sans text-[14px] text-bone placeholder:text-bone-4 focus:border-brass focus:outline-none resize-none"
            />
            <button
              type="button"
              onClick={sendChat}
              disabled={!chatInput.trim() || chatPosting}
              className="inline-flex items-center gap-2 px-4 py-3 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-50"
            >
              {chatPosting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {t('Send', 'Envoyer')}
            </button>
          </div>
        </div>
      )}

      {/* Modals */}
      <ChangeRequestModal
        isOpen={showCRModal}
        onClose={() => setShowCRModal(false)}
        onSubmit={createCR}
      />
      {showSettings && project && (
        <ProjectSettingsModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          projectId={project.id}
          onSaved={() => {
            // Refetch project data after save
            api.get(`/api/projects/${project.id}`)
              .then((p) => setProject(p))
              .catch(() => { /* keep current */ });
          }}
        />
      )}

      {/* Bottom unobtrusive return link */}
      <div className="mt-12 pt-6 border-t border-bone/10">
        <button
          type="button"
          onClick={() => navigate('/projects')}
          className="inline-flex items-center gap-2 font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 hover:text-brass transition-colors"
        >
          <ExternalLink className="w-3 h-3" />
          {t('Back to all productions', 'Retour à toutes les productions')}
        </button>
      </div>
    </section>
  );
}
