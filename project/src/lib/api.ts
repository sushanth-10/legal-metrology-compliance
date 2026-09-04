const configuredApiBase = String(import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');
const developmentApiBase = 'http://127.0.0.1:8001';

function configuredBaseUrl(): string {
  const baseUrl = configuredApiBase || (import.meta.env.DEV ? developmentApiBase : '');

  if (!baseUrl) {
    throw new Error(
      'The NIRIKSHA backend URL is not configured for this deployment. Set VITE_API_BASE_URL to the public HTTPS backend URL in Vercel, then redeploy.'
    );
  }

  if (import.meta.env.PROD) {
    let hostname = '';
    try {
      hostname = new URL(baseUrl).hostname.toLowerCase();
    } catch {
      throw new Error('VITE_API_BASE_URL must be a valid backend URL.');
    }

    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
      throw new Error(
        'VITE_API_BASE_URL points to this computer. Configure the public HTTPS backend URL in Vercel and redeploy.'
      );
    }
  }

  return baseUrl;
}

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
  return fetch(`${configuredBaseUrl()}${path}`, { ...init, headers });
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
  return configuredBaseUrl();
}

export function absoluteApiUrl(path: string): string {
  return path.startsWith('http') ? path : `${configuredBaseUrl()}${path}`;
}
