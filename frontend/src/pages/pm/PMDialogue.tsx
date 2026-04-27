/**
 * PM Dialogue Page — Conversational interface with PM Orchestrator.
 *
 * Page legacy (non routée actuellement dans App.tsx). Sera refondue dans
 * A5.3 (Théâtre). On conserve la logique pour usage futur, en types stricts.
 */
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from '../../lib/motion';
import pmService from '../../services/pmService';

interface ChatMessage {
  role: 'pm' | 'user';
  content: string;
  timestamp: Date;
  nextQuestions?: string[];
  isError?: boolean;
}

const INITIAL_PM_MESSAGE: ChatMessage = {
  role: 'pm',
  content:
    "Hi! I'm your Product Manager. Let's transform your business need into a complete Salesforce implementation plan.\n\nTell me about your project:\n• What problem are you solving?\n• Who are the users?\n• What's your timeline?",
  timestamp: new Date(),
};

export default function PMDialogue() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_PM_MESSAGE]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [canGeneratePRD, setCanGeneratePRD] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || loading || !projectId) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await pmService.dialogue(projectId, userMessage.content, false);
      const pmMessage: ChatMessage = {
        role: 'pm',
        content: response.pm_response,
        timestamp: new Date(),
        nextQuestions: response.next_questions,
      };
      setMessages((prev) => [...prev, pmMessage]);
      setCanGeneratePRD(Boolean(response.can_generate_prd));
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'pm',
          content: err instanceof Error ? err.message : 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date(),
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePRD = async () => {
    if (!projectId) return;
    setGenerating(true);
    try {
      const response = await pmService.generatePRD(projectId);
      if (response.generation_status === 'completed') {
        navigate(`/projects/${projectId}/prd-review`);
      } else {
        window.alert('PRD generation started. You will be notified when it completes.');
      }
    } catch {
      window.alert('Failed to generate PRD. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Describe Your Business Need</h1>
          <p className="text-gray-600 mt-2">
            Have a conversation with the PM to refine your requirements
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 h-[500px] overflow-y-auto">
          {messages.map((message, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`mb-4 ${message.role === 'user' ? 'text-right' : 'text-left'}`}
            >
              <div
                className={`inline-block max-w-[80%] rounded-lg p-4 ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : message.isError
                      ? 'bg-red-500 text-white'
                      : 'bg-gray-100 text-gray-900'
                }`}
              >
                <div className="flex items-center mb-2">
                  <span className="text-lg mr-2">{message.role === 'user' ? '👤' : '🤖'}</span>
                  <span className="font-semibold">
                    {message.role === 'user' ? 'You' : 'PM Assistant'}
                  </span>
                </div>
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.nextQuestions && message.nextQuestions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-sm font-semibold mb-2">Next questions to consider:</p>
                    <ul className="text-sm space-y-1">
                      {message.nextQuestions.map((q, i) => (
                        <li key={i}>• {q}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </motion.div>
          ))}

          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-left mb-4">
              <div className="inline-block bg-gray-100 rounded-lg p-4">
                <div className="flex items-center">
                  <div className="animate-pulse flex space-x-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full" />
                  </div>
                  <span className="ml-3 text-gray-600">PM is typing...</span>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your response here..."
              className="flex-1 border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={3}
              disabled={loading}
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={() => void handleSendMessage()}
                disabled={!input.trim() || loading}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
              {canGeneratePRD && (
                <button
                  onClick={() => void handleGeneratePRD()}
                  disabled={generating}
                  className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {generating ? 'Generating...' : 'Generate PRD'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
