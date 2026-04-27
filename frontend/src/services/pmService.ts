/**
 * PM Orchestrator API Service.
 * Couvre les 4 pages legacy `pages/pm/*` (dialogue, PRD, user stories,
 * roadmap). Ces pages ne sont pas routées dans `App.tsx` actuellement —
 * elles seront refondues lors de A5.2/A5.3, ce service garde donc une
 * surface stable et minimaliste.
 */
import { api } from './api';

export interface DialogueResponse {
  pm_response: string;
  next_questions?: string[];
  can_generate_prd?: boolean;
}

export interface GeneratePRDResponse {
  generation_status: string;
}

export interface PRDResponse {
  prd_content: string;
}

export interface UserStory {
  id: string;
  title: string;
  description: string;
  priority: string;
  story_points: number;
  acceptance_criteria?: string[];
  dependencies?: string[];
}

export interface UserStoriesResponse {
  user_stories: UserStory[];
}

export interface RoadmapPhase {
  name: string;
  duration_weeks: number;
  user_stories?: string[];
  deliverables?: string[];
  success_criteria?: string[];
}

export interface Roadmap {
  total_duration_weeks: number;
  phases: RoadmapPhase[];
}

export interface RoadmapResponse {
  roadmap: Roadmap;
}

const pmService = {
  dialogue: (
    projectId: number | string,
    message: string,
    isFinalInput = false,
  ): Promise<DialogueResponse> =>
    api.post('/pm/dialogue', {
      project_id: projectId,
      message,
      is_final_input: isFinalInput,
    }),

  generatePRD: (projectId: number | string): Promise<GeneratePRDResponse> =>
    api.post('/pm/generate-prd', { project_id: projectId }),

  getPRD: (projectId: number | string): Promise<PRDResponse> =>
    api.get(`/pm/projects/${projectId}/prd`),

  updatePRD: (projectId: number | string, prdContent: string): Promise<PRDResponse> =>
    api.put(`/pm/projects/${projectId}/prd`, { prd_content: prdContent }),

  generateUserStories: (projectId: number | string): Promise<UserStoriesResponse> =>
    api.post(`/pm/projects/${projectId}/generate-user-stories`),

  getUserStories: (projectId: number | string): Promise<UserStoriesResponse> =>
    api.get(`/pm/projects/${projectId}/user-stories`),

  generateRoadmap: (projectId: number | string): Promise<RoadmapResponse> =>
    api.post(`/pm/projects/${projectId}/generate-roadmap`),

  getRoadmap: (projectId: number | string): Promise<RoadmapResponse> =>
    api.get(`/pm/projects/${projectId}/roadmap`),
};

export default pmService;
