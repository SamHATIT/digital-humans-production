/**
 * API Service - Centralized API calls using native fetch
 */

const API_URL = import.meta.env.VITE_API_URL || '';

// LOT-F — cla:SEC-02 / ope:SEC-05.
// Le frontend posait ici un cookie `token` lisible en JS (pas de HttpOnly),
// miroir du JWT, pour que nginx `auth_request` puisse valider /admin/docs/.
// Un cookie posé par `document.cookie` ne peut PAS être HttpOnly : il était
// donc exfiltrable par n'importe quelle XSS, au même titre que localStorage,
// tout en élargissant la surface (envoyé sur `path=/`, donc sur chaque asset).
// La pose est supprimée. `clearTokenCookie` est conservé et toujours appelé
// au logout et sur 401, pour purger les cookies déjà déposés sur les
// navigateurs des utilisateurs existants.
// ⚠ Conséquence assumée, à reprendre côté backend : tant que le serveur
// n'émet pas lui-même le cookie HttpOnly au login, l'`auth_request` nginx de
// /admin/docs/ n'a plus de cookie à valider. Voir le rapport LOT-F.
function clearTokenCookie() {
  document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
}


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
    clearTokenCookie();
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

// ============ ACCÈS AUTHENTIFIÉ AUX FICHIERS (kim:SEC-07) ============

/**
 * Ces deux helpers remplacent les `window.open('...?token=' + jwt)` qui
 * parsemaient les pages. Le JWT partait en query string : il se retrouvait
 * dans les access logs nginx, les logs applicatifs et l'historique du
 * navigateur, et restait rejouable 24 h (ACCESS_TOKEN_EXPIRE_MINUTES=1440).
 *
 * Les routes visées acceptent déjà l'en-tête `Authorization` : elles dépendent
 * de `get_current_user_from_token_or_header`, qui essaie l'en-tête AVANT le
 * paramètre de requête. Aucune modification backend n'est donc requise.
 */
async function fetchAuthenticatedBlob(endpoint: string): Promise<Blob> {
  const token = localStorage.getItem('token');
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: { ...(token && { Authorization: `Bearer ${token}` }) },
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('token');
      clearTokenCookie();
      window.location.href = '/login';
    }
    throw new Error(`Request failed (${response.status})`);
  }

  return response.blob();
}

/**
 * Affiche une ressource protégée *inline* dans un nouvel onglet (SDS HTML).
 * L'onglet est ouvert de façon synchrone, avant l'`await`, pour rester dans
 * le geste utilisateur — sinon les bloqueurs de popup le rejettent.
 */
async function openAuthenticated(endpoint: string): Promise<void> {
  const tab = window.open('', '_blank');
  try {
    const blob = await fetchAuthenticatedBlob(endpoint);
    const blobUrl = URL.createObjectURL(blob);
    if (tab) {
      tab.location.href = blobUrl;
    } else {
      window.location.href = blobUrl;
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
  } catch (err) {
    tab?.close();
    throw err;
  }
}

/**
 * Télécharge une ressource protégée servie en `Content-Disposition:
 * attachment` (export CSV des BR, .docx d'une version de SDS). On passe par
 * un lien `download` afin de conserver un nom de fichier lisible, que l'URL
 * `blob:` ne porte pas.
 */
async function downloadAuthenticated(endpoint: string, filename: string): Promise<void> {
  const blob = await fetchAuthenticatedBlob(endpoint);
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

/**
 * POST authentifié dont la réponse est un FLUX (SSE sur POST), rendu brut à
 * l'appelant pour qu'il le consomme via `response.body.getReader()`.
 *
 * `apiCall` ne convient pas ici : il fait `return response.json()`, ce qui
 * consommerait le corps d'un coup et ferait perdre tout l'intérêt du flux.
 * On reproduit donc juste ce qu'il fait d'utile — en-tête `Authorization` et
 * traitement du 401 — puis on rend la `Response` intacte.
 */
async function streamAuthenticated(endpoint: string, body?: unknown): Promise<Response> {
  const token = localStorage.getItem('token');

  const response = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    clearTokenCookie();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `Request failed (${response.status})`);
  }

  return response;
}

export const files = { openAuthenticated, downloadAuthenticated };
export const stream = { post: streamAuthenticated };

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
    clearTokenCookie();
    window.location.href = '/login';
  },

  getCurrentUser: async () => {
    return apiCall('/api/auth/me', { method: 'GET' });
  },

  register: async (email: string, name: string, password: string, requestedTier?: string) => {
    // ⚠️ Legacy single-step signup. Kept for back-compat — new UI uses
    // signupRequest + signupConfirm instead (ONBOARDING-002).
    return apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        name,
        password,
        ...(requestedTier ? { requested_tier: requestedTier } : {}),
      }),
    });
  },

  signupRequest: async (
    email: string,
    name: string,
    password: string,
    requestedTier?: string,
    lang?: string,
  ) => {
    // ONBOARDING-002 — step 1: send the verification email. No account yet.
    return apiCall('/api/auth/signup-request', {
      method: 'POST',
      body: JSON.stringify({
        email,
        name,
        password,
        ...(requestedTier ? { requested_tier: requestedTier } : {}),
        ...(lang ? { lang } : {}),
      }),
    });
  },

  signupConfirm: async (token: string) => {
    // ONBOARDING-002 — step 2: redeem the token, get an access token back.
    return apiCall('/api/auth/signup-confirm', {
      method: 'POST',
      body: JSON.stringify({ token }),
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

  // P2-Full: Validation gates configuration
  getValidationGates: async (projectId: number) => {
    return apiCall(`/api/pm-orchestrator/projects/${projectId}/validation-gates`, {
      method: 'GET',
    });
  },

  updateValidationGates: async (projectId: number, gates: Record<string, boolean>) => {
    return apiCall(`/api/pm-orchestrator/projects/${projectId}/validation-gates`, {
      method: 'PUT',
      body: JSON.stringify(gates),
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

  // LOT-F — `getResultFile()` (export .docx legacy) est supprimé : aucun
  // appelant dans le frontend, et il fabriquait une URL portant le JWT.

  /**
   * Ouvre le SDS rendu (Jinja2, DB-driven) dans un nouvel onglet.
   * Remplace l'ancien `getSdsHtmlUrl()`, qui retournait une URL contenant le
   * JWT en query string (kim:SEC-07). Le jeton part désormais dans l'en-tête
   * `Authorization` et n'apparaît plus nulle part dans l'URL.
   * La page rendue porte son propre bouton PRINT · PDF.
   */
  openSdsHtml: (executionId: number | string) =>
    openAuthenticated(`/api/pm-orchestrator/execute/${executionId}/sds-html`),

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

// I1.4: Get budget/cost status for an execution
  getBudget: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/budget`, {
      method: 'GET',
    });
  },

  // P2-Full: Validation gates
  getValidationGate: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/validation-gate`, {
      method: 'GET',
    });
  },

  submitValidationGate: async (executionId: number, approved: boolean, annotations?: string) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/validation-gate/submit`, {
      method: 'POST',
      body: JSON.stringify({ approved, annotations }),
    });
  },

  getValidationHistory: async (executionId: number) => {
    return apiCall(`/api/pm-orchestrator/execute/${executionId}/validation-history`, {
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

// ==================== DOCUMENTS (P3: RAG Project Isolation) ====================

export const documents = {
  upload: async (projectId: number, file: File, collectionName: string = 'technical') => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${API_URL}/api/projects/${projectId}/documents?collection_name=${encodeURIComponent(collectionName)}`,
      {
        method: 'POST',
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: formData,
      }
    );

    if (response.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  },

  list: async (projectId: number) => {
    return apiCall(`/api/projects/${projectId}/documents`, { method: 'GET' });
  },

  delete: async (projectId: number, documentId: number) => {
    return apiCall(`/api/projects/${projectId}/documents/${documentId}`, { method: 'DELETE' });
  },
};
