const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('vb_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function fetchAPI(endpoint: string) {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      headers: getAuthHeaders(),
    });
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
      headers: getAuthHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
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
      headers: getAuthHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error PUT ${endpoint}:`, e);
    return null;
  }
}

export async function getClients() {
  return await fetchAPI('/api/clients');
}

export async function getClientDetail(id: string) {
  return await fetchAPI(`/api/clients/${id}`);
}

export async function getInvoices() {
  return await fetchAPI('/api/invoices');
}

export async function getDashboardStats() {
  return await fetchAPI('/api/dashboard/stats');
}

export async function getAlerts() {
  return await fetchAPI('/api/alerts');
}

export async function approveInvoice(id: string) {
  return await postAPI(`/api/invoices/${id}/approve`);
}

export async function rejectInvoice(id: string) {
  return await postAPI(`/api/invoices/${id}/reject`);
}

export async function createClient(data: { name: string; phone: string; gstin: string; state: string }) {
  return await postAPI('/api/clients', data);
}

export async function getProfile() {
  return await fetchAPI('/auth/me');
}

export async function updateProfile(data: { name?: string; phone?: string; ca_number?: string; white_label_name?: string }) {
  return await putAPI('/auth/profile', data);
}

export async function sendWhatsAppReminder(phone: string, clientName: string) {
  return await postAPI('/api/clients/remind', { phone, clientName });
}

export async function downloadFilingPdf(clientId: string) {
  try {
    const res = await fetch(`${BASE_URL}/api/clients/${clientId}/filing-pdf`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `filing-summary-${clientId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    return { success: true };
  } catch (e) {
    console.error('PDF download error:', e);
    return { success: false };
  }
}