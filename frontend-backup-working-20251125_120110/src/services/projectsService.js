/**
 * Projects API Service
 */
import api from './api';

const projectsService = {
  /**
   * List all projects with optional filtering
   */
  async list(skip = 0, limit = 50, status) {
    const params = { skip, limit };
    if (status) {
      params.status = status;
    }
    const response = await api.get('/projects/', { params });
    return response.data;
  },

  /**
   * Get a specific project by ID
   */
  async get(projectId) {
    const response = await api.get(`/projects/${projectId}`);
    return response.data;
  },

  /**
   * Create a new project
   */
  async create(projectData) {
    const response = await api.post('/projects/', projectData);
    return response.data;
  },

  /**
   * Update an existing project
   */
  async update(projectId, projectData) {
    const response = await api.put(`/projects/${projectId}`, projectData);
    return response.data;
  },

  /**
   * Delete a project
   */
  async delete(projectId) {
    const response = await api.delete(`/projects/${projectId}`);
    return response.data;
  },
};

export default projectsService;
