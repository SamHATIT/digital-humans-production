import { useState, useRef, useEffect } from 'react';
import { X, Send, Loader2, MessageCircle, User, Bot } from 'lucide-react';
import { executions } from '../services/api';
import DiffViewer from './DiffViewer';

interface ChatMessage {
  role: 'user' | 'sophie';
  content: string;
  timestamp: string;
  diff?: { old: string; new: string } | null;
}

interface ChatSidebarProps {
  executionId: number;
  isOpen: boolean;
  onClose: () => void;
  deliverableContext?: string;
}

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
}: ChatSidebarProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

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
      const contextPrefix = deliverableContext
        ? `[Context: reviewing "${deliverableContext}"]\n\n`
        : '';
      const response = await executions.chatWithPM(
        executionId,
        contextPrefix + trimmed
      );

      const sophieMessage: ChatMessage = {
        role: 'sophie',
        content: response.reply || response.message || response.content || JSON.stringify(response),
        timestamp: new Date().toISOString(),
        diff: response.diff || null,
      };

      setMessages((prev) => [...prev, sophieMessage]);
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
    <div className="fixed top-0 right-0 h-full w-96 bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col animate-[slideIn_0.2s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-800/50">
        <div className="flex items-center gap-2">
          <MessageCircle className="w-5 h-5 text-purple-400" />
          <span className="font-medium text-white">Chat with Sophie</span>
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
            <Bot className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">
              Start a conversation with Sophie (PM).
            </p>
            <p className="text-slate-600 text-xs mt-1">
              Ask questions about deliverables or request changes.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user'
                  ? 'bg-cyan-500/20'
                  : 'bg-purple-500/20'
              }`}
            >
              {msg.role === 'user' ? (
                <User className="w-4 h-4 text-cyan-400" />
              ) : (
                <Bot className="w-4 h-4 text-purple-400" />
              )}
            </div>

            {/* Message bubble */}
            <div
              className={`max-w-[80%] ${
                msg.role === 'user'
                  ? 'bg-cyan-500/10 border-cyan-500/30'
                  : 'bg-slate-800/80 border-slate-700'
              } border rounded-xl px-3 py-2`}
            >
              <p
                className="text-sm text-slate-200 whitespace-pre-wrap break-words"
                dangerouslySetInnerHTML={{ __html: formatMarkdownInline(msg.content) }}
              />
              {msg.diff && (
                <div className="mt-2">
                  <DiffViewer
                    oldText={msg.diff.old}
                    newText={msg.diff.new}
                    oldLabel="Before"
                    newLabel="After"
                  />
                </div>
              )}
              <p className="text-[10px] text-slate-600 mt-1">
                {new Date(msg.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>
          </div>
        ))}

        {isSending && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-purple-400" />
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2">
              <div className="flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin" />
                <span className="text-xs text-slate-400">Sophie is thinking...</span>
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
          <p className="text-[10px] text-slate-600 mb-1.5 truncate">
            Context: {deliverableContext}
          </p>
        )}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            rows={2}
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            className="self-end px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
