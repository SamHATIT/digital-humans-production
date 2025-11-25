import { Agent } from './types';

// DEMO_MODE = false to use real backend
export const DEMO_MODE = false;

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://srv1064321.hstgr.cloud:8002';

export const AGENTS: Agent[] = [
  { id: 'sophie', name: 'Sophie', role: 'Project Manager', description: 'Orchestrates the entire project lifecycle and ensures requirements are met.', avatar: '/avatars/sophie-pm.png', isMandatory: true },
  { id: 'olivia', name: 'Olivia', role: 'Business Analyst', description: 'Analyzes business needs and translates them into functional requirements.', avatar: '/avatars/olivia-ba.png', isMandatory: true },
  { id: 'marcus', name: 'Marcus', role: 'Solution Architect', description: 'Designs the technical architecture and data model.', avatar: '/avatars/marcus-architect.png' },
  { id: 'diego', name: 'Diego', role: 'Apex Developer', description: 'Implements backend logic, triggers, and batch processes.', avatar: '/avatars/diego-apex.png' },
  { id: 'zara', name: 'Zara', role: 'LWC Developer', description: 'Builds modern user interfaces using Lightning Web Components.', avatar: '/avatars/zara-lwc.png' },
  { id: 'raj', name: 'Raj', role: 'Salesforce Admin', description: 'Handles configuration, security, and declarative setups.', avatar: '/avatars/raj-admin.png' },
  { id: 'elena', name: 'Elena', role: 'QA Specialist', description: 'Executes test plans and ensures quality assurance.', avatar: '/avatars/elena-qa.png' },
  { id: 'jordan', name: 'Jordan', role: 'DevOps Engineer', description: 'Manages deployments, CI/CD pipelines, and version control.', avatar: '/avatars/jordan-devops.png' },
  { id: 'aisha', name: 'Aisha', role: 'Data Specialist', description: 'Manages data migration and transformation.', avatar: '/avatars/aisha-data.png' },
  { id: 'lucas', name: 'Lucas', role: 'Trainer', description: 'Prepares documentation and training materials.', avatar: '/avatars/lucas-trainer.png' },
];

// Mandatory agents that are always selected
export const MANDATORY_AGENTS = ['sophie', 'olivia'];
