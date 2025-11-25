/**
 * PM Dialogue Page - Conversational interface with PM Orchestrator
 */
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import pmService from '../../services/pmService';

export default function PMDialogue() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      role: 'pm',
      content: "Hi! I'm your Product Manager. Let's transform your business need into a complete Salesforce implementation plan.\n\nTell me about your project:\n• What problem are you solving?\n• Who are the users?\n• What's your timeline?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [canGeneratePRD, setCanGeneratePRD] = useState(false);
  const [generating, setGenerating] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await pmService.dialogue(projectId, input, false);

      const pmMessage = {
        role: 'pm',
        content: response.pm_response,
        timestamp: new Date(),
        nextQuestions: response.next_questions,
      };

      setMessages((prev) => [...prev, pmMessage]);
      setCanGeneratePRD(response.can_generate_prd);
    } catch (error) {
      console.error('Error in PM dialogue:', error);
      const errorMessage = {
        role: 'pm',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePRD = async () => {
    setGenerating(true);

    try {
      const response = await pmService.generatePRD(projectId);

      if (response.generation_status === 'completed') {
        // Navigate to PRD review page
        navigate(`/projects/${projectId}/prd-review`);
      } else {
        alert('PRD generation started. You will be notified when it completes.');
      }
    } catch (error) {
      console.error('Error generating PRD:', error);
      alert('Failed to generate PRD. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Describe Your Business Need
          </h1>
          <p className="text-gray-600 mt-2">
            Have a conversation with the PM to refine your requirements
          </p>
        </div>

        {/* Chat Messages */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 h-[500px] overflow-y-auto">
          {messages.map((message, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`mb-4 ${
                message.role === 'user' ? 'text-right' : 'text-left'
              }`}
            >
              <div
                className={`inline-block max-w-[80%] rounded-lg p-4 ${
                  message.role === 'user'
                    ? 'bg-pm-primary text-white'
                    : message.isError
                    ? 'bg-pm-error text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <div className="flex items-center mb-2">
                  <span className="text-lg mr-2">
                    {message.role === 'user' ? '👤' : '🤖'}
                  </span>
                  <span className="font-semibold">
                    {message.role === 'user' ? 'You' : 'PM Assistant'}
                  </span>
                </div>
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.nextQuestions && message.nextQuestions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-sm font-semibold mb-2">
                      Next questions to consider:
                    </p>
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
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-left mb-4"
            >
              <div className="inline-block bg-gray-100 rounded-lg p-4">
                <div className="flex items-center">
                  <div className="animate-pulse flex space-x-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                  </div>
                  <span className="ml-3 text-gray-600">PM is typing...</span>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your response here..."
              className="flex-1 border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-pm-primary resize-none"
              rows={3}
              disabled={loading}
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={handleSendMessage}
                disabled={!input.trim() || loading}
                className="px-6 py-3 bg-pm-primary text-white rounded-lg hover:bg-pm-secondary disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
              {canGeneratePRD && (
                <button
                  onClick={handleGeneratePRD}
                  disabled={generating}
                  className="px-6 py-3 bg-pm-success text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
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
