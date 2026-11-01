import { useState } from "react";
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { inr, SEG_COLORS, SegmentRow } from "../types";

type SegResp = { summary: SegmentRow[]; rules: [string, string][]; clusters: { cluster: number; size: number; avg_recency_days: number; avg_frequency: number; avg_monetary: number; dominant_segment: string }[];
  scatter: { customer_id: number; segment: string; recency_days: number; frequency: number; monetary: number }[]; last_run: string | null };

export default function Segments() {
  const canWrite = useCanWrite();
  const { data, loading, error, reload } = useApi<SegResp>("/api/segments");
  const [busy, setBusy] = useState(false);
  const [k, setK] = useState(4);
  const run = async () => { setBusy(true); try { await api(`/api/segments/run?k=${k}`, { method: "POST" }); await reload(); } finally { setBusy(false); } };
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorBox msg={error ?? ""} />;
  const groups = data.summary.map((s) => ({ seg: s.segment, pts: data.scatter.filter((p) => p.segment === s.segment) }));
  return (
    <>
      <PageHeader title="Customer segmentation">{canWrite && <><label className="flex items-center gap-2 text-sm">K-means k<input className="input w-16" type="number" min={2} max={8} value={k} onChange={(e) => setK(Number(e.target.value))} /></label><button className="btn" onClick={run} disabled={busy}>{busy ? "Running…" : "Re-run segmentation"}</button></>}</PageHeader>
      <p className="mb-4 text-sm text-slate-500">Last run: {data.last_run ? new Date(data.last_run).toLocaleString() : "never"}. RFM scores (1–5) are percentile ranks within your customer base; rules are applied top-down.</p>
      <div className="card overflow-x-auto p-0"><table className="w-full"><thead className="bg-slate-50"><tr><th className="th">Segment</th><th className="th">Rule</th><th className="th">Customers</th><th className="th">Avg recency</th><th className="th">Avg frequency</th><th className="th">Avg spend</th><th className="th">Avg redemptions</th></tr></thead>
        <tbody className="divide-y">{data.summary.map((s) => <tr key={s.segment}><td className="td font-medium"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: SEG_COLORS[s.segment] }} />{s.segment}</td><td className="td text-xs">{s.rule}</td><td className="td">{s.customers}</td>
          <td className="td">{s.avg_recency_days ?? "—"}{s.avg_recency_days !== null && " d"}</td><td className="td">{s.avg_frequency ?? "—"}</td><td className="td">{s.avg_monetary !== null ? inr(s.avg_monetary) : "—"}</td><td className="td">{s.avg_redemptions ?? "—"}</td></tr>)}</tbody></table></div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2"><p className="label">Recency vs spend (bubble = frequency)</p>
          {data.scatter.length ? <ResponsiveContainer height={340}><ScatterChart><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="recency_days" name="Recency (days)" type="number" fontSize={11} /><YAxis dataKey="monetary" name="Spend (₹)" type="number" fontSize={11} /><ZAxis dataKey="frequency" range={[20, 200]} name="Purchases" /><Tooltip /><Legend />
            {groups.map((g) => <Scatter key={g.seg} name={g.seg} data={g.pts} fill={SEG_COLORS[g.seg]} />)}</ScatterChart></ResponsiveContainer> : <Empty title="No segmented customers" />}</div>
        <div className="card"><p className="label">K-means clusters</p>{data.clusters.length ? <ul className="space-y-3 text-sm">{data.clusters.map((c) => <li key={c.cluster} className="rounded-lg bg-slate-50 p-3"><p className="font-medium">Cluster {c.cluster} · {c.size} customers</p>
          <p className="text-xs text-slate-600">recency {c.avg_recency_days} d · {c.avg_frequency} purchases · {inr(c.avg_monetary)} · mostly <b>{c.dominant_segment}</b></p></li>)}</ul> : <p className="text-sm text-slate-500">Needs at least 4 customers.</p>}
          <p className="mt-3 text-xs text-slate-400">Clusters are computed on standardized log(recency, frequency, spend, redemptions). They are shown alongside the rule-based segments so you can validate them.</p></div>
      </div>
    </>
  );
}
