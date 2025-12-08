import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  MessageSquare, FileText, GitBranch, CheckCircle, Download, Plus,
  Send, Clock, AlertCircle, Loader2, X, ChevronDown, ChevronUp, Play
} from 'lucide-react';
import api from '../services/api';

interface Project {
  id: number;
  name: string;
  description: string;
  salesforce_product: string;
  organization_type: string;
  status: string;
  current_sds_version: number;
}

interface SDSVersion {
  id: number;
  version_number: number;
  file_name: string;
  notes: string;
  generated_at: string;
  download_url: string;
}

interface ChangeRequest {
  id: number;
  cr_number: string;
  title: string;
  description?: string;
  category: string;
  status: string;
  priority: string;
  created_at: string;
  impact_analysis?: any;
  estimated_cost?: number;
}

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  message: string;
  created_at: string;
}

const CR_CATEGORIES = [
  { value: 'business_rule', label: 'Business Rule', icon: '📋' },
  { value: 'data_model', label: 'Data Model', icon: '🗄️' },
  { value: 'process', label: 'Process / Flow', icon: '🔄' },
  { value: 'ui_ux', label: 'UI / UX', icon: '🎨' },
  { value: 'integration', label: 'Integration', icon: '🔗' },
  { value: 'security', label: 'Security', icon: '🔒' },
  { value: 'other', label: 'Other', icon: '📝' },
];

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-500',
  submitted: 'bg-blue-500',
  analyzed: 'bg-yellow-500',
  approved: 'bg-green-500',
  processing: 'bg-purple-500',
  completed: 'bg-emerald-600',
  rejected: 'bg-red-500',
};

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  
  const [project, setProject] = useState<Project | null>(null);
  const [sdsVersions, setSdsVersions] = useState<SDSVersion[]>([]);
  const [changeRequests, setChangeRequests] = useState<ChangeRequest[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [chatLoading, setChatLoading] = useState(false);
  const [showCRModal, setShowCRModal] = useState(false);
  const [approvingSDSLoading, setApprovingSDSLoading] = useState(false);
  const [expandedCR, setExpandedCR] = useState<number | null>(null);
  const [startingBuild, setStartingBuild] = useState(false);
  const [latestExecutionId, setLatestExecutionId] = useState<number | null>(null);
  
  const [newCR, setNewCR] = useState({
    category: 'business_rule',
    title: '',
    description: '',
    priority: 'medium'
  });
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadProjectData();
  }, [projectId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const loadProjectData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [projectRes, versionsRes, crsRes, chatRes] = await Promise.all([
        api.get(`/api/projects/${projectId}`),
        api.get(`/api/projects/${projectId}/sds-versions`).catch(() => ({ versions: [] })),
        api.get(`/api/projects/${projectId}/change-requests`).catch(() => ({ change_requests: [] })),
        api.get(`/api/projects/${projectId}/chat/history`).catch(() => ({ messages: [] }))
      ]);
      
      setProject(projectRes);
      setSdsVersions(versionsRes.versions || []);
      setChangeRequests(crsRes.change_requests || []);
      setChatMessages(chatRes.messages || []);
    } catch (error) {
      console.error('Failed to load project:', error);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || chatLoading) return;
    const userMessage = newMessage;
    setNewMessage('');
    setChatLoading(true);
    
    setChatMessages(prev => [...prev, {
      id: Date.now(),
      role: 'user',
      message: userMessage,
      created_at: new Date().toISOString()
    }]);
    
    try {
      const response = await api.post(`/api/projects/${projectId}/chat`, { message: userMessage });
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        message: response.data.message,
        created_at: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Chat error:', error);
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        message: "Désolée, une erreur s'est produite. Veuillez réessayer.",
        created_at: new Date().toISOString()
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const createChangeRequest = async () => {
    if (!newCR.title || !newCR.description) return;
    try {
      await api.post(`/api/projects/${projectId}/change-requests`, newCR);
      setShowCRModal(false);
      setNewCR({ category: 'business_rule', title: '', description: '', priority: 'medium' });
      loadProjectData();
    } catch (error) {
      console.error('Failed to create CR:', error);
    }
  };

  const submitCR = async (crId: number) => {
    try {
      await api.post(`/api/projects/${projectId}/change-requests/${crId}/submit`);
      loadProjectData();
    } catch (error) {
      console.error('Failed to submit CR:', error);
    }
  };

  const approveCR = async (crId: number) => {
    try {
      await api.post(`/api/projects/${projectId}/change-requests/${crId}/approve`, {});
      loadProjectData();
    } catch (error) {
      console.error('Failed to approve CR:', error);
    }
  };

  const approveSDS = async () => {
    setApprovingSDSLoading(true);
    try {
      await api.post(`/api/projects/${projectId}/approve-sds`);
      loadProjectData();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to approve SDS');
    } finally {
      setApprovingSDSLoading(false);
    }
  };
  
  const startBuild = async () => {
    setStartingBuild(true);
    try {
      const response = await api.post(`/api/pm-orchestrator/projects/${projectId}/start-build`);
      // Navigate to BUILD monitoring page
      navigate(`/execution/${response.data.execution_id}/build`);
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to start BUILD phase');
    } finally {
      setStartingBuild(false);
    }
  };

  const downloadSDS = async (versionNumber: number) => {
    const token = localStorage.getItem('token');
    window.open(`/api/projects/${projectId}/sds-versions/${versionNumber}/download?token=${token}`, '_blank');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a1628] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-[#0a1628] flex items-center justify-center text-white">
        Project not found
      </div>
    );
  }

  const pendingCRs = changeRequests.filter(cr => !['completed', 'rejected'].includes(cr.status));
  const canApproveSDS = pendingCRs.length === 0 && sdsVersions.length > 0;

  return (
    <div className="min-h-screen bg-[#0a1628] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-cyan-400">{project.name}</h1>
        <p className="text-gray-400">{project.salesforce_product} • {project.organization_type}</p>
        <div className="mt-2 flex items-center gap-2">
          <span className={`px-2 py-1 rounded text-xs ${
            project.status === 'sds_approved' ? 'bg-green-600' : 'bg-blue-600'
          }`}>
            {project.status.toUpperCase().replace(/_/g, ' ')}
          </span>
          {project.current_sds_version > 0 && (
            <span className="px-2 py-1 rounded text-xs bg-purple-600">
              SDS v{project.current_sds_version}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: SDS Versions & Change Requests */}
        <div className="lg:col-span-1 space-y-6">
          {/* SDS Versions */}
          <div className="bg-[#1a2744] rounded-xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-cyan-400" />
              <h2 className="font-semibold">SDS Documents</h2>
            </div>
            
            {sdsVersions.length === 0 ? (
              <p className="text-gray-500 text-sm">No SDS versions yet</p>
            ) : (
              <div className="space-y-2">
                {sdsVersions.map(version => (
                  <div key={version.id} className="flex items-center justify-between p-2 bg-[#0d1829] rounded-lg">
                    <div>
                      <span className="font-medium">v{version.version_number}</span>
                      {version.version_number === project.current_sds_version && (
                        <span className="ml-2 text-xs bg-green-600 px-1 rounded">Current</span>
                      )}
                      <p className="text-xs text-gray-500">
                        {new Date(version.generated_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={() => downloadSDS(version.version_number)}
                      className="p-2 hover:bg-[#2a3f5f] rounded"
                    >
                      <Download className="w-4 h-4 text-cyan-400" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Change Requests */}
          <div className="bg-[#1a2744] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold">Change Requests</h2>
              </div>
              <button
                onClick={() => setShowCRModal(true)}
                className="p-1 hover:bg-[#2a3f5f] rounded"
              >
                <Plus className="w-5 h-5 text-purple-400" />
              </button>
            </div>

            {changeRequests.length === 0 ? (
              <p className="text-gray-500 text-sm">No change requests</p>
            ) : (
              <div className="space-y-2">
                {changeRequests.map(cr => (
                  <div key={cr.id} className="bg-[#0d1829] rounded-lg overflow-hidden">
                    <div 
                      className="p-3 cursor-pointer hover:bg-[#152238]"
                      onClick={() => setExpandedCR(expandedCR === cr.id ? null : cr.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[cr.status]}`} />
                          <span className="font-medium text-sm">{cr.cr_number}</span>
                        </div>
                        {expandedCR === cr.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </div>
                      <p className="text-sm text-gray-300 mt-1 truncate">{cr.title}</p>
                    </div>
                    
                    {expandedCR === cr.id && (
                      <div className="p-3 border-t border-gray-700 text-sm">
                        <p className="text-gray-400 mb-2">{cr.description}</p>
                        <div className="flex items-center gap-2 text-xs text-gray-500 mb-3">
                          <span className="capitalize">{cr.category.replace('_', ' ')}</span>
                          <span>•</span>
                          <span className="capitalize">{cr.priority}</span>
                          <span>•</span>
                          <span className="capitalize">{cr.status}</span>
                        </div>
                        
                        {cr.impact_analysis && (
                          <div className="bg-[#1a2744] p-2 rounded mb-3">
                            <p className="text-xs text-cyan-400 mb-1">Impact Analysis:</p>
                            <p className="text-xs">{cr.impact_analysis.summary}</p>
                            {cr.estimated_cost && (
                              <p className="text-xs text-yellow-400 mt-1">
                                Estimated cost: ${cr.estimated_cost.toFixed(2)}
                              </p>
                            )}
                          </div>
                        )}
                        
                        <div className="flex gap-2">
                          {cr.status === 'draft' && (
                            <button
                              onClick={() => submitCR(cr.id)}
                              className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs"
                            >
                              Submit for Analysis
                            </button>
                          )}
                          {cr.status === 'analyzed' && (
                            <button
                              onClick={() => approveCR(cr.id)}
                              className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-xs"
                            >
                              Approve & Process
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Approve SDS Button - Show only if not yet approved */}
          {project.status !== 'sds_approved' && project.status !== 'build_in_progress' && (
            <>
              <button
                onClick={approveSDS}
                disabled={!canApproveSDS || approvingSDSLoading}
                className={`w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 ${
                  canApproveSDS 
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700' 
                    : 'bg-gray-600 cursor-not-allowed opacity-50'
                }`}
              >
                {approvingSDSLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <CheckCircle className="w-5 h-5" />
                    Approve SDS & Continue
                  </>
                )}
              </button>
              
              {pendingCRs.length > 0 && (
                <p className="text-xs text-yellow-400 text-center">
                  <AlertCircle className="w-3 h-3 inline mr-1" />
                  {pendingCRs.length} pending CR(s) must be resolved first
                </p>
              )}
            </>
          )}
          
          {/* Start BUILD Button - Show after SDS approval */}
          {project.status === 'sds_approved' && (
            <button
              onClick={startBuild}
              disabled={startingBuild}
              className="w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600"
            >
              {startingBuild ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Start BUILD Phase
                </>
              )}
            </button>
          )}
          
          {/* BUILD in progress - Link to monitoring */}
          {project.status === 'build_in_progress' && (
            <button
              onClick={() => navigate(`/execution/${latestExecutionId}/build`)}
              className="w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
            >
              <Clock className="w-5 h-5" />
              View BUILD Progress
            </button>
          )}
        </div>

        {/* Right Column: Chat with Sophie */}
        <div className="lg:col-span-2 bg-[#1a2744] rounded-xl flex flex-col h-[600px]">
          <div className="p-4 border-b border-gray-700 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center">
              <span className="text-lg">S</span>
            </div>
            <div>
              <h2 className="font-semibold">Chat with Sophie</h2>
              <p className="text-xs text-gray-400">Project Manager • Ask anything about your SDS</p>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.length === 0 && (
              <div className="text-center text-gray-500 mt-8">
                <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Start a conversation with Sophie</p>
                <p className="text-sm">Ask questions about your SDS, requirements, or request clarifications</p>
              </div>
            )}
            
            {chatMessages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] p-3 rounded-xl ${
                  msg.role === 'user' 
                    ? 'bg-cyan-600 text-white' 
                    : 'bg-[#0d1829] text-gray-200'
                }`}>
                  <p className="whitespace-pre-wrap">{msg.message}</p>
                  <p className="text-xs opacity-50 mt-1">
                    {new Date(msg.created_at).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
            
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-[#0d1829] p-3 rounded-xl">
                  <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask Sophie about your project..."
                className="flex-1 bg-[#0d1829] rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              />
              <button
                onClick={sendMessage}
                disabled={chatLoading || !newMessage.trim()}
                className="px-4 py-3 bg-cyan-600 hover:bg-cyan-700 rounded-xl disabled:opacity-50"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* CR Modal */}
      {showCRModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#1a2744] rounded-xl p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">New Change Request</h2>
              <button onClick={() => setShowCRModal(false)}>
                <X className="w-5 h-5 text-gray-400 hover:text-white" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Category</label>
                <select
                  value={newCR.category}
                  onChange={(e) => setNewCR({ ...newCR, category: e.target.value })}
                  className="w-full bg-[#0d1829] rounded-lg px-4 py-2 text-white"
                >
                  {CR_CATEGORIES.map(cat => (
                    <option key={cat.value} value={cat.value}>
                      {cat.icon} {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Title</label>
                <input
                  type="text"
                  value={newCR.title}
                  onChange={(e) => setNewCR({ ...newCR, title: e.target.value })}
                  placeholder="Brief description of the change"
                  className="w-full bg-[#0d1829] rounded-lg px-4 py-2 text-white placeholder-gray-500"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Description</label>
                <textarea
                  value={newCR.description}
                  onChange={(e) => setNewCR({ ...newCR, description: e.target.value })}
                  placeholder="Explain the change in detail..."
                  rows={4}
                  className="w-full bg-[#0d1829] rounded-lg px-4 py-2 text-white placeholder-gray-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Priority</label>
                <div className="flex gap-2">
                  {['low', 'medium', 'high', 'critical'].map(p => (
                    <button
                      key={p}
                      onClick={() => setNewCR({ ...newCR, priority: p })}
                      className={`px-3 py-1 rounded capitalize text-sm ${
                        newCR.priority === p 
                          ? 'bg-cyan-600' 
                          : 'bg-[#0d1829] hover:bg-[#152238]'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCRModal(false)}
                className="flex-1 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={createChangeRequest}
                disabled={!newCR.title || !newCR.description}
                className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg disabled:opacity-50"
              >
                Create CR
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
