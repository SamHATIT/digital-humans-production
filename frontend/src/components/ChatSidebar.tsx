import { useState, useRef, useEffect } from 'react';
import { X, Send, Loader2, User, Bot, ChevronDown } from 'lucide-react';
import { api } from '../services/api';
import DiffViewer from './DiffViewer';

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

interface ChatSidebarProps {
  executionId: number;
  isOpen: boolean;
  onClose: () => void;
  deliverableContext?: string;
  initialAgent?: string;
}

const AGENT_COLORS: Record<string, { bg: string; text: string; border: string; avatar: string }> = {
  purple: { bg: 'bg-plum/10', text: 'text-plum', border: 'border-plum/30', avatar: 'bg-plum/20' },
  blue:   { bg: 'bg-indigo/10',   text: 'text-indigo',   border: 'border-indigo/30',   avatar: 'bg-indigo/20' },
  green:  { bg: 'bg-sage/10',  text: 'text-sage',  border: 'border-sage/30',  avatar: 'bg-sage/20' },
  cyan:   { bg: 'bg-brass/10',   text: 'text-brass',   border: 'border-brass/30',   avatar: 'bg-brass/20' },
  pink:   { bg: 'bg-plum/10',   text: 'text-plum',   border: 'border-plum/30',   avatar: 'bg-plum/20' },
  yellow: { bg: 'bg-warning/10', text: 'text-ochre', border: 'border-warning/30', avatar: 'bg-warning/20' },
  orange: { bg: 'bg-ochre/10', text: 'text-ochre', border: 'border-ochre/30', avatar: 'bg-ochre/20' },
  teal:   { bg: 'bg-sage/10',   text: 'text-sage',   border: 'border-sage/30',   avatar: 'bg-sage/20' },
  indigo: { bg: 'bg-indigo/10', text: 'text-indigo', border: 'border-indigo/30', avatar: 'bg-indigo/20' },
  slate:  { bg: 'bg-bone/5',  text: 'text-bone-4',  border: 'border-bone/20',  avatar: 'bg-bone/10' },
};

function formatMarkdownInline(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-ink-3 text-brass-2 rounded text-xs font-mono">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-bone font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="text-bone-2">$1</em>');
}

export default function ChatSidebar({
  executionId,
  isOpen,
  onClose,
  deliverableContext,
  initialAgent = 'sophie',
}: ChatSidebarProps) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>(initialAgent);
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const currentAgent = agents.find(a => a.agent_id === selectedAgent);
  const colors = AGENT_COLORS[currentAgent?.color || 'purple'] || AGENT_COLORS.purple;

  // Load available agents
  useEffect(() => {
    if (!isOpen) return;
    api.get(`/api/pm-orchestrator/executions/${executionId}/agents`)
      .then((data: any) => setAgents(data.agents || []))
      .catch(() => {});
  }, [executionId, isOpen]);

  // Load chat history when agent changes
  useEffect(() => {
    if (!isOpen) return;
    api.get(`/api/pm-orchestrator/executions/${executionId}/chat/history?agent_id=${selectedAgent}`)
      .then((data: any) => {
        const msgs = (data.messages || []).map((m: any) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: m.timestamp || new Date().toISOString(),
        }));
        setMessages(msgs);
      })
      .catch(() => setMessages([]));
  }, [executionId, selectedAgent, isOpen]);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen, selectedAgent]);

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

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsSending(true);
    setError('');

    try {
      const response = await api.post(`/api/pm-orchestrator/executions/${executionId}/chat`, {
        message: trimmed,
        agent_id: selectedAgent,
      });

      const agentMessage: ChatMessage = {
        role: 'assistant',
        content: response.response || response.content || JSON.stringify(response),
        timestamp: new Date().toISOString(),
        diff: response.diff || null,
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (err: any) {
      setError(err.message || 'Failed to send message');
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

  return (
    <div className="fixed top-0 right-0 h-full w-[420px] bg-ink border-l border-bone/10 shadow-2xl z-50 flex flex-col animate-[slideIn_0.2s_ease-out]">
      {/* Header with agent selector */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-bone/10 bg-ink-2">
        <div className="relative">
          <button
            onClick={() => setShowAgentPicker(!showAgentPicker)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${colors.border} ${colors.bg} transition-colors hover:opacity-80`}
          >
            <Bot className={`w-4 h-4 ${colors.text}`} />
            <span className={`font-medium text-sm ${colors.text}`}>
              {currentAgent?.name || 'Sophie'}
            </span>
            <span className="text-xs text-bone-4">{currentAgent?.role || 'PM'}</span>
            <ChevronDown className="w-3.5 h-3.5 text-bone-4" />
          </button>

          {showAgentPicker && (
            <div className="absolute top-full left-0 mt-1 w-64 bg-ink-2 border border-bone/10 rounded-xl shadow-2xl z-10 py-1 max-h-72 overflow-y-auto">
              {agents.filter(a => a.available).map(agent => {
                const ac = AGENT_COLORS[agent.color] || AGENT_COLORS.slate;
                const isSelected = agent.agent_id === selectedAgent;
                return (
                  <button
                    key={agent.agent_id}
                    onClick={() => {
                      setSelectedAgent(agent.agent_id);
                      setShowAgentPicker(false);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-ink-3/60 transition-colors ${isSelected ? 'bg-ink-3/30' : ''}`}
                  >
                    <div className={`w-7 h-7 rounded-full ${ac.avatar} flex items-center justify-center`}>
                      <Bot className={`w-3.5 h-3.5 ${ac.text}`} />
                    </div>
                    <div>
                      <span className={`text-sm font-medium ${ac.text}`}>{agent.name}</span>
                      <span className="text-xs text-bone-4 ml-1.5">{agent.role}</span>
                    </div>
                    {isSelected && <span className="ml-auto text-xs text-sage">●</span>}
                  </button>
                );
              })}
              {agents.filter(a => !a.available).length > 0 && (
                <div className="border-t border-bone/10 mt-1 pt-1 px-3 py-1.5 text-xs text-bone-4">
                  Unavailable (no deliverables yet)
                </div>
              )}
              {agents.filter(a => !a.available).map(agent => (
                <div key={agent.agent_id} className="flex items-center gap-3 px-3 py-2 opacity-40">
                  <Bot className="w-3.5 h-3.5 text-bone-4" />
                  <span className="text-xs text-bone-4">{agent.name} — {agent.role}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-ink-3 transition-colors text-bone-4 hover:text-bone"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Bot className={`w-10 h-10 ${colors.text} mx-auto mb-3 opacity-40`} />
            <p className="text-bone-4 text-sm">
              Start a conversation with {currentAgent?.name || 'Sophie'} ({currentAgent?.role || 'PM'}).
            </p>
            <p className="text-bone-4 text-xs mt-1">
              Ask questions about deliverables or request changes.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              msg.role === 'user' ? 'bg-brass/20' : colors.avatar
            }`}>
              {msg.role === 'user' ? (
                <User className="w-4 h-4 text-brass" />
              ) : (
                <Bot className={`w-4 h-4 ${colors.text}`} />
              )}
            </div>

            <div className={`max-w-[80%] ${
              msg.role === 'user'
                ? 'bg-brass/10 border-brass/30'
                : `${colors.bg} ${colors.border}`
            } border rounded-xl px-3 py-2`}>
              <p
                className="text-sm text-bone-2 whitespace-pre-wrap break-words"
                dangerouslySetInnerHTML={{ __html: formatMarkdownInline(msg.content) }}
              />
              {msg.diff && (
                <div className="mt-2">
                  <DiffViewer oldText={msg.diff.old} newText={msg.diff.new} oldLabel="Before" newLabel="After" />
                </div>
              )}
              <p className="text-[10px] text-bone-4 mt-1">
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}

        {isSending && (
          <div className="flex gap-3">
            <div className={`w-8 h-8 rounded-full ${colors.avatar} flex items-center justify-center flex-shrink-0`}>
              <Bot className={`w-4 h-4 ${colors.text}`} />
            </div>
            <div className={`${colors.bg} border ${colors.border} rounded-xl px-3 py-2`}>
              <div className="flex items-center gap-2">
                <Loader2 className={`w-3.5 h-3.5 ${colors.text} animate-spin`} />
                <span className="text-xs text-bone-4">{currentAgent?.name || 'Agent'} is thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 bg-error/10 border-t border-error/30 text-error text-xs">
          {error}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-bone/10 p-3 bg-ink-2/60">
        {deliverableContext && (
          <p className="text-[10px] text-bone-4 mb-1.5 truncate">Context: {deliverableContext}</p>
        )}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${currentAgent?.name || 'Sophie'}...`}
            rows={2}
            className={`flex-1 bg-ink-2 border border-bone/15 rounded-lg px-3 py-2 text-sm text-bone-2 placeholder-bone-4 focus:${colors.border} focus:ring-1 outline-none resize-none`}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            className={`self-end px-3 py-2 bg-plum hover:bg-plum disabled:opacity-40 disabled:cursor-not-allowed text-bone rounded-lg transition-colors`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
