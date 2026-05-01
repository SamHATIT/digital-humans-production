/**
 * AgentTesterPage — A5.4
 * № 09 · AGENT TESTER — test an ensemble member in isolation.
 * Outil dev/admin Studio.
 */
import { useEffect, useRef, useState } from 'react';
import { Loader2, Cloud, FolderOpen } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import {
  STUDIO_ENSEMBLE,
  getAgentAccent,
  ACCENT_TEXT,
  ACCENT_BORDER,
  ACT_LABELS,
  groupByAct,
} from '../lib/agents';
import type { StudioAgent } from '../lib/agents';

interface AgentBackend {
  name?: string;
  role?: string;
  description?: string;
  capabilities?: string[];
}

interface SalesforceOrg {
  alias?: string;
  username?: string;
  instance_url?: string;
  connected?: boolean;
}

interface LogEntry {
  type: string;
  level?: string;
  message?: string;
  agent?: string;
  task?: string;
  timestamp?: string;
}

type LogLevel = 'success' | 'error' | 'llm' | 'sfdx' | 'info';

function classifyLevel(level?: string): LogLevel {
  const v = level?.toUpperCase();
  if (v === 'SUCCESS') return 'success';
  if (v === 'ERROR' || v === 'FAIL') return 'error';
  if (v === 'LLM') return 'llm';
  if (v === 'SFDX') return 'sfdx';
  return 'info';
}

const LEVEL_TEXT: Record<LogLevel, string> = {
  success: 'text-success',
  error:   'text-error',
  llm:     'text-ochre',
  sfdx:    'text-indigo',
  info:    'text-bone-3',
};

const LEVEL_GLYPH: Record<LogLevel, string> = {
  success: '✓',
  error:   '✗',
  llm:     '◎',
  sfdx:    '☁',
  info:    '·',
};

export default function AgentTesterPage() {
  const { t, lang } = useLang();
  const [backendAgents, setBackendAgents] = useState<Record<string, AgentBackend>>({});
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [taskDescription, setTaskDescription] = useState<string>('');
  const [salesforceOrg, setSalesforceOrg] = useState<SalesforceOrg | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [workspaceFiles, setWorkspaceFiles] = useState<Record<string, string[]>>({});
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void fetchAgents();
    void fetchWorkspaceFiles();
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/agent-tester/agents');
      const data = await response.json();
      setBackendAgents(data.agents ?? {});
      setSalesforceOrg(data.salesforce_org ?? null);
      if (!selectedAgentId && data.agents) {
        const first = Object.keys(data.agents)[0];
        if (first) setSelectedAgentId(first);
      }
    } catch (err) {
      console.error('Error fetching agents:', err);
    }
  };

  const fetchWorkspaceFiles = async () => {
    try {
      const response = await fetch('/api/agent-tester/workspace/files');
      const data = await response.json();
      setWorkspaceFiles(data.files ?? {});
    } catch (err) {
      console.error('Error fetching workspace files:', err);
    }
  };

  const runAgentTest = async () => {
    if (!selectedAgentId || !taskDescription.trim()) return;
    setIsRunning(true);
    setLogs([]);
    try {
      const response = await fetch(`/api/agent-tester/test/${selectedAgentId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgentId,
          task_description: taskDescription,
          deploy_to_org: true,
        }),
      });
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              setLogs((prev) => [...prev, data]);
            } catch { /* ignore */ }
          }
        }
      }
    } catch (err: any) {
      setLogs((prev) => [...prev, { type: 'error', level: 'ERROR', message: `${err}` }]);
    } finally {
      setIsRunning(false);
      void fetchWorkspaceFiles();
    }
  };

  // We map backend agent ids onto the Studio ensemble for accents/avatars.
  // Fallback if backend returns extra/unknown ids.
  const studioAgent = (id: string): StudioAgent | null => {
    return STUDIO_ENSEMBLE.find((a) => a.id === id) ?? null;
  };

  const grouped = groupByAct();
  const visibleGroups = grouped
    .map((g) => ({
      ...g,
      agents: g.agents.filter((a) => Object.prototype.hasOwnProperty.call(backendAgents, a.id)),
    }))
    .filter((g) => g.agents.length > 0);

  const selected = studioAgent(selectedAgentId);
  const selectedBackend = backendAgents[selectedAgentId];
  const accent = selected ? getAgentAccent(selectedAgentId) : 'brass';

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="mb-12">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
          № 09 · {t('Agent tester', 'Test des agents')}
        </p>
        <h1 className="font-serif italic text-4xl md:text-5xl text-bone leading-[1.05] mb-4">
          {t('Test an ensemble member in isolation.', 'Tester un membre de l’ensemble isolément.')}
        </h1>
        <p className="font-mono text-[12px] text-bone-3 max-w-3xl">
          {t(
            'Pick an agent, describe a task, run it. The live log streams from the backend.',
            'Choisissez un agent, décrivez une tâche, lancez-la. Le log live arrive du backend.',
          )}
        </p>
      </div>

      {/* Salesforce org indicator */}
      {salesforceOrg && (
        <div className="mb-8 inline-flex items-center gap-2 px-3 py-2 bg-ink-2 border border-bone/10 font-mono text-[11px] text-bone-3">
          <Cloud className="w-3.5 h-3.5 text-indigo" />
          <span>
            {t('Connected org', 'Org connectée')} :{' '}
            <span className="text-bone">{salesforceOrg.alias ?? salesforceOrg.username ?? '—'}</span>
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* LEFT — Agent picker */}
        <aside className="bg-ink-2 border border-bone/10 p-5 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
          <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-4">
            {t('Ensemble', 'Ensemble')}
          </p>
          {visibleGroups.length === 0 ? (
            <p className="font-mono text-[11px] text-bone-3 italic">
              {t('No agents available.', 'Aucun agent disponible.')}
            </p>
          ) : (
            <div className="space-y-5">
              {visibleGroups.map((g) => (
                <div key={g.act}>
                  <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-2">
                    {t(ACT_LABELS[g.act].en, ACT_LABELS[g.act].fr)}
                  </p>
                  <ul className="space-y-1">
                    {g.agents.map((a) => {
                      const isActive = selectedAgentId === a.id;
                      const acc = getAgentAccent(a.id);
                      return (
                        <li key={a.id}>
                          <button
                            type="button"
                            onClick={() => setSelectedAgentId(a.id)}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                              isActive
                                ? `bg-ink-3 border-l-2 ${ACCENT_BORDER[acc]}`
                                : 'border-l-2 border-transparent hover:bg-ink-3/50'
                            }`}
                          >
                            <span
                              className={`font-mono text-[10px] tracking-eyebrow uppercase flex-shrink-0 w-5 ${
                                isActive ? ACCENT_TEXT[acc] : 'text-bone-4'
                              }`}
                            >
                              {isActive ? '◗' : '·'}
                            </span>
                            <span
                              className={`font-serif italic ${
                                isActive ? 'text-bone' : 'text-bone-2'
                              }`}
                            >
                              {t(a.name.en, a.name.fr)}
                            </span>
                            <span className="ml-auto font-mono text-[10px] text-bone-4 truncate max-w-[60px]">
                              {t(a.role.en, a.role.fr).split(' ')[0]}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* RIGHT — Agent detail + run + log */}
        <div className="space-y-6 min-w-0">
          {/* Selected agent card */}
          <div className={`bg-ink-2 border ${ACCENT_BORDER[accent]} p-6`}>
            {selected ? (
              <div className="flex items-start gap-5">
                <div
                  className={`w-16 h-16 bg-ink-3 border-2 ${ACCENT_BORDER[accent]} flex items-center justify-center flex-shrink-0`}
                >
                  <span className={`font-serif italic text-2xl ${ACCENT_TEXT[accent]}`}>
                    {t(selected.name.en, selected.name.fr)[0]}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className={`font-mono text-[10px] tracking-eyebrow uppercase mb-1 ${ACCENT_TEXT[accent]}`}>
                    {t(ACT_LABELS[selected.act].en, ACT_LABELS[selected.act].fr)}
                  </p>
                  <h2 className="font-serif italic text-3xl text-bone mb-1">{t(selected.name.en, selected.name.fr)}</h2>
                  <p className="font-mono text-[12px] text-bone-3 mb-3">
                    {t(selected.role.en, selected.role.fr)}
                  </p>
                  {(selectedBackend?.description || selected.tagline) && (
                    <p className="font-mono text-[12px] text-bone-2 leading-relaxed">
                      {selectedBackend?.description ?? t(selected.tagline?.en ?? '', selected.tagline?.fr ?? '')}
                    </p>
                  )}
                  {selectedBackend?.capabilities && selectedBackend.capabilities.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-bone/10">
                      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-2">
                        {t('Capabilities', 'Compétences')}
                      </p>
                      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                        {selectedBackend.capabilities.map((cap, i) => (
                          <li key={i} className="font-mono text-[11px] text-bone-3 flex items-baseline gap-2">
                            <span className={ACCENT_TEXT[accent]}>·</span>
                            <span>{cap}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="font-mono text-[11px] text-bone-3 italic">
                {t('Select an agent to begin.', 'Choisissez un agent pour commencer.')}
              </p>
            )}
          </div>

          {/* Task input + run */}
          <div className="bg-ink-2 border border-bone/10 p-6">
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-3">
              {t('Task input', 'Description de la tâche')}
            </p>
            <textarea
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              placeholder={t(
                'Describe what the agent should attempt...',
                "Décrivez ce que l'agent doit tenter…",
              )}
              rows={4}
              className="w-full bg-ink-3 border border-bone/10 px-4 py-3 font-sans text-[14px] text-bone placeholder:text-bone-4 focus:border-brass focus:outline-none resize-y"
            />
            <div className="mt-4 flex items-center justify-end">
              <button
                type="button"
                onClick={runAgentTest}
                disabled={!selectedAgentId || !taskDescription.trim() || isRunning}
                className="inline-flex items-center gap-2 px-5 py-3 bg-brass text-ink font-mono text-[10px] tracking-cta uppercase hover:bg-brass-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {t('Running…', 'Exécution…')}
                  </>
                ) : (
                  <>
                    ◗ {t('Run task', 'Lancer la tâche')} →
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Live log */}
          <div className="bg-ink-2 border border-bone/10">
            <div className="px-5 py-3 border-b border-bone/10 flex items-center justify-between">
              <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                {t('Live log', 'Log en direct')}
              </p>
              <p className="font-mono text-[10px] text-bone-4 tabular-nums">
                {logs.length} {t('lines', 'lignes')}
              </p>
            </div>
            <div className="max-h-[400px] overflow-y-auto p-5">
              {logs.length === 0 ? (
                <p className="font-mono text-[11px] text-bone-3 italic">
                  {t('No log yet.', 'Pas de log pour le moment.')}
                </p>
              ) : (
                <pre className="font-mono text-[11px] leading-[1.6] whitespace-pre-wrap">
                  {logs.map((log, i) => {
                    const lvl = classifyLevel(log.level);
                    const time = log.timestamp
                      ? new Date(log.timestamp).toLocaleTimeString(lang === 'fr' ? 'fr-FR' : 'en-GB', { hour12: false })
                      : '';
                    return (
                      <div key={i} className={LEVEL_TEXT[lvl]}>
                        <span className="text-bone-4">[{time || '--:--:--'}]</span>{' '}
                        <span>{LEVEL_GLYPH[lvl]}</span>{' '}
                        {log.agent && <span className="text-brass">{log.agent}</span>}{' '}
                        <span>{log.message ?? log.task ?? ''}</span>
                      </div>
                    );
                  })}
                </pre>
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* Workspace files */}
          {Object.keys(workspaceFiles).length > 0 && (
            <div className="bg-ink-2 border border-bone/10 p-6">
              <div className="flex items-center gap-2 mb-4">
                <FolderOpen className="w-3.5 h-3.5 text-brass" />
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                  {t('Workspace files', 'Fichiers du workspace')}
                </p>
              </div>
              <div className="space-y-4">
                {Object.entries(workspaceFiles).map(([dir, files]) => (
                  <div key={dir}>
                    <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-1">
                      {dir}
                    </p>
                    <ul className="space-y-0.5">
                      {files.slice(0, 12).map((f, i) => (
                        <li key={i} className="font-mono text-[11px] text-bone-2 truncate">
                          · {f}
                        </li>
                      ))}
                      {files.length > 12 && (
                        <li className="font-mono text-[10px] text-bone-4 italic">
                          + {files.length - 12} {t('more', 'autres')}
                        </li>
                      )}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
