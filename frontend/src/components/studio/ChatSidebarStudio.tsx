import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, ChevronDown, Loader2 } from 'lucide-react';
import { api } from '../../services/api';
import { useLang } from '../../contexts/LangContext';
import {
  ACCENT_BORDER,
  ACCENT_BORDER_STRONG,
  ACCENT_TEXT,
  type AccentToken,
  findAgentByLabel,
  STUDIO_ENSEMBLE,
  type StudioAgent,
} from '../../lib/agents';
import DiffViewer from '../DiffViewer';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  diff?: { old: string; new: string } | null;
}

interface AgentInfo {
  agent_id: string;
  name: string;
  role: string;
  color: string;
  available: boolean;
}

interface ChatSidebarStudioProps {
  executionId: number;
  isOpen: boolean;
  onClose: () => void;
  /** Highlight the sidebar (HITL pulse). */
  alert?: boolean;
  /** Agent the chat opens on by default. */
  initialAgent?: string;
  deliverableContext?: string;
}

function inlineFormat(text: string): string {
  return text
    .replace(
      /`([^`]+)`/g,
      '<code class="px-1 py-0.5 bg-ink-3 text-brass-2 text-[11px] font-mono">$1</code>',
    )
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-bone font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="text-bone-2">$1</em>');
}

/**
 * Studio version of the HITL chat sidebar.
 * Re-uses the same `/api/pm-orchestrator/executions/{id}/...` endpoints
 * as the legacy ChatSidebar so the backend contract is unchanged.
 */
export default function ChatSidebarStudio({
  executionId,
  isOpen,
  onClose,
  alert = false,
  initialAgent = 'pm',
  deliverableContext,
}: ChatSidebarStudioProps) {
  const { t, lang } = useLang();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(initialAgent);
  const [showPicker, setShowPicker] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const selected: StudioAgent =
    findAgentByLabel(selectedAgentId) ??
    STUDIO_ENSEMBLE.find((a) => a.id === selectedAgentId) ??
    STUDIO_ENSEMBLE[0];
  const tone: AccentToken = selected.accent;

  useEffect(() => {
    if (!isOpen) return;
    api
      .get(`/api/pm-orchestrator/executions/${executionId}/agents`)
      .then((data: any) => setAgents(data?.agents || []))
      .catch(() => setAgents([]));
  }, [executionId, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    api
      .get(`/api/pm-orchestrator/executions/${executionId}/chat/history?agent_id=${selectedAgentId}`)
      .then((data: any) => {
        const msgs = (data?.messages || []).map((m: any) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: m.timestamp || new Date().toISOString(),
        }));
        setMessages(msgs);
      })
      .catch(() => setMessages([]));
  }, [executionId, selectedAgentId, isOpen]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen, selectedAgentId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsSending(true);
    setError('');

    try {
      const response = await api.post(
        `/api/pm-orchestrator/executions/${executionId}/chat`,
        { message: trimmed, agent_id: selectedAgentId },
      );
      const agentMessage: ChatMessage = {
        role: 'assistant',
        content: response?.response || response?.content || JSON.stringify(response),
        timestamp: new Date().toISOString(),
        diff: response?.diff || null,
      };
      setMessages((prev) => [...prev, agentMessage]);
    } catch (err: any) {
      setError(err?.message || 'Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  const availableAgents = agents.filter((a) => a.available);
  const unavailableAgents = agents.filter((a) => !a.available);

  return (
    <motion.aside
      initial={{ x: 480, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 480, opacity: 0 }}
      transition={{ duration: 0.32, ease: 'easeOut' }}
      className={[
        'fixed top-0 right-0 h-full w-[420px] bg-ink-2 border-l',
        ACCENT_BORDER[tone],
        'z-50 flex flex-col',
      ].join(' ')}
    >
      {/* HITL pulse */}
      {alert && (
        <motion.div
          aria-hidden
          className={`pointer-events-none absolute inset-0 border-2 ${ACCENT_BORDER_STRONG[tone]}`}
          animate={{ opacity: [0.25, 0.6, 0.25] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      {/* Header */}
      <header className="flex items-center justify-between border-b border-bone/10 px-4 py-3">
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowPicker(!showPicker)}
            className="flex items-center gap-2 group"
          >
            <img
              src={`/avatars/small/${selected.slug}.png`}
              alt={selected.name[lang]}
              className={`w-7 h-7 object-cover border ${ACCENT_BORDER[tone]}`}
            />
            <span className="flex flex-col text-left leading-tight">
              <span className={`font-mono text-[9px] tracking-eyebrow uppercase ${ACCENT_TEXT[tone]}`}>
                {t(selected.role.en, selected.role.fr)}
              </span>
              <span className="font-serif italic text-[16px] text-bone">
                {selected.name[lang]}
              </span>
            </span>
            <ChevronDown className="w-3 h-3 text-bone-4 group-hover:text-bone-2 ml-1" />
          </button>

          {showPicker && (
            <div className="absolute top-full left-0 mt-2 w-72 max-h-80 overflow-y-auto bg-ink border border-bone/15 z-10 shadow-xl">
              {availableAgents.length > 0 && (
                <div className="px-3 py-2 font-mono text-[9px] tracking-eyebrow uppercase text-bone-4 border-b border-bone/10">
                  {t('Available', 'Disponibles')}
                </div>
              )}
              {availableAgents.map((agent) => {
                const studioAgent = findAgentByLabel(agent.agent_id) ?? findAgentByLabel(agent.name);
                const slug = studioAgent?.slug || 'sophie-pm';
                const accent: AccentToken = studioAgent?.accent || 'brass';
                const isCurrent = agent.agent_id === selectedAgentId;
                return (
                  <button
                    key={agent.agent_id}
                    type="button"
                    onClick={() => {
                      setSelectedAgentId(agent.agent_id);
                      setShowPicker(false);
                    }}
                    className={[
                      'w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-ink-2',
                      isCurrent ? 'bg-ink-2' : '',
                    ].join(' ')}
                  >
                    <img
                      src={`/avatars/small/${slug}.png`}
                      alt={agent.name}
                      className="w-7 h-7 object-cover border border-bone/10"
                    />
                    <div className="min-w-0 flex-1">
                      <p className={`font-mono text-[9px] tracking-eyebrow uppercase ${ACCENT_TEXT[accent]}`}>
                        {agent.role}
                      </p>
                      <p className="font-serif italic text-bone text-sm">{agent.name}</p>
                    </div>
                    {isCurrent && <span className="text-brass font-mono text-[10px]">●</span>}
                  </button>
                );
              })}
              {unavailableAgents.length > 0 && (
                <div className="px-3 py-2 mt-1 font-mono text-[9px] tracking-eyebrow uppercase text-bone-4 border-y border-bone/10">
                  {t('Backstage', 'En coulisses')}
                </div>
              )}
              {unavailableAgents.map((agent) => (
                <div key={agent.agent_id} className="px-3 py-2 opacity-50">
                  <p className="font-mono text-[10px] text-bone-4">
                    {agent.name} — {agent.role}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="p-1.5 text-bone-4 hover:text-bone transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        <AnimatePresence initial={false}>
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center py-16"
            >
              <p className="font-serif italic text-bone-3 text-sm">
                {t(
                  `Speak with ${selected.name.en}.`,
                  `Adressez-vous à ${selected.name.fr}.`,
                )}
              </p>
              <p className="font-mono text-[10px] text-bone-4 mt-2">
                {t(
                  'Ask about deliverables or request a revision.',
                  'Posez vos questions ou demandez une révision.',
                )}
              </p>
            </motion.div>
          )}

          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              {msg.role === 'assistant' && (
                <img
                  src={`/avatars/small/${selected.slug}.png`}
                  alt={selected.name[lang]}
                  className={`w-7 h-7 object-cover border ${ACCENT_BORDER[tone]} shrink-0`}
                />
              )}
              {msg.role === 'user' && (
                <div className="w-7 h-7 border border-brass/40 bg-brass/5 flex items-center justify-center shrink-0">
                  <span className="font-mono text-[10px] text-brass">YOU</span>
                </div>
              )}

              <div
                className={[
                  'max-w-[78%] border px-3 py-2',
                  msg.role === 'user'
                    ? 'bg-brass/5 border-brass/30'
                    : `bg-ink border ${ACCENT_BORDER[tone]}`,
                ].join(' ')}
              >
                <p
                  className="font-serif text-bone-2 text-[14px] leading-relaxed whitespace-pre-wrap break-words"
                  dangerouslySetInnerHTML={{ __html: inlineFormat(msg.content) }}
                />
                {msg.diff && (
                  <div className="mt-2">
                    <DiffViewer
                      oldText={msg.diff.old}
                      newText={msg.diff.new}
                      oldLabel={t('Before', 'Avant')}
                      newLabel={t('After', 'Après')}
                    />
                  </div>
                )}
                <p className="mt-1 font-mono text-[9px] text-bone-4">
                  {new Date(msg.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {isSending && (
          <div className="flex gap-3 items-center">
            <img
              src={`/avatars/small/${selected.slug}.png`}
              alt={selected.name[lang]}
              className={`w-7 h-7 object-cover border ${ACCENT_BORDER[tone]} shrink-0`}
            />
            <div className={`bg-ink border ${ACCENT_BORDER[tone]} px-3 py-2 flex items-center gap-2`}>
              <Loader2 className={`w-3.5 h-3.5 ${ACCENT_TEXT[tone]} animate-spin`} />
              <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                {t(`${selected.name.en} is thinking…`, `${selected.name.fr} réfléchit…`)}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 border-t border-error/30 text-error font-mono text-[11px]">
          {error}
        </div>
      )}

      {/* Composer */}
      <footer className="border-t border-bone/10 px-4 py-3">
        {deliverableContext && (
          <p className="font-mono text-[9px] text-bone-4 mb-2 truncate">
            {t('Context', 'Contexte')}: {deliverableContext}
          </p>
        )}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t(
              `Message ${selected.name.en}…`,
              `Message à ${selected.name.fr}…`,
            )}
            rows={2}
            className="flex-1 bg-ink border border-bone/15 px-3 py-2 font-serif text-[14px] text-bone placeholder-bone-4 focus:border-brass focus:outline-none resize-none"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            aria-label={t('Send', 'Envoyer')}
            className="self-end px-3 py-2 bg-brass text-ink hover:bg-brass-2 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="mt-2 font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">
          {t('Submit feedback ↩', 'Envoyer ↩')}
        </p>
      </footer>
    </motion.aside>
  );
}
