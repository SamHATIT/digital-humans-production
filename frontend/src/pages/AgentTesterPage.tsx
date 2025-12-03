import React, { useState, useEffect, useRef } from 'react';
import { Play, Terminal, CheckCircle, XCircle, Loader2, Database, RefreshCw, User, Zap, Cloud, FolderOpen } from 'lucide-react';

interface Agent {
  name: string;
  role: string;
  description: string;
  capabilities: string[];
  color: string;
}

interface SalesforceOrg {
  alias: string;
  username: string;
  instance_url: string;
  connected: boolean;
}

interface LogEntry {
  type: string;
  level?: string;
  message?: string;
  agent?: string;
  task?: string;
  timestamp?: string;
}

const AgentTesterPage: React.FC = () => {
  const [agents, setAgents] = useState<Record<string, Agent>>({});
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [taskDescription, setTaskDescription] = useState<string>('');
  const [salesforceOrg, setSalesforceOrg] = useState<SalesforceOrg | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [workspaceFiles, setWorkspaceFiles] = useState<Record<string, string[]>>({});
  const logsEndRef = useRef<HTMLDivElement>(null);

  const API_URL = ''; // Proxy via Vite

  useEffect(() => {
    fetchAgents();
    fetchWorkspaceFiles();
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const fetchAgents = async () => {
    try {
      const response = await fetch(`${API_URL}/api/agent-tester/agents`);
      const data = await response.json();
      setAgents(data.agents);
      setSalesforceOrg(data.salesforce_org);
      if (Object.keys(data.agents).length > 0) {
        setSelectedAgent(Object.keys(data.agents)[0]);
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const fetchWorkspaceFiles = async () => {
    try {
      const response = await fetch(`${API_URL}/api/agent-tester/workspace/files`);
      const data = await response.json();
      setWorkspaceFiles(data.files);
    } catch (error) {
      console.error('Error fetching workspace files:', error);
    }
  };

  const runAgentTest = async () => {
    if (!selectedAgent || !taskDescription.trim()) return;
    
    setIsRunning(true);
    setLogs([]);

    try {
      const response = await fetch(`${API_URL}/api/agent-tester/test/${selectedAgent}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent,
          task_description: taskDescription,
          deploy_to_org: true
        })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              setLogs(prev => [...prev, data]);
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (error) {
      console.error('Error running test:', error);
      setLogs(prev => [...prev, { type: 'error', message: `Erreur: ${error}` }]);
    } finally {
      setIsRunning(false);
      fetchWorkspaceFiles();
    }
  };

  const getLogIcon = (level?: string) => {
    switch (level) {
      case 'SUCCESS': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'ERROR': return <XCircle className="w-4 h-4 text-red-500" />;
      case 'LLM': return <Zap className="w-4 h-4 text-yellow-500" />;
      case 'SFDX': return <Cloud className="w-4 h-4 text-blue-500" />;
      default: return <Terminal className="w-4 h-4 text-gray-400" />;
    }
  };

  const getLogColor = (level?: string) => {
    switch (level) {
      case 'SUCCESS': return 'text-green-400';
      case 'ERROR': return 'text-red-400';
      case 'LLM': return 'text-yellow-400';
      case 'SFDX': return 'text-blue-400';
      default: return 'text-gray-300';
    }
  };

  const selectedAgentData = agents[selectedAgent];

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Terminal className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-xl font-bold">Agent Tester</h1>
              <p className="text-sm text-gray-400">Test individuel des agents Salesforce</p>
            </div>
          </div>
          {salesforceOrg && (
            <div className="flex items-center gap-2 bg-green-900/30 border border-green-700 rounded-lg px-4 py-2">
              <Cloud className="w-5 h-5 text-green-500" />
              <div className="text-sm">
                <div className="text-green-400 font-medium">{salesforceOrg.alias}</div>
                <div className="text-green-600 text-xs">{salesforceOrg.username}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex h-[calc(100vh-80px)]">
        {/* Left Panel - Agent Selection */}
        <div className="w-80 bg-gray-800 border-r border-gray-700 p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-gray-400 uppercase mb-4">Agents disponibles</h2>
          <div className="space-y-2">
            {Object.entries(agents).map(([id, agent]) => (
              <button
                key={id}
                onClick={() => setSelectedAgent(id)}
                className={`w-full text-left p-3 rounded-lg transition-all ${
                  selectedAgent === id 
                    ? 'bg-blue-600 border-blue-500' 
                    : 'bg-gray-700 hover:bg-gray-600 border-gray-600'
                } border`}
              >
                <div className="flex items-center gap-3">
                  <div 
                    className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
                    style={{ backgroundColor: agent.color }}
                  >
                    {agent.name[0]}
                  </div>
                  <div>
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-xs text-gray-400">{agent.role}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Workspace Files */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-400 uppercase">Workspace SFDX</h2>
              <button onClick={fetchWorkspaceFiles} className="text-gray-500 hover:text-white">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2 text-sm">
              {Object.entries(workspaceFiles).map(([folder, files]) => (
                <div key={folder} className="bg-gray-700 rounded p-2">
                  <div className="flex items-center gap-2 text-gray-300">
                    <FolderOpen className="w-4 h-4" />
                    <span>{folder}/</span>
                    <span className="text-gray-500">({files.length})</span>
                  </div>
                  {files.length > 0 && (
                    <div className="mt-1 pl-6 text-xs text-gray-500">
                      {files.slice(0, 3).join(', ')}
                      {files.length > 3 && ` +${files.length - 3}`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center Panel - Task Input & Logs */}
        <div className="flex-1 flex flex-col">
          {/* Agent Info & Task Input */}
          <div className="p-4 bg-gray-850 border-b border-gray-700">
            {selectedAgentData && (
              <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: `${selectedAgentData.color}20` }}>
                <div className="flex items-center gap-3 mb-2">
                  <div 
                    className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-xl"
                    style={{ backgroundColor: selectedAgentData.color }}
                  >
                    {selectedAgentData.name[0]}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold">{selectedAgentData.name}</h3>
                    <p className="text-sm text-gray-400">{selectedAgentData.role}</p>
                  </div>
                </div>
                <p className="text-sm text-gray-300 mb-2">{selectedAgentData.description}</p>
                <div className="flex flex-wrap gap-2">
                  {selectedAgentData.capabilities.map(cap => (
                    <span key={cap} className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <textarea
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                placeholder="Décrivez la tâche à effectuer... Ex: Créer un trigger sur Account qui met à jour un champ custom"
                className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
                rows={3}
                disabled={isRunning}
              />
              <button
                onClick={runAgentTest}
                disabled={isRunning || !taskDescription.trim()}
                className={`px-6 rounded-lg font-medium flex items-center gap-2 ${
                  isRunning || !taskDescription.trim()
                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Exécution...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Exécuter
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Logs Panel */}
          <div className="flex-1 bg-gray-900 p-4 overflow-y-auto font-mono text-sm">
            <div className="flex items-center gap-2 mb-3 text-gray-500">
              <Terminal className="w-4 h-4" />
              <span>Logs d'exécution</span>
            </div>
            
            {logs.length === 0 ? (
              <div className="text-gray-600 text-center py-8">
                Les logs apparaîtront ici lors de l'exécution...
              </div>
            ) : (
              <div className="space-y-1">
                {logs.map((log, index) => (
                  <div key={index} className="flex items-start gap-2">
                    {log.type === 'start' ? (
                      <div className="text-blue-400">
                        ▶ Démarrage test: {log.agent} - "{log.task?.substring(0, 50)}..."
                      </div>
                    ) : log.type === 'end' ? (
                      <div className="text-green-400">
                        ✓ {log.message}
                      </div>
                    ) : log.type === 'error' ? (
                      <div className="text-red-400 flex items-center gap-2">
                        <XCircle className="w-4 h-4" />
                        {log.message}
                      </div>
                    ) : log.type === 'heartbeat' ? (
                      <div className="text-gray-500 flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {log.message}
                      </div>
                    ) : (
                      <>
                        {getLogIcon(log.level)}
                        <span className={getLogColor(log.level)}>{log.message}</span>
                      </>
                    )}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentTesterPage;
