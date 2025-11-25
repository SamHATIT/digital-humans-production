export interface User {
  id: string;
  email: string;
  name: string;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  avatar: string;
  isMandatory?: boolean;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  status: 'draft' | 'ready' | 'in_progress' | 'completed' | 'failed';
  created_at: string;
  updated_at?: string;
}

export type Phase = 'Discovery' | 'Design' | 'Build' | 'QA' | 'Release';

export interface WorkflowStage {
  phase: Phase;
  agents: string[];
}

export interface LogEntry {
  id: string;
  timestamp: string;
  agent_name: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'warning';
}

export interface Task {
  id: string;
  agent_name: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  logs: LogEntry[];
  updated_at: string;
}

export interface ExecutionStatus {
  project_id: number;
  status: string;
  progress: number;
  current_stage: string;
  active_agents: string[];
  logs: LogEntry[];
  tasks?: Task[];
}

export interface AgentContext {
  currentTask: string;
  thoughtChain: string[];
  memoryUsage: string;
  activeFiles: string[];
}
