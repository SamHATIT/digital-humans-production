/**
 * Agent definitions for Digital Humans Salesforce Automation
 */

export interface Agent {
  id: string;
  name: string;
  avatar: string;
  description: string;
  estimatedTime: number;
  required: boolean;
}

export const AGENTS: Agent[] = [
  {
    id: 'ba',
    name: 'Olivia (Business Analyst)',
    avatar: '/avatars/olivia-ba.png',
    description: 'Analyzes business requirements and processes',
    estimatedTime: 4,
    required: true
  },
  {
    id: 'architect',
    name: 'Marcus (Solution Architect)',
    avatar: '/avatars/marcus-architect.png',
    description: 'Designs technical architecture and integration strategy',
    estimatedTime: 5,
    required: false
  },
  {
    id: 'apex',
    name: 'Diego (Apex Developer)',
    avatar: '/avatars/diego-apex.png',
    description: 'Creates Apex classes, triggers, and backend logic',
    estimatedTime: 6,
    required: false
  },
  {
    id: 'lwc',
    name: 'Zara (LWC Developer)',
    avatar: '/avatars/zara-lwc.png',
    description: 'Builds Lightning Web Components and UI',
    estimatedTime: 5,
    required: false
  },
  {
    id: 'admin',
    name: 'Raj (Administrator)',
    avatar: '/avatars/raj-admin.png',
    description: 'Configures objects, fields, flows, and validation rules',
    estimatedTime: 4,
    required: false
  },
  {
    id: 'qa',
    name: 'Elena (QA Engineer)',
    avatar: '/avatars/elena-qa.png',
    description: 'Creates test strategy and test cases',
    estimatedTime: 5,
    required: false
  },
  {
    id: 'devops',
    name: 'Jordan (DevOps Engineer)',
    avatar: '/avatars/jordan-devops.png',
    description: 'Sets up CI/CD pipelines and deployment strategy',
    estimatedTime: 4,
    required: false
  },
  {
    id: 'data',
    name: 'Aisha (Data Migration Specialist)',
    avatar: '/avatars/aisha-data.png',
    description: 'Designs data migration strategy and ETL processes',
    estimatedTime: 4,
    required: false
  },
  {
    id: 'trainer',
    name: 'Lucas (Trainer)',
    avatar: '/avatars/lucas-trainer.png',
    description: 'Creates training materials and user documentation',
    estimatedTime: 3,
    required: false
  }
];

/**
 * Calculate total estimated time for selected agents
 */
export function calculateTotalTime(selectedAgentIds: string[]): number {
  return AGENTS
    .filter(agent => selectedAgentIds.includes(agent.id))
    .reduce((total, agent) => total + agent.estimatedTime, 0);
}

/**
 * Get agent by ID
 */
export function getAgentById(id: string): Agent | undefined {
  return AGENTS.find(agent => agent.id === id);
}

/**
 * Get all required agents
 */
export function getRequiredAgents(): Agent[] {
  return AGENTS.filter(agent => agent.required);
}

/**
 * Get all optional agents
 */
export function getOptionalAgents(): Agent[] {
  return AGENTS.filter(agent => !agent.required);
}
