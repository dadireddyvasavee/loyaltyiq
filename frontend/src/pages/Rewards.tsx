import { FormEvent, useState } from "react";
import { Badge, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { Reward } from "../types";

const blank = { name: "", description: "", category: "general", points_cost: 100, stock: 50, min_tier: "bronze", active: true, valid_until: null as string | null };

export default function Rewards() {
  const canWrite = useCanWrite();
  const { data, loading, error, reload } = useApi<Reward[]>("/api/rewards");
  const [edit, setEdit] = useState<(typeof blank & { id?: number }) | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const save = async (e: FormEvent) => {
    e.preventDefault(); if (!edit) return; setErr(null);
    const { id, ...body } = edit;
    try { await api(id ? `/api/rewards/${id}` : "/api/rewards", { method: id ? "PUT" : "POST", json: body }); setEdit(null); reload(); } catch (x) { setErr((x as Error).message); }
  };
  return (
    <>
      <PageHeader title="Reward catalog">{canWrite && <button className="btn" onClick={() => setEdit({ ...blank })}>New reward</button>}</PageHeader>
      {edit && <form onSubmit={save} className="card mb-4 grid gap-3 md:grid-cols-4">{err && <div className="md:col-span-4"><ErrorBox msg={err} /></div>}
        <label className="md:col-span-2"><span className="label">Name</span><input className="input" required value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></label>
        <label><span className="label">Category</span><input className="input" value={edit.category} onChange={(e) => setEdit({ ...edit, category: e.target.value })} /></label>
        <label><span className="label">Min tier</span><select className="input" value={edit.min_tier} onChange={(e) => setEdit({ ...edit, min_tier: e.target.value })}>{["bronze", "silver", "gold"].map((t) => <option key={t}>{t}</option>)}</select></label>
        <label><span className="label">Points cost</span><input className="input" type="number" min={1} value={edit.points_cost} onChange={(e) => setEdit({ ...edit, points_cost: Number(e.target.value) })} /></label>
        <label><span className="label">Stock</span><input className="input" type="number" min={0} value={edit.stock} onChange={(e) => setEdit({ ...edit, stock: Number(e.target.value) })} /></label>
        <label><span className="label">Valid until</span><input className="input" type="date" value={edit.valid_until?.slice(0, 10) ?? ""} onChange={(e) => setEdit({ ...edit, valid_until: e.target.value ? new Date(e.target.value).toISOString() : null })} /></label>
        <label className="flex items-end gap-2 text-sm"><input type="checkbox" checked={edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} /> Active</label>
        <label className="md:col-span-4"><span className="label">Description</span><input className="input" value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></label>
        <div className="flex gap-2"><button className="btn">Save</button><button type="button" className="btn-ghost" onClick={() => setEdit(null)}>Cancel</button></div></form>}
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : !data?.length ? <Empty title="No rewards yet" /> :
        <div className="grid gap-4 md:grid-cols-3">{data.map((r) => <div key={r.id} className="card"><div className="flex justify-between"><p className="font-semibold">{r.name}</p>{!r.active && <Badge tone="red">inactive</Badge>}</div>
          <p className="mt-1 text-sm text-slate-500">{r.description}</p><p className="mt-3 text-2xl font-bold text-brand-600">{r.points_cost} pts</p>
          <p className="mt-1 text-xs text-slate-500">{r.category} · {r.min_tier}+ · stock {r.stock}{r.valid_until && ` · until ${new Date(r.valid_until).toLocaleDateString()}`}</p>
          {canWrite && <button className="mt-3 text-sm text-brand-700" onClick={() => setEdit({ ...r })}>Edit</button>}</div>)}</div>}
    </>
  );
}
