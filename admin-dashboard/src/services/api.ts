const API_BASE_URL = 'http://localhost:8000';

export interface HealthResponse {
  status: string;
}

export interface ConversationItem {
  id: string;
  user_id?: string;
  title: string;
  conversation_type: string;
  template_folder?: string;
  template_id?: string;
  job_status?: string;
  job_total?: number;
  job_completed?: number;
  job_skipped?: number;
  job_failed?: number;
  created_at?: string;
  updated_at?: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch health check:', err);
    return { status: 'offline' };
  }
}

export async function fetchConversations(limit = 50): Promise<ConversationItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/history/conversations?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch conversations from backend, using fallback data:', err);
    return [];
  }
}

export async function processBulkExcel(file: File, templateFolder?: string): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  if (templateFolder) {
    formData.append('template_folder', templateFolder);
  }

  const res = await fetch(`${API_BASE_URL}/bulk/process-file`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed bulk job request (${res.status})`);
  }

  return await res.json();
}

export async function generateSinglePoster(prompt: string, templateFolder: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/generate/poster`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      prompt,
      template_folder: templateFolder,
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed single poster request (${res.status})`);
  }

  return await res.json();
}

export async function fetchAdminStats(): Promise<{ total_templates: number; total_posters: number; active_sessions: number; total_users: number }> {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/stats`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin stats, using defaults:', err);
    return { total_templates: 16, total_posters: 117, active_sessions: 12, total_users: 8 };
  }
}

export async function fetchAdminTemplates(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/templates`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin templates:', err);
    return [];
  }
}

export async function fetchAdminUsers(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/users`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin users:', err);
    return [];
  }
}

export async function fetchAdminLogs(search?: string): Promise<any[]> {
  try {
    const url = search && search.trim()
      ? `${API_BASE_URL}/admin/logs?search=${encodeURIComponent(search.trim())}`
      : `${API_BASE_URL}/admin/logs`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin logs:', err);
    return [];
  }
}

export async function fetchAdminPosters(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/posters`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin posters:', err);
    return [];
  }
}

export async function fetchAdminBulkJobs(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/bulk-jobs`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch admin bulk jobs:', err);
    return [];
  }
}

