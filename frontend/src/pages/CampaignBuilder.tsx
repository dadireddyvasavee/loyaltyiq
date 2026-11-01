import { FormEvent, useState } from "react";
import { Badge, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { Campaign, Reward, SEGMENTS } from "../types";

type Draft = { name: string; objective: string; segment: string; message_template: string; ideas: string[]; reward_id: number | null; bonus_points: number; generated_by: "manual" | "llm"; rationale?: string };
const empty: Draft = { name: "", objective: "", segment: "at_risk", message_template: "Hi {first_name}, you have {points_balance} points waiting at {business_name}!", ideas: [], reward_id: null, bonus_points: 0, generated_by: "manual" };
const tone = (s: string) => (s === "active" ? "green" : s === "approved" ? "brand" : s === "completed" ? "slate" : "amber") as "green" | "brand" | "slate" | "amber";

export default function CampaignBuilder() {
  const canWrite = useCanWrite();
  const list = useApi<Campaign[]>("/api/campaigns");
  const rewards = useApi<Reward[]>("/api/rewards");
  const [d, setD] = useState<Draft>(empty);
  const [editing, setEditing] = useState<number | null>(null);
  const [gen, setGen] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [preview, setPreview] = useState<{ audience_size: number; samples: { customer: string; message: string }[] } | null>(null);
  const [tn, setTn] = useState("warm and friendly");
  const act = async (fn: () => Promise<unknown>, ok: string) => { setMsg(null); try { await fn(); setMsg({ ok: true, text: ok }); list.reload(); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } };
  const generate = async () => {
    setGen(true); setMsg(null);
    try { const r = await api<Draft & { validation: { reward_id_rejected: boolean } }>("/api/campaigns/generate", { method: "POST", json: { objective: d.objective, segment: d.segment, tone: tn } });
      setD({ ...r, generated_by: "llm" }); setEditing(null);
      setMsg({ ok: true, text: "AI draft generated. Review and edit it, then save. Nothing is sent until the campaign is approved and activated." + (r.validation.reward_id_rejected ? " (The AI suggested a reward that doesn't exist; it was removed.)" : "") });
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setGen(false); }
  };
  const save = (e: FormEvent) => { e.preventDefault(); act(() => api(editing ? `/api/campaigns/${editing}` : "/api/campaigns", { method: editing ? "PUT" : "POST", json: d }).then(() => { setD(empty); setEditing(null); }), "Saved as draft."); };
  const showPreview = async (id: number) => setPreview(await api(`/api/campaigns/${id}/preview`));
  return (
    <>
      <PageHeader title="AI campaign builder" />
      {msg && <div className={`mb-4 rounded-lg p-3 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{msg.text}</div>}
      {canWrite && <form onSubmit={save} className="card grid gap-4 md:grid-cols-2">
        <label className="md:col-span-2"><span className="label">1 · Campaign objective</span><input className="input" required minLength={5} value={d.objective} onChange={(e) => setD({ ...d, objective: e.target.value })} placeholder="e.g. Win back customers who haven't visited in 3 months" /></label>
        <label><span className="label">2 · Target segment</span><select className="input" value={d.segment} onChange={(e) => setD({ ...d, segment: e.target.value })}>{SEGMENTS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label><span className="label">Tone</span><input className="input" value={tn} onChange={(e) => setTn(e.target.value)} /></label>
        <div className="md:col-span-2"><button type="button" className="btn-ghost" onClick={generate} disabled={gen || d.objective.length < 5}>{gen ? "Generating…" : "✨ 3 · Generate ideas & message with AI"}</button></div>
        {d.ideas.length > 0 && <div className="rounded-lg bg-brand-50 p-3 text-sm md:col-span-2"><p className="label">AI campaign ideas</p><ul className="list-disc pl-5">{d.ideas.map((i) => <li key={i}>{i}</li>)}</ul>{d.rationale && <p className="mt-2 text-xs text-slate-600">{d.rationale}</p>}</div>}
        <label><span className="label">Campaign name</span><input className="input" required value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} /></label>
        <label><span className="label">4 · Reward</span><select className="input" value={d.reward_id ?? ""} onChange={(e) => setD({ ...d, reward_id: e.target.value ? Number(e.target.value) : null })}><option value="">No reward</option>{rewards.data?.filter((r) => r.active).map((r) => <option key={r.id} value={r.id}>{r.name} ({r.points_cost} pts)</option>)}</select></label>
        <label className="md:col-span-2"><span className="label">5 · Personalised message. Placeholders: {"{first_name} {points_balance} {tier} {reward_name} {business_name}"}</span><textarea className="input" rows={3} required value={d.message_template} onChange={(e) => setD({ ...d, message_template: e.target.value })} /></label>
        <label><span className="label">Bonus points per recipient (0–1000)</span><input className="input" type="number" min={0} max={1000} value={d.bonus_points} onChange={(e) => setD({ ...d, bonus_points: Number(e.target.value) })} /></label>
        <div className="flex items-end gap-2"><button className="btn">{editing ? "Update draft" : "6 · Save as draft"}</button>{editing && <button type="button" className="btn-ghost" onClick={() => { setD(empty); setEditing(null); }}>Cancel</button>}</div>
      </form>}
      <h2 className="mb-3 mt-8 text-lg font-semibold">Campaigns</h2>
      {list.loading ? <Spinner /> : list.error ? <ErrorBox msg={list.error} /> : !list.data?.length ? <Empty title="No campaigns yet" /> :
        <div className="space-y-3">{list.data.map((c) => <div key={c.id} className="card"><div className="flex flex-wrap items-center justify-between gap-2">
          <div><p className="font-semibold">{c.name} <Badge tone={tone(c.status)}>{c.status}</Badge> {c.generated_by === "llm" && <Badge>AI-drafted</Badge>}</p><p className="text-xs text-slate-500">Segment {c.segment} · {c.bonus_points} bonus pts · {c.objective}</p></div>
          <div className="flex flex-wrap gap-2"><button className="btn-ghost" onClick={() => showPreview(c.id)}>Preview</button>
            {canWrite && c.status === "draft" && <><button className="btn-ghost" onClick={() => { setD({ ...c, generated_by: c.generated_by as "manual" | "llm" }); setEditing(c.id); window.scrollTo(0, 0); }}>Edit</button><button className="btn" onClick={() => act(() => api(`/api/campaigns/${c.id}/approve`, { method: "POST" }), "Approved. You can now activate it.")}>Approve</button></>}
            {canWrite && c.status === "approved" && <button className="btn" onClick={() => act(() => api(`/api/campaigns/${c.id}/activate`, { method: "POST" }), "Activated: recipients resolved and messages personalised.")}>Activate</button>}
            {canWrite && c.status === "active" && <button className="btn-ghost" onClick={() => act(() => api(`/api/campaigns/${c.id}/complete`, { method: "POST" }), "Marked completed.")}>Complete</button>}</div></div>
          <p className="mt-2 rounded bg-slate-50 p-2 text-sm italic text-slate-700">{c.message_template}</p></div>)}</div>}
      {preview && <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/30 p-4" onClick={() => setPreview(null)}><div className="card max-w-lg" onClick={(e) => e.stopPropagation()}>
        <p className="font-semibold">Audience: {preview.audience_size} customers</p>{preview.samples.map((s) => <div key={s.customer} className="mt-3 rounded bg-slate-50 p-3 text-sm"><p className="text-xs text-slate-500">To {s.customer}</p>{s.message}</div>)}
        <button className="btn-ghost mt-4" onClick={() => setPreview(null)}>Close</button></div></div>}
    </>
  );
}
