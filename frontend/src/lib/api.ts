const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function getToken() { return localStorage.getItem("token"); }
export function setToken(t: string | null) { t ? localStorage.setItem("token", t) : localStorage.removeItem("token"); }

export async function api<T = unknown>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body = opts.body;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers, body });
  if (res.status === 401 && token) { setToken(null); window.location.href = "/login"; }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === "string" ? d.detail : Array.isArray(d.detail) ? d.detail.map((e: { msg: string }) => e.msg).join("; ") : msg;
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
