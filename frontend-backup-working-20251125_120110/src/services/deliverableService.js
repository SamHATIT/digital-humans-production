/**
 * Deliverables API Service
 */
import api from './api';

const deliverableService = {
  /**
   * Get all deliverables for an execution
   */
  async getExecutionDeliverables(executionId) {
    const response = await api.get(`/deliverables/executions/${executionId}`);
    return response.data;
  },

  /**
   * Get deliverable previews for an execution
   */
  async getExecutionPreviews(executionId) {
    const response = await api.get(`/deliverables/executions/${executionId}/previews`);
    return response.data;
  },

  /**
   * Get full deliverable content
   */
  async getFullDeliverable(deliverableId) {
    const response = await api.get(`/deliverables/${deliverableId}/full`);
    return response.data;
  },

  /**
   * Get deliverables for a specific agent
   */
  async getAgentDeliverables(executionId, agentId) {
    const response = await api.get(`/deliverables/executions/${executionId}/agents/${agentId}`);
    return response.data;
  },

  /**
   * Get deliverable by type
   */
  async getDeliverableByType(executionId, deliverableType) {
    const response = await api.get(`/deliverables/executions/${executionId}/types/${deliverableType}`);
    return response.data;
  },

  /**
   * Create new deliverable
   */
  async createDeliverable(data) {
    const response = await api.post('/deliverables/', data);
    return response.data;
  },

  /**
   * Update deliverable
   */
  async updateDeliverable(deliverableId, data) {
    const response = await api.put(`/deliverables/${deliverableId}`, data);
    return response.data;
  },
};

export default deliverableService;
