const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "pharmacore_access";
const REFRESH_KEY = "pharmacore_refresh";

/* Named once and reused. The retry guard used to test a bare auth prefix
   inline, and the CI gate that resolves every literal API path in the frontend
   read that prefix as a call to an endpoint which does not exist. Comparing
   against the real paths is both clearer and gate-safe. */
const REFRESH_PATH = "/api/auth/refresh";
const LOGIN_PATH = "/api/auth/login";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/** The long-lived token, kept so an expired session can renew itself.
 *
 * The login response has always carried one and it was thrown away, so an
 * access token simply expired mid-shift: the next request failed, and a cashier
 * with a basket on screen was signed out with no explanation. */
export function setRefreshToken(token: string | null): void {
  if (token) localStorage.setItem(REFRESH_KEY, token);
  else localStorage.removeItem(REFRESH_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

/** Called when renewal fails, so the app can send the user back to sign in. */
let onSessionLost: (() => void) | null = null;
export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

/* One renewal at a time. A screen firing six queries at once would otherwise
   send six refreshes, and every one after the first fails against a rotated
   token — turning a recoverable expiry into a forced sign-out. */
let renewing: Promise<string | null> | null = null;

async function renew(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  if (renewing) return renewing;

  renewing = (async () => {
    try {
      const res = await fetch(`${BASE}${REFRESH_PATH}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return null;
      const body = (await res.json()) as { access?: string; refresh?: string };
      if (!body.access) return null;
      setToken(body.access);
      // Some backends rotate the refresh token on use; keep whichever we get.
      if (body.refresh) setRefreshToken(body.refresh);
      return body.access;
    } catch {
      return null;
    } finally {
      renewing = null;
    }
  })();
  return renewing;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res = await fetch(`${BASE}${path}`, { ...options, headers });

  /* An expired access token is recoverable, so recover from it rather than
     throwing the user out. Only once: if the renewed token is also refused,
     the session really is over. The refresh call itself is excluded, or a
     failure there would recurse. */
  if (res.status === 401 && path !== REFRESH_PATH && path !== LOGIN_PATH) {
    const renewed = await renew();
    if (renewed) {
      headers.set("Authorization", `Bearer ${renewed}`);
      res = await fetch(`${BASE}${path}`, { ...options, headers });
    } else {
      setToken(null);
      setRefreshToken(null);
      onSessionLost?.();
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      } else {
        detail = JSON.stringify(body);
      }
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fetch a file with auth and trigger a browser download. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
