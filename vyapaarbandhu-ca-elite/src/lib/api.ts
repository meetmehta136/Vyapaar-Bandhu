const BASE_URL = import.meta.env.VITE_API_URL || 'https://vyapaar-bandhu-h53q.onrender.com';

// ── Auth helpers ──────────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem('vb_token');
}

export function saveToken(token: string) {
  localStorage.setItem('vb_token', token);
}

export function clearToken() {
  localStorage.removeItem('vb_token');
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token
    ? { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    : { 'Content-Type': 'application/json' };
}

// ── Core fetch wrappers ───────────────────────────────────────────────────────

async function fetchAPI(endpoint: string) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, { headers: authHeaders() });
    if (res.status === 401) { clearToken(); window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error ${endpoint}:`, e);
    return null;
  }
}

async function postAPI(endpoint: string, body?: object) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: authHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) { clearToken(); window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error POST ${endpoint}:`, e);
    return null;
  }
}

async function putAPI(endpoint: string, body?: object) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error PUT ${endpoint}:`, e);
    return null;
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.token) saveToken(data.token);
    return data;
  } catch (e) {
    console.error('Login error:', e);
    return null;
  }
}

export async function signup(payload: {
  name: string; email: string; password: string;
  phone?: string; ca_number?: string;
}) {
  try {
    const res = await fetch(`${BASE_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.token) saveToken(data.token);
    return data;
  } catch (e) {
    console.error('Signup error:', e);
    return null;
  }
}

export async function getMe() {
  return await fetchAPI('/auth/me');
}

export async function updateProfile(data: Record<string, string>) {
  return await putAPI('/auth/profile', data);
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export async function getDashboardStats() {
  return await fetchAPI('/api/dashboard/stats');
}

// ── Clients ───────────────────────────────────────────────────────────────────

export async function getClients() {
  const d = await fetchAPI('/api/clients');
  return Array.isArray(d) ? d : d?.clients ?? d?.data ?? d?.items ?? [];
}

export async function getClientDetail(id: string) {
  return await fetchAPI(`/api/clients/${id}`);
}

export async function createClient(data: {
  name: string; phone: string; gstin: string; state: string;
}) {
  return await postAPI('/api/clients', data);
}

export async function sendWhatsAppReminder(clientId: string) {
  return await postAPI(`/api/clients/${clientId}/remind`);   // FIXED: was /remind with body
}

// ── Invoices ──────────────────────────────────────────────────────────────────

export async function getInvoices() {
  const d = await fetchAPI('/api/invoices');
  return Array.isArray(d) ? d : d?.invoices ?? d?.data ?? d?.items ?? [];
}
export async function approveInvoice(id: string) {
  return await postAPI(`/api/invoices/${id}/approve`);
}

export async function rejectInvoice(id: string) {
  return await postAPI(`/api/invoices/${id}/reject`);
}

// ── GSTR-3B ───────────────────────────────────────────────────────────────────

export async function downloadGSTR3B(clientId: string, period?: string) {
  try {
    const url = period
      ? `${BASE_URL}/api/clients/${clientId}/gstr3b-json?period=${period}`
      : `${BASE_URL}/api/clients/${clientId}/gstr3b-json`;
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = window.URL.createObjectURL(blob);
    a.download = `GSTR3B_${clientId}_${period || 'current'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return { success: true };
  } catch (e) {
    console.error('GSTR-3B download error:', e);
    return { success: false };
  }
}

// ── Filing PDF ────────────────────────────────────────────────────────────────

export async function downloadFilingPdf(clientId: string) {
  try {
    const res = await fetch(`${BASE_URL}/api/clients/${clientId}/filing-pdf`, {
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = window.URL.createObjectURL(blob);
    a.download = `filing-summary-${clientId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return { success: true };
  } catch (e) {
    console.error('PDF download error:', e);
    return { success: false };
  }
}

// ── Alerts ────────────────────────────────────────────────────────────────────

export async function getAlerts() {
  return await fetchAPI('/api/alerts');
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export async function getAdminStats() {
  return await fetchAPI('/api/admin/stats');
}

// ── Compliance ────────────────────────────────────────────────────────────────

export async function getDeadlines(period: string) {
  return await fetchAPI(`/compliance/deadlines/${period}`);
}

export async function checkITC(category: string) {
  return await fetchAPI(`/compliance/itc/${encodeURIComponent(category)}`);
}

