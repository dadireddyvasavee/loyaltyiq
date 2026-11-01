import { FormEvent, useEffect, useState } from "react";
import { ErrorBox, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { Org } from "../types";

const FIELDS: [keyof Org, string, string][] = [["points_per_currency", "Points per ₹1 spent", "0.1 = 1 point per ₹10"], ["min_purchase_for_points", "Minimum purchase to earn (₹)", ""],
  ["points_expiry_days", "Points expire after (days)", "FIFO: oldest points are spent first"], ["tier_silver_points", "Silver tier at lifetime points", ""], ["tier_gold_points", "Gold tier at lifetime points", ""], ["welcome_bonus", "Welcome bonus (points)", "Granted once at registration"]];

export default function Program() {
  const canWrite = useCanWrite();
  const { data, loading, error } = useApi<Org>("/api/org");
  const [f, setF] = useState<Org | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (data) setF(data); }, [data]);
  if (loading || !f) return error ? <ErrorBox msg={error} /> : <Spinner />;
  const save = async (e: FormEvent) => { e.preventDefault(); try { await api("/api/org", { method: "PUT", json: f }); setMsg("Loyalty rules saved (change recorded in audit log)."); } catch (x) { setMsg((x as Error).message); } };
  const expire = async () => { const r = await api<{ expired_points: number }>("/api/points/expire", { method: "POST" }); setMsg(`Expiry job ran: ${r.expired_points} points expired.`); };
  return (
    <>
      <PageHeader title="Loyalty program rules">{canWrite && <button className="btn-ghost" onClick={expire}>Run expiry job now</button>}</PageHeader>
      <form onSubmit={save} className="card grid max-w-3xl gap-4 md:grid-cols-2">
        {FIELDS.map(([k, label, hint]) => <label key={k}><span className="label">{label}</span><input className="input" type="number" step="any" disabled={!canWrite} value={f[k] as number} onChange={(e) => setF({ ...f, [k]: Number(e.target.value) })} />{hint && <span className="text-xs text-slate-400">{hint}</span>}</label>)}
        {canWrite && <div className="md:col-span-2"><button className="btn">Save rules</button></div>}
        {msg && <p className="text-sm text-slate-600 md:col-span-2">{msg}</p>}
      </form>
      <div className="card mt-6 max-w-3xl text-sm text-slate-600"><p className="label">How the engine guarantees consistency</p>
        <ul className="list-disc space-y-1 pl-5"><li>Each purchase carries a unique order reference. Re-sending it returns 409 and awards no points.</li><li>Redemptions lock the account and reward rows, check tier, stock, validity and balance, then consume points from the oldest lots first.</li>
          <li>Redemptions are idempotent: retrying with the same key returns the original redemption.</li><li>A database CHECK constraint prevents negative balances or stock.</li><li>All mutations are written to the audit log.</li></ul></div>
    </>
  );
}
