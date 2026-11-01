import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

export type User = { id: number; email: string; full_name: string; role: string; organization_id?: number };
type Ctx = { user: User | null; ready: boolean; login: (email: string, password: string) => Promise<void>;
  register: (data: Record<string, string>) => Promise<void>; logout: () => void };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const loadMe = async () => { try { setUser(await api<User>("/api/auth/me")); } catch { setUser(null); } };
  useEffect(() => { (getToken() ? loadMe() : Promise.resolve()).finally(() => setReady(true)); }, []);
  const login = async (email: string, password: string) => {
    const r = await api<{ access_token: string }>("/api/auth/login", { method: "POST", json: { email, password } });
    setToken(r.access_token); await loadMe();
  };
  const register = async (data: Record<string, string>) => {
    const r = await api<{ access_token: string }>("/api/auth/register", { method: "POST", json: data });
    setToken(r.access_token); await loadMe();
  };
  const logout = () => { setToken(null); setUser(null); };
  return <AuthCtx.Provider value={{ user, ready, login, register, logout }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);
