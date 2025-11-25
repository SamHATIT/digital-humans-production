/**
 * PM Orchestrator API Service
 */
import api from './api';

const pmService = {
  /**
   * Send message to PM in dialogue
   */
  async dialogue(projectId, message, isFinalInput = false) {
    const response = await api.post('/pm/dialogue', {
      project_id: projectId,
      message,
      is_final_input: isFinalInput,
    });
    return response.data;
  },

  /**
   * Generate PRD from business need
   */
  async generatePRD(projectId) {
    const response = await api.post('/pm/generate-prd', {
      project_id: projectId,
    });
    return response.data;
  },

  /**
   * Get PRD for a project
   */
  async getPRD(projectId) {
    const response = await api.get(`/pm/projects/${projectId}/prd`);
    return response.data;
  },

  /**
   * Update PRD content
   */
  async updatePRD(projectId, prdContent) {
    const response = await api.put(`/pm/projects/${projectId}/prd`, {
      prd_content: prdContent,
    });
    return response.data;
  },

  /**
   * Generate user stories from PRD
   */
  async generateUserStories(projectId) {
    const response = await api.post(`/pm/projects/${projectId}/generate-user-stories`);
    return response.data;
  },

  /**
   * Get user stories for a project
   */
  async getUserStories(projectId) {
    const response = await api.get(`/pm/projects/${projectId}/user-stories`);
    return response.data;
  },

  /**
   * Update user stories
   */
  async updateUserStories(projectId, userStories) {
    const response = await api.put(`/pm/projects/${projectId}/prd`, {
      user_stories: userStories,
    });
    return response.data;
  },

  /**
   * Generate roadmap from user stories
   */
  async generateRoadmap(projectId) {
    const response = await api.post(`/pm/projects/${projectId}/generate-roadmap`);
    return response.data;
  },

  /**
   * Get roadmap for a project
   */
  async getRoadmap(projectId) {
    const response = await api.get(`/pm/projects/${projectId}/roadmap`);
    return response.data;
  },

  /**
   * Update roadmap
   */
  async updateRoadmap(projectId, roadmap) {
    const response = await api.put(`/pm/projects/${projectId}/prd`, {
      roadmap,
    });
    return response.data;
  },

  /**
   * Create new orchestration
   */
  async createOrchestration(projectId, businessNeed, businessContext = {}) {
    const response = await api.post('/pm/orchestration', {
      project_id: projectId,
      business_need: businessNeed,
      business_context: businessContext,
    });
    return response.data;
  },
};

export default pmService;
