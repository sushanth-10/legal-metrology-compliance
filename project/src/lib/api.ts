const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export function sessionToken(): string | null {
  try {
    const raw = localStorage.getItem('niriksha_session');
    return raw ? (JSON.parse(raw) as { token?: string }).token ?? null : null;
  } catch {
    return null;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = sessionToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    /* handled below */
  }
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in payload ? String((payload as { detail?: unknown }).detail ?? '') : '';
    throw new Error(detail || 'The NIRIKSHA backend could not complete the request.');
  }
  return payload as T;
}

export function apiBaseUrl(): string {
  return API_BASE;
}

export function absoluteApiUrl(path: string): string {
  return path.startsWith('http') ? path : `${API_BASE}${path}`;
}
