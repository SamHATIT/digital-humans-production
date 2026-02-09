/**
 * API Service - Centralized API calls using native fetch
 */

const API_URL = import.meta.env.VITE_API_URL || '';

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
    const errorMsg = Array.isArray(error.detail) ? error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ") : (error.detail || 'Request failed');
    throw new Error(errorMsg);
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

  // H12: Resume execution with optional action (architecture validation)
  resume: async (executionId: number, action?: string) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/resume`, {
      method: 'POST',
      body: action ? JSON.stringify({ action }) : '{}',
    });
  },

  // ORCH-04: Retry failed execution
  retry: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/retry`, {
      method: 'POST',
    });
  },

  // ORCH-04: Get retry info for failed execution
  getRetryInfo: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/retry-info`, {
      method: 'GET',
    });
  },

  chatWithPM: async (executionId: number, message: string) => {
    return apiCall(`/api/pm-orchestrator/chat/${executionId}`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },

  // SDS v3 - Generate full SDS with micro-analysis + synthesis + DOCX
  generateSDSv3: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/generate-sds-v3`, {
      method: 'POST',
    });
  },

  // SDS v3 - Download generated DOCX
  downloadSDSv3: (executionId: number) => {
    const token = localStorage.getItem('token');
    return `${API_URL}/api/pm-orchestrator/execute/${executionId}/download-sds-v3?token=${token}`;
  },

  // SDS v3 - Get synthesis preview (domains summary)
  getSDSv3Preview: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/sds-preview`, {
      method: 'GET',
    });
  },
};

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

// Export default AFTER api is defined
export default { auth, projects, executions, get: api.get, post: api.post, put: api.put, delete: api.delete };
// ==================== WIZARD ====================

export const wizard = {
  create: async (data: {
    name: string;
    description?: string;
    project_code?: string;
    client_name?: string;
    client_contact_name?: string;
    client_contact_email?: string;
    client_contact_phone?: string;
    start_date?: string;
    end_date?: string;
  }) => {
    return apiCall('/api/wizard/create', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateStep: async (projectId: number, step: number, data: any) => {
    return apiCall(`/api/wizard/${projectId}/step/${step}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  getProgress: async (projectId: number) => {
    return apiCall(`/api/wizard/${projectId}/progress`, {
      method: 'GET',
    });
  },

  testSalesforce: async (projectId: number) => {
    return apiCall(`/api/wizard/${projectId}/test/salesforce`, {
      method: 'POST',
    });
  },

  testGit: async (projectId: number) => {
    return apiCall(`/api/wizard/${projectId}/test/git`, {
      method: 'POST',
    });
  },
};
