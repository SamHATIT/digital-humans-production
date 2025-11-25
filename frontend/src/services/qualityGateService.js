/**
 * Quality Gates API Service
 */
import api from './api';

const qualityGateService = {
  /**
   * Get all quality gates for an execution
   */
  async getExecutionQualityGates(executionId) {
    const response = await api.get(`/quality-gates/executions/${executionId}`);
    return response.data;
  },

  /**
   * Get quality gates for a specific agent
   */
  async getAgentQualityGates(executionId, agentId) {
    const response = await api.get(`/quality-gates/executions/${executionId}/agents/${agentId}`);
    return response.data;
  },

  /**
   * Get quality gate summary for an agent
   */
  async getQualityGateSummary(executionId, agentId) {
    const response = await api.get(`/quality-gates/executions/${executionId}/agents/${agentId}/summary`);
    return response.data;
  },

  /**
   * Check if ERD is present
   */
  async checkERD(executionId, agentId) {
    const response = await api.post(`/quality-gates/executions/${executionId}/agents/${agentId}/check-erd`);
    return response.data;
  },

  /**
   * Check process flows count
   */
  async checkProcessFlows(executionId, agentId, minimum = 3) {
    const response = await api.post(
      `/quality-gates/executions/${executionId}/agents/${agentId}/check-flows?minimum=${minimum}`
    );
    return response.data;
  },

  /**
   * Check HLD document size
   */
  async checkHLDSize(executionId, agentId, minimumPages = 100) {
    const response = await api.post(
      `/quality-gates/executions/${executionId}/agents/${agentId}/check-hld?minimum_pages=${minimumPages}`
    );
    return response.data;
  },

  /**
   * Get iterations for an agent
   */
  async getAgentIterations(executionId, agentId) {
    const response = await api.get(`/quality-gates/executions/${executionId}/agents/${agentId}/iterations`);
    return response.data;
  },

  /**
   * Check if agent should retry
   */
  async shouldRetry(executionId, agentId, maxIterations = 2) {
    const response = await api.get(
      `/quality-gates/executions/${executionId}/agents/${agentId}/should-retry?max_iterations=${maxIterations}`
    );
    return response.data;
  },

  /**
   * Create quality gate
   */
  async createQualityGate(data) {
    const response = await api.post('/quality-gates/', data);
    return response.data;
  },

  /**
   * Create iteration
   */
  async createIteration(data) {
    const response = await api.post('/quality-gates/iterations', data);
    return response.data;
  },
};

export default qualityGateService;
