// DEMO_MODE = false to use real backend
export const DEMO_MODE = false;

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://srv1064321.hstgr.cloud:8002';

export interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  avatar: string;
  isMandatory?: boolean;
}

// Agent IDs must match backend: pm, ba, architect, apex, lwc, admin, qa, devops, data, trainer
export const AGENTS: Agent[] = [
  { id: 'pm', name: 'Sophie', role: 'Project Manager', description: 'Orchestrates the entire project lifecycle and ensures requirements are met.', avatar: '/avatars/sophie-pm.png', isMandatory: true },
  { id: 'ba', name: 'Olivia', role: 'Business Analyst', description: 'Analyzes business needs and translates them into functional requirements.', avatar: '/avatars/olivia-ba.png', isMandatory: true },
  { id: 'architect', name: 'Marcus', role: 'Solution Architect', description: 'Designs the technical architecture and data model.', avatar: '/avatars/marcus-architect.png' },
  { id: 'apex', name: 'Diego', role: 'Apex Developer', description: 'Implements backend logic, triggers, and batch processes.', avatar: '/avatars/diego-apex.png' },
  { id: 'lwc', name: 'Zara', role: 'LWC Developer', description: 'Builds modern user interfaces using Lightning Web Components.', avatar: '/avatars/zara-lwc.png' },
  { id: 'admin', name: 'Raj', role: 'Salesforce Admin', description: 'Handles configuration, security, and declarative setups.', avatar: '/avatars/raj-admin.png' },
  { id: 'qa', name: 'Elena', role: 'QA Specialist', description: 'Executes test plans and ensures quality assurance.', avatar: '/avatars/elena-qa.png' },
  { id: 'devops', name: 'Jordan', role: 'DevOps Engineer', description: 'Manages deployments, CI/CD pipelines, and version control.', avatar: '/avatars/jordan-devops.png' },
  { id: 'data', name: 'Aisha', role: 'Data Specialist', description: 'Manages data migration and transformation.', avatar: '/avatars/aisha-data.png' },
  { id: 'trainer', name: 'Lucas', role: 'Trainer', description: 'Prepares documentation and training materials.', avatar: '/avatars/lucas-trainer.png' },
];

// Mandatory agents that are always selected (using backend IDs)
export const MANDATORY_AGENTS = ['pm', 'ba'];
