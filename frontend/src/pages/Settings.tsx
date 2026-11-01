import { FormEvent, useState } from "react";
import { Badge, ErrorBox, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";
import { Org } from "../types";

type U = { id: number; email: string; full_name: string; role: string };
type A = { id: number; at: string; user_id: number | null; action: string; entity: string; entity_id: number | null; detail: Record<string, unknown> };

export default function Settings() {
  const { user } = useAuth();
  const org = useApi<Org>("/api/org");
  const users = useApi<U[]>("/api/org/users");
  const audit = useApi<A[]>(user?.role === "analyst" ? null : "/api/audit?limit=50");
  const [f, setF] = useState({ email: "", full_name: "", password: "", role: "analyst" });
  const [err, setErr] = useState<string | null>(null);
  const add = async (e: FormEvent) => { e.preventDefault(); setErr(null); try { await api("/api/org/users", { method: "POST", json: f }); setF({ email: "", full_name: "", password: "", role: "analyst" }); users.reload(); } catch (x) { setErr((x as Error).message); } };
  return (
    <>
      <PageHeader title={`Organization · ${org.data?.name ?? ""}`}>{org.data?.is_synthetic && <Badge tone="amber">SYNTHETIC DATA</Badge>}</PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card"><p className="label">Team members & roles</p><ul className="divide-y text-sm">{users.data?.map((u) => <li key={u.id} className="flex justify-between py-2"><span>{u.full_name} · {u.email}</span><Badge tone={u.role === "owner" ? "brand" : "slate"}>{u.role}</Badge></li>)}</ul>
          <p className="mt-3 text-xs text-slate-500">owner: everything · admin: manage customers, points, rewards, campaigns · analyst: read-only.</p>
          {user?.role === "owner" && <form onSubmit={add} className="mt-4 grid gap-2 border-t pt-4 md:grid-cols-2">{err && <div className="md:col-span-2"><ErrorBox msg={err} /></div>}
            <input className="input" placeholder="Full name" required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
            <input className="input" type="email" placeholder="Email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
            <input className="input" type="password" placeholder="Temporary password (8+)" required minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
            <select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="analyst">analyst</option><option value="admin">admin</option></select>
            <button className="btn md:col-span-2">Add team member</button></form>}</div>
        <div className="card"><p className="label">Audit log</p>{user?.role === "analyst" ? <p className="text-sm text-slate-500">Visible to owners and admins.</p> :
          <ul className="max-h-[28rem] divide-y overflow-y-auto text-xs">{audit.data?.map((a) => <li key={a.id} className="py-2"><span className="font-medium">{a.action}</span> · {a.entity} #{a.entity_id} <span className="text-slate-400">· {new Date(a.at).toLocaleString()} · user {a.user_id ?? "system"}</span>
            <p className="truncate text-slate-500">{JSON.stringify(a.detail)}</p></li>)}</ul>}</div>
      </div>
    </>
  );
}
