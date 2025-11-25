/**
 * API Service - Centralized API calls using native fetch
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper function for API calls
async function apiCall(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token');
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }

  return response.json();
}

// ==================== AUTH ====================

export const auth = {
  login: async (email: string, password: string) => {
    const data = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    
    if (data.access_token) {
      localStorage.setItem('token', data.access_token);
    }
    return data;
  },

  logout: () => {
    localStorage.removeItem('token');
    window.location.href = '/login';
  },

  getCurrentUser: async () => {
    return apiCall('/api/auth/me', { method: 'GET' });
  },

  register: async (email: string, name: string, password: string) => {
    return apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, name, password }),
    });
  },
};

// ==================== PROJECTS ====================

export const projects = {
  create: async (data: any) => {
    return apiCall('/api/pm-orchestrator/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  list: async (skip = 0, limit = 50, status?: string) => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (status) params.append('status', status);
    return apiCall(`/api/pm-orchestrator/projects?${params}`, { method: 'GET' });
  },

  get: async (projectId: number) => {
    return apiCall(`/api/pm-orchestrator/projects/${projectId}`, { method: 'GET' });
  },

  update: async (projectId: number, data: any) => {
    return apiCall(`/api/pm-orchestrator/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: async (projectId: number) => {
    return apiCall(`/api/pm-orchestrator/projects/${projectId}`, { method: 'DELETE' });
  },

  getDashboardStats: async () => {
    return apiCall('/api/pm-orchestrator/dashboard/stats', { method: 'GET' });
  },

  updateStatus: async (projectId: number, status: string) => {
    return apiCall(`/api/projects/${projectId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },
};

// ==================== EXECUTIONS ====================

export const executions = {
  start: async (projectId: number, selectedAgents: string[]) => {
    return apiCall('/api/pm-orchestrator/execute', {
      method: 'POST',
      body: JSON.stringify({ 
        project_id: projectId, 
        selected_agents: selectedAgents 
      }),
    });
  },

  getProgress: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/progress`, { 
      method: 'GET' 
    });
  },

  getDetailedProgress: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/detailed-progress`, {
      method: 'GET',
    });
  },

  getResult: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/result`, { 
      method: 'GET' 
    });
  },

  getResultFile: (executionId: number) => {
    const token = localStorage.getItem('token');
    return `${API_URL}/api/pm-orchestrator/execute/${executionId}/download?token=${token}`;
  },

  chatWithPM: async (executionId: number, message: string) => {
    return apiCall(`/api/pm-orchestrator/chat/${executionId}`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
};

export default { auth, projects, executions };

// ==================== GENERIC API ====================

export const api = {
  get: async (endpoint: string) => {
    return apiCall(endpoint, { method: 'GET' });
  },
  
  post: async (endpoint: string, data?: any) => {
    return apiCall(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  },
  
  put: async (endpoint: string, data?: any) => {
    return apiCall(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  },
  
  delete: async (endpoint: string) => {
    return apiCall(endpoint, { method: 'DELETE' });
  },
};
