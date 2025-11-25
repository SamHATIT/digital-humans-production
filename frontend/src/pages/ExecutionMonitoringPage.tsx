import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, ArrowLeft, Send, CheckCircle, Circle, Loader } from 'lucide-react';
import { executions, projects } from '../services/api';

// Mapping complet des agents avec avatars large (400x400)
const AGENTS_INFO = {
  'ba': { name: 'Olivia', role: 'Business Analyst', avatar: '/avatars/large/olivia-ba.png' },
  'architect': { name: 'Marcus', role: 'Solution Architect', avatar: '/avatars/large/marcus-architect.png' },
  'apex': { name: 'Diego', role: 'Apex Developer', avatar: '/avatars/large/diego-apex.png' },
  'lwc': { name: 'Zara', role: 'LWC Developer', avatar: '/avatars/large/zara-lwc.png' },
  'admin': { name: 'Raj', role: 'Salesforce Administrator', avatar: '/avatars/large/raj-admin.png' },
  'qa': { name: 'Elena', role: 'QA Engineer', avatar: '/avatars/large/elena-qa.png' },
  'devops': { name: 'Jordan', role: 'DevOps Engineer', avatar: '/avatars/large/jordan-devops.png' },
  'data': { name: 'Aisha', role: 'Data Migration Specialist', avatar: '/avatars/large/aisha-data.png' },
  'trainer': { name: 'Lucas', role: 'Technical Trainer', avatar: '/avatars/large/lucas-trainer.png' },
  'pm': { name: 'Sophie', role: 'PM Orchestrator', avatar: '/avatars/large/sophie-pm.png' },
};

interface Task {
  order: number;
  name: string;
  agent: string;
  status: 'completed' | 'running' | 'waiting';
}

interface ChatMessage {
  from: 'user' | 'pm';
  message: string;
  timestamp: Date;
}

export default function ExecutionMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  
  const [tasks, setTasks] = useState<Task[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [executionStatus, setExecutionStatus] = useState<string>('running');
  const [project, setProject] = useState<any>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [sdsPath, setSdsPath] = useState<string | null>(null);

  useEffect(() => {
    if (executionId) {
      loadInitialData();
      const interval = setInterval(fetchProgress, 3000);
      return () => clearInterval(interval);
    }
  }, [executionId]);

  const loadInitialData = async () => {
    try {
      // Charger les infos de l'exécution pour récupérer le project_id
      const execData = await executions.getProgress(Number(executionId));
      if (execData.project_id) {
        const projectData = await projects.get(execData.project_id);
        setProject(projectData);
      }
      setIsLoading(false);
    } catch (error) {
      console.error('Error loading initial data:', error);
      setIsLoading(false);
    }
  };

  const fetchProgress = async () => {
    try {
      const data = await executions.getDetailedProgress(Number(executionId));
      
      setTasks(data.tasks || []);
      setExecutionStatus(data.status);
      setSdsPath(data.sds_document_path);
      
      // Trouver l'agent en cours
      const runningTask = data.tasks?.find((t: Task) => t.status === 'running');
      if (runningTask) {
        setCurrentAgent(runningTask.agent);
      } else if (data.status === 'completed' || data.status === 'SDS Completed') {
        setCurrentAgent('pm'); // Sophie pour la consolidation finale
      }
      
      // Arrêter le polling si terminé
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'SDS Completed') {
        return; // Le interval sera nettoyé par useEffect cleanup
      }
    } catch (error) {
      console.error('Error fetching progress:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return;
    
    const userMessage: ChatMessage = {
      from: 'user',
      message: chatInput,
      timestamp: new Date()
    };
    
    setChatMessages([...chatMessages, userMessage]);
    setChatInput('');
    
    try {
      const response = await executions.chatWithPM(Number(executionId), chatInput);
      const pmMessage: ChatMessage = {
        from: 'pm',
        message: response.pm_response,
        timestamp: new Date()
      };
      setChatMessages(prev => [...prev, pmMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  const handleDownloadSDS = () => {
    if (sdsPath) {
      window.open(executions.getResultFile(Number(executionId)), '_blank');
    }
  };

  const completedCount = tasks.filter(t => t.status === 'completed').length;
  const totalCount = tasks.length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading execution data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate('/projects')}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition"
            >
              <ArrowLeft size={20} />
              <span>Back to Projects</span>
            </button>
            
            <div className="text-center flex-1 mx-8">
              <h1 className="text-2xl font-bold text-gray-900">
                {project?.name || 'Project Execution'}
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                {project?.salesforce_product} • {project?.organization_type}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <div className={`px-4 py-2 rounded-lg font-medium text-sm ${
                executionStatus === 'running' ? 'bg-blue-100 text-blue-700' :
                executionStatus === 'SDS Completed' || executionStatus === 'completed' ? 'bg-green-100 text-green-700' :
                executionStatus === 'failed' ? 'bg-red-100 text-red-700' :
                'bg-gray-100 text-gray-700'
              }`}>
                {executionStatus.toUpperCase()}
              </div>
              <div className="text-sm text-gray-600">
                <span className="font-semibold">{completedCount}</span> / {totalCount} tasks
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-5 gap-8">
          
          {/* Timeline - Left 40% */}
          <div className="col-span-2 bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-h-[calc(100vh-250px)] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-6 text-gray-900">Execution Timeline</h2>
            
            <div className="space-y-4">
              {tasks.map((task, index) => (
                <div key={task.order} className="relative">
                  {/* Vertical line */}
                  {index < tasks.length - 1 && (
                    <div className="absolute left-4 top-12 bottom-0 w-0.5 bg-gray-200" />
                  )}
                  
                  <div className={`relative flex items-start gap-4 p-4 rounded-lg transition-all ${
                    task.status === 'completed' ? 'opacity-60' :
                    task.status === 'running' ? 'bg-blue-50 ring-2 ring-blue-200' :
                    'opacity-40'
                  }`}>
                    {/* Icon */}
                    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      task.status === 'completed' ? 'bg-green-100 text-green-600' :
                      task.status === 'running' ? 'bg-blue-500 text-white' :
                      'bg-gray-200 text-gray-400'
                    }`}>
                      {task.status === 'completed' ? <CheckCircle size={18} /> :
                       task.status === 'running' ? <Loader size={18} className="animate-spin" /> :
                       <Circle size={18} />}
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1">
                      <h3 className={`font-medium ${
                        task.status === 'completed' ? 'line-through text-gray-500' :
                        task.status === 'running' ? 'text-blue-900' :
                        'text-gray-600'
                      }`}>
                        {task.name}
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Agent: {AGENTS_INFO[task.agent as keyof typeof AGENTS_INFO]?.name || task.agent}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agent Display - Right 60% */}
          <div className="col-span-3 bg-white rounded-lg shadow-sm border border-gray-200 p-8 flex flex-col items-center justify-center min-h-[500px]">
            {currentAgent && AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO] ? (
              <div className="text-center animate-fadeIn">
                <img
                  src={AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO].avatar}
                  alt={AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO].name}
                  className="w-64 h-64 rounded-full mx-auto mb-6 shadow-2xl ring-4 ring-blue-100 object-cover"
                  onError={(e) => {
                    e.currentTarget.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="%234F46E5"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-size="96" font-family="sans-serif">' + AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO].name[0] + '</text></svg>';
                  }}
                />
                <h2 className="text-3xl font-bold text-gray-900 mb-2">
                  {AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO].name}
                </h2>
                <p className="text-xl text-gray-600 mb-4">
                  {AGENTS_INFO[currentAgent as keyof typeof AGENTS_INFO].role}
                </p>
                {executionStatus === 'running' && (
                  <div className="flex items-center justify-center gap-2 text-blue-600">
                    <div className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                    <span className="text-sm font-medium">Currently working...</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-gray-400">
                <Circle size={64} className="mx-auto mb-4" />
                <p>Waiting for execution to start...</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Chat PM - Sticky Bottom */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-4">
          {/* Messages récents (max 3) */}
          {chatMessages.length > 0 && (
            <div className="mb-3 space-y-2 max-h-32 overflow-y-auto">
              {chatMessages.slice(-3).map((msg, idx) => (
                <div key={idx} className={`flex ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-md px-4 py-2 rounded-lg text-sm ${
                    msg.from === 'user' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-gray-100 text-gray-900'
                  }`}>
                    {msg.message}
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {/* Input */}
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <img
                src="/avatars/small/sophie-pm.png"
                alt="Sophie"
                className="w-10 h-10 rounded-full"
              />
            </div>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Ask Sophie (PM) a question..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={executionStatus === 'failed'}
            />
            <button
              onClick={handleSendMessage}
              disabled={!chatInput.trim() || executionStatus === 'failed'}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition flex items-center gap-2"
            >
              <Send size={18} />
              <span>Send</span>
            </button>
            
            {/* Download Button */}
            {(executionStatus === 'SDS Completed' || executionStatus === 'completed') && sdsPath && (
              <button
                onClick={handleDownloadSDS}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center gap-2 font-medium"
              >
                <Download size={18} />
                <span>Download SDS</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
