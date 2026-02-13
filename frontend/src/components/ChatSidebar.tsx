import { useState, useRef, useEffect } from 'react';
import { X, Send, Loader2, MessageCircle, User, Bot, ChevronDown } from 'lucide-react';
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
  purple: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30', avatar: 'bg-purple-500/20' },
  blue:   { bg: 'bg-blue-500/10',   text: 'text-blue-400',   border: 'border-blue-500/30',   avatar: 'bg-blue-500/20' },
  green:  { bg: 'bg-green-500/10',  text: 'text-green-400',  border: 'border-green-500/30',  avatar: 'bg-green-500/20' },
  cyan:   { bg: 'bg-cyan-500/10',   text: 'text-cyan-400',   border: 'border-cyan-500/30',   avatar: 'bg-cyan-500/20' },
  pink:   { bg: 'bg-pink-500/10',   text: 'text-pink-400',   border: 'border-pink-500/30',   avatar: 'bg-pink-500/20' },
  yellow: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30', avatar: 'bg-yellow-500/20' },
  orange: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30', avatar: 'bg-orange-500/20' },
  teal:   { bg: 'bg-teal-500/10',   text: 'text-teal-400',   border: 'border-teal-500/30',   avatar: 'bg-teal-500/20' },
  indigo: { bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/30', avatar: 'bg-indigo-500/20' },
  slate:  { bg: 'bg-slate-500/10',  text: 'text-slate-400',  border: 'border-slate-500/30',  avatar: 'bg-slate-500/20' },
};

function formatMarkdownInline(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-slate-700 text-cyan-300 rounded text-xs font-mono">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="text-slate-200">$1</em>');
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
    <div className="fixed top-0 right-0 h-full w-[420px] bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col animate-[slideIn_0.2s_ease-out]">
      {/* Header with agent selector */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-800/50">
        <div className="relative">
          <button
            onClick={() => setShowAgentPicker(!showAgentPicker)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${colors.border} ${colors.bg} transition-colors hover:opacity-80`}
          >
            <Bot className={`w-4 h-4 ${colors.text}`} />
            <span className={`font-medium text-sm ${colors.text}`}>
              {currentAgent?.name || 'Sophie'}
            </span>
            <span className="text-xs text-slate-500">{currentAgent?.role || 'PM'}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {showAgentPicker && (
            <div className="absolute top-full left-0 mt-1 w-64 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-10 py-1 max-h-72 overflow-y-auto">
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
                    className={`w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-slate-700/50 transition-colors ${isSelected ? 'bg-slate-700/30' : ''}`}
                  >
                    <div className={`w-7 h-7 rounded-full ${ac.avatar} flex items-center justify-center`}>
                      <Bot className={`w-3.5 h-3.5 ${ac.text}`} />
                    </div>
                    <div>
                      <span className={`text-sm font-medium ${ac.text}`}>{agent.name}</span>
                      <span className="text-xs text-slate-500 ml-1.5">{agent.role}</span>
                    </div>
                    {isSelected && <span className="ml-auto text-xs text-green-400">●</span>}
                  </button>
                );
              })}
              {agents.filter(a => !a.available).length > 0 && (
                <div className="border-t border-slate-700 mt-1 pt-1 px-3 py-1.5 text-xs text-slate-600">
                  Unavailable (no deliverables yet)
                </div>
              )}
              {agents.filter(a => !a.available).map(agent => (
                <div key={agent.agent_id} className="flex items-center gap-3 px-3 py-2 opacity-40">
                  <Bot className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-xs text-slate-500">{agent.name} — {agent.role}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Bot className={`w-10 h-10 ${colors.text} mx-auto mb-3 opacity-40`} />
            <p className="text-slate-500 text-sm">
              Start a conversation with {currentAgent?.name || 'Sophie'} ({currentAgent?.role || 'PM'}).
            </p>
            <p className="text-slate-600 text-xs mt-1">
              Ask questions about deliverables or request changes.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              msg.role === 'user' ? 'bg-cyan-500/20' : colors.avatar
            }`}>
              {msg.role === 'user' ? (
                <User className="w-4 h-4 text-cyan-400" />
              ) : (
                <Bot className={`w-4 h-4 ${colors.text}`} />
              )}
            </div>

            <div className={`max-w-[80%] ${
              msg.role === 'user'
                ? 'bg-cyan-500/10 border-cyan-500/30'
                : `${colors.bg} ${colors.border}`
            } border rounded-xl px-3 py-2`}>
              <p
                className="text-sm text-slate-200 whitespace-pre-wrap break-words"
                dangerouslySetInnerHTML={{ __html: formatMarkdownInline(msg.content) }}
              />
              {msg.diff && (
                <div className="mt-2">
                  <DiffViewer oldText={msg.diff.old} newText={msg.diff.new} oldLabel="Before" newLabel="After" />
                </div>
              )}
              <p className="text-[10px] text-slate-600 mt-1">
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
                <span className="text-xs text-slate-400">{currentAgent?.name || 'Agent'} is thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-slate-700 p-3 bg-slate-800/30">
        {deliverableContext && (
          <p className="text-[10px] text-slate-600 mb-1.5 truncate">Context: {deliverableContext}</p>
        )}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${currentAgent?.name || 'Sophie'}...`}
            rows={2}
            className={`flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:${colors.border} focus:ring-1 outline-none resize-none`}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            className={`self-end px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
