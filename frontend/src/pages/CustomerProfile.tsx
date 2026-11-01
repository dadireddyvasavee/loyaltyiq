import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { Badge, ErrorBox, PageHeader, Spinner, Stat } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { Customer, inr, Reward, RewardRec } from "../types";

type Txn = { id: number; external_ref: string; amount: number; category: string; occurred_at: string; points_awarded: number };
type Led = { id: number; kind: string; points: number; remaining: number; expires_at: string | null; note: string | null; occurred_at: string };
type Seg = { segment: string; reason: string; recency_days: number; frequency: number; monetary: number; r_score: number; f_score: number; m_score: number; cluster: number | null } | null;

export default function CustomerProfile() {
  const { id } = useParams();
  const canWrite = useCanWrite();
  const c = useApi<Customer>(`/api/customers/${id}`);
  const seg = useApi<Seg>(`/api/customers/${id}/segment`);
  const tx = useApi<Txn[]>(`/api/customers/${id}/transactions`);
  const led = useApi<Led[]>(`/api/customers/${id}/ledger`);
  const recs = useApi<RewardRec[]>(`/api/customers/${id}/recommendations`);
  const rewards = useApi<Reward[]>("/api/rewards");
  const [buy, setBuy] = useState({ amount: "", ref: "", category: "general" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const refresh = () => { c.reload(); tx.reload(); led.reload(); recs.reload(); };
  const run = async (fn: () => Promise<{ [k: string]: unknown }>, ok: (r: { [k: string]: unknown }) => string) => {
    setMsg(null); try { const r = await fn(); setMsg({ ok: true, text: ok(r) }); refresh(); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } };
  const purchase = (e: FormEvent) => { e.preventDefault(); run(() => api(`/api/customers/${id}/purchases`, { method: "POST", json: { amount: Number(buy.amount), external_ref: buy.ref, category: buy.category } }), (r) => `+${r.points_awarded} points (balance ${r.balance}, tier ${r.tier})`); };
  const redeem = (rid: number) => run(() => api(`/api/customers/${id}/redeem`, { method: "POST", json: { reward_id: rid, idempotency_key: `ui-${id}-${rid}-${crypto.randomUUID()}` } }), (r) => `Redeemed for ${r.points_spent} pts (balance ${r.balance})`);
  if (c.loading) return <Spinner />;
  if (c.error || !c.data) return <ErrorBox msg={c.error ?? "Not found"} />;
  const cu = c.data;
  return (
    <>
      <PageHeader title={`${cu.first_name} ${cu.last_name}`}><Badge tone="amber">{cu.account?.tier}</Badge>{seg.data && <Badge tone="brand">{seg.data.segment}</Badge>}</PageHeader>
      <div className="grid gap-4 sm:grid-cols-4"><Stat label="Points balance" value={cu.account?.balance.toLocaleString()} /><Stat label="Lifetime points" value={cu.account?.lifetime_points.toLocaleString()} />
        <Stat label="Purchases" value={tx.data?.length ?? "…"} sub={tx.data ? inr(tx.data.reduce((s, t) => s + t.amount, 0)) + " total" : undefined} /><Stat label="Member since" value={new Date(cu.joined_at).toLocaleDateString()} sub={cu.email} /></div>
      {msg && <div className={`mt-4 rounded-lg p-3 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{msg.text}</div>}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card space-y-3"><p className="label">Segment & RFM</p>{seg.data ? <><p className="text-sm">{seg.data.reason}</p>
          <p className="text-sm">R{seg.data.r_score} · F{seg.data.f_score} · M{seg.data.m_score} {seg.data.cluster !== null && <>· cluster {seg.data.cluster}</>}</p></> : <p className="text-sm text-slate-500">Not segmented yet.</p>}
          {canWrite && <form onSubmit={purchase} className="space-y-2 border-t pt-3"><p className="label">Record purchase</p>
            <input className="input" type="number" step="0.01" min="0.01" required placeholder="Amount (₹)" value={buy.amount} onChange={(e) => setBuy({ ...buy, amount: e.target.value })} />
            <input className="input" required placeholder="Order / POS reference (unique)" value={buy.ref} onChange={(e) => setBuy({ ...buy, ref: e.target.value })} />
            <input className="input" placeholder="Category" value={buy.category} onChange={(e) => setBuy({ ...buy, category: e.target.value })} />
            <button className="btn w-full">Award points</button></form>}</div>
        <div className="card lg:col-span-2"><p className="label">Recommended rewards</p>
          {recs.data?.length ? <ul className="divide-y">{recs.data.map((r) => <li key={r.reward_id} className="flex items-start justify-between gap-3 py-3"><div><p className="font-medium">{r.name} <span className="text-xs text-slate-500">· {r.points_cost} pts · score {r.score}</span></p>
            <ul className="mt-1 text-xs text-slate-600">{r.reasons.map((x) => <li key={x}>• {x}</li>)}</ul></div>
            {canWrite && <button className="btn-ghost shrink-0" disabled={!r.affordable} onClick={() => redeem(r.reward_id)}>Redeem</button>}</li>)}</ul> : <p className="text-sm text-slate-500">No eligible rewards.</p>}
          {canWrite && <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-500">Redeem any reward</summary><div className="mt-2 flex flex-wrap gap-2">{rewards.data?.map((r) => <button key={r.id} className="btn-ghost" onClick={() => redeem(r.id)}>{r.name} ({r.points_cost})</button>)}</div></details>}</div>
        <div className="card lg:col-span-2"><p className="label">Points ledger</p><div className="max-h-80 overflow-y-auto"><table className="w-full"><thead><tr><th className="th">Date</th><th className="th">Type</th><th className="th">Points</th><th className="th">Unspent</th><th className="th">Expires</th><th className="th">Note</th></tr></thead>
          <tbody className="divide-y">{led.data?.map((e) => <tr key={e.id}><td className="td">{new Date(e.occurred_at).toLocaleDateString()}</td><td className="td"><Badge tone={e.points > 0 ? "green" : "red"}>{e.kind}</Badge></td><td className="td">{e.points > 0 ? "+" : ""}{e.points}</td><td className="td">{e.points > 0 ? e.remaining : ""}</td><td className="td text-xs">{e.expires_at ? new Date(e.expires_at).toLocaleDateString() : ""}</td><td className="td text-xs">{e.note}</td></tr>)}</tbody></table></div></div>
        <div className="card"><p className="label">Purchase history</p><ul className="max-h-80 divide-y overflow-y-auto text-sm">{tx.data?.map((t) => <li key={t.id} className="flex justify-between py-2"><span>{new Date(t.occurred_at).toLocaleDateString()} · {t.category}</span><span>{inr(t.amount)} <span className="text-xs text-emerald-600">+{t.points_awarded}</span></span></li>)}</ul></div>
      </div>
    </>
  );
}
